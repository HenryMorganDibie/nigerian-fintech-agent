from fastapi import APIRouter
from app.core.decision_engine import drift_monitor, feedback_store
from app.core.pipeline import run_pipeline
from app.core.security import customer_ref
from app.core.compliance import AuditLogEntry, scrub_pii_for_llm
from app.core.llm_factory import get_llm_with_fallback
from app.core.llm_router import message_text
from app.core.prompts import FRAUD_SYSTEM_PROMPT
from app.core.config import settings
from app.models.schemas import FraudAnalysisRequest
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Literal
import json, uuid

router = APIRouter(prefix="/api/fraud", tags=["fraud"])


@router.post("/analyze")
async def analyze_fraud(req: FraudAnalysisRequest):
    provider = req.provider or settings.default_llm_provider
    tx = req.transaction

    # ── Deterministic pipeline (shared with /v1/decisions) ────────────────
    result = run_pipeline(tx, tenant_id="demo")
    sig, behavioral, graph, decision, filings = (
        result.signals, result.behavioral, result.graph, result.decision, result.filings)

    drift_monitor.record(decision.composite_score, [s.name for s in sig.triggered], decision.risk_level, tx.amount)

    # ── LLM narrative — receives evidence, not just signal names ──────────
    # The LLM sees a pseudonym, never the raw account number (NDPA data minimisation).
    customer_alias = "CUST-" + customer_ref("demo", tx.sender_account)[:10].upper()
    safe_ctx = scrub_pii_for_llm({
        "customer_id": customer_alias,
        "transaction_id": tx.transaction_id,
        "amount_ngn": tx.amount,
        "channel": tx.channel,
        "hour_of_day": result.local_time.hour,
        "narration": tx.narration,
        "composite_score": decision.composite_score,
        "posterior_fraud_probability_pct": round(sig.posterior_fraud_probability * 100, 1),
        "risk_level": decision.risk_level,
        "behavioral_dominated": decision.behavioral_dominated,
        "hard_override": decision.hard_override,
        "cbn_references": sig.cbn_references,
        # Evidence strings — what actually triggered each signal
        "signal_evidence": sig.evidence_summary,
        # Behavioral evidence
        "behavioral_factors": behavioral.get("factors", []),
        "behavioral_score": behavioral["behavioral_deviation_score"],
        # Graph evidence
        "graph_patterns": [p["type"] + ": " + p["detail"] for p in graph["patterns_detected"]],
        "graph_score": graph["graph_risk_score"],
    })

    llm_resp = None
    try:
        llm_resp = get_llm_with_fallback(provider=provider).invoke([
        SystemMessage(content=FRAUD_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Fraud analysis for customer {customer_alias}, transaction {tx.transaction_id}:\n\n"
            f"{json.dumps(safe_ctx, indent=2)}\n\n"
            "Write the compliance officer report using ONLY the evidence provided above. "
            "Do not add signals or evidence that are not listed. "
            "If signal_evidence says 'No fraud signals triggered', report that clearly and explain "
            "which factors contributed to the low risk score."
        )),
        ])
        narrative = message_text(llm_resp).strip()
        provider_used = llm_resp.response_metadata.get("routed_provider", provider)
    except Exception:
        # Every provider is down or rate-limited: the decision stands on its own,
        # so return the deterministic evidence instead of failing the request.
        narrative = ("Narrative unavailable (all LLM providers are down or rate-limited). "
                     "Deterministic evidence:\n" + sig.evidence_summary)
        provider_used = "rules_only"

    # ── Audit log ─────────────────────────────────────────────────────────
    audit = AuditLogEntry(
        event_type="fraud_analysis", transaction_id=tx.transaction_id,
        ai_decision=decision.risk_level, risk_score=decision.composite_score,
        signals_triggered=[s.name for s in sig.triggered], cbn_references=sig.cbn_references,
        llm_provider=provider_used,
        human_review_required=decision.decision in ("review_queue", "escalate", "freeze_and_str"),
        data_retention_expires=(datetime.now(timezone.utc) + timedelta(days=365*5)).isoformat(),
    )

    return {
        "case_id":                  str(uuid.uuid4())[:12],
        "transaction_id":           tx.transaction_id,
        "customer_id":              tx.sender_account,
        "composite_score":          decision.composite_score,
        "risk_level":               decision.risk_level,
        "decision":                 decision.decision,
        "action":                   decision.action,
        "posterior_fraud_probability": round(sig.posterior_fraud_probability, 4),
        "behavioral_dominated":     decision.behavioral_dominated,
        "hard_override":            decision.hard_override,
        "override_reason":          decision.override_reason,
        "layer_breakdown":          decision.layer_breakdown,
        "analyst_notes":            decision.analyst_notes,
        "top_3_signals":            sig.top_3,           # includes evidence per signal
        "signal_evidence_summary":  sig.evidence_summary, # for display
        "signal_contributions":     sig.contributions,
        "behavioral_deviation":     behavioral,
        "graph_risk":               graph,
        "regulatory_filings":       [
            {"filing_type": f.filing_type, "deadline": f.deadline_description,
             "regulatory_body": f.regulatory_body, "urgency_hours": f.urgency_hours}
            for f in filings
        ],
        "llm_narrative":            narrative,
        "audit_log_id":             audit.audit_id,
        "provider_used":            provider_used,
        "created_at":               datetime.now(timezone.utc).isoformat(),
    }


class FeedbackRequest(BaseModel):
    transaction_id: str
    audit_id: str
    outcome: Literal["fraud_confirmed","fraud_rejected","false_positive","chargeback_confirmed"]
    analyst_id: str = "system"
    notes: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    entry = feedback_store.record(req.transaction_id, req.audit_id, req.outcome, req.analyst_id, req.notes)
    drift_monitor.record_feedback(req.outcome)
    return {"status": "recorded", "entry": entry, "summary": feedback_store.summary()}


@router.get("/drift")
async def get_drift():
    return drift_monitor.report()


@router.post("/events/publish")
async def publish_event(req: FraudAnalysisRequest):
    from app.core.event_stream import publish_transaction_event, get_queue_stats
    event_id = await publish_transaction_event(req.transaction)
    return {"event_id": event_id, "status": "queued", "queue_stats": get_queue_stats()}


@router.get("/events/stats")
async def event_stats():
    from app.core.event_stream import get_queue_stats
    return get_queue_stats()
