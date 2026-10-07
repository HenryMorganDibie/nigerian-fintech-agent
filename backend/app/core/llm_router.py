"""
LLM Router — rotating, health-aware failover across Ollama, Groq, OpenAI and Anthropic
=========================================================================================
Python port of the provider router in interview-copilot (packages/ai/src):

  * ProviderHealthTracker — per-candidate cooldowns. A rate limit (429, or
    Anthropic's 529 overload) parks the candidate for 60 s, the window in which
    Groq's RPM/TPM limits reset. Timeouts and other errors back off
    exponentially from 2 s up to 5 min. One success clears the record.
  * LocalModelPool — discovers whatever is pulled on the Ollama server
    (/api/tags, including Ollama's free "-cloud" models), benchmarks the models
    one at a time and always routes to the fastest healthy model that clears a
    quality floor. Re-benchmarks every 10 minutes.
  * LLMRouter — tries candidates in order, skips any in cooldown, and fails
    over on timeout, connection error, rate limit or model error. If every
    candidate is cooling down it tries them all anyway rather than refusing.

Default order: local pool → Groq models (strongest first) → OpenAI → Anthropic,
with the local pool's position set by LLM_LOCAL_POOL:

  first  try Ollama before any paid or remote provider
  last   remote first (lowest latency for interactive calls), Ollama as the
         final fallback when every remote provider is down or rate-limited
  off    never use Ollama
  only   data-residency mode: on-machine Ollama models only, "-cloud" models
         excluded, so no customer data leaves the deployment

RoutedChatModel wraps the router as a LangChain chat model, so `.invoke`,
`.stream` and `.bind_tools` keep working at every call site, including the
tool-calling chat agent. Every reply carries the candidate that produced it in
`response_metadata["routed_provider"]`, which the audit trail records.

The LLM never sits on the payment decision path; this module serves narratives,
chat and document analysis only.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Literal, Optional, Sequence

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import ConfigDict

from app.core.config import settings

logger = logging.getLogger(__name__)

FailureKind = Literal["timeout", "rate_limit", "error"]
LocalPoolPosition = Literal["first", "last", "off", "only"]


# ── Health tracking ───────────────────────────────────────────────────────────

BASE_COOLDOWN_S = 2.0
MAX_COOLDOWN_S = 5 * 60.0
# Provider rate limits (Groq RPM/TPM) reset on the order of a minute.
RATE_LIMIT_COOLDOWN_S = 60.0
# Anthropic signals overload with 529; treat it like a rate limit, not a fault.
_RATE_LIMIT_STATUSES = {429, 529}


class AllProvidersFailedError(RuntimeError):
    """Every candidate failed for this call."""


class NoLocalModelError(RuntimeError):
    """The local pool has no model that meets the quality and health bar."""


def classify(error: BaseException) -> FailureKind:
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if status in _RATE_LIMIT_STATUSES or "RateLimit" in type(error).__name__:
        return "rate_limit"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)) or "Timeout" in type(error).__name__:
        return "timeout"
    return "error"


@dataclass
class _HealthEntry:
    consecutive_failures: int
    cooldown_until: float
    last_kind: FailureKind


class ProviderHealthTracker:
    """Thread-safe per-candidate cooldowns, so the router skips providers that are down."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, _HealthEntry] = {}

    def is_available(self, candidate_id: str) -> bool:
        with self._lock:
            entry = self._entries.get(candidate_id)
            return entry is None or self._clock() >= entry.cooldown_until

    def cooldown_remaining(self, candidate_id: str) -> float:
        with self._lock:
            entry = self._entries.get(candidate_id)
            return 0.0 if entry is None else max(0.0, entry.cooldown_until - self._clock())

    def record_success(self, candidate_id: str) -> None:
        with self._lock:
            self._entries.pop(candidate_id, None)

    def record_failure(self, candidate_id: str, kind: FailureKind) -> float:
        with self._lock:
            prev = self._entries.get(candidate_id)
            failures = (prev.consecutive_failures if prev else 0) + 1
            if kind == "rate_limit":
                cooldown = RATE_LIMIT_COOLDOWN_S
            else:
                cooldown = min(MAX_COOLDOWN_S, BASE_COOLDOWN_S * 2 ** (failures - 1))
            self._entries[candidate_id] = _HealthEntry(failures, self._clock() + cooldown, kind)
            return cooldown

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            now = self._clock()
            return {
                cid: {"consecutive_failures": e.consecutive_failures, "last_failure": e.last_kind,
                      "cooldown_remaining_s": round(max(0.0, e.cooldown_until - now), 1)}
                for cid, e in self._entries.items()
            }


# ── Candidates ────────────────────────────────────────────────────────────────

class Candidate:
    """One routable provider. Subclasses call the model and raise on any failure."""

    id: str
    kind: str

    def invoke(self, messages: list[BaseMessage], tools: Sequence[Any], tool_kwargs: dict,
               stop: Optional[list[str]]) -> BaseMessage:
        raise NotImplementedError

    def stream(self, messages: list[BaseMessage], tools: Sequence[Any], tool_kwargs: dict,
               stop: Optional[list[str]]) -> Iterator[BaseMessage]:
        yield self.invoke(messages, tools, tool_kwargs, stop)

    def describe(self) -> dict:
        return {"id": self.id, "kind": self.kind}


class ChatModelCandidate(Candidate):
    """A single remote model (one model = one candidate, so models fail over independently)."""

    def __init__(self, kind: str, model: str, build: Callable[[], BaseChatModel]):
        self.kind = kind
        self.model = model
        self.id = f"{kind}:{model}"
        self._build = build
        self._client: Optional[BaseChatModel] = None
        self._lock = threading.Lock()

    def _runnable(self, tools: Sequence[Any], tool_kwargs: dict):
        with self._lock:
            if self._client is None:
                self._client = self._build()
        return self._client.bind_tools(list(tools), **tool_kwargs) if tools else self._client

    def invoke(self, messages, tools, tool_kwargs, stop):
        return self._runnable(tools, tool_kwargs).invoke(messages, stop=stop)

    def stream(self, messages, tools, tool_kwargs, stop):
        yield from self._runnable(tools, tool_kwargs).stream(messages, stop=stop)


# ── Ollama discovery and the local model pool ─────────────────────────────────

@dataclass(frozen=True)
class DiscoveredOllamaModel:
    name: str
    family: Optional[str]
    parameter_size: Optional[str]
    # Ollama's free cloud-hosted models are proxied through the local daemon to
    # ollama.com: not CPU-bound here, but data does leave the machine.
    is_cloud: bool


@dataclass(frozen=True)
class LocalModelSpec:
    model: str
    quality_score: float
    is_cloud: bool = False


def discover_ollama_models(base_url: str, timeout_s: float = 3.0) -> list[DiscoveredOllamaModel]:
    """Lists whatever models are actually pulled on this Ollama server right now."""
    try:
        res = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_s)
    except httpx.HTTPError:
        return []
    if res.status_code != 200:
        return []
    out = []
    for m in res.json().get("models", []) or []:
        details = m.get("details") or {}
        name = m.get("name") or m.get("model") or ""
        out.append(DiscoveredOllamaModel(
            name=name, family=details.get("family"), parameter_size=details.get("parameter_size"),
            is_cloud=bool(m.get("remote_host")) or name.endswith("-cloud"),
        ))
    return out


def score_model_quality(model: DiscoveredOllamaModel) -> float:
    """
    Heuristic 0-1 fitness for compliance narratives and analyst chat, not a
    capability benchmark. Code-tuned models answer in terse code-like fragments
    and rank lower; cloud models are larger and not limited by local hardware.
    """
    name = model.name.lower()
    if "coder" in name or "code" in name:
        return 0.5
    if model.is_cloud:
        return 0.85
    return 0.7


def _param_count(size: Optional[str]) -> float:
    match = re.search(r"([\d.]+)\s*B", size or "", re.IGNORECASE)
    return float(match.group(1)) if match else float("inf")


def to_local_model_specs(models: list[DiscoveredOllamaModel]) -> list[LocalModelSpec]:
    """Smallest parameter count first: a cheap speed proxy, so early-stop benchmarking stays short."""
    ordered = sorted(models, key=lambda m: _param_count(m.parameter_size))
    return [LocalModelSpec(m.name, score_model_quality(m), m.is_cloud) for m in ordered]


@dataclass
class _Benchmark:
    latency_s: float
    measured_at: float
    ok: bool


class LocalModelPool(Candidate):
    """
    All Ollama models exposed as one candidate. Benchmarks real latency on this
    machine and routes to the fastest healthy model above the quality floor,
    instead of a fixed "primary model".
    """

    kind = "ollama"
    id = "ollama-pool"

    def __init__(
        self,
        base_url: str,
        specs: Optional[list[LocalModelSpec]] = None,
        *,
        min_quality: float = 0.5,
        exclude_cloud: bool = False,
        benchmark_ttl_s: float = 10 * 60.0,
        good_enough_latency_s: float = 5.0,
        timeout_s: float = 30.0,
        benchmark_prompt: str = "Reply with just the word OK.",
        clock: Callable[[], float] = time.monotonic,
        build_model: Optional[Callable[[str], BaseChatModel]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._dynamic = specs is None
        self._specs: list[LocalModelSpec] = list(specs or [])
        self._discovered = False
        self.min_quality = min_quality
        self.exclude_cloud = exclude_cloud
        self.benchmark_ttl_s = benchmark_ttl_s
        self.good_enough_latency_s = good_enough_latency_s
        self.timeout_s = timeout_s
        self.benchmark_prompt = benchmark_prompt
        self._clock = clock
        self.health = ProviderHealthTracker(clock)
        self._benchmarks: dict[str, _Benchmark] = {}
        self._clients: dict[str, BaseChatModel] = {}
        self._lock = threading.Lock()           # guards discovery + benchmarking
        self._build_model = build_model or self._default_build

    def _default_build(self, model: str) -> BaseChatModel:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, base_url=self.base_url, temperature=0.1,
                          client_kwargs={"timeout": self.timeout_s})

    def _client(self, model: str) -> BaseChatModel:
        client = self._clients.get(model)
        if client is None:
            client = self._clients[model] = self._build_model(model)
        return client

    def _eligible_specs(self) -> list[LocalModelSpec]:
        # Below-floor models are never benchmarked: otherwise a fast but
        # unusable model could end the early-stop pass and leave nothing to pick.
        return [s for s in self._specs
                if s.quality_score >= self.min_quality and not (self.exclude_cloud and s.is_cloud)]

    def _ensure_discovered(self) -> None:
        if self._dynamic and not self._discovered:
            self._specs = to_local_model_specs(discover_ollama_models(self.base_url))
            # An unreachable server is retried on the next benchmark cycle.
            self._discovered = bool(self._specs)

    def _benchmark_one(self, model: str) -> _Benchmark:
        from langchain_core.messages import HumanMessage
        start = self._clock()
        try:
            self._client(model).invoke([HumanMessage(content=self.benchmark_prompt)])
            return _Benchmark(self._clock() - start, self._clock(), True)
        except Exception as exc:
            logger.info("Ollama benchmark failed for %s: %s", model, exc)
            return _Benchmark(float("inf"), self._clock(), False)

    def benchmark_all(self) -> dict[str, _Benchmark]:
        """
        Sequential on purpose: local models share one machine's RAM/CPU, and
        loading several at once starves the larger ones. Stops at the first
        model that answers within `good_enough_latency_s`, so a first call
        never waits for every installed model to load.
        """
        for spec in self._eligible_specs():
            result = self._benchmark_one(spec.model)
            self._benchmarks[spec.model] = result
            if result.ok and result.latency_s <= self.good_enough_latency_s:
                break
        return dict(self._benchmarks)

    def _ensure_benchmarks(self) -> None:
        # One thread benchmarks; concurrent callers wait and reuse its results.
        with self._lock:
            self._ensure_discovered()
            if not self._eligible_specs():
                return
            now = self._clock()
            stale = (not self._benchmarks
                     or any(now - b.measured_at > self.benchmark_ttl_s for b in self._benchmarks.values()))
            if stale:
                self._benchmarks.clear()
                self.benchmark_all()

    def ranked_models(self) -> list[str]:
        ranked = sorted(
            ((s.model, self._benchmarks[s.model].latency_s) for s in self._eligible_specs()
             if self.health.is_available(s.model)
             and s.model in self._benchmarks and self._benchmarks[s.model].ok),
            key=lambda pair: pair[1],
        )
        return [model for model, _ in ranked]

    def pick_model(self) -> Optional[str]:
        ranked = self.ranked_models()
        return ranked[0] if ranked else None

    def _ranked_or_raise(self) -> list[str]:
        self._ensure_benchmarks()
        ranked = self.ranked_models()
        if not ranked:
            raise NoLocalModelError("No local Ollama model currently meets the quality/health bar")
        return ranked

    def invoke(self, messages, tools, tool_kwargs, stop):
        # Fastest first; a crashing or timing-out model is cooled down and the
        # next healthy one answers in the same call.
        last_error: Optional[BaseException] = None
        for model in self._ranked_or_raise():
            client = self._client(model)
            runnable = client.bind_tools(list(tools), **tool_kwargs) if tools else client
            try:
                out = runnable.invoke(messages, stop=stop)
            except Exception as exc:
                self.health.record_failure(model, classify(exc))
                last_error = exc
                continue
            self.health.record_success(model)
            out.response_metadata["ollama_model"] = model
            return out
        raise last_error

    def stream(self, messages, tools, tool_kwargs, stop):
        model = self._ranked_or_raise()[0]
        client = self._client(model)
        runnable = client.bind_tools(list(tools), **tool_kwargs) if tools else client
        try:
            yield from runnable.stream(messages, stop=stop)
        except Exception as exc:
            self.health.record_failure(model, classify(exc))
            raise
        self.health.record_success(model)

    def describe(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "base_url": self.base_url,
            "exclude_cloud": self.exclude_cloud, "min_quality": self.min_quality,
            "models": [
                {"model": s.model, "quality": s.quality_score, "cloud": s.is_cloud,
                 "eligible": s.quality_score >= self.min_quality and not (self.exclude_cloud and s.is_cloud),
                 "benchmark_s": (round(self._benchmarks[s.model].latency_s, 3)
                                 if s.model in self._benchmarks and self._benchmarks[s.model].ok else None)}
                for s in self._specs
            ],
            "model_health": self.health.snapshot(),
        }


# ── Router ────────────────────────────────────────────────────────────────────

class LLMRouter:
    def __init__(self, candidates: list[Candidate], clock: Callable[[], float] = time.monotonic):
        if not candidates:
            raise ValueError("LLMRouter requires at least one candidate")
        self.candidates = candidates
        self.health = ProviderHealthTracker(clock)

    def ordered(self, preferred: Optional[str] = None) -> list[Candidate]:
        """Preferred kind first, then healthy candidates; if all are cooling down, try them all anyway."""
        pool = list(self.candidates)
        if preferred:
            pool.sort(key=lambda c: c.kind != preferred)   # stable: keeps relative order
        available = [c for c in pool if self.health.is_available(c.id)]
        return available or pool

    def invoke(self, messages: list[BaseMessage], *, tools: Sequence[Any] = (), tool_kwargs: Optional[dict] = None,
               stop: Optional[list[str]] = None, preferred: Optional[str] = None) -> BaseMessage:
        errors: list[str] = []
        for candidate in self.ordered(preferred):
            try:
                message = candidate.invoke(messages, tools, tool_kwargs or {}, stop)
            except Exception as exc:
                kind = classify(exc)
                cooldown = self.health.record_failure(candidate.id, kind)
                logger.warning("LLM candidate %s failed (%s, cooling %.0fs): %s", candidate.id, kind, cooldown, exc)
                errors.append(f"{candidate.id}: {kind}: {type(exc).__name__}")
                continue
            self.health.record_success(candidate.id)
            message.response_metadata["routed_provider"] = _provider_label(candidate, message)
            return message
        raise AllProvidersFailedError("All LLM providers failed: " + "; ".join(errors))

    def stream(self, messages: list[BaseMessage], *, tools: Sequence[Any] = (), tool_kwargs: Optional[dict] = None,
               stop: Optional[list[str]] = None, preferred: Optional[str] = None) -> Iterator[BaseMessage]:
        """Fails over only before the first chunk; once text has reached the caller it cannot be taken back."""
        errors: list[str] = []
        for candidate in self.ordered(preferred):
            emitted = False
            try:
                for chunk in candidate.stream(messages, tools, tool_kwargs or {}, stop):
                    if not emitted:
                        chunk.response_metadata["routed_provider"] = candidate.id
                    emitted = True
                    yield chunk
            except Exception as exc:
                self.health.record_failure(candidate.id, classify(exc))
                if emitted:
                    raise
                errors.append(f"{candidate.id}: {classify(exc)}: {type(exc).__name__}")
                continue
            self.health.record_success(candidate.id)
            return
        raise AllProvidersFailedError("All LLM providers failed: " + "; ".join(errors))

    def status(self) -> dict:
        return {
            "order": [c.id for c in self.candidates],
            "health": self.health.snapshot(),
            "candidates": [c.describe() for c in self.candidates],
        }


def _provider_label(candidate: Candidate, message: BaseMessage) -> str:
    model = message.response_metadata.get("ollama_model")
    return f"ollama:{model}" if model else candidate.id


class RoutedChatModel(BaseChatModel):
    """The router exposed as an ordinary LangChain chat model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    router: Any
    preferred: Optional[str] = None
    tools: list = []
    tool_kwargs: dict = {}

    @property
    def _llm_type(self) -> str:
        return "naijafinai-router"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "RoutedChatModel":
        # Each provider converts the tool schema to its own wire format at call time.
        return RoutedChatModel(router=self.router, preferred=self.preferred,
                               tools=list(tools), tool_kwargs=kwargs)

    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        message = self.router.invoke(messages, tools=self.tools, tool_kwargs=self.tool_kwargs,
                                     stop=stop, preferred=self.preferred)
        if not isinstance(message, AIMessage):
            message = AIMessage(content=message.content, response_metadata=message.response_metadata)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(self, messages: list[BaseMessage], stop: Optional[list[str]] = None,
                run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        for chunk in self.router.stream(messages, tools=self.tools, tool_kwargs=self.tool_kwargs,
                                        stop=stop, preferred=self.preferred):
            if not isinstance(chunk, AIMessageChunk):
                chunk = AIMessageChunk(content=chunk.content, response_metadata=chunk.response_metadata)
            yield ChatGenerationChunk(message=chunk)


def message_text(message: Any) -> str:
    """
    Plain text of a reply. Current Claude models return content as a list of
    blocks (thinking + text) rather than a string; other providers return a
    string. Keep the original message in conversation history unchanged and
    use this only for display.
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


# ── Default wiring from settings ──────────────────────────────────────────────

DEFAULT_GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]


def groq_model_order() -> list[str]:
    """GROQ_MODELS if set; otherwise the copilot's defaults followed by the legacy GROQ_MODEL / GROQ_FALLBACK_MODEL."""
    if settings.groq_models.strip():
        models = [m.strip() for m in settings.groq_models.split(",") if m.strip()]
    else:
        models = DEFAULT_GROQ_MODELS + [settings.groq_model, settings.groq_fallback_model]
    return list(dict.fromkeys(m for m in models if m))


def _remote_candidates() -> list[Candidate]:
    timeout = settings.llm_timeout_s
    out: list[Candidate] = []
    # max_retries=0 everywhere: the SDKs' own retry loops would spend minutes
    # on a 429 that the router resolves instantly by moving to the next model.
    if settings.groq_api_key:
        from langchain_groq import ChatGroq
        for model in groq_model_order():
            extra = {"base_url": settings.groq_base_url} if settings.groq_base_url else {}
            out.append(ChatModelCandidate("groq", model, lambda m=model, extra=extra: ChatGroq(
                model=m, api_key=settings.groq_api_key, temperature=0.1, timeout=timeout, max_retries=0, **extra)))
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        out.append(ChatModelCandidate("openai", settings.openai_model, lambda: ChatOpenAI(
            model=settings.openai_model, api_key=settings.openai_api_key, temperature=0.1,
            timeout=timeout, max_retries=0)))
    if settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        # No temperature: current Claude models reject sampling parameters.
        out.append(ChatModelCandidate("anthropic", settings.anthropic_model, lambda: ChatAnthropic(
            model=settings.anthropic_model, api_key=settings.anthropic_api_key, max_tokens=16000,
            timeout=timeout, max_retries=0)))
    if settings.google_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            pass
        else:
            out.append(ChatModelCandidate("google", settings.google_model, lambda: ChatGoogleGenerativeAI(
                model=settings.google_model, google_api_key=settings.google_api_key, temperature=0.1)))
    return out


def build_router(local_pool: LocalPoolPosition) -> Optional[LLMRouter]:
    candidates: list[Candidate] = []
    pool = None
    if local_pool != "off" and settings.ollama_base_url:
        pool = LocalModelPool(settings.ollama_base_url, min_quality=settings.ollama_min_quality,
                              exclude_cloud=(local_pool == "only"), timeout_s=settings.ollama_timeout_s)
    if local_pool == "only":
        return LLMRouter([pool]) if pool else None
    if pool and local_pool == "first":
        candidates.append(pool)
    candidates.extend(_remote_candidates())
    if pool and local_pool == "last":
        candidates.append(pool)
    return LLMRouter(candidates) if candidates else None


# Two profiles, as in the copilot: interactive calls (chat, analyst
# explanations) keep remote first so nobody waits on a cold local load;
# batch calls (workflows, statement insights) try the free local pool first.
Profile = Literal["interactive", "batch"]

_routers: dict[str, Optional[LLMRouter]] = {}
_routers_lock = threading.Lock()


def _position_for(profile: Profile) -> LocalPoolPosition:
    configured = settings.llm_local_pool
    if configured in ("off", "only"):
        return configured
    return configured if profile == "interactive" else "first"


def get_router(profile: Profile = "interactive") -> LLMRouter:
    with _routers_lock:
        if profile not in _routers:
            _routers[profile] = build_router(_position_for(profile))
        router = _routers[profile]
    if router is None:
        raise RuntimeError("No LLM providers configured. Set GROQ_API_KEY, ANTHROPIC_API_KEY, "
                           "OPENAI_API_KEY or OLLAMA_BASE_URL.")
    return router


def reset_routers() -> None:
    with _routers_lock:
        _routers.clear()


_PROVIDER_ALIASES = {"groq_primary": "groq", "groq_fallback": "groq", "groq_fast": "groq", "auto": None}


def get_routed_llm(provider: Optional[str] = None, profile: Profile = "interactive") -> RoutedChatModel:
    """
    `provider` reorders the chain only when it is an explicit choice (e.g. the
    UI's provider picker). The configured default is already reflected in the
    router's own order, so passing it changes nothing.
    """
    preferred = _PROVIDER_ALIASES.get(provider, provider) if provider else None
    if preferred == settings.default_llm_provider:
        preferred = None
    return RoutedChatModel(router=get_router(profile), preferred=preferred)
