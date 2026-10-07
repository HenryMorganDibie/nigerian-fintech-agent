import os
import sys
from pathlib import Path

# Configure the app before anything imports settings.
# TEST_DATABASE_URL / TEST_REDIS_URL run the same suite against real Postgres and Redis.
TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "")
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["DEMO_MODE"] = "true"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["GROQ_API_KEY"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

ADMIN = {"X-Admin-Token": "test-admin-token"}


@pytest.fixture
def client():
    from app import db
    from app.core.feature_store import reset_memory_store
    from app.core.fraud_graph import reset_graphs
    import main

    db.configure(TEST_DB)
    db.Base.metadata.drop_all(db.engine())
    db.Base.metadata.create_all(db.engine())
    reset_memory_store()
    reset_graphs()
    from app.core.feature_store import _redis
    if _redis() is not None:
        _redis().flushdb()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def make_tenant(client):
    def _make(name="Acme MFB", mode="live"):
        r = client.post("/v1/admin/tenants", json={"name": name, "mode": mode}, headers=ADMIN)
        assert r.status_code == 201, r.text
        body = r.json()
        return body["tenant"], {"Authorization": f"Bearer {body['api_key']['key']}"}
    return _make


def tx(**overrides) -> dict:
    """A clean, low-risk transfer; override fields to build attack scenarios."""
    base = {
        "transaction_id": "TX-1",
        "amount": 15_000,
        "timestamp": "2026-10-07T14:00:00+01:00",
        "sender_account": "0123456789",
        "recipient_account": "9876543210",
        "channel": "transfer",
    }
    base.update(overrides)
    return base
