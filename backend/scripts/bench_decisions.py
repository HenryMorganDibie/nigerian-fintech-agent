"""
In-process latency benchmark for POST /v1/decisions.

    DATABASE_URL=postgresql+psycopg://... REDIS_URL=redis://... python scripts/bench_decisions.py 1000

Reports end-to-end (client-observed, in-process) and server-recorded latency.
Network and TLS are excluded; measure those against your deployment with Locust.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ADMIN_TOKEN", "bench-admin")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app.core.config import settings  # noqa: E402


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def run(n: int) -> None:
    c = TestClient(main.app)
    t = c.post("/v1/admin/tenants", json={"name": f"bench-{time.time()}", "mode": "live"},
               headers={"X-Admin-Token": settings.admin_token}).json()
    auth = {"Authorization": f"Bearer {t['api_key']['key']}"}
    e2e, server = [], []
    for i in range(n):
        body = {"transaction": {
            "transaction_id": f"BENCH-{i}", "amount": 10_000 + (i % 50) * 7_500,
            "timestamp": "2026-10-07T14:00:00+01:00",
            "sender_account": f"ACC-{i % 200}", "recipient_account": f"BEN-{i % 900}",
            "channel": ("transfer", "ussd", "pos")[i % 3], "device_id": f"dev-{i % 250}",
        }}
        t0 = time.perf_counter()
        r = c.post("/v1/decisions", json=body, headers=auth)
        e2e.append((time.perf_counter() - t0) * 1000)
        r.raise_for_status()
        server.append(r.json()["latency_ms"])
    print(f"database={settings.database_url.split(':', 1)[0]} redis={'on' if settings.redis_url else 'off'} n={n}")
    for name, xs in (("end-to-end", e2e), ("server", server)):
        print(f"  {name:<11} p50={pct(xs, .5):6.2f}ms  p95={pct(xs, .95):6.2f}ms  p99={pct(xs, .99):6.2f}ms")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 500)
