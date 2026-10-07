import time

import pytest

from tests.conftest import tx

SIM_SWAP = dict(channel="ussd", amount=85_000, sim_replaced_hours_ago=4)


@pytest.fixture
def no_llm(monkeypatch):
    """Fail loudly if anything on the decision path reaches for an LLM."""
    import app.core.llm_factory as lf

    def boom(*a, **k):
        raise AssertionError("LLM called on the decision path")
    monkeypatch.setattr(lf, "get_llm_with_fallback", boom)
    monkeypatch.setattr(lf, "get_llm", boom)


def test_decision_contract(client, make_tenant, no_llm):
    _, auth = make_tenant()
    r = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["id"].startswith("dec_")
    assert d["action"] == "allow" and d["recommended_action"] == "allow"
    assert d["mode"] == "live"
    for field in ("score", "risk_level", "fraud_probability", "reason_codes", "layers",
                  "regulatory_filings", "model_version", "latency_ms", "audit", "created_at"):
        assert field in d
    assert "0123456789" not in str(d)   # raw account numbers are not echoed back


def test_attack_is_blocked_with_reason_codes(client, make_tenant, no_llm):
    _, auth = make_tenant(mode="live")
    d = client.post("/v1/decisions", json={"transaction": tx(**SIM_SWAP)}, headers=auth).json()
    assert d["action"] == "block"
    assert d["hard_override"] == "SIM_SWAP_USSD"
    codes = [c["code"] for c in d["reason_codes"]]
    assert "SIM_SWAP_HIGH_VALUE_USSD" in codes
    assert all(c["evidence"] for c in d["reason_codes"])


def test_shadow_mode_never_enforces(client, make_tenant):
    _, auth = make_tenant(mode="shadow")
    d = client.post("/v1/decisions", json={"transaction": tx(**SIM_SWAP)}, headers=auth).json()
    assert d["mode"] == "shadow"
    assert d["recommended_action"] == "block"
    assert d["action"] == "allow"


def test_shadow_tenant_cannot_opt_into_enforcement_per_request(client, make_tenant):
    _, auth = make_tenant(mode="shadow")
    d = client.post("/v1/decisions", json={"transaction": tx(**SIM_SWAP), "mode": "live"}, headers=auth).json()
    assert d["mode"] == "shadow" and d["action"] == "allow"


def test_live_tenant_can_shadow_a_single_request(client, make_tenant):
    _, auth = make_tenant(mode="live")
    d = client.post("/v1/decisions", json={"transaction": tx(**SIM_SWAP), "mode": "shadow"}, headers=auth).json()
    assert d["mode"] == "shadow" and d["action"] == "allow" and d["recommended_action"] == "block"


def test_idempotent_replay_returns_the_original_decision(client, make_tenant):
    _, auth = make_tenant()
    h = {**auth, "Idempotency-Key": "abc-123"}
    first = client.post("/v1/decisions", json={"transaction": tx()}, headers=h)
    second = client.post("/v1/decisions", json={"transaction": tx()}, headers=h)
    assert first.status_code == 201 and second.status_code == 200
    assert second.headers.get("Idempotent-Replayed") == "true"
    assert first.json() == second.json()
    assert len(client.get("/v1/decisions", headers=auth).json()["data"]) == 1


def test_reusing_a_key_with_a_different_body_is_a_conflict(client, make_tenant):
    _, auth = make_tenant()
    h = {**auth, "Idempotency-Key": "abc-123"}
    client.post("/v1/decisions", json={"transaction": tx()}, headers=h)
    r = client.post("/v1/decisions", json={"transaction": tx(amount=20_000)}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "idempotency_conflict"


def test_transaction_id_is_the_default_idempotency_key(client, make_tenant):
    _, auth = make_tenant()
    a = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth)
    b = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth)
    assert a.json()["id"] == b.json()["id"]
    assert client.post("/v1/decisions", json={"transaction": tx(amount=1)}, headers=auth).status_code == 409


def test_replay_does_not_double_count_behaviour(client, make_tenant):
    from app.core.feature_store import get_user_profile
    tenant, auth = make_tenant()
    for _ in range(3):
        client.post("/v1/decisions", json={"transaction": tx()}, headers=auth)
    assert get_user_profile("0123456789", tenant["id"])["total_tx_count"] == 1


def test_list_filters_by_recommended_action(client, make_tenant):
    _, auth = make_tenant()
    client.post("/v1/decisions", json={"transaction": tx()}, headers=auth)
    client.post("/v1/decisions", json={"transaction": tx(transaction_id="TX-2", **SIM_SWAP)}, headers=auth)
    blocked = client.get("/v1/decisions?action=block", headers=auth).json()["data"]
    assert [d["transaction_id"] for d in blocked] == ["TX-2"]


def test_labels_feed_the_metrics_summary(client, make_tenant):
    _, auth = make_tenant()
    ok = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth).json()
    bad = client.post("/v1/decisions", json={"transaction": tx(transaction_id="TX-2", **SIM_SWAP)}, headers=auth).json()
    missed = client.post("/v1/decisions", json={"transaction": tx(transaction_id="TX-3", amount=12_000)}, headers=auth).json()
    for d, label in ((ok, "legit"), (bad, "fraud"), (missed, "fraud")):
        r = client.post(f"/v1/decisions/{d['id']}/labels", json={"label": label, "source": "chargeback"}, headers=auth)
        assert r.status_code == 200
    m = client.get("/v1/metrics/summary", headers=auth).json()
    assert m["decisions"] == 3
    assert m["labels"]["confusion"] == {"true_positive": 1, "false_positive": 0,
                                        "false_negative": 1, "true_negative": 1}
    assert m["labels"]["precision"] == 1.0 and m["labels"]["recall"] == 0.5
    assert m["latency_ms"]["p99"] is not None
    assert client.get(f"/v1/decisions/{bad['id']}", headers=auth).json()["label"] == "fraud"


def test_explanation_is_generated_on_demand_and_cached(client, make_tenant, monkeypatch):
    import app.core.llm_factory as lf
    calls = []

    class FakeLLM:
        def invoke(self, messages):
            from langchain_core.messages import AIMessage
            calls.append(messages)
            return AIMessage(content="  Account takeover via SIM swap.  ",
                             response_metadata={"routed_provider": "groq:openai/gpt-oss-120b"})
    monkeypatch.setattr(lf, "get_llm_with_fallback", lambda **k: FakeLLM())

    _, auth = make_tenant()
    d = client.post("/v1/decisions", json={"transaction": tx(**SIM_SWAP)}, headers=auth).json()
    first = client.post(f"/v1/decisions/{d['id']}/explanation", headers=auth).json()
    second = client.post(f"/v1/decisions/{d['id']}/explanation", headers=auth).json()
    assert first == {"id": d["id"], "explanation": "Account takeover via SIM swap.", "cached": False,
                     "provider": "groq:openai/gpt-oss-120b"}
    assert second["cached"] is True and len(calls) == 1
    prompt = calls[0][1].content
    assert "0123456789" not in prompt and "9876543210" not in prompt


def test_explanation_reports_503_without_an_llm(client, make_tenant, no_llm):
    _, auth = make_tenant()
    d = client.post("/v1/decisions", json={"transaction": tx()}, headers=auth).json()
    r = client.post(f"/v1/decisions/{d['id']}/explanation", headers=auth)
    assert r.status_code == 503


def test_decision_latency_budget(client, make_tenant, no_llm):
    """In-process p99 well under the 100ms production budget (generous margin for CI runners)."""
    _, auth = make_tenant()
    timings = []
    for i in range(200):
        t0 = time.perf_counter()
        r = client.post("/v1/decisions", json={"transaction": tx(transaction_id=f"TX-{i}")}, headers=auth)
        timings.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 201
    timings.sort()
    p99 = timings[int(0.99 * (len(timings) - 1))]
    assert p99 < 100, f"p99 {p99:.1f}ms"
