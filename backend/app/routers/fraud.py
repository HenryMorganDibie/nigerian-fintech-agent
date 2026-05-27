from fastapi import APIRouter
from app.models.schemas import (
    FraudAnalysisRequest, FraudAnalysisResponse,
    FraudSignalOut, RegulatoryFilingOut, CaseOutput,
)
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score
from app.core.compliance import get_required_filings, AuditLogEntry, scrub_pii_for_llm
from app.core.llm_factory import get_llm
from app.core.prompts import FRAUD_SYSTEM_PROMPT
from app.core.config import settings
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timezone, timedelta
import json, uuid

router = APIRouter(prefix="/api/fraud", tags=["fraud"])


@router.post("/analyze", response_model=dict)
async def analyze_fraud(req: FraudAnalysisRequest):
    provider = req.provider or settings.default_llm_provider
    tx = req.transaction

    # 1. Nigerian heuristic engine — triggers signals
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

    # 2. Bayesian scorer — calibrated probability
    triggered_names = [s.name for s in heuristic.triggered_signals]
    bayes = bayesian_fraud_score(triggered_names)

    # 3. Regulatory filings
    filings = get_required_filings(
        risk_level=bayes.risk_level,
        amount_ngn=tx.amount,
        signal_names=triggered_names,
    )

    # 4. LLM narrative (PII scrubbed)
    safe_ctx = scrub_pii_for_llm({
        "amount_ngn": tx.amount, "channel": tx.channel,
        "hour": tx.timestamp.hour, "narration": tx.narration,
        "risk_score": bayes.risk_score,
        "posterior_fraud_probability": bayes.posterior_fraud_probability,
        "signals": triggered_names,
        "cbn_references": bayes.cbn_references,
    })
    llm = get_llm(provider=provider)
    llm_resp = llm.invoke([
        SystemMessage(content=FRAUD_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Transaction: {json.dumps(safe_ctx)}\n\n"
            "Write a 2–3 sentence compliance-ready explanation for a Nigerian fintech "
            "compliance officer. Cite the specific CBN circulars triggered. "
            "Include the Bayesian fraud probability and recommended action."
        )),
    ])

    # 5. Audit log
    audit = AuditLogEntry(
        event_type="fraud_analysis",
        transaction_id=tx.transaction_id,
        ai_decision=bayes.risk_level,
        risk_score=bayes.risk_score,
        signals_triggered=triggered_names,
        cbn_references=bayes.cbn_references,
        llm_provider=provider,
        human_review_required=bayes.risk_level in ("high", "critical"),
        data_retention_expires=(
            datetime.now(timezone.utc) + timedelta(days=365 * 5)
        ).isoformat(),
    )

    # 6. Structured case output
    case = CaseOutput(
        case_id=str(uuid.uuid4())[:12],
        transaction_id=tx.transaction_id,
        risk_score=bayes.risk_score,
        posterior_fraud_probability=bayes.posterior_fraud_probability,
        risk_level=bayes.risk_level,
        top_3_signals=bayes.top_3_signals,
        regulatory_action=bayes.recommended_action,
        filings_required=[
            RegulatoryFilingOut(
                filing_type=f.filing_type,
                deadline_description=f.deadline_description,
                regulatory_body=f.regulatory_body,
                form_reference=f.form_reference,
                urgency_hours=f.urgency_hours,
            ) for f in filings
        ],
        audit_log_id=audit.audit_id,
        llm_narrative=llm_resp.content.strip(),
        provider_used=provider,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    return case.model_dump()
