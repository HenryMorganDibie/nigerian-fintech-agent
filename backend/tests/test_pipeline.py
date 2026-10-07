from datetime import datetime, timezone

from app.core.feature_store import get_user_profile
from app.core.fraud_graph import flag_account
from app.core.pipeline import run_pipeline, to_wat
from app.models.schemas import Transaction

from tests.conftest import tx


def T(**kw) -> Transaction:
    return Transaction(**tx(**kw))


def test_utc_timestamps_are_evaluated_in_wat():
    assert to_wat(datetime(2026, 10, 7, 0, 30, tzinfo=timezone.utc)).hour == 1
    assert to_wat(datetime(2026, 10, 7, 9, 0)).hour == 9   # naive = already WAT


def test_ussd_after_hours_window_is_wat_not_utc(client):
    # 00:30 UTC is 01:30 WAT: inside the 01:00–05:00 window.
    inside = run_pipeline(T(channel="ussd", timestamp="2026-10-07T00:30:00Z"), "t")
    assert "USSD_AFTER_HOURS" in {s.name for s in inside.signals.triggered}
    # 05:00 UTC is 06:00 WAT: outside it (the old UTC logic flagged this).
    outside = run_pipeline(T(transaction_id="TX-2", channel="ussd", timestamp="2026-10-07T05:00:00Z"), "t")
    assert "USSD_AFTER_HOURS" not in {s.name for s in outside.signals.triggered}


def test_only_allowed_transactions_extend_the_customer_baseline(client):
    run_pipeline(T(), "t")
    assert get_user_profile("0123456789", "t")["total_tx_count"] == 1
    blocked = run_pipeline(T(transaction_id="TX-2", channel="ussd", amount=85_000, sim_replaced_hours_ago=3), "t")
    assert blocked.action == "block"
    assert get_user_profile("0123456789", "t")["total_tx_count"] == 1


def test_behavioral_baselines_are_tenant_scoped(client):
    run_pipeline(T(), "tenant-a")
    assert get_user_profile("0123456789", "tenant-a")["total_tx_count"] == 1
    assert get_user_profile("0123456789", "tenant-b")["total_tx_count"] == 0


def test_flagged_accounts_do_not_leak_across_tenants(client):
    flag_account("9876543210", tenant_id="tenant-a")
    a = run_pipeline(T(), "tenant-a")
    b = run_pipeline(T(), "tenant-b")
    assert any(p["type"] == "FLAGGED_RECIPIENT" for p in a.graph["patterns_detected"])
    assert b.graph["patterns_detected"] == []


def test_device_id_drives_shared_device_detection(client):
    for i in range(3):
        run_pipeline(T(transaction_id=f"TX-{i}", sender_account=f"ACC-{i}", device_id="dev-farm"), "t")
    r = run_pipeline(T(transaction_id="TX-9", sender_account="ACC-9", device_id="dev-farm"), "t")
    assert any(p["type"] == "SHARED_DEVICE" for p in r.graph["patterns_detected"])
