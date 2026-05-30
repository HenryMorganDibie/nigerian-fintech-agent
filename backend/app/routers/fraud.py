from fastapi import APIRouter
from app.models.schemas import FraudAnalysisRequest, FraudSignalOut, RegulatoryFilingOut, CaseOutput
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score
from app.core.feature_store import compute_behavioral_deviation, update_user_profile
from app.core.fraud_graph import analyze_graph_risk, record_transaction_edge
from app.core.decision_engine import apply_decision_engine, drift_monitor, feedback_store
from app.core.explainability import build_explainability_report
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

    # ── Layer 1: Nigerian heuristic signals ───────────────────────────────
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

    # ── Layer 2: Bayesian scorer ──────────────────────────────────────────
    bayes = bayesian_fraud_score(triggered_names)

    # ── Layer 3: Behavioral deviation ────────────────────────────────────
    behavioral = compute_behavioral_deviation(
        user_id=tx.sender_account, amount=tx.amount, channel=tx.channel,
        device_fingerprint=str(tx.device_changed_hours_ago) if tx.device_changed_hours_ago else None,
        beneficiary_account=tx.recipient_account,
        hour_of_day=tx.timestamp.hour,
        location=getattr(tx, "location", None),
    )

    # ── Layer 4: Graph risk ───────────────────────────────────────────────
    graph = analyze_graph_risk(
        sender_account=tx.sender_account,
        recipient_account=tx.recipient_account,
        device_fingerprint=str(tx.device_changed_hours_ago) if tx.device_changed_hours_ago else None,
        amount=tx.amount,
    )
    record_transaction_edge(tx.sender_account, tx.recipient_account, tx.amount)

    # ── Layer 5: Decision engine ──────────────────────────────────────────
    decision = apply_decision_engine(
        bayesian_score=bayes.risk_score,
        bayesian_signals=triggered_names,
        behavioral_score=behavioral["behavioral_deviation_score"],
        graph_score=graph["graph_risk_score"],
        amount=tx.amount,
        graph_patterns=graph["patterns_detected"],
    )

    drift_monitor.record_decision(
        composite_score=decision.composite_score,
        signals=triggered_names,
        risk_level=decision.risk_level,
        amount=tx.amount,
    )

    # ── Explainability ────────────────────────────────────────────────────
    explain = build_explainability_report(
        risk_score=decision.composite_score,
        risk_level=decision.risk_level,
        posterior_probability=bayes.posterior_fraud_probability,
        triggered_signals=bayes.signal_contributions,
        top_3_signals=bayes.top_3_signals,
        recommended_action=decision.action,
        hard_override=decision.hard_override,
        behavioral_factors=behavioral.get("factors", []),
        graph_patterns=graph["patterns_detected"],
        amount=tx.amount,
        user_avg_amount=behavioral.get("user_avg_tx_amount", 0),
    )

    # ── Regulatory filings ────────────────────────────────────────────────
    all_signal_names = triggered_names + [p.get("type","") for p in graph["patterns_detected"]]
    filings = get_required_filings(
        risk_level=decision.risk_level,
        amount_ngn=tx.amount,
        signal_names=all_signal_names,
    )

    # ── LLM narrative — only if risk is medium+ (save tokens) ────────────
    llm_narrative = ""
    if decision.risk_level in ("medium", "high", "critical"):
        try:
            safe_ctx = scrub_pii_for_llm({
                "amount_ngn": tx.amount, "channel": tx.channel,
                "hour": tx.timestamp.hour, "narration": tx.narration,
                "composite_score": decision.composite_score,
                "risk_level": decision.risk_level,
                "signals": triggered_names[:3],          # limit tokens
                "cbn_references": bayes.cbn_references[:2],
            })
            llm = get_llm_with_fallback(provider=provider)
            llm_resp = llm.invoke([
                SystemMessage(content=FRAUD_SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Fraud result: {json.dumps(safe_ctx)}\n"
                    "Write ONE sentence for a compliance officer: risk level, main signal, recommended action. "
                    "Cite the CBN circular. Be direct."
                )),
            ])
            llm_narrative = llm_resp.content.strip()
        except Exception as e:
            llm_narrative = f"[LLM narrative unavailable: {str(e)[:60]}]"
    else:
        llm_narrative = explain.summary_sentence

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
        "case_id":             str(uuid.uuid4())[:12],
        "transaction_id":      tx.transaction_id,
        "composite_score":     decision.composite_score,
        "risk_level":          decision.risk_level,
        "decision":            decision.decision,
        "action":              decision.action,
        "hard_override":       decision.hard_override,
        "override_reason":     decision.override_reason,
        "explainability":      explain.to_dict(),
        "layer_breakdown":     decision.layer_breakdown,
        "analyst_notes":       decision.analyst_notes,
        "behavioral_deviation": behavioral,
        "graph_risk":          graph,
        "regulatory_filings":  [
            {"filing_type": f.filing_type, "deadline": f.deadline_description,
             "regulatory_body": f.regulatory_body, "urgency_hours": f.urgency_hours}
            for f in filings
        ],
        "llm_narrative":       llm_narrative,
        "audit_log_id":        audit.audit_id,
        "provider_used":       provider,
        "created_at":          datetime.now(timezone.utc).isoformat(),
    }


class FeedbackRequest(BaseModel):
    transaction_id: str
    audit_id: str
    outcome: Literal["fraud_confirmed", "fraud_rejected", "false_positive", "chargeback_confirmed"]
    analyst_id: str = "system"
    notes: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    entry = feedback_store.record(
        transaction_id=req.transaction_id, audit_id=req.audit_id,
        outcome=req.outcome, analyst_id=req.analyst_id, notes=req.notes,
    )
    drift_monitor.record_feedback(req.outcome)
    return {"status": "recorded", "entry": entry, "feedback_summary": feedback_store.summary()}


@router.get("/drift")
async def get_drift_report():
    return drift_monitor.get_drift_report()


@router.post("/events/publish")
async def publish_event(req: FraudAnalysisRequest):
    from app.core.event_stream import publish_transaction_event, get_queue_stats
    event_id = await publish_transaction_event(req.transaction)
    return {"event_id": event_id, "status": "queued", "queue_stats": get_queue_stats()}


@router.get("/events/stats")
async def event_stream_stats():
    from app.core.event_stream import get_queue_stats
    return get_queue_stats()
