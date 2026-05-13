from fastapi import APIRouter
from app.models.schemas import LoanEligibilityRequest, LoanEligibilityResponse
from app.core.compliance import AuditLogEntry, scrub_pii_for_llm
from app.core.llm_factory import get_llm
from app.core.prompts import LOAN_SYSTEM_PROMPT
from app.core.config import settings
from langchain_core.messages import HumanMessage, SystemMessage
from app.tools.fintech_tools import cbn_loan_eligibility
import json

router = APIRouter(prefix="/api/loans", tags=["loans"])


@router.post("/eligibility", response_model=LoanEligibilityResponse)
async def loan_eligibility(req: LoanEligibilityRequest):
    provider = req.provider or settings.default_llm_provider

    # Run heuristic engine
    result_json = cbn_loan_eligibility.invoke({
        "monthly_income_ngn": req.monthly_income_ngn,
        "employment_status": req.employment_status,
        "bvn_verified": req.bvn_verified,
        "nin_verified": req.nin_verified,
        "account_tier": req.account_tier,
        "credit_bureau_score": req.credit_bureau_score,
        "existing_loan_count": req.existing_loan_count,
        "requested_amount_ngn": req.requested_amount_ngn,
        "tenor_months": req.tenor_months,
        "loan_purpose": req.loan_purpose,
    })
    data = json.loads(result_json)

    audit = AuditLogEntry(
        event_type="loan_decision",
        ai_decision=data["decision"],
        llm_provider=provider,
        human_review_required=not data["eligible"],
        cbn_references=data.get("cbn_references", []),
    )

    return LoanEligibilityResponse(
        eligible=data["eligible"],
        decision=data["decision"],
        approved_amount_ngn=data.get("approved_amount_ngn"),
        monthly_rate_pct=data.get("monthly_rate_pct"),
        tenor_months=data["tenor_months"],
        estimated_monthly_repayment_ngn=data.get("estimated_monthly_repayment_ngn"),
        reasons=data.get("reasons", []),
        warnings=data.get("warnings", []),
        cbn_references=data.get("cbn_references", []),
        audit_id=audit.audit_id,
        provider_used=provider,
    )
