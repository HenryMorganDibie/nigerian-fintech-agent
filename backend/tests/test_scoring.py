from app.core.compliance import get_required_filings
from app.core.decision_engine import apply_decision
from app.core.scoring_engine import compute_signal_score

DEFAULTS = dict(
    amount=15_000, channel="transfer", hour_of_day=14, day_of_week=2,
    is_new_recipient=False, is_new_device=False, device_changed_hours_ago=None,
    sim_replaced_hours_ago=None, transactions_last_hour=0, micro_tx_last_10min=0,
    bvn_verified=True, nin_bvn_match=True, narration="", is_post_loan_disbursement=False,
    is_agent_terminal=False, agent_tx_count_last_hour=0, is_pos=False, is_pos_reversal=False,
    recent_outbound_ngn=0, recent_inbound_from_same_ngn=0, account_age_days=365,
    new_beneficiaries_last_hour=0,
)


def names(**kw):
    return {s.name for s in compute_signal_score(**{**DEFAULTS, **kw}).triggered}


def test_clean_transaction_triggers_nothing_and_auto_approves():
    sig = compute_signal_score(**DEFAULTS)
    assert sig.triggered == []
    d = apply_decision(sig.score, [], 0, 0, 15_000)
    assert d.decision == "auto_approve"


def test_structuring_band_sits_just_below_individual_ctr_threshold():
    assert "CBN_STRUCTURING" in names(amount=4_985_000)
    assert "CBN_STRUCTURING" in names(amount=4_500_000)
    assert "CBN_STRUCTURING" not in names(amount=4_499_999)
    assert "CBN_STRUCTURING" not in names(amount=5_000_000)
    # The old ₦900k–₦999k band contradicted the ₦5M CTR threshold used for filings.
    assert "CBN_STRUCTURING" not in names(amount=998_500)


def test_structuring_band_uses_corporate_threshold_for_corporates():
    assert "CBN_STRUCTURING" in names(amount=9_800_000, customer_type="corporate")
    assert "CBN_STRUCTURING" not in names(amount=4_985_000, customer_type="corporate")


def test_split_pattern_needs_several_sub_threshold_transfers_crossing_ctr():
    assert "SPLIT_TRANSACTION_PATTERN" in names(amount=2_000_000, transactions_last_hour=3)
    assert "SPLIT_TRANSACTION_PATTERN" not in names(amount=300_000, transactions_last_hour=3)
    # A single transfer above the threshold is a plain CTR, not a split.
    assert "SPLIT_TRANSACTION_PATTERN" not in names(amount=6_000_000, transactions_last_hour=3)
    assert "SPLIT_TRANSACTION_PATTERN" not in names(amount=6_000_000, transactions_last_hour=1)


def test_sim_swap_ussd_forces_critical_via_hard_override():
    sig = compute_signal_score(**{**DEFAULTS, "channel": "ussd", "amount": 85_000, "sim_replaced_hours_ago": 6})
    d = apply_decision(sig.score, [s.name for s in sig.triggered], 0, 0, 85_000)
    assert d.hard_override and d.override_reason == "SIM_SWAP_USSD"
    assert d.decision == "freeze_and_str"


def test_every_triggered_signal_carries_evidence():
    sig = compute_signal_score(**{**DEFAULTS, "nin_bvn_match": False, "amount": 250_000,
                                  "bvn_verified": False, "narration": "guaranteed forex roi"})
    assert len(sig.triggered) >= 3
    assert all(s.evidence for s in sig.triggered)


def test_ctr_filing_follows_customer_type():
    ind = {f.filing_type for f in get_required_filings("low", 6_000_000, [], customer_type="individual")}
    corp = {f.filing_type for f in get_required_filings("low", 6_000_000, [], customer_type="corporate")}
    assert "CTR" in ind
    assert "CTR" not in corp


def test_str_filing_has_no_monetary_floor():
    filings = {f.filing_type for f in get_required_filings("high", 1_000, ["SCAM_KEYWORDS_NARRATION"])}
    assert "STR" in filings
