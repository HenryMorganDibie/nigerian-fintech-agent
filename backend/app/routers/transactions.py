from fastapi import APIRouter
from app.models.schemas import TransactionInsightsRequest, TransactionInsightsResponse
from app.core.llm_factory import get_llm
from app.core.prompts import TRANSACTION_SYSTEM_PROMPT
from app.core.config import settings
from langchain_core.messages import HumanMessage, SystemMessage
import json

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("/insights", response_model=TransactionInsightsResponse)
async def transaction_insights(req: TransactionInsightsRequest):
    provider = req.provider or settings.default_llm_provider
    llm = get_llm(provider=provider)

    debits = [t for t in req.transactions if t.type == "debit"]
    credits = [t for t in req.transactions if t.type == "credit"]
    total_out = sum(t.amount for t in debits)
    total_in = sum(t.amount for t in credits)
    net = total_in - total_out
    savings_rate = round((net / total_in * 100) if total_in > 0 else 0, 1)

    tx_lines = "\n".join(
        f"- {t.date} | {t.type.upper()} | ₦{t.amount:,.2f} | {t.description or t.merchant or 'N/A'} | {t.category or 'Uncategorized'}"
        for t in req.transactions[:60]
    )

    prompt = (
        f"Period: {req.period_days} days | Inflow: ₦{total_in:,.2f} | Outflow: ₦{total_out:,.2f} | "
        f"Net: ₦{net:,.2f} | Savings rate: {savings_rate}%\n\n"
        f"Transactions:\n{tx_lines}\n\n"
        "Return JSON only — no markdown:\n"
        '{"top_categories": [{"category": str, "amount": float, "count": int}], '
        '"anomalies": [str], "insights": "2-3 paragraph plain-language analysis for a Nigerian customer"}'
    )

    response = llm.invoke([SystemMessage(content=TRANSACTION_SYSTEM_PROMPT), HumanMessage(content=prompt)])
    raw = response.content.strip().replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
    except Exception:
        data = {"top_categories": [], "anomalies": ["Could not parse"], "insights": "Please try again."}

    return TransactionInsightsResponse(
        total_inflow=total_in, total_outflow=total_out, net_flow=net,
        savings_rate_pct=savings_rate,
        top_categories=data.get("top_categories", []),
        anomalies=data.get("anomalies", []),
        insights=data.get("insights", ""),
        provider_used=provider,
    )
