from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.core.simulation import get_scenario, list_scenarios
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score
from app.core.feature_store import compute_behavioral_deviation
from app.core.fraud_graph import analyze_graph_risk, record_transaction_edge
from app.core.decision_engine import apply_decision as apply_decision_engine
from app.core.explainability import build_explainability_report
from app.core.compliance import get_required_filings, AuditLogEntry
from app.core.config import settings
from datetime import datetime, timezone, timedelta
import uuid

router = APIRouter(prefix="/api/simulate", tags=["fraud simulation"])


class SimulationRequest(BaseModel):
    scenario_id: str
    provider: Optional[str] = None


@router.get("/scenarios")
async def list_simulation_scenarios():
    return {"scenarios": list_scenarios()}


@router.post("/run")
async def run_simulation(req: SimulationRequest):
    scenario = get_scenario(req.scenario_id)
    if not scenario:
        return {"error": f"Scenario '{req.scenario_id}' not found. Available: {[s['id'] for s in list_scenarios()]}"}

    tx = scenario["transaction"]

    # Run full 4-layer pipeline
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

    triggered = [s.name for s in heuristic.triggered_signals]
    bayes = bayesian_fraud_score(triggered)
    behavioral = compute_behavioral_deviation(
        user_id=tx.sender_account, amount=tx.amount, channel=tx.channel,
        device_fingerprint=None, beneficiary_account=tx.recipient_account,
        hour_of_day=tx.timestamp.hour,
    )
    graph = analyze_graph_risk(tx.sender_account, tx.recipient_account, amount=tx.amount)
    record_transaction_edge(tx.sender_account, tx.recipient_account, tx.amount)
    decision = apply_decision_engine(
        signal_score=bayes.risk_score,
        signal_names=triggered,
        behavioral_score=behavioral["behavioral_deviation_score"],
        graph_score=graph["graph_risk_score"],
        amount=tx.amount,
        graph_patterns=graph["patterns_detected"],
    )

    # Full explainability
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
    )

    filings = get_required_filings(
        risk_level=decision.risk_level, amount_ngn=tx.amount, signal_names=triggered
    )

    audit = AuditLogEntry(
        event_type="simulation",
        transaction_id=tx.transaction_id,
        ai_decision=decision.risk_level,
        risk_score=decision.composite_score,
        signals_triggered=triggered,
        cbn_references=bayes.cbn_references,
        llm_provider="none — deterministic engine",
        human_review_required=decision.decision in ("review_queue", "escalate", "freeze_and_str"),
        data_retention_expires=(datetime.now(timezone.utc) + timedelta(days=365*5)).isoformat(),
    )

    match = decision.risk_level == scenario["expected_risk"]

    return {
        "simulation_id": str(uuid.uuid4())[:10],
        "scenario_id": req.scenario_id,
        "scenario_name": scenario["name"],
        "attack_story": scenario["attack_story"],
        "expected_risk": scenario["expected_risk"],
        "detected_risk": decision.risk_level,
        "detection_correct": match,
        "explainability": explain.to_dict(),
        "layer_breakdown": decision.layer_breakdown,
        "regulatory_filings": [
            {"type": f.filing_type, "deadline": f.deadline_description, "urgency_hours": f.urgency_hours}
            for f in filings
        ],
        "audit_log_id": audit.audit_id,
        "note": "⚡ Scoring by deterministic Bayesian engine — no LLM tokens consumed",
    }
