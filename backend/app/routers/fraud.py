from fastapi import APIRouter
from app.models.schemas import (
    FraudAnalysisRequest, FraudSignalOut, RegulatoryFilingOut, CaseOutput,
)
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score
from app.core.feature_store import compute_behavioral_deviation, update_user_profile
from app.core.fraud_graph import analyze_graph_risk, record_transaction_edge
from app.core.decision_engine import apply_decision_engine, drift_monitor, feedback_store
from app.core.compliance import get_required_filings, AuditLogEntry, scrub_pii_for_llm
from app.core.llm_factory import get_llm_with_fallback
from app.core.prompts import FRAUD_SYSTEM_PROMPT
from app.core.config import settings
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel
import json, uuid

router = APIRouter(prefix="/api/fraud", tags=["fraud"])


@router.post("/analyze")
async def analyze_fraud(req: FraudAnalysisRequest):
    provider = req.provider or settings.default_llm_provider
    tx = req.transaction

    # ── LAYER 1: Nigerian heuristic signal engine ─────────────────────────
    heuristic = evaluate_transaction(
        amount=tx.amount, channel=tx.channel,
        hour_of_day=tx.timestamp.hour, day_of_week=tx.timestamp.weekday(),
        is_new_recipient=tx.is_new_recipient, is_new_device=tx.is_new_device,
        device_changed_hours_ago=tx.device_changed_hours_ago,
        sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
        transactions_last_hour=tx.transactions_last_hour,
        bvn_verified=tx.bvn_verified, nin_bvn_match=tx.nin_bvn_match,
        narration=tx.narration,
        is_post_loan_disbursement=tx.is_post_loan_disbursement,
        is_agent_terminal=tx.is_agent_terminal,
        agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
        is_pos=tx.is_pos,
        recent_outbound_ngn=tx.recent_outbound_ngn,
        recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
    )
    triggered_names = [s.name for s in heuristic.triggered_signals]

    # ── LAYER 2: Bayesian scorer ──────────────────────────────────────────
    bayes = bayesian_fraud_score(triggered_names)

    # ── LAYER 3: Behavioral deviation (feature store) ─────────────────────
    behavioral = compute_behavioral_deviation(
        user_id=tx.sender_account,
        amount=tx.amount,
        channel=tx.channel,
        device_fingerprint=tx.device_changed_hours_ago and str(tx.device_changed_hours_ago),
        beneficiary_account=tx.recipient_account,
        hour_of_day=tx.timestamp.hour,
        location=getattr(tx, "location", None),
    )

    # ── LAYER 4: Graph risk ───────────────────────────────────────────────
    graph = analyze_graph_risk(
        sender_account=tx.sender_account,
        recipient_account=tx.recipient_account,
        device_fingerprint=str(tx.device_changed_hours_ago) if tx.device_changed_hours_ago else None,
        amount=tx.amount,
    )
    record_transaction_edge(tx.sender_account, tx.recipient_account, tx.amount)

    # ── LAYER 5: Multi-layer decision engine ──────────────────────────────
    decision = apply_decision_engine(
        bayesian_score=bayes.risk_score,
        bayesian_signals=triggered_names,
        behavioral_score=behavioral["behavioral_deviation_score"],
        graph_score=graph["graph_risk_score"],
        amount=tx.amount,
        graph_patterns=graph["patterns_detected"],
    )

    # Record to drift monitor
    drift_monitor.record_decision(
        composite_score=decision.composite_score,
        signals=triggered_names,
        risk_level=decision.risk_level,
        amount=tx.amount,
    )

    # ── Regulatory filings ────────────────────────────────────────────────
    all_signal_names = triggered_names + [p.get("type","") for p in graph["patterns_detected"]]
    filings = get_required_filings(
        risk_level=decision.risk_level,
        amount_ngn=tx.amount,
        signal_names=all_signal_names,
    )

    # ── LLM narrative (PII scrubbed, Groq with fallback) ──────────────────
    safe_ctx = scrub_pii_for_llm({
        "amount_ngn": tx.amount, "channel": tx.channel,
        "hour": tx.timestamp.hour, "narration": tx.narration,
        "composite_score": decision.composite_score,
        "bayesian_score": bayes.risk_score,
        "behavioral_score": behavioral["behavioral_deviation_score"],
        "graph_score": graph["graph_risk_score"],
        "hard_override": decision.hard_override,
        "signals": triggered_names,
        "graph_patterns": [p["type"] for p in graph["patterns_detected"]],
        "cbn_references": bayes.cbn_references,
    })
    llm = get_llm_with_fallback(provider=provider)
    llm_resp = llm.invoke([
        SystemMessage(content=FRAUD_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Multi-layer fraud analysis result: {json.dumps(safe_ctx)}\n\n"
            "Write a 3-sentence compliance-ready explanation for a Nigerian fintech compliance officer. "
            "Mention the composite score breakdown (Bayesian + behavioral + graph). "
            "Cite specific CBN circulars. State the recommended action clearly."
        )),
    ])

    # ── Audit log ─────────────────────────────────────────────────────────
    audit = AuditLogEntry(
        event_type="fraud_analysis",
        transaction_id=tx.transaction_id,
        ai_decision=decision.risk_level,
        risk_score=decision.composite_score,
        signals_triggered=triggered_names,
        cbn_references=bayes.cbn_references,
        llm_provider=provider,
        human_review_required=decision.decision in ("review_queue", "escalate", "freeze_and_str"),
        data_retention_expires=(datetime.now(timezone.utc) + timedelta(days=365*5)).isoformat(),
    )

    return {
        "case_id":           str(uuid.uuid4())[:12],
        "transaction_id":    tx.transaction_id,
        "composite_score":   decision.composite_score,
        "risk_level":        decision.risk_level,
        "decision":          decision.decision,
        "action":            decision.action,
        "hard_override":     decision.hard_override,
        "override_reason":   decision.override_reason,
        "layer_breakdown":   decision.layer_breakdown,
        "analyst_notes":     decision.analyst_notes,
        "top_3_signals":     bayes.top_3_signals,
        "behavioral_deviation": behavioral,
        "graph_risk":        graph,
        "regulatory_filings": [
            {"filing_type": f.filing_type, "deadline": f.deadline_description,
             "regulatory_body": f.regulatory_body, "urgency_hours": f.urgency_hours}
            for f in filings
        ],
        "llm_narrative":     llm_resp.content.strip(),
        "audit_log_id":      audit.audit_id,
        "provider_used":     provider,
        "created_at":        datetime.now(timezone.utc).isoformat(),
    }


# ── Feedback endpoint (analyst-in-the-loop) ───────────────────────────────────
class FeedbackRequest(BaseModel):
    transaction_id: str
    audit_id: str
    outcome: Literal["fraud_confirmed", "fraud_rejected", "false_positive", "chargeback_confirmed"]
    analyst_id: str = "system"
    notes: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Analyst submits outcome — feeds back into drift monitor and signal accuracy."""
    entry = feedback_store.record(
        transaction_id=req.transaction_id,
        audit_id=req.audit_id,
        outcome=req.outcome,
        analyst_id=req.analyst_id,
        notes=req.notes,
    )
    drift_monitor.record_feedback(req.outcome)
    return {"status": "recorded", "entry": entry, "feedback_summary": feedback_store.summary()}


# ── Drift monitoring endpoint ─────────────────────────────────────────────────
@router.get("/drift")
async def get_drift_report():
    """Get signal drift and fraud pattern change detection report."""
    return drift_monitor.get_drift_report()


# ── Event stream endpoint ─────────────────────────────────────────────────────
@router.post("/events/publish")
async def publish_event(req: FraudAnalysisRequest):
    """Publish transaction to event stream for async processing."""
    from app.core.event_stream import publish_transaction_event, get_queue_stats
    event_id = await publish_transaction_event(req.transaction)
    return {"event_id": event_id, "status": "queued", "queue_stats": get_queue_stats()}


@router.get("/events/stats")
async def event_stream_stats():
    from app.core.event_stream import get_queue_stats
    return get_queue_stats()
