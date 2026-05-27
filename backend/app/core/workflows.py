"""
Fintech Workflow Demo Scenarios
=================================
One-click end-to-end workflow simulations for:
1. Loan Application Fraud Check
2. Agent Wallet Monitoring
3. Chargeback Investigation

Each scenario runs multiple steps, produces a CaseOutput,
and uses the Bayesian + CBN compliance engines.
"""

from datetime import datetime, timezone
from app.core.nigeria_intelligence import evaluate_transaction
from app.core.bayesian_scorer import bayesian_fraud_score
from app.core.compliance import get_required_filings, AuditLogEntry
from app.core.llm_factory import get_llm
from app.core.config import settings
from langchain_core.messages import HumanMessage, SystemMessage
import uuid, json


SCENARIOS = {
    "loan_application_fraud_check": {
        "name": "Loan Application Fraud Check",
        "description": "Detects first-party fraud on digital loan disbursements — checks BVN/NIN, bureau score, then monitors post-disbursement transaction behaviour.",
    },
    "agent_wallet_monitoring": {
        "name": "Agent Wallet Monitoring",
        "description": "Monitors Moniepoint/OPay/PalmPay agent terminals for mule chain patterns — velocity spikes, round-trip transfers, suspicious narrations.",
    },
    "chargeback_investigation": {
        "name": "Chargeback Investigation",
        "description": "Investigates disputed transactions for authorisation anomalies, device changes, SIM swap indicators, and CBN dispute resolution timeline.",
    },
}


def _make_audit(provider: str, event: str, risk_level: str, signals: list[str], score: int) -> AuditLogEntry:
    from datetime import timedelta
    return AuditLogEntry(
        event_type=event,
        ai_decision=risk_level,
        risk_score=score,
        signals_triggered=signals,
        llm_provider=provider,
        human_review_required=risk_level in ("high", "critical"),
        data_retention_expires=(
            datetime.now(timezone.utc) + timedelta(days=365 * 5)
        ).isoformat(),
    )


def run_workflow(scenario_id: str, provider: str | None = None) -> dict:
    provider = provider or settings.default_llm_provider
    llm = get_llm(provider=provider)
    now = datetime.now(timezone.utc)
    case_id = str(uuid.uuid4())[:12]
    steps = []

    # ── SCENARIO 1: Loan Application Fraud Check ──────────────────────────────
    if scenario_id == "loan_application_fraud_check":
        steps.append({
            "step": 1, "name": "KYC Verification",
            "result": "BVN verified ✅ | NIN verified ✅ | Tier 2 account | Bureau score: 580",
            "status": "pass",
        })
        steps.append({
            "step": 2, "name": "Loan Eligibility Assessment",
            "result": "Income ₦180,000/month | DTI 28% (below 33% CBN cap) | No existing loans | APPROVED ₦250,000 @ 4% monthly",
            "status": "pass",
        })
        # Simulate post-disbursement suspicious behaviour
        heuristic = evaluate_transaction(
            amount=250000, channel="transfer",
            hour_of_day=3, day_of_week=5,
            is_new_recipient=True, is_new_device=False,
            device_changed_hours_ago=None, sim_replaced_hours_ago=None,
            transactions_last_hour=1,
            bvn_verified=True, nin_bvn_match=True,
            narration="",
            is_post_loan_disbursement=True,
            is_agent_terminal=False, agent_tx_count_last_hour=0,
            is_pos=False, recent_outbound_ngn=0, recent_inbound_from_same_ngn=0,
        )
        triggered = [s.name for s in heuristic.triggered_signals]
        bayes = bayesian_fraud_score(triggered)
        steps.append({
            "step": 3, "name": "Post-Disbursement Monitoring",
            "result": f"Full ₦250,000 withdrawn to new recipient within 30 mins at 03:00 WAT | Signal: FIRST_PARTY_FRAUD_LOAN | Risk: {bayes.risk_level.upper()}",
            "status": "alert",
        })
        steps.append({
            "step": 4, "name": "Regulatory Action",
            "result": "Loan flagged for recovery. STR filed with NFIU. Customer callback initiated.",
            "status": "action",
        })
        verdict = "LOAN DISBURSEMENT BLOCKED — First-party fraud detected post-disbursement. STR filed."

    # ── SCENARIO 2: Agent Wallet Monitoring ───────────────────────────────────
    elif scenario_id == "agent_wallet_monitoring":
        steps.append({
            "step": 1, "name": "Agent Profile Check",
            "result": "Terminal ID: AGT-LOS-00847 | Location: Alaba Market, Lagos | Licensed: ✅ | Active 14 months",
            "status": "pass",
        })
        steps.append({
            "step": 2, "name": "Baseline Velocity Check",
            "result": "Normal avg: 8 transactions/hour | Current: 31 transactions/hour ⚠️ | All to unique recipients",
            "status": "alert",
        })
        heuristic = evaluate_transaction(
            amount=45000, channel="agent",
            hour_of_day=14, day_of_week=2,
            is_new_recipient=True, is_new_device=False,
            device_changed_hours_ago=None, sim_replaced_hours_ago=None,
            transactions_last_hour=5,
            bvn_verified=True, nin_bvn_match=True,
            narration="investment returns payment",
            is_post_loan_disbursement=False,
            is_agent_terminal=True, agent_tx_count_last_hour=31,
            is_pos=False, recent_outbound_ngn=0, recent_inbound_from_same_ngn=0,
        )
        triggered = [s.name for s in heuristic.triggered_signals]
        bayes = bayesian_fraud_score(triggered)
        steps.append({
            "step": 3, "name": "Pattern Analysis",
            "result": f"Signals: AGENT_VELOCITY_SPIKE + SCAM_KEYWORDS_NARRATION | Bayesian P(fraud) = {bayes.posterior_fraud_probability:.1%} | Risk: {bayes.risk_level.upper()}",
            "status": "alert",
        })
        steps.append({
            "step": 4, "name": "Regulatory Action",
            "result": "Terminal suspended. Compliance escalation raised. STR filed per CBN Agent Banking Guidelines 2019 §6.3.",
            "status": "action",
        })
        verdict = "AGENT TERMINAL SUSPENDED — Mule chain pattern detected. STR filed with NFIU."

    # ── SCENARIO 3: Chargeback Investigation ─────────────────────────────────
    else:
        steps.append({
            "step": 1, "name": "Dispute Intake",
            "result": "Customer disputes ₦85,000 POS transaction at 02:30 WAT | Claims card not present | Merchant: FuelStation Lagos",
            "status": "info",
        })
        steps.append({
            "step": 2, "name": "Device & SIM Check",
            "result": "SIM replaced 20 hours before transaction ⚠️ | New device fingerprint at time of auth ⚠️",
            "status": "alert",
        })
        heuristic = evaluate_transaction(
            amount=85000, channel="pos",
            hour_of_day=2, day_of_week=4,
            is_new_recipient=False, is_new_device=True,
            device_changed_hours_ago=4, sim_replaced_hours_ago=20,
            transactions_last_hour=1,
            bvn_verified=True, nin_bvn_match=True,
            narration="",
            is_post_loan_disbursement=False,
            is_agent_terminal=False, agent_tx_count_last_hour=0,
            is_pos=True, recent_outbound_ngn=0, recent_inbound_from_same_ngn=0,
        )
        triggered = [s.name for s in heuristic.triggered_signals]
        bayes = bayesian_fraud_score(triggered)
        steps.append({
            "step": 3, "name": "Fraud Signal Scoring",
            "result": f"Signals: SIM_SWAP_HIGH_VALUE_USSD + DEVICE_CHANGE_BEFORE_TRANSFER + POS_ABOVE_CBN_LIMIT | P(fraud) = {bayes.posterior_fraud_probability:.1%}",
            "status": "alert",
        })
        steps.append({
            "step": 4, "name": "CBN Dispute Timeline",
            "result": "Chargeback upheld. Provisional credit issued within 24h per CBN Consumer Protection Framework. Merchant dispute window: 14 days.",
            "status": "action",
        })
        verdict = "CHARGEBACK UPHELD — SIM swap + device change confirmed. Provisional credit issued. Merchant notified."

    # ── LLM Narrative ─────────────────────────────────────────────────────────
    narrative_prompt = (
        f"Scenario: {SCENARIOS[scenario_id]['name']}\n"
        f"Steps completed: {json.dumps([s['name'] + ': ' + s['result'] for s in steps])}\n"
        f"Verdict: {verdict}\n\n"
        "Write a 2-sentence compliance-ready summary for a Nigerian fintech risk officer. "
        "Reference relevant CBN regulations. Be direct and actionable."
    )
    llm_response = llm.invoke([
        SystemMessage(content="You are a Nigerian fintech compliance AI. Be concise and cite CBN regulations."),
        HumanMessage(content=narrative_prompt),
    ])
    narrative = llm_response.content.strip()

    # Build CaseOutput
    filings = get_required_filings(
        risk_level=bayes.risk_level,
        amount_ngn=heuristic.triggered_signals[0].score_delta * 1000 if heuristic.triggered_signals else 50000,
        signal_names=triggered,
    )
    audit = _make_audit(provider, scenario_id, bayes.risk_level, triggered, bayes.risk_score)

    from app.models.schemas import CaseOutput, RegulatoryFilingOut
    case = CaseOutput(
        case_id=case_id,
        transaction_id=f"WF-{scenario_id[:6].upper()}-{case_id[:6]}",
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
        llm_narrative=narrative,
        provider_used=provider,
        created_at=now.isoformat(),
    )

    return {
        "scenario_id": scenario_id,
        "scenario_name": SCENARIOS[scenario_id]["name"],
        "steps": steps,
        "final_verdict": verdict,
        "case_output": case.model_dump(),
        "provider_used": provider,
    }
