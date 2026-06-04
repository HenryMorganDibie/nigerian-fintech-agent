"""
NaijaFinAI Agent Tools
========================
Tools the LLM can call via bind_tools().

CRITICAL DESIGN PRINCIPLE:
  - Fraud scoring runs on the Bayesian/heuristic engine — NO LLM in the decision path
  - LLM is presentation layer only (narrative explanation)
  - All tool parameters have safe defaults so LLM never passes "unknown"
  - Type coercion handles LLM passing strings instead of ints/bools
"""

from langchain_core.tools import tool
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score
from typing import Optional
import json


def _bool(v, default: bool = False) -> bool:
    """Coerce any LLM value to bool safely."""
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.lower() in ("true", "yes", "1")
    if isinstance(v, (int, float)): return bool(v)
    return default


def _int(v, default: int = 0) -> int:
    """Coerce any LLM value to int safely."""
    if isinstance(v, int): return v
    try: return int(float(str(v)))
    except: return default


def _float(v, default: float = 0.0) -> float:
    """Coerce any LLM value to float safely."""
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v))
    except: return default


@tool
def nigerian_fraud_score(
    amount: float,
    channel: str = "transfer",
    hour_of_day: int = 12,
    day_of_week: int = 1,
    is_new_recipient: bool = False,
    is_new_device: bool = False,
    device_changed_hours_ago: Optional[int] = None,
    sim_replaced_hours_ago: Optional[int] = None,
    transactions_last_hour: int = 0,
    bvn_verified: bool = True,
    nin_bvn_match: bool = True,
    narration: str = "",
    is_post_loan_disbursement: bool = False,
    is_agent_terminal: bool = False,
    agent_tx_count_last_hour: int = 0,
    is_pos: bool = False,
    recent_outbound_ngn: float = 0.0,
    recent_inbound_from_same_ngn: float = 0.0,
) -> str:
    """
    Score a Nigerian fintech transaction for fraud risk using CBN-cited signals and Bayesian scoring.
    All unknown fields default to safe values — only provide what you actually know.

    Args:
        amount: Transaction amount in NGN (required)
        channel: 'transfer', 'ussd', 'pos', 'mobile', 'web', 'agent' (default: transfer)
        hour_of_day: Hour 0-23 (default: 12)
        day_of_week: 0=Monday, 6=Sunday (default: 1)
        is_new_recipient: True if recipient never received from this sender before
        is_new_device: True if device fingerprint is new
        device_changed_hours_ago: Hours since device change (None if unknown)
        sim_replaced_hours_ago: Hours since SIM replacement (None if unknown)
        transactions_last_hour: Count of transactions in last hour (default: 0)
        bvn_verified: Whether BVN is verified (default: True — assume verified unless stated)
        nin_bvn_match: Whether NIN and BVN match (default: True)
        narration: Transaction description/narration
        is_post_loan_disbursement: True if within 30 mins of loan disbursement
        is_agent_terminal: True if OPay/Moniepoint agent terminal
        agent_tx_count_last_hour: Agent transactions in last hour
        is_pos: True if POS transaction
        recent_outbound_ngn: Total outbound in last 24h from same account
        recent_inbound_from_same_ngn: Total inbound from same source in last 24h
    """
    # Type-coerce everything — LLM sometimes passes strings
    safe_hour    = _int(hour_of_day, 12)
    safe_dow     = _int(day_of_week, 1)
    safe_txlh    = _int(transactions_last_hour, 0)
    safe_agtx    = _int(agent_tx_count_last_hour, 0)
    safe_dcha    = _int(device_changed_hours_ago, None) if device_changed_hours_ago is not None else None
    safe_simra   = _int(sim_replaced_hours_ago, None) if sim_replaced_hours_ago is not None else None
    safe_bvn     = _bool(bvn_verified, True)
    safe_nin     = _bool(nin_bvn_match, True)
    safe_newrec  = _bool(is_new_recipient, False)
    safe_newdev  = _bool(is_new_device, False)
    safe_loan    = _bool(is_post_loan_disbursement, False)
    safe_agent   = _bool(is_agent_terminal, False)
    safe_pos     = _bool(is_pos, False)
    safe_out     = _float(recent_outbound_ngn, 0.0)
    safe_in      = _float(recent_inbound_from_same_ngn, 0.0)
    safe_amount  = _float(amount, 0.0)

    # Run heuristic engine
    heuristic = evaluate_transaction(
        amount=safe_amount, channel=str(channel),
        hour_of_day=safe_hour, day_of_week=safe_dow,
        is_new_recipient=safe_newrec, is_new_device=safe_newdev,
        device_changed_hours_ago=safe_dcha,
        sim_replaced_hours_ago=safe_simra,
        transactions_last_hour=safe_txlh,
        bvn_verified=safe_bvn, nin_bvn_match=safe_nin,
        narration=str(narration),
        is_post_loan_disbursement=safe_loan,
        is_agent_terminal=safe_agent,
        agent_tx_count_last_hour=safe_agtx,
        is_pos=safe_pos,
        recent_outbound_ngn=safe_out,
        recent_inbound_from_same_ngn=safe_in,
    )

    # Bayesian scoring on top
    triggered = [s.name for s in heuristic.triggered_signals]
    bayes = bayesian_fraud_score(triggered)

    # Build explainability breakdown
    signal_contributions = []
    for sig in heuristic.triggered_signals:
        bs = next((b for b in bayes.signal_contributions if b["signal"] == sig.name), None)
        signal_contributions.append({
            "signal": sig.name,
            "severity": sig.severity,
            "description": sig.description,
            "score_contribution": bs["contribution"] if bs else sig.score_delta,
            "cbn_reference": sig.cbn_reference,
            "recommended_action": sig.recommended_action,
        })

    return json.dumps({
        "risk_score": bayes.risk_score,
        "posterior_fraud_probability": round(bayes.posterior_fraud_probability, 4),
        "risk_level": bayes.risk_level,
        "recommended_action": bayes.recommended_action,
        "top_3_signals": bayes.top_3_signals,
        "signal_contributions": signal_contributions,
        "cbn_references": bayes.cbn_references,
        "amount_ngn": f"₦{safe_amount:,.2f}",
        "note": "Scoring performed by deterministic Bayesian engine — LLM not involved in risk calculation",
    })


@tool
def cbn_loan_eligibility(
    monthly_income_ngn: float,
    employment_status: str = "employed",
    bvn_verified: bool = True,
    nin_verified: bool = True,
    account_tier: str = "tier2",
    credit_bureau_score: int = 600,
    existing_loan_count: int = 0,
    requested_amount_ngn: float = 100000,
    tenor_months: int = 6,
    loan_purpose: str = "",
) -> str:
    """
    Assess loan eligibility under CBN digital lending guidelines.
    Only call this if the user has provided actual applicant data.
    Do NOT guess values — use what the user explicitly stated.
    """
    eligible = True
    reasons = []
    warnings = []
    cbn_refs = []

    # Type coerce
    income     = _float(monthly_income_ngn, 0)
    score      = _int(credit_bureau_score, 600)
    loans      = _int(existing_loan_count, 0)
    amount     = _float(requested_amount_ngn, 100000)
    tenor      = _int(tenor_months, 6)
    bvn        = _bool(bvn_verified, True)
    nin        = _bool(nin_verified, True)

    if not bvn:
        eligible = False
        reasons.append("BVN not verified — CBN Circular BPS/DIR/2020/004")
        cbn_refs.append("CBN Circular BPS/DIR/2020/004")

    if not nin:
        eligible = False
        reasons.append("NIN not linked — CBN Circular BPS/DIR/GEN/CIR/03/002")
        cbn_refs.append("CBN Circular BPS/DIR/GEN/CIR/03/002")

    if str(account_tier) == "tier1" and amount > 50_000:
        eligible = False
        reasons.append("Tier 1 accounts capped at ₦50,000 loans")
        cbn_refs.append("CBN KYC Framework 2023")

    if score < 400:
        eligible = False
        reasons.append(f"Bureau score {score} below minimum threshold of 400")
    elif score < 550:
        warnings.append(f"Below-average score {score} — higher rate applies")

    monthly_repayment = amount / tenor if tenor > 0 else amount
    dti = monthly_repayment / income if income > 0 else 1
    if dti > 0.33:
        eligible = False
        reasons.append(f"DTI {dti:.0%} exceeds CBN 33% cap — CBN Digital Lending Guidelines 2023")
        cbn_refs.append("CBN Digital Lending Guidelines 2023")

    if str(employment_status) == "unemployed":
        eligible = False
        reasons.append("Unemployed — requires collateral or guarantor")

    if loans >= 3:
        eligible = False
        reasons.append("Exceeds 2 concurrent loan limit — FCCPC Digital Money Lender Guidelines 2022")
        cbn_refs.append("FCCPC Digital Money Lender Guidelines 2022")
    elif loans == 2:
        warnings.append("2 active loans — stricter terms apply")

    if any(kw in str(loan_purpose).lower() for kw in ["crypto", "forex", "bet", "gambling"]):
        eligible = False
        reasons.append("Loan purpose not eligible under CBN responsible lending guidelines")

    approved_amount = None
    monthly_rate = None
    repayment = None
    if eligible and income > 0:
        approved_amount = min(income * 2, amount)
        base_rate = 3.5
        if score < 550: base_rate += 1.5
        if str(employment_status) == "self_employed": base_rate += 0.5
        monthly_rate = round(base_rate, 2)
        r = monthly_rate / 100
        repayment = round(approved_amount * r / (1 - (1 + r) ** -tenor), 2) if tenor > 0 else approved_amount

    return json.dumps({
        "eligible": eligible,
        "decision": "APPROVED" if eligible else "DECLINED",
        "approved_amount_ngn": round(approved_amount, 2) if approved_amount else None,
        "monthly_rate_pct": monthly_rate,
        "estimated_monthly_repayment_ngn": round(repayment, 2) if repayment else None,
        "tenor_months": tenor,
        "debt_to_income_ratio": round(dti, 3),
        "reasons": reasons,
        "warnings": warnings,
        "cbn_references": list(set(cbn_refs)),
    })


@tool
def naija_spending_insights(
    total_debits_ngn: float,
    total_credits_ngn: float,
    categories: str = "{}",
    period_days: int = 30,
    transaction_count: int = 0,
) -> str:
    """
    Generate spending insights for a Nigerian customer.
    categories: JSON string like '{"food": 45000, "transport": 18000, "airtime": 12000}'
    """
    import json as _json
    debits  = _float(total_debits_ngn, 0)
    credits = _float(total_credits_ngn, 0)
    days    = _int(period_days, 30)
    count   = _int(transaction_count, 0)

    try:
        cats = _json.loads(str(categories)) if isinstance(categories, str) else categories
    except Exception:
        cats = {}

    net = credits - debits
    savings_rate = (net / credits * 100) if credits > 0 else 0
    daily_spend = debits / days if days > 0 else 0
    sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:3]

    tips = []
    if savings_rate < 10:
        tips.append(f"Savings rate {savings_rate:.1f}% is below 10% target — set aside ₦{daily_spend*6:,.0f}/week in Piggyvest or Cowrywise")
    if cats.get("airtime", 0) + cats.get("data", 0) > 8000:
        tips.append("High telecom spend — MTN/Airtel data bundles save 30–40% vs pay-as-you-go")
    if cats.get("transport", 0) > debits * 0.20:
        tips.append("Transport is >20% of spend — consider carpooling or a monthly ride plan")
    if savings_rate > 30:
        tips.append("Strong savings — consider Risevest or Bamboo dollar-denominated instruments to hedge Naira depreciation")
    if cats.get("food", 0) > debits * 0.35:
        tips.append("Food >35% of budget — bulk buying at Mile 12 or Makro can reduce costs 25–30%")

    anomalies = []
    if daily_spend > 50_000:
        anomalies.append(f"Above-average daily spend of ₦{daily_spend:,.0f}")
    if cats.get("transfers", 0) > debits * 0.5:
        anomalies.append("More than half of outflows are peer transfers — verify no unauthorized transfers")

    return json.dumps({
        "net_flow_ngn": f"₦{net:,.2f}",
        "savings_rate_pct": round(savings_rate, 1),
        "avg_daily_spend_ngn": f"₦{daily_spend:,.2f}",
        "top_spending_categories": [
            {"category": c, "amount_ngn": f"₦{a:,.2f}", "pct_of_spend": round(a / debits * 100, 1) if debits > 0 else 0}
            for c, a in sorted_cats
        ],
        "anomalies": anomalies,
        "actionable_tips": tips,
        "financial_health": "Strong" if savings_rate > 25 else "Fair" if savings_rate > 10 else "Needs Attention",
        "period_days": days,
        "transaction_count": count,
    })




@tool
def fetch_url_content(url: str) -> str:
    """
    Fetch and read the content of a URL. Use this whenever the user shares a link.
    Works for GitHub repos, news articles, web pages, documentation, and any public URL.
    Do NOT use the fraud scoring tools on a URL — always fetch the URL first.

    Args:
        url: The full URL to fetch (must start with http:// or https://)

    Returns:
        The page title, description, and main text content (truncated to 3000 chars).
    """
    import httpx, re

    if not url.startswith(("http://", "https://")):
        return json.dumps({"error": "Invalid URL — must start with http:// or https://"})

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; NaijaFinAI/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        r = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        r.raise_for_status()

        text = r.text

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "No title"

        # Extract meta description
        desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
                                text, re.IGNORECASE)
        description = desc_match.group(1).strip() if desc_match else ""

        # Strip HTML tags for content
        clean = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        # For GitHub repos, extract README-like content
        if "github.com" in url:
            # Try to get README via GitHub API
            parts = url.rstrip("/").split("github.com/")
            if len(parts) > 1:
                repo_path = parts[1].split("/tree/")[0].split("/blob/")[0]
                api_url = f"https://api.github.com/repos/{repo_path}/readme"
                try:
                    api_r = httpx.get(api_url, headers={**headers, "Accept": "application/vnd.github.v3.raw"}, timeout=8)
                    if api_r.status_code == 200:
                        readme = api_r.text[:3000]
                        return json.dumps({
                            "url": url,
                            "title": title,
                            "type": "github_repository",
                            "readme_content": readme,
                            "note": "README fetched via GitHub API",
                        })
                except Exception:
                    pass

        return json.dumps({
            "url": url,
            "title": title,
            "description": description,
            "content": clean[:3000],
            "content_length": len(clean),
        })

    except httpx.TimeoutException:
        return json.dumps({"error": f"Request timed out fetching {url}"})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP {e.response.status_code} from {url}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def web_search(query: str) -> str:
    """
    Search the web for current information. Use this when:
    - The user asks about recent news, events, or data
    - You need to look up a company, regulation, or topic
    - The user asks a question that requires up-to-date information
    - You need to verify facts about Nigerian fintechs, CBN regulations, or fraud trends

    Args:
        query: The search query string

    Returns:
        Top search results with titles, URLs, and snippets.
    """
    import httpx

    try:
        # Use DuckDuckGo instant answer API (no key needed)
        r = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers={"User-Agent": "NaijaFinAI/1.0"},
            timeout=8,
        )
        data = r.json()

        results = []

        # Abstract (main answer)
        if data.get("AbstractText"):
            results.append({
                "type": "answer",
                "text": data["AbstractText"],
                "source": data.get("AbstractSource", ""),
                "url": data.get("AbstractURL", ""),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "type": "related",
                    "text": topic["Text"],
                    "url": topic.get("FirstURL", ""),
                })

        if not results:
            return json.dumps({
                "query": query,
                "results": [],
                "note": "No results found. Try a more specific query or use fetch_url_content with a direct URL.",
            })

        return json.dumps({"query": query, "results": results})

    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


AGENT_TOOLS = [nigerian_fraud_score, cbn_loan_eligibility, naija_spending_insights,
               fetch_url_content, web_search]
