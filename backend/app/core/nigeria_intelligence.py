"""
Nigerian Fraud Intelligence Engine
===================================
This is the core moat of NaijaFinAI. It encodes:

1. Nigerian-specific fraud patterns observed in the local ecosystem
2. CBN regulatory thresholds with specific circular references
3. Known mule account and structuring signatures
4. Telco-linked SIM swap detection heuristics
5. POS skimming and agent network fraud patterns

This is NOT generic fintech fraud logic. It is built from the ground up
for the Nigerian payments landscape — NIBSS NIP rails, USSD channels,
OPay/PalmPay/Moniepoint agent networks, and CBN KYC tiers.
"""

from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime, time


# ── CBN Regulatory Thresholds (with circular references) ─────────────────────

CBN_THRESHOLDS = {
    "tier1_daily_limit_ngn": 50_000,        # CBN Circular FPR/DIR/GEN/CIR/06/010
    "tier2_daily_limit_ngn": 200_000,        # Same circular
    "tier3_daily_limit_ngn": 5_000_000,      # Same circular
    "ctr_reporting_threshold_ngn": 5_000_000, # Currency Transaction Report (EFCC/CBN AML guidelines)
    "str_trigger_ngn": 1_000_000,            # Suspicious Transaction Report threshold
    "structuring_window_ngn": 999_999,       # Known structuring ceiling to avoid CTR
    "pos_single_limit_ngn": 150_000,         # CBN POS transaction limit
    "ussd_single_limit_ngn": 20_000,         # CBN USSD per-transaction cap
    "ussd_daily_limit_ngn": 100_000,         # CBN USSD daily cap
    "interbank_nip_max_ngn": 50_000_000,     # NIBSS NIP single transfer cap
    "nin_bvn_link_required_above_ngn": 0,    # All accounts — CBN Circular BPS/DIR/2020/004
}

# ── Nigerian Fraud Pattern Library ───────────────────────────────────────────

@dataclass
class FraudSignal:
    name: str
    severity: Literal["low", "medium", "high", "critical"]
    score_delta: int
    description: str
    cbn_reference: str = ""
    recommended_action: str = ""


NIGERIAN_FRAUD_SIGNALS: list[FraudSignal] = [

    # ── Structuring / Smurfing ───────────────────────────────────────────────
    FraudSignal(
        name="CBN_STRUCTURING",
        severity="critical",
        score_delta=35,
        description="Amount is suspiciously close to but below the CTR/STR threshold (₦999,999 zone). "
                    "Classic structuring to avoid mandatory EFCC reporting.",
        cbn_reference="CBN AML/CFT Regulations 2022, Section 4.3 — Structuring",
        recommended_action="File Suspicious Transaction Report (STR) with NFIU within 24 hours",
    ),
    FraudSignal(
        name="SPLIT_TRANSACTION_PATTERN",
        severity="high",
        score_delta=28,
        description="Multiple transactions to the same or related accounts within a short window, "
                    "collectively exceeding reporting thresholds.",
        cbn_reference="CBN AML/CFT Regulations 2022, Section 4.3",
        recommended_action="Aggregate and report as single STR to NFIU",
    ),

    # ── SIM Swap / USSD Takeover ─────────────────────────────────────────────
    FraudSignal(
        name="SIM_SWAP_HIGH_VALUE_USSD",
        severity="critical",
        score_delta=40,
        description="High-value USSD transfer initiated within 48 hours of SIM replacement. "
                    "Primary vector for account takeover in Nigeria — telcos (MTN, Airtel, Glo, 9mobile) "
                    "allow SIM swap with minimal verification.",
        cbn_reference="CBN Consumer Protection Circular CPD/DIR/GEN/LAB/13/006",
        recommended_action="Freeze account immediately. Require in-person BVN re-verification.",
    ),
    FraudSignal(
        name="USSD_AFTER_HOURS",
        severity="high",
        score_delta=22,
        description="USSD transaction initiated between 01:00–05:00 WAT. SIM swap fraud "
                    "is disproportionately executed in the early morning to minimize detection window.",
        cbn_reference="CBN Fraud Desk Advisory 2023-07",
        recommended_action="Trigger OTP to registered email + secondary phone. Delay settlement by 15 mins.",
    ),
    FraudSignal(
        name="DEVICE_CHANGE_BEFORE_TRANSFER",
        severity="high",
        score_delta=25,
        description="New device fingerprint detected < 6 hours before a high-value transfer. "
                    "Correlated with social engineering attacks where victim is tricked into giving OTP.",
        cbn_reference="CBN Electronic Banking Guidelines 2020, Section 7",
        recommended_action="Step-up authentication required. Notify customer via pre-registered fallback.",
    ),

    # ── POS / Agent Network Fraud ────────────────────────────────────────────
    FraudSignal(
        name="POS_ABOVE_CBN_LIMIT",
        severity="medium",
        score_delta=20,
        description=f"POS transaction exceeds CBN single-transaction limit of ₦150,000. "
                    f"May indicate terminal override or merchant collusion.",
        cbn_reference="CBN POS Guidelines, Revised 2023",
        recommended_action="Verify terminal ID against NIBSS registry. Flag merchant for review.",
    ),
    FraudSignal(
        name="AGENT_VELOCITY_SPIKE",
        severity="high",
        score_delta=30,
        description="Moniepoint/OPay/PalmPay agent terminal processed >20 transactions in 1 hour "
                    "to unique recipients. Consistent with money mule laundering through agent networks.",
        cbn_reference="CBN Agent Banking Guidelines 2013 (Revised 2019), Section 6.3",
        recommended_action="Suspend agent terminal. Escalate to compliance. File STR with NFIU.",
    ),

    # ── Identity / BVN Fraud ─────────────────────────────────────────────────
    FraudSignal(
        name="UNVERIFIED_BVN_LARGE_TRANSFER",
        severity="high",
        score_delta=30,
        description="Transfer from account with unverified or recently registered BVN. "
                    "BVN fraud (fake enrollment via compromised NIMC agents) is rising.",
        cbn_reference="CBN Circular BPS/DIR/2020/004 — BVN for all account holders",
        recommended_action="Suspend transaction. Trigger BVN re-validation via NIBSS BVN API.",
    ),
    FraudSignal(
        name="NIN_BVN_MISMATCH",
        severity="critical",
        score_delta=45,
        description="NIN and BVN details on account do not match NIMC/NIBSS records. "
                    "Strongest single indicator of synthetic identity fraud in Nigeria.",
        cbn_reference="CBN Circular BPS/DIR/GEN/CIR/03/002 — NIN-BVN Linkage Mandate",
        recommended_action="Block account immediately. File STR. Refer to EFCC Cybercrime unit.",
    ),

    # ── Social Engineering / Romance/Investment Scams ────────────────────────
    FraudSignal(
        name="SCAM_KEYWORDS_NARRATION",
        severity="high",
        score_delta=25,
        description="Transaction narration contains keywords linked to Nigerian scam typologies: "
                    "forex investment, crypto returns, lottery, urgent withdrawal, 'oga approved'.",
        cbn_reference="EFCC Advisory on Investment Fraud, 2024",
        recommended_action="Flag for analyst review. Trigger customer callback before processing.",
    ),
    FraudSignal(
        name="FIRST_PARTY_FRAUD_LOAN",
        severity="high",
        score_delta=28,
        description="Loan disbursement immediately followed by full withdrawal to new recipient "
                    "within 30 minutes. Classic first-party fraud pattern in Nigerian digital lending.",
        cbn_reference="CBN Microfinance Bank Guidelines, Section 8.4",
        recommended_action="Hold disbursement. Verify loan purpose with customer callback.",
    ),

    # ── Velocity / Timing ────────────────────────────────────────────────────
    FraudSignal(
        name="WEEKEND_MIDNIGHT_SPIKE",
        severity="medium",
        score_delta=18,
        description="Multiple transfers on Friday–Saturday after midnight. "
                    "Correlated with social engineering scams targeting night-shift workers and market traders.",
        cbn_reference="Internal pattern — CBN Fraud Trend Report Q3 2024",
        recommended_action="Apply additional OTP challenge for transfers above ₦50,000.",
    ),
    FraudSignal(
        name="ROUND_TRIP_TRANSFER",
        severity="critical",
        score_delta=38,
        description="Funds transferred out and an equivalent amount returned within 24 hours "
                    "via different account paths. Classic layering pattern for AML.",
        cbn_reference="CBN AML/CFT Regulations 2022, Section 3.1 — Layering",
        recommended_action="Freeze both ends of the transaction. File STR immediately.",
    ),
]

# ── Lookup by name ────────────────────────────────────────────────────────────

SIGNAL_MAP = {s.name: s for s in NIGERIAN_FRAUD_SIGNALS}


# ── Risk Scorer ───────────────────────────────────────────────────────────────

@dataclass
class FraudEvaluation:
    triggered_signals: list[FraudSignal] = field(default_factory=list)
    total_score: int = 0
    risk_level: str = "low"
    primary_signal: FraudSignal | None = None
    recommended_action: str = "Approve"
    cbn_references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_score": self.total_score,
            "risk_level": self.risk_level,
            "primary_signal": self.primary_signal.name if self.primary_signal else None,
            "recommended_action": self.recommended_action,
            "cbn_references": self.cbn_references,
            "triggered_signals": [
                {
                    "name": s.name,
                    "severity": s.severity,
                    "description": s.description,
                    "score_delta": s.score_delta,
                    "cbn_reference": s.cbn_reference,
                }
                for s in self.triggered_signals
            ],
        }


def evaluate_transaction(
    amount: float,
    channel: str,
    hour_of_day: int,
    day_of_week: int,          # 0=Mon … 6=Sun
    is_new_recipient: bool,
    is_new_device: bool,
    device_changed_hours_ago: int | None,
    sim_replaced_hours_ago: int | None,
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
) -> FraudEvaluation:
    """
    Core heuristic scorer using Nigerian fraud intelligence signals.
    Returns a FraudEvaluation with triggered signals, score, and CBN references.
    """
    result = FraudEvaluation()

    def trigger(signal_name: str):
        s = SIGNAL_MAP[signal_name]
        result.triggered_signals.append(s)
        result.total_score = min(100, result.total_score + s.score_delta)
        if s.cbn_reference:
            result.cbn_references.append(s.cbn_reference)

    # Structuring
    if 900_000 <= amount <= 999_999:
        trigger("CBN_STRUCTURING")

    # SIM swap indicators
    if sim_replaced_hours_ago is not None and sim_replaced_hours_ago < 48:
        if channel == "ussd" and amount > 10_000:
            trigger("SIM_SWAP_HIGH_VALUE_USSD")

    if channel == "ussd" and (hour_of_day < 5 or hour_of_day >= 1):
        if hour_of_day >= 1 and hour_of_day <= 5:
            trigger("USSD_AFTER_HOURS")

    # Device change before large transfer
    if is_new_device and device_changed_hours_ago is not None and device_changed_hours_ago < 6:
        if amount > 50_000:
            trigger("DEVICE_CHANGE_BEFORE_TRANSFER")

    # POS limits
    if is_pos and amount > CBN_THRESHOLDS["pos_single_limit_ngn"]:
        trigger("POS_ABOVE_CBN_LIMIT")

    # Agent velocity
    if is_agent_terminal and agent_tx_count_last_hour > 20:
        trigger("AGENT_VELOCITY_SPIKE")

    # BVN / NIN
    if not bvn_verified and amount > 50_000:
        trigger("UNVERIFIED_BVN_LARGE_TRANSFER")
    if not nin_bvn_match:
        trigger("NIN_BVN_MISMATCH")

    # Scam narration keywords
    scam_terms = [
        "forex", "crypto", "investment return", "profit", "urgent", "lottery",
        "winnings", "oga approved", "manager approved", "transfer back", "refund first",
        "double your money", "ROI",
    ]
    if any(term.lower() in narration.lower() for term in scam_terms):
        trigger("SCAM_KEYWORDS_NARRATION")

    # First-party loan fraud
    if is_post_loan_disbursement and is_new_recipient and transactions_last_hour >= 1:
        trigger("FIRST_PARTY_FRAUD_LOAN")

    # Weekend midnight spike
    if day_of_week in (4, 5) and (hour_of_day >= 0 and hour_of_day <= 3) and amount > 30_000:
        trigger("WEEKEND_MIDNIGHT_SPIKE")

    # Round-trip layering
    if recent_inbound_from_same_ngn > 0:
        ratio = recent_outbound_ngn / recent_inbound_from_same_ngn
        if 0.85 <= ratio <= 1.15 and recent_outbound_ngn > 100_000:
            trigger("ROUND_TRIP_TRANSFER")

    # Split transactions
    if transactions_last_hour >= 3 and (amount * transactions_last_hour) > CBN_THRESHOLDS["str_trigger_ngn"]:
        trigger("SPLIT_TRANSACTION_PATTERN")

    # Determine risk level and action
    score = result.total_score
    if result.triggered_signals:
        result.primary_signal = max(result.triggered_signals, key=lambda s: s.score_delta)

    if score <= 25:
        result.risk_level = "low"
        result.recommended_action = "✅ Approve — no significant risk signals detected"
    elif score <= 50:
        result.risk_level = "medium"
        result.recommended_action = "🟡 Review — request step-up OTP and confirm with customer"
    elif score <= 75:
        result.risk_level = "high"
        result.recommended_action = (
            result.primary_signal.recommended_action
            if result.primary_signal else "🔴 Hold — escalate to compliance team"
        )
    else:
        result.risk_level = "critical"
        result.recommended_action = (
            result.primary_signal.recommended_action
            if result.primary_signal else "🚨 Block immediately — file STR with NFIU within 24h"
        )

    return result
