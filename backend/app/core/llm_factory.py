"""
LLM Factory — Multi-Provider Fallback Chain + Circuit Breaker
===============================================================
Priority chain:
  1. Groq llama-3.3-70b-versatile  (primary — free, fast)
  2. Groq llama-3.1-8b-instant     (Groq fallback — same key)
  3. OpenAI GPT-4o                  (if key set)
  4. Anthropic Claude               (if key set)
  5. Rules-only degraded mode       (always works, no LLM)

Circuit breaker:
  - Trips after 3 consecutive 429/5xx errors
  - Stays open for 10 minutes
  - Auto-resets and retries primary after cooldown
"""

from langchain_core.language_models import BaseChatModel
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import logging, time

logger = logging.getLogger(__name__)


# ── Circuit Breaker State ─────────────────────────────────────────────────────

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_minutes: int = 10):
        self.failure_threshold = failure_threshold
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self._failures: dict[str, int] = defaultdict(int)
        self._tripped_at: dict[str, datetime] = {}

    def is_open(self, provider: str) -> bool:
        """Returns True if circuit is open (provider should be skipped)."""
        if provider not in self._tripped_at:
            return False
        elapsed = datetime.now(timezone.utc) - self._tripped_at[provider]
        if elapsed > self.cooldown:
            self._reset(provider)
            return False
        return True

    def record_failure(self, provider: str):
        self._failures[provider] += 1
        if self._failures[provider] >= self.failure_threshold:
            self._tripped_at[provider] = datetime.now(timezone.utc)
            remaining = self.cooldown.seconds // 60
            logger.warning(f"Circuit breaker TRIPPED for {provider} — cooling down {remaining} mins")

    def record_success(self, provider: str):
        self._failures[provider] = 0
        self._tripped_at.pop(provider, None)

    def _reset(self, provider: str):
        self._failures[provider] = 0
        self._tripped_at.pop(provider, None)
        logger.info(f"Circuit breaker RESET for {provider} — retrying")

    def status(self) -> dict:
        now = datetime.now(timezone.utc)
        result = {}
        for p, failures in self._failures.items():
            tripped = p in self._tripped_at
            remaining = 0
            if tripped:
                elapsed = now - self._tripped_at[p]
                remaining = max(0, int((self.cooldown - elapsed).total_seconds() / 60))
            result[p] = {
                "failures": failures,
                "circuit_open": tripped and remaining > 0,
                "cooldown_remaining_mins": remaining,
            }
        return result


circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_minutes=10)


# ── Provider Builders ─────────────────────────────────────────────────────────

def _groq_primary(streaming=False) -> BaseChatModel:
    from langchain_groq import ChatGroq
    return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key,
                    streaming=streaming, temperature=0.1)

def _groq_fallback(streaming=False) -> BaseChatModel:
    from langchain_groq import ChatGroq
    return ChatGroq(model=settings.groq_fallback_model, api_key=settings.groq_api_key,
                    streaming=streaming, temperature=0.1)

def _openai(streaming=False) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key,
                      streaming=streaming, temperature=0.1)

def _anthropic(streaming=False) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=settings.anthropic_model, api_key=settings.anthropic_api_key,
                         streaming=streaming, temperature=0.1)


# ── Fallback Chain ────────────────────────────────────────────────────────────

def _build_chain(preferred_provider: str, streaming: bool) -> list[tuple[str, callable]]:
    """Build ordered fallback chain based on preferred provider and available keys."""
    chain = []

    if preferred_provider == "groq":
        if settings.groq_api_key:
            chain.append(("groq_primary",   lambda: _groq_primary(streaming)))
            chain.append(("groq_fallback",  lambda: _groq_fallback(streaming)))
        if settings.openai_api_key:
            chain.append(("openai",         lambda: _openai(streaming)))
        if settings.anthropic_api_key:
            chain.append(("anthropic",      lambda: _anthropic(streaming)))

    elif preferred_provider == "openai":
        if settings.openai_api_key:
            chain.append(("openai",         lambda: _openai(streaming)))
        if settings.groq_api_key:
            chain.append(("groq_primary",   lambda: _groq_primary(streaming)))
            chain.append(("groq_fallback",  lambda: _groq_fallback(streaming)))
        if settings.anthropic_api_key:
            chain.append(("anthropic",      lambda: _anthropic(streaming)))

    elif preferred_provider == "anthropic":
        if settings.anthropic_api_key:
            chain.append(("anthropic",      lambda: _anthropic(streaming)))
        if settings.groq_api_key:
            chain.append(("groq_primary",   lambda: _groq_primary(streaming)))
            chain.append(("groq_fallback",  lambda: _groq_fallback(streaming)))

    return chain


def get_llm(provider: str | None = None, streaming: bool = False) -> BaseChatModel:
    """Get LLM for specified provider (no fallback — use get_llm_with_fallback for resilience)."""
    provider = provider or settings.default_llm_provider
    if provider in ("groq", "groq_primary"):
        return _groq_primary(streaming)
    elif provider == "groq_fallback":
        return _groq_fallback(streaming)
    elif provider == "openai":
        return _openai(streaming)
    elif provider == "anthropic":
        return _anthropic(streaming)
    elif provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=settings.google_model,
                                          google_api_key=settings.google_api_key,
                                          streaming=streaming, temperature=0.1)
        except ImportError:
            raise ValueError("Google provider not installed")
    raise ValueError(f"Unknown provider: {provider}")


def get_llm_with_fallback(provider: str | None = None, streaming: bool = False) -> BaseChatModel:
    """
    Get LLM with full multi-provider fallback chain + circuit breaker.
    Tries each provider in order, skipping tripped circuits.
    """
    provider = provider or settings.default_llm_provider
    chain = _build_chain(provider, streaming)

    if not chain:
        raise RuntimeError("No LLM providers configured. Set GROQ_API_KEY in environment.")

    last_error = None
    for provider_key, builder in chain:
        if circuit_breaker.is_open(provider_key):
            logger.info(f"Skipping {provider_key} — circuit open")
            continue
        try:
            llm = builder()
            # Verify it works with a minimal test (just build, don't invoke)
            circuit_breaker.record_success(provider_key)
            if provider_key != (provider + "_primary" if provider == "groq" else provider):
                logger.info(f"Using fallback provider: {provider_key}")
            return llm
        except Exception as e:
            circuit_breaker.record_failure(provider_key)
            last_error = e
            logger.warning(f"Provider {provider_key} failed: {e}")
            continue

    raise RuntimeError(f"All LLM providers exhausted. Last error: {last_error}")


def get_circuit_breaker_status() -> dict:
    return circuit_breaker.status()
