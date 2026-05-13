from langchain_core.tools import tool
from app.core.nigeria_intelligence import evaluate_transaction
import json


@tool
def nigerian_fraud_score(
    amount: float,
    channel: str,
    hour_of_day: int,
    day_of_week: int,
    is_new_recipient: bool,
    is_new_device: bool,
    device_changed_hours_ago: int,
    sim_replaced_hours_ago: int,
    transactions_last_hour: int,
    bvn_verified: bool,
    nin_bvn_match: bool,
    narration: str,
    is_post_loan_disbursement: bool,
    is_agent_terminal: bool,
    agent_tx_count_last_hour: int,
    is_pos: bool,
    recent_outbound_ngn: float,
    recent_inbound_from_same_ngn: float,
) -> str:
    """
    Score a Nigerian fintech transaction using local fraud intelligence signals.
    References CBN circulars, EFCC advisories, and NFIU guidelines.
    Returns risk score, triggered signals, CBN references, and recommended action.
    """
    result = evaluate_transaction(
        amount=amount, channel=channel, hour_of_day=hour_of_day,
        day_of_week=day_of_week, is_new_recipient=is_new_recipient,
        is_new_device=is_new_device, device_changed_hours_ago=device_changed_hours_ago,
        sim_replaced_hours_ago=sim_replaced_hours_ago,
        transactions_last_hour=transactions_last_hour,
        bvn_verified=bvn_verified, nin_bvn_match=nin_bvn_match,
        narration=narration, is_post_loan_disbursement=is_post_loan_disbursement,
        is_agent_terminal=is_agent_terminal,
        agent_tx_count_last_hour=agent_tx_count_last_hour,
        is_pos=is_pos, recent_outbound_ngn=recent_outbound_ngn,
        recent_inbound_from_same_ngn=recent_inbound_from_same_ngn,
    )
    return json.dumps(result.to_dict())


@tool
def cbn_loan_eligibility(
    monthly_income_ngn: float,
    employment_status: str,
    bvn_verified: bool,
    nin_verified: bool,
    account_tier: str,
    credit_bureau_score: int,
    existing_loan_count: int,
    requested_amount_ngn: float,
    tenor_months: int,
    loan_purpose: str = "",
) -> str:
    """
    Assess loan eligibility under CBN digital lending guidelines.
    Applies CRC/FirstCentral score bands, DTI limits, and KYC tier restrictions.
    Returns decision, approved amount, rate, repayment, and CBN references.
    """
    eligible = True
    reasons = []
    warnings = []
    cbn_refs = []

    # BVN — mandatory per CBN Circular BPS/DIR/2020/004
    if not bvn_verified:
        eligible = False
        reasons.append("BVN not verified — mandatory for all accounts (CBN Circular BPS/DIR/2020/004)")
        cbn_refs.append("CBN Circular BPS/DIR/2020/004")

    # NIN linkage — CBN Circular BPS/DIR/GEN/CIR/03/002
    if not nin_verified:
        eligible = False
        reasons.append("NIN not linked — required since March 2024 (CBN Circular BPS/DIR/GEN/CIR/03/002)")
        cbn_refs.append("CBN Circular BPS/DIR/GEN/CIR/03/002")

    # Tier 1 accounts — very limited loan access
    if account_tier == "tier1":
        max_loan = 50_000
        if requested_amount_ngn > max_loan:
            eligible = False
            reasons.append(f"Tier 1 accounts capped at ₦50,000 loans — upgrade KYC to Tier 2 (CBN KYC Framework 2023)")
            cbn_refs.append("CBN KYC Framework 2023")

    # Bureau score bands (CRC/FirstCentral)
    if credit_bureau_score < 400:
        eligible = False
        reasons.append(f"Credit bureau score {credit_bureau_score} is below minimum threshold of 400")
    elif credit_bureau_score < 550:
        warnings.append(f"Score {credit_bureau_score} is below-average — higher interest rate applies")

    # Debt-to-Income: CBN Digital Lending Guidelines — max 33% DTI
    monthly_repayment = requested_amount_ngn / tenor_months if tenor_months > 0 else requested_amount_ngn
    dti = monthly_repayment / monthly_income_ngn if monthly_income_ngn > 0 else 1
    if dti > 0.33:
        eligible = False
        reasons.append(f"DTI ratio {dti:.0%} exceeds CBN cap of 33% (CBN Digital Lending Guidelines 2023)")
        cbn_refs.append("CBN Digital Lending Guidelines 2023")

    # Employment
    if employment_status == "unemployed":
        eligible = False
        reasons.append("Unemployed applicants require collateral or guarantor (CBN MFB Guidelines)")
        cbn_refs.append("CBN Microfinance Bank Regulatory Framework")

    # Concurrent loans
    if existing_loan_count >= 3:
        eligible = False
        reasons.append("Maximum 2 concurrent unsecured digital loans per CBN FCCPC guidelines")
        cbn_refs.append("FCCPC Digital Money Lender Guidelines 2022")
    elif existing_loan_count == 2:
        warnings.append("Customer has 2 active loans — stricter terms apply")

    # Loan purpose flags
    if any(kw in loan_purpose.lower() for kw in ["crypto", "forex", "bet", "gambling"]):
        eligible = False
        reasons.append("Loan purpose not eligible under CBN responsible lending guidelines")

    # Calculate terms
    approved_amount = None
    monthly_rate = None
    repayment = None

    if eligible:
        max_eligible = min(monthly_income_ngn * 2, requested_amount_ngn)
        approved_amount = max_eligible
        base_rate = 3.5
        if credit_bureau_score < 550:
            base_rate += 1.5
        if employment_status == "self_employed":
            base_rate += 0.5
        monthly_rate = round(base_rate, 2)
        repayment = round(approved_amount * (monthly_rate / 100) / (1 - (1 + monthly_rate / 100) ** -tenor_months), 2)

    return json.dumps({
        "eligible": eligible,
        "decision": "APPROVED" if eligible else "DECLINED",
        "approved_amount_ngn": approved_amount,
        "monthly_rate_pct": monthly_rate,
        "estimated_monthly_repayment_ngn": repayment,
        "tenor_months": tenor_months,
        "reasons": reasons,
        "warnings": warnings,
        "cbn_references": list(set(cbn_refs)),
    })


@tool
def naija_spending_insights(
    total_debits_ngn: float,
    total_credits_ngn: float,
    categories: dict,
    period_days: int,
    transaction_count: int,
) -> str:
    """
    Generate spending insights calibrated for Nigerian economic context.
    Accounts for inflation, fuel costs post-subsidy removal, local cost-of-living.
    Returns savings rate, category breakdown, anomalies, and practical tips.
    """
    net = total_credits_ngn - total_debits_ngn
    savings_rate = (net / total_credits_ngn * 100) if total_credits_ngn > 0 else 0
    daily_spend = total_debits_ngn / period_days if period_days > 0 else 0

    sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_cats[:3]

    tips = []
    # Nigerian-specific tips
    if categories.get("transport", 0) > total_debits_ngn * 0.20:
        tips.append("Transport is over 20% of spend — consider a ride-sharing monthly plan or carpooling")
    if categories.get("airtime", 0) + categories.get("data", 0) > 8000:
        tips.append("High telecom spend — MTN/Airtel data bundles can save up to 40% vs pay-as-you-go")
    if savings_rate < 10:
        tips.append(f"Savings rate is {savings_rate:.1f}% — target at least 20%. Lock ₦{daily_spend * 6:,.0f}/week in Piggyvest or Cowrywise")
    if savings_rate > 30:
        tips.append("Excellent savings rate! Consider a dollar-denominated instrument (Risevest, Bamboo) to hedge against Naira depreciation")
    if categories.get("food", 0) > total_debits_ngn * 0.35:
        tips.append("Food is >35% of budget — bulk buying at Makro or Mile 12 market can reduce costs by 25–30%")

    anomalies = []
    if daily_spend > 50_000:
        anomalies.append(f"Above-average daily spend of ₦{daily_spend:,.0f} — review discretionary items")
    if categories.get("transfers", 0) > total_debits_ngn * 0.5:
        anomalies.append("More than half of outflows are peer transfers — verify no unauthorized transfers")

    return json.dumps({
        "net_flow_ngn": round(net, 2),
        "savings_rate_pct": round(savings_rate, 1),
        "avg_daily_spend_ngn": round(daily_spend, 2),
        "top_categories": [
            {"category": c, "amount_ngn": a, "pct_of_spend": round(a / total_debits_ngn * 100, 1)}
            for c, a in top3
        ],
        "anomalies": anomalies,
        "tips": tips,
        "financial_health": "Strong" if savings_rate > 25 else "Fair" if savings_rate > 10 else "Needs Attention",
    })


AGENT_TOOLS = [nigerian_fraud_score, cbn_loan_eligibility, naija_spending_insights]
