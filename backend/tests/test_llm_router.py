"""
Router behaviour, ported from interview-copilot's ProviderRouter / LocalModelPool.

Unit tests use scripted candidates and a fake clock. Wire tests run real HTTP
servers for Groq (OpenAI-compatible) and Ollama, so failover is exercised
through the actual SDK clients and their real error types.
"""
import asyncio
import json
import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.tools import tool

from app.core import llm_router as lr


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class HTTPStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class Scripted(lr.Candidate):
    """Candidate whose replies/failures are scripted per call."""

    def __init__(self, cid, script, kind=None):
        self.id = cid
        self.kind = kind or cid.split(":")[0]
        self.script = list(script)
        self.calls = []

    def _next(self):
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, BaseException):
            raise step
        return step

    def invoke(self, messages, tools, tool_kwargs, stop):
        self.calls.append({"tools": list(tools)})
        return AIMessage(content=self._next())

    def stream(self, messages, tools, tool_kwargs, stop):
        self.calls.append({"tools": list(tools)})
        step = self._next()
        for part in step if isinstance(step, list) else [step]:
            if isinstance(part, BaseException):
                raise part
            yield AIMessageChunk(content=part)


HI = [HumanMessage(content="hi")]


# ── Health tracker and classification ────────────────────────────────────────

def test_rate_limit_parks_a_candidate_for_sixty_seconds():
    clock = Clock()
    h = lr.ProviderHealthTracker(clock)
    assert h.record_failure("groq:x", "rate_limit") == 60
    assert not h.is_available("groq:x")
    clock.t += 59.9
    assert not h.is_available("groq:x")
    clock.t += 0.2
    assert h.is_available("groq:x")


def test_errors_back_off_exponentially_and_cap_at_five_minutes():
    h = lr.ProviderHealthTracker(Clock())
    cooldowns = [h.record_failure("a", "error") for _ in range(10)]
    assert cooldowns[:4] == [2, 4, 8, 16]
    assert cooldowns[-1] == 300


def test_success_clears_the_failure_record():
    h = lr.ProviderHealthTracker(Clock())
    h.record_failure("a", "timeout")
    h.record_success("a")
    assert h.is_available("a") and h.snapshot() == {}


def test_classification():
    import httpx
    assert lr.classify(HTTPStatusError(429)) == "rate_limit"
    assert lr.classify(HTTPStatusError(529)) == "rate_limit"     # Anthropic overloaded_error
    assert lr.classify(HTTPStatusError(500)) == "error"
    assert lr.classify(httpx.ReadTimeout("slow")) == "timeout"
    assert lr.classify(TimeoutError()) == "timeout"
    assert lr.classify(ValueError("bad json")) == "error"


# ── Router ───────────────────────────────────────────────────────────────────

def test_fails_over_in_order_and_labels_the_serving_provider():
    a = Scripted("groq:big", [HTTPStatusError(429)])
    b = Scripted("groq:small", ["from small"])
    c = Scripted("anthropic:claude", ["from claude"])
    router = lr.LLMRouter([a, b, c], clock=Clock())
    out = router.invoke(HI)
    assert out.content == "from small"
    assert out.response_metadata["routed_provider"] == "groq:small"
    assert c.calls == []


def test_cooling_candidates_are_skipped_until_they_recover():
    clock = Clock()
    a = Scripted("groq:big", [HTTPStatusError(429), "big is back"])
    b = Scripted("groq:small", ["small"])
    router = lr.LLMRouter([a, b], clock=clock)
    router.invoke(HI)
    router.invoke(HI)
    assert len(a.calls) == 1          # second call skipped the rate-limited model
    clock.t += 61
    assert router.invoke(HI).content == "big is back"


def test_when_everything_is_cooling_it_still_tries_rather_than_refusing():
    clock = Clock()
    a = Scripted("groq:big", [HTTPStatusError(429), "recovered"])
    router = lr.LLMRouter([a], clock=clock)
    with pytest.raises(lr.AllProvidersFailedError):
        router.invoke(HI)
    assert router.invoke(HI).content == "recovered"


def test_all_failures_raise_with_a_reason_per_candidate():
    router = lr.LLMRouter([Scripted("groq:a", [HTTPStatusError(429)]),
                           Scripted("anthropic:b", [TimeoutError()])], clock=Clock())
    with pytest.raises(lr.AllProvidersFailedError) as e:
        router.invoke(HI)
    assert "groq:a: rate_limit" in str(e.value) and "anthropic:b: timeout" in str(e.value)


def test_explicit_provider_choice_moves_that_kind_to_the_front():
    g = Scripted("groq:a", ["groq"])
    an = Scripted("anthropic:b", ["claude"])
    router = lr.LLMRouter([g, an], clock=Clock())
    assert router.invoke(HI, preferred="anthropic").content == "claude"
    assert router.invoke(HI).content == "groq"


def test_routed_chat_model_works_as_a_langchain_model_and_forwards_tools():
    @tool
    def lookup(account: str) -> str:
        """Look up an account."""
        return account

    a = Scripted("groq:a", [HTTPStatusError(500)])
    b = Scripted("groq:b", ["ok"])
    model = lr.RoutedChatModel(router=lr.LLMRouter([a, b], clock=Clock()))
    out = model.bind_tools([lookup]).invoke(HI)
    assert out.content == "ok" and out.response_metadata["routed_provider"] == "groq:b"
    assert [t.name for t in b.calls[0]["tools"]] == ["lookup"]


def test_stream_fails_over_before_the_first_chunk_only():
    a = Scripted("groq:a", [[HTTPStatusError(429)]])
    b = Scripted("groq:b", [["Hel", "lo"]])
    router = lr.LLMRouter([a, b], clock=Clock())
    assert "".join(c.content for c in router.stream(HI)) == "Hello"

    half = Scripted("groq:c", [["Hel", RuntimeError("dropped")]])
    spare = Scripted("groq:d", [["never"]])
    router = lr.LLMRouter([half, spare], clock=Clock())
    with pytest.raises(RuntimeError):
        list(router.stream(HI))
    assert spare.calls == []


def test_message_text_handles_claude_block_content():
    blocks = AIMessage(content=[{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Done."}])
    assert lr.message_text(blocks) == "Done."
    assert lr.message_text(AIMessage(content="plain")) == "plain"


# ── Ollama discovery heuristics ──────────────────────────────────────────────

def test_quality_scores_and_speed_ordering():
    models = [
        lr.DiscoveredOllamaModel("llama3.1:70b", "llama", "70.6B", False),
        lr.DiscoveredOllamaModel("qwen2.5-coder:7b", "qwen2", "7.6B", False),
        lr.DiscoveredOllamaModel("llama3.2:3b", "llama", "3.2B", False),
        lr.DiscoveredOllamaModel("gpt-oss:120b-cloud", None, None, True),
    ]
    specs = lr.to_local_model_specs(models)
    assert [s.model for s in specs] == ["llama3.2:3b", "qwen2.5-coder:7b", "llama3.1:70b", "gpt-oss:120b-cloud"]
    scores = {s.model: s.quality_score for s in specs}
    assert scores == {"llama3.2:3b": 0.7, "qwen2.5-coder:7b": 0.5, "llama3.1:70b": 0.7, "gpt-oss:120b-cloud": 0.85}


# ── Wire tests: real HTTP servers for Groq and Ollama ────────────────────────

OLLAMA_MODELS = {
    # name: (seconds per reply, parameter size, remote_host)
    "llama3.2:3b":        (0.30, "3.2B", None),
    "qwen2.5:7b":         (0.05, "7.6B", None),
    "qwen2.5-coder:1.5b": (0.01, "1.5B", None),       # fastest, but below the quality floor
    "gpt-oss:120b-cloud": (0.01, None, "https://ollama.com:443"),
}
_ollama_broken: set = set()
_ollama_calls: list = []
_groq_calls: list = []
_groq_bodies: list = []


def _fake_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/tags")
    async def tags():
        return {"models": [
            {"name": n, "model": n, **({"remote_host": rh} if rh else {}),
             "details": {"family": "x", **({"parameter_size": ps} if ps else {})}}
            for n, (_, ps, rh) in OLLAMA_MODELS.items()
        ]}

    @app.post("/api/chat")
    async def chat(request: Request):
        body = await request.json()
        model = body["model"]
        _ollama_calls.append(model)
        if model in _ollama_broken:
            return JSONResponse({"error": "model crashed"}, status_code=500)
        await asyncio.sleep(OLLAMA_MODELS[model][0])
        text = f"answer from {model}"

        def lines():
            yield json.dumps({"model": model, "created_at": "2026-10-07T00:00:00Z",
                              "message": {"role": "assistant", "content": text}, "done": False}) + "\n"
            yield json.dumps({"model": model, "created_at": "2026-10-07T00:00:00Z",
                              "message": {"role": "assistant", "content": ""}, "done": True,
                              "done_reason": "stop", "total_duration": 1, "load_duration": 1,
                              "prompt_eval_count": 1, "prompt_eval_duration": 1,
                              "eval_count": 1, "eval_duration": 1}) + "\n"
        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @app.post("/openai/v1/chat/completions")
    async def groq(request: Request):
        body = await request.json()
        _groq_calls.append(body["model"])
        _groq_bodies.append(body)
        if body["model"] == "limited":
            return JSONResponse({"error": {"message": "Rate limit reached for TPM", "type": "tokens",
                                           "code": "rate_limit_exceeded"}}, status_code=429)
        return {"id": "c1", "object": "chat.completion", "created": 1, "model": body["model"],
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": f"groq {body['model']}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    return app


@pytest.fixture(scope="module")
def fake_server():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(_fake_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _reset_fake_state():
    _ollama_broken.clear()
    _ollama_calls.clear()
    _groq_calls.clear()
    _groq_bodies.clear()
    yield
    lr.reset_routers()


def test_discovery_reads_tags_and_flags_cloud_models(fake_server):
    found = {m.name: m.is_cloud for m in lr.discover_ollama_models(fake_server)}
    assert found == {"llama3.2:3b": False, "qwen2.5:7b": False, "qwen2.5-coder:1.5b": False, "gpt-oss:120b-cloud": True}
    assert lr.discover_ollama_models("http://127.0.0.1:9") == []      # unreachable → empty, no exception


def test_pool_respects_quality_floor_and_prefers_fastest(fake_server):
    pool = lr.LocalModelPool(fake_server, min_quality=0.6, good_enough_latency_s=0.0)
    out = lr.LLMRouter([pool]).invoke(HI)
    # Coder (1.5B, fastest) is below the floor; the cloud model is fastest of the rest.
    assert out.response_metadata["routed_provider"] == "ollama:gpt-oss:120b-cloud"


def test_data_residency_mode_never_uses_cloud_models(fake_server):
    pool = lr.LocalModelPool(fake_server, min_quality=0.6, exclude_cloud=True, good_enough_latency_s=0.0)
    out = lr.LLMRouter([pool]).invoke(HI)
    assert out.response_metadata["routed_provider"] == "ollama:qwen2.5:7b"
    assert "gpt-oss:120b-cloud" not in _ollama_calls


def test_benchmarking_stops_at_the_first_good_enough_model(fake_server):
    pool = lr.LocalModelPool(fake_server, exclude_cloud=True, good_enough_latency_s=5.0)
    lr.LLMRouter([pool]).invoke(HI)
    # Smallest first: the 1.5B model answers well within 5s, so no other model is loaded.
    assert _ollama_calls == ["qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b"]   # benchmark, then the real call


def test_below_floor_models_are_never_benchmarked(fake_server):
    # Regression: the fast coder model used to end the early-stop pass and
    # leave the pool with nothing above the floor to pick.
    pool = lr.LocalModelPool(fake_server, min_quality=0.6, exclude_cloud=True, good_enough_latency_s=5.0)
    out = lr.LLMRouter([pool]).invoke(HI)
    assert "qwen2.5-coder:1.5b" not in _ollama_calls
    assert out.response_metadata["routed_provider"] == "ollama:llama3.2:3b"


def test_a_crashing_local_model_is_cooled_down_and_the_next_one_used(fake_server):
    pool = lr.LocalModelPool(fake_server, min_quality=0.6, exclude_cloud=True, good_enough_latency_s=0.0)
    router = lr.LLMRouter([pool])
    assert router.invoke(HI).response_metadata["routed_provider"] == "ollama:qwen2.5:7b"
    _ollama_broken.add("qwen2.5:7b")
    # Same call: the crash is absorbed and the next-fastest healthy model answers.
    assert router.invoke(HI).response_metadata["routed_provider"] == "ollama:llama3.2:3b"
    assert pool.health.snapshot()["qwen2.5:7b"]["last_failure"] == "error"
    _ollama_calls.clear()
    router.invoke(HI)
    assert _ollama_calls == ["llama3.2:3b"]     # the crashed model is skipped while it cools down


def test_real_groq_429_fails_over_to_the_next_groq_model(fake_server, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_base_url", fake_server)
    monkeypatch.setattr(settings, "groq_models", "limited,healthy")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "ollama_base_url", "")
    lr.reset_routers()
    llm = lr.get_routed_llm()
    out = llm.invoke(HI)
    assert out.content == "groq healthy"
    assert out.response_metadata["routed_provider"] == "groq:healthy"
    assert _groq_calls == ["limited", "healthy"]       # no SDK retries burned on the 429
    llm.invoke(HI)
    assert _groq_calls == ["limited", "healthy", "healthy"]   # limited model is cooling down
    assert lr.get_router().status()["health"]["groq:limited"]["last_failure"] == "rate_limit"


def test_local_pool_last_is_the_fallback_when_every_remote_is_limited(fake_server, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_base_url", fake_server)
    monkeypatch.setattr(settings, "groq_models", "limited")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "ollama_base_url", fake_server)
    monkeypatch.setattr(settings, "llm_local_pool", "last")
    lr.reset_routers()
    assert [c.id for c in lr.get_router("interactive").candidates] == ["groq:limited", "ollama-pool"]
    assert [c.id for c in lr.get_router("batch").candidates] == ["ollama-pool", "groq:limited"]
    out = lr.get_routed_llm().invoke(HI)
    assert out.response_metadata["routed_provider"].startswith("ollama:")


def test_only_mode_builds_a_local_only_router(fake_server, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "ollama_base_url", fake_server)
    monkeypatch.setattr(settings, "llm_local_pool", "only")
    lr.reset_routers()
    for profile in ("interactive", "batch"):
        router = lr.get_router(profile)
        assert [c.id for c in router.candidates] == ["ollama-pool"]
        assert router.candidates[0].exclude_cloud is True


def test_no_providers_configured_is_a_clear_error(monkeypatch):
    from app.core.config import settings
    for field in ("groq_api_key", "openai_api_key", "anthropic_api_key", "google_api_key", "ollama_base_url"):
        monkeypatch.setattr(settings, field, "")
    lr.reset_routers()
    with pytest.raises(RuntimeError, match="No LLM providers configured"):
        lr.get_routed_llm()


def test_chat_agent_end_to_end_reports_the_provider_that_answered(fake_server, monkeypatch, client):
    from app.core.config import settings
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_base_url", fake_server)
    monkeypatch.setattr(settings, "groq_models", "limited,healthy")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "ollama_base_url", "")
    lr.reset_routers()
    r = client.post("/api/chat", json={"message": "How do I report a SIM swap fraud?", "stream": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "groq healthy"
    assert body["provider_used"] == "groq:healthy"
    # The agent's tools reached the provider through the router.
    assert {t["function"]["name"] for t in _groq_bodies[-1]["tools"]} >= {"nigerian_fraud_score"}
