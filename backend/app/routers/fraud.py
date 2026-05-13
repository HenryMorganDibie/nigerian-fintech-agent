from fastapi import APIRouter
from app.models.schemas import FraudAnalysisRequest, FraudAnalysisResponse, FraudSignalOut, RegulatoryFilingOut
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.compliance import get_required_filings, AuditLogEntry, scrub_pii_for_llm
from app.core.llm_factory import get_llm
from app.core.prompts import FRAUD_SYSTEM_PROMPT
from app.core.config import settings
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timezone, timedelta
import json

router = APIRouter(prefix="/api/fraud", tags=["fraud"])


@router.post("/analyze", response_model=FraudAnalysisResponse)
async def analyze_fraud(req: FraudAnalysisRequest):
    provider = req.provider or settings.default_llm_provider
    tx = req.transaction

    # 1. Run Nigerian heuristic engine
    evaluation = evaluate_transaction(
        amount=tx.amount,
        channel=tx.channel,
        hour_of_day=tx.timestamp.hour,
        day_of_week=tx.timestamp.weekday(),
        is_new_recipient=tx.is_new_recipient,
        is_new_device=tx.is_new_device,
        device_changed_hours_ago=tx.device_changed_hours_ago,
        sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
        transactions_last_hour=tx.transactions_last_hour,
        bvn_verified=tx.bvn_verified,
        nin_bvn_match=tx.nin_bvn_match,
        narration=tx.narration,
        is_post_loan_disbursement=tx.is_post_loan_disbursement,
        is_agent_terminal=tx.is_agent_terminal,
        agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
        is_pos=tx.is_pos,
        recent_outbound_ngn=tx.recent_outbound_ngn,
        recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
    )

    # 2. Determine regulatory filings
    filings = get_required_filings(
        risk_level=evaluation.risk_level,
        amount_ngn=tx.amount,
        signal_names=[s.name for s in evaluation.triggered_signals],
    )

    # 3. LLM narrative explanation (PII scrubbed)
    safe_context = scrub_pii_for_llm({
        "amount_ngn": tx.amount,
        "channel": tx.channel,
        "hour": tx.timestamp.hour,
        "narration": tx.narration,
        "risk_score": evaluation.total_score,
        "signals": [s.name for s in evaluation.triggered_signals],
        "cbn_references": evaluation.cbn_references,
    })

    llm = get_llm(provider=provider)
    messages = [
        SystemMessage(content=FRAUD_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Transaction context: {json.dumps(safe_context)}\n\n"
            f"Write a 2–3 sentence compliance-ready explanation of this risk assessment "
            f"that a Nigerian fintech compliance officer would understand. "
            f"Mention the specific CBN circulars triggered. Be concise and actionable."
        )),
    ]
    llm_response = llm.invoke(messages)
    explanation = llm_response.content.strip()

    # 4. Audit log
    audit = AuditLogEntry(
        event_type="fraud_analysis",
        transaction_id=tx.transaction_id,
        ai_decision=evaluation.risk_level,
        risk_score=evaluation.total_score,
        signals_triggered=[s.name for s in evaluation.triggered_signals],
        cbn_references=evaluation.cbn_references,
        llm_provider=provider,
        human_review_required=evaluation.risk_level in ("high", "critical"),
        data_retention_expires=(
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + __import__("datetime").timedelta(days=365 * 5)
        ).isoformat(),
    )

    return FraudAnalysisResponse(
        transaction_id=tx.transaction_id,
        risk_score=evaluation.total_score,
        risk_level=evaluation.risk_level,
        recommended_action=evaluation.recommended_action,
        triggered_signals=[
            FraudSignalOut(
                name=s.name, severity=s.severity,
                description=s.description, score_delta=s.score_delta,
                cbn_reference=s.cbn_reference,
            )
            for s in evaluation.triggered_signals
        ],
        cbn_references=evaluation.cbn_references,
        regulatory_filings_required=[
            RegulatoryFilingOut(
                filing_type=f.filing_type,
                deadline_description=f.deadline_description,
                regulatory_body=f.regulatory_body,
                form_reference=f.form_reference,
                urgency_hours=f.urgency_hours,
            )
            for f in filings
        ],
        llm_explanation=explanation,
        audit_id=audit.audit_id,
        provider_used=provider,
    )
