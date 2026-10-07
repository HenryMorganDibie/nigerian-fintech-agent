"""
Deterministic scoring pipeline
================================
Signals → behavioural deviation → graph risk → decision → regulatory filings.

No network calls and no LLM on this path: it is what runs inside a payment
authorisation, so it must be fast, reproducible and auditable. LLM narratives
are generated separately, on demand, from the stored result.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.compliance import get_required_filings
from app.core.decision_engine import FinalDecision, apply_decision
from app.core.feature_store import compute_behavioral_deviation, update_user_profile
from app.core.fraud_graph import analyze_graph_risk, record_transaction_edge
from app.core.scoring_engine import SignalScore, compute_signal_score
from app.models.schemas import Transaction

# West Africa Time is UTC+1 all year (no DST), so a fixed offset is exact.
WAT = timezone(timedelta(hours=1))

# Internal decision tier → action a payment system can act on.
ACTION_FOR_DECISION = {
    "auto_approve":   "allow",
    "review_queue":   "review",
    "escalate":       "hold",
    "freeze_and_str": "block",
}


def to_wat(ts: datetime) -> datetime:
    """Naive timestamps are taken to already be in WAT; aware ones are converted."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=WAT)
    return ts.astimezone(WAT)


@dataclass
class PipelineResult:
    signals: SignalScore
    behavioral: dict
    graph: dict
    decision: FinalDecision
    filings: list
    local_time: datetime

    @property
    def action(self) -> str:
        return ACTION_FOR_DECISION[self.decision.decision]


def run_pipeline(tx: Transaction, tenant_id: str = "demo") -> PipelineResult:
    local = to_wat(tx.timestamp)

    sig = compute_signal_score(
        amount=tx.amount, channel=tx.channel,
        hour_of_day=local.hour, day_of_week=local.weekday(),
        is_new_recipient=tx.is_new_recipient, is_new_device=tx.is_new_device,
        device_changed_hours_ago=tx.device_changed_hours_ago,
        sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
        transactions_last_hour=tx.transactions_last_hour,
        micro_tx_last_10min=tx.micro_tx_last_10min,
        bvn_verified=tx.bvn_verified, nin_bvn_match=tx.nin_bvn_match,
        narration=tx.narration,
        is_post_loan_disbursement=tx.is_post_loan_disbursement,
        is_agent_terminal=tx.is_agent_terminal,
        agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
        is_pos=tx.is_pos,
        is_pos_reversal=tx.is_pos_reversal,
        recent_outbound_ngn=tx.recent_outbound_ngn,
        recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
        account_age_days=tx.account_age_days,
        new_beneficiaries_last_hour=tx.new_beneficiaries_last_hour,
        customer_type=tx.customer_type,
    )

    behavioral = compute_behavioral_deviation(
        user_id=tx.sender_account, amount=tx.amount, channel=tx.channel,
        device_fingerprint=tx.device_id,
        beneficiary_account=tx.recipient_account,
        hour_of_day=local.hour,
        tenant_id=tenant_id,
    )

    # Graph risk is read before this edge is recorded, so a transfer is not
    # judged against itself.
    graph = analyze_graph_risk(
        sender_account=tx.sender_account, recipient_account=tx.recipient_account,
        device_fingerprint=tx.device_id, amount=tx.amount, tenant_id=tenant_id,
    )
    record_transaction_edge(tx.sender_account, tx.recipient_account, tx.amount,
                            device_fingerprint=tx.device_id, tenant_id=tenant_id)

    decision = apply_decision(
        signal_score=sig.score,
        signal_names=[s.name for s in sig.triggered],
        behavioral_score=behavioral["behavioral_deviation_score"],
        graph_score=graph["graph_risk_score"],
        amount=tx.amount,
        graph_patterns=graph["patterns_detected"],
    )

    filings = get_required_filings(
        risk_level=decision.risk_level, amount_ngn=tx.amount,
        signal_names=[s.name for s in sig.triggered] + [p.get("type", "") for p in graph["patterns_detected"]],
        customer_type=tx.customer_type,
    )

    result = PipelineResult(sig, behavioral, graph, decision, filings, local)

    # Only transactions the engine itself would allow extend the customer's
    # baseline, so fraud cannot teach the model that fraud is normal.
    if result.action == "allow":
        update_user_profile(
            user_id=tx.sender_account, amount=tx.amount, channel=tx.channel,
            device_fingerprint=tx.device_id, beneficiary_account=tx.recipient_account,
            hour_of_day=local.hour, location=None, timestamp=local.isoformat(),
            tenant_id=tenant_id,
        )
    return result
