"""
Races that only a real database can exhibit. Skipped on SQLite (single shared
connection); CI runs them against Postgres.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.conftest import TEST_DB, tx

pytestmark = pytest.mark.skipif(TEST_DB.startswith("sqlite"), reason="needs a real database")


def test_concurrent_retries_with_one_idempotency_key_create_one_decision(client, make_tenant):
    _, auth = make_tenant()
    h = {**auth, "Idempotency-Key": "race-1"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: client.post("/v1/decisions", json={"transaction": tx()}, headers=h),
                                range(16)))
    assert {r.status_code for r in results} <= {200, 201}
    assert len({r.json()["id"] for r in results}) == 1
    assert len(client.get("/v1/decisions", headers=auth).json()["data"]) == 1


def test_concurrent_decisions_keep_the_audit_chain_intact(client, make_tenant):
    _, auth = make_tenant()

    def post(i):
        return client.post("/v1/decisions", json={"transaction": tx(transaction_id=f"TX-{i}")}, headers=auth)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(post, range(40)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results if r.status_code != 201][:3]
    v = client.get("/v1/audit/verify", headers=auth).json()
    assert v["valid"] is True and v["events_checked"] == 42
