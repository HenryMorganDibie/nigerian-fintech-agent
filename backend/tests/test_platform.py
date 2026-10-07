def test_health_endpoints(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["database"] == "ok"
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and "model_version" in h


def test_demo_structuring_scenario_still_reaches_critical(client):
    r = client.post("/api/simulate/run", json={"scenario_id": "structuring_attack"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "error" not in body
    assert "CBN_STRUCTURING" in str(body)


def test_synthetic_eval_still_runs(client):
    r = client.post("/api/eval/run", json={"use_synthetic": True})
    assert r.status_code == 200, r.text
    assert r.json()["total_samples"] > 0


def test_platform_postgres_urls_use_psycopg3():
    from app.db import normalise_url
    assert normalise_url("postgres://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert normalise_url("postgresql://u@h/d") == "postgresql+psycopg://u@h/d"
    assert normalise_url("postgresql+psycopg://u@h/d") == "postgresql+psycopg://u@h/d"
    assert normalise_url("sqlite://") == "sqlite://"
