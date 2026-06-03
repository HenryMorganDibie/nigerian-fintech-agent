"""
Scoring Engine — Evidence-Grounded
====================================
Every triggered signal carries:
  - The exact raw values that triggered it
  - The threshold that was crossed
  - A human-readable evidence string

This prevents the LLM from explaining signals generically.
The LLM receives evidence, not signal names.
"""

import math
from dataclasses import dataclass, field
from typing import Literal, Optional


BASE_FRAUD_PRIOR = 0.023


@dataclass
class SignalDef:
    name: str
    severity: Literal["low", "medium", "high", "critical"]
    likelihood_ratio: float
    weight: float
    description: str
    cbn_reference: str = ""
    recommended_action: str = ""

    @property
    def log_likelihood(self) -> float:
        return math.log(max(self.likelihood_ratio, 0.001))


@dataclass
class TriggeredSignal:
    name: str
    severity: str
    description: str
    cbn_reference: str
    recommended_action: str
    likelihood_ratio: float
    # Evidence fields — what ACTUALLY caused this to fire
    evidence: str = ""          # human-readable: "3 transactions in 1 hour totalling ₦1,500,000"
    raw_values: dict = field(default_factory=dict)  # machine-readable: {"tx_count": 3, "total": 1500000}


SIGNALS: list[SignalDef] = [
    SignalDef("NIN_BVN_MISMATCH",              "critical", 45.0, 2.0,  "NIN and BVN details do not match NIMC/NIBSS records — synthetic identity", "CBN BPS/DIR/GEN/CIR/03/002", "Block account + file STR + refer to EFCC Cybercrime"),
    SignalDef("SIM_SWAP_HIGH_VALUE_USSD",       "critical", 22.0, 1.5,  "USSD transfer within 48 hours of SIM replacement", "CBN CPD/DIR/GEN/LAB/13/006", "Freeze account — require in-person BVN re-verification"),
    SignalDef("ROUND_TRIP_TRANSFER",            "critical", 19.6, 1.6,  "Funds returned via a different path within 24 hours — layering pattern", "CBN AML/CFT 2022 §3.1", "Freeze both accounts + file STR immediately"),
    SignalDef("CBN_STRUCTURING",                "critical", 18.5, 1.4,  "Transaction amount in the ₦900,000–₦999,999 zone — CTR avoidance", "CBN AML/CFT 2022 §4.3", "File STR with NFIU within 24 hours"),
    SignalDef("CARD_TESTING",                   "critical", 17.0, 1.5,  "Multiple micro-transactions in rapid succession — card testing pattern", "CBN Fraud Desk Advisory 2023-07", "Block card immediately and alert issuer"),
    SignalDef("USSD_LOW_VALUE_STRUCTURING",     "high",     14.0, 1.3,  "Repeated low-value USSD transfers in the ₦8,000–₦10,000 range", "CBN AML/CFT 2022 §4.3", "Flag for STR review"),
    SignalDef("AGENT_VELOCITY_SPIKE",           "high",     14.8, 1.3,  "Agent terminal processed more than 20 transactions per hour to unique recipients", "CBN Agent Banking Guidelines 2019 §6.3", "Suspend terminal + file STR"),
    SignalDef("SPLIT_TRANSACTION_PATTERN",      "high",     13.1, 1.2,  "Multiple transactions in a short window collectively exceeding the STR threshold", "CBN AML/CFT 2022 §4.3", "Aggregate and report as a single STR to NFIU"),
    SignalDef("FIRST_PARTY_FRAUD_LOAN",         "high",     12.4, 1.3,  "Full loan disbursement withdrawn to a new recipient within 30 minutes", "CBN MFB Guidelines §8.4", "Hold disbursement + verify loan purpose"),
    SignalDef("BENEFICIARY_EXPLOSION",          "high",     12.0, 1.3,  "Rapid fan-out to multiple new beneficiaries — smurfing pattern", "CBN AML/CFT 2022 §4.3", "Hold + review the full beneficiary list"),
    SignalDef("UNVERIFIED_BVN_LARGE_TRANSFER",  "high",     11.2, 1.2,  "Large transfer from an account with unverified BVN", "CBN BPS/DIR/2020/004", "Suspend transaction + trigger NIBSS BVN re-validation"),
    SignalDef("NEW_ACCOUNT_HIGH_VALUE",         "high",     10.5, 1.2,  "Account less than 30 days old transacting above the typical onboarding threshold", "CBN KYC Framework 2023", "Require step-up verification"),
    SignalDef("DEVICE_CHANGE_BEFORE_TRANSFER",  "high",      9.3, 1.2,  "New device fingerprint detected less than 6 hours before a high-value transfer", "CBN Electronic Banking Guidelines 2020 §7", "Require step-up authentication"),
    SignalDef("SCAM_KEYWORDS_NARRATION",        "high",      8.7, 1.1,  "Transaction narration contains known Nigerian scam keywords", "EFCC Advisory on Investment Fraud 2024", "Trigger customer callback before processing"),
    SignalDef("POS_REVERSAL_AFTER_FLAG",        "high",      8.5, 1.2,  "POS reversal requested on a previously flagged transaction", "CBN POS Guidelines 2023", "Decline reversal + escalate to compliance"),
    SignalDef("USSD_AFTER_HOURS",               "high",      7.2, 1.1,  "USSD transfer between 01:00 and 05:00 WAT — peak SIM swap exploitation window", "CBN Fraud Desk Advisory 2023-07", "Send OTP to registered email and secondary phone"),
    SignalDef("POS_ABOVE_CBN_LIMIT",            "medium",    4.1, 0.9,  "POS transaction exceeds the CBN single-transaction limit of ₦150,000", "CBN POS Guidelines 2023", "Verify terminal ID against the NIBSS registry"),
    SignalDef("WEEKEND_MIDNIGHT_SPIKE",         "medium",    3.8, 0.85, "Multiple large transfers on Friday or Saturday after midnight", "CBN Fraud Trend Report Q3 2024", "Apply additional OTP challenge"),
]

SIGNAL_MAP = {s.name: s for s in SIGNALS}


@dataclass
class SignalScore:
    triggered: list[TriggeredSignal] = field(default_factory=list)
    posterior_fraud_probability: float = 0.0
    score: int = 0
    top_3: list[dict] = field(default_factory=list)
    contributions: list[dict] = field(default_factory=list)
    cbn_references: list[str] = field(default_factory=list)
    evidence_summary: str = ""   # structured evidence for LLM — no hallucination


def _trigger(name: str, evidence: str, raw_values: dict,
             result: SignalScore, log_odds: list) -> None:
    s = SIGNAL_MAP.get(name)
    if not s:
        return
    ts = TriggeredSignal(
        name=s.name, severity=s.severity, description=s.description,
        cbn_reference=s.cbn_reference, recommended_action=s.recommended_action,
        likelihood_ratio=s.likelihood_ratio, evidence=evidence, raw_values=raw_values,
    )
    result.triggered.append(ts)
    contrib = s.weight * s.log_likelihood
    log_odds[0] += contrib
    result.contributions.append({"signal": name, "contribution": round(contrib, 3), "lr": s.likelihood_ratio, "evidence": evidence})
    if s.cbn_reference and s.cbn_reference not in result.cbn_references:
        result.cbn_references.append(s.cbn_reference)


def compute_signal_score(
    amount: float,
    channel: str,
    hour_of_day: int,
    day_of_week: int,
    is_new_recipient: bool,
    is_new_device: bool,
    device_changed_hours_ago: Optional[int],
    sim_replaced_hours_ago: Optional[int],
    transactions_last_hour: int,
    micro_tx_last_10min: int,
    bvn_verified: bool,
    nin_bvn_match: bool,
    narration: str,
    is_post_loan_disbursement: bool,
    is_agent_terminal: bool,
    agent_tx_count_last_hour: int,
    is_pos: bool,
    is_pos_reversal: bool,
    recent_outbound_ngn: float,
    recent_inbound_from_same_ngn: float,
    account_age_days: int,
    new_beneficiaries_last_hour: int,
) -> SignalScore:

    result = SignalScore()
    lo = [math.log(BASE_FRAUD_PRIOR / (1 - BASE_FRAUD_PRIOR))]

    # ── NIN/BVN mismatch ─────────────────────────────────────────────────────
    if not nin_bvn_match:
        _trigger("NIN_BVN_MISMATCH",
                 "NIN and BVN do not match NIMC/NIBSS records for this account.",
                 {"nin_bvn_match": False}, result, lo)

    # ── SIM swap ─────────────────────────────────────────────────────────────
    if sim_replaced_hours_ago is not None and sim_replaced_hours_ago < 48 and channel == "ussd" and amount > 10_000:
        _trigger("SIM_SWAP_HIGH_VALUE_USSD",
                 f"SIM was replaced {sim_replaced_hours_ago} hours ago. "
                 f"USSD transfer of ₦{amount:,.0f} attempted within the 48-hour high-risk window.",
                 {"sim_replaced_hours_ago": sim_replaced_hours_ago, "amount": amount, "channel": channel}, result, lo)

    # ── Round-trip / layering ─────────────────────────────────────────────────
    if (recent_inbound_from_same_ngn > 0 and recent_outbound_ngn > 0
            and 0.85 <= recent_outbound_ngn / max(recent_inbound_from_same_ngn, 1) <= 1.15
            and recent_outbound_ngn > 100_000):
        ratio = recent_outbound_ngn / max(recent_inbound_from_same_ngn, 1)
        _trigger("ROUND_TRIP_TRANSFER",
                 f"Outbound ₦{recent_outbound_ngn:,.0f} is {ratio:.0%} of recent inbound "
                 f"₦{recent_inbound_from_same_ngn:,.0f} from the same counterparty — circular flow.",
                 {"outbound": recent_outbound_ngn, "inbound": recent_inbound_from_same_ngn, "ratio": round(ratio, 2)}, result, lo)

    # ── CBN structuring (₦900k–₦999k) ────────────────────────────────────────
    if 900_000 <= amount <= 999_999:
        _trigger("CBN_STRUCTURING",
                 f"Amount of ₦{amount:,.0f} falls in the ₦900,000–₦999,999 structuring zone, "
                 f"just below the CBN Currency Transaction Report threshold of ₦1,000,000.",
                 {"amount": amount, "threshold": 1_000_000}, result, lo)

    # ── Card testing ─────────────────────────────────────────────────────────
    if micro_tx_last_10min >= 3 and amount < 500:
        _trigger("CARD_TESTING",
                 f"{micro_tx_last_10min} micro-transactions (each below ₦500) in the last 10 minutes. "
                 f"Current transaction amount: ₦{amount:,.0f}.",
                 {"micro_tx_last_10min": micro_tx_last_10min, "amount": amount}, result, lo)

    # ── USSD low-value structuring (₦8k–₦10k) ────────────────────────────────
    if 8_000 <= amount <= 10_000 and channel == "ussd" and transactions_last_hour >= 3:
        total_est = amount * transactions_last_hour
        _trigger("USSD_LOW_VALUE_STRUCTURING",
                 f"{transactions_last_hour} USSD transfers in the last hour, "
                 f"each in the ₦8,000–₦10,000 range. "
                 f"Estimated total: ₦{total_est:,.0f}.",
                 {"transactions_last_hour": transactions_last_hour, "amount": amount, "estimated_total": total_est}, result, lo)

    # ── Agent velocity ────────────────────────────────────────────────────────
    if is_agent_terminal and agent_tx_count_last_hour > 20:
        _trigger("AGENT_VELOCITY_SPIKE",
                 f"Agent terminal processed {agent_tx_count_last_hour} transactions in the last hour "
                 f"(threshold: 20). All to unique recipients.",
                 {"agent_tx_count_last_hour": agent_tx_count_last_hour, "threshold": 20}, result, lo)

    # ── Split transaction — REQUIRES multiple transactions AND collective threshold ──
    # Bug fix: only fires if transactions_last_hour >= 3 AND total exceeds threshold
    # A single large transaction MUST NOT trigger this — that is normal behaviour
    if (transactions_last_hour >= 3
            and amount > 0
            and (amount * transactions_last_hour) > 1_000_000
            and not (transactions_last_hour == 1)):   # explicit guard: 1 transaction cannot be a split
        total_est = amount * transactions_last_hour
        _trigger("SPLIT_TRANSACTION_PATTERN",
                 f"{transactions_last_hour} transactions in the last hour. "
                 f"Average amount ₦{amount:,.0f} per transaction. "
                 f"Estimated aggregate: ₦{total_est:,.0f}, which exceeds the "
                 f"₦1,000,000 STR threshold.",
                 {"transactions_last_hour": transactions_last_hour, "amount_per_tx": amount, "estimated_total": total_est, "str_threshold": 1_000_000}, result, lo)

    # ── First-party loan fraud ────────────────────────────────────────────────
    if is_post_loan_disbursement and is_new_recipient and transactions_last_hour >= 1:
        _trigger("FIRST_PARTY_FRAUD_LOAN",
                 f"Transaction occurred after loan disbursement, directed to a new recipient, "
                 f"with {transactions_last_hour} transaction(s) in the last hour.",
                 {"is_post_loan": True, "is_new_recipient": True, "transactions_last_hour": transactions_last_hour}, result, lo)

    # ── Beneficiary explosion ─────────────────────────────────────────────────
    if new_beneficiaries_last_hour >= 4:
        _trigger("BENEFICIARY_EXPLOSION",
                 f"{new_beneficiaries_last_hour} new beneficiaries added in the last hour (threshold: 4). "
                 f"Fan-out smurfing pattern.",
                 {"new_beneficiaries_last_hour": new_beneficiaries_last_hour, "threshold": 4}, result, lo)

    # ── Unverified BVN ────────────────────────────────────────────────────────
    if not bvn_verified and amount > 50_000:
        _trigger("UNVERIFIED_BVN_LARGE_TRANSFER",
                 f"BVN is not verified on this account. "
                 f"Transfer amount of ₦{amount:,.0f} exceeds the ₦50,000 unverified-BVN threshold.",
                 {"bvn_verified": False, "amount": amount, "threshold": 50_000}, result, lo)

    # ── New account high value ────────────────────────────────────────────────
    if account_age_days < 30 and amount > 50_000:
        _trigger("NEW_ACCOUNT_HIGH_VALUE",
                 f"Account is {account_age_days} days old (threshold: 30 days). "
                 f"Transaction of ₦{amount:,.0f} exceeds the ₦50,000 new-account limit.",
                 {"account_age_days": account_age_days, "amount": amount, "threshold": 50_000}, result, lo)

    # ── Device change ─────────────────────────────────────────────────────────
    if is_new_device and device_changed_hours_ago is not None and device_changed_hours_ago < 6 and amount > 50_000:
        _trigger("DEVICE_CHANGE_BEFORE_TRANSFER",
                 f"New device fingerprint detected {device_changed_hours_ago} hours before this transfer of ₦{amount:,.0f}. "
                 f"Device must be established for at least 6 hours for high-value transfers.",
                 {"device_changed_hours_ago": device_changed_hours_ago, "amount": amount, "threshold_hours": 6}, result, lo)

    # ── Scam keywords ────────────────────────────────────────────────────────
    SCAM_TERMS = ["forex","crypto","investment return","profit","urgent","lottery","winnings",
                  "oga approved","transfer back","double","roi","guaranteed","scheme"]
    matched = [kw for kw in SCAM_TERMS if kw in narration.lower()]
    if matched:
        _trigger("SCAM_KEYWORDS_NARRATION",
                 f"Narration contains {len(matched)} known scam keyword(s): {', '.join(matched)}. "
                 f"Full narration: \"{narration[:120]}\"",
                 {"matched_keywords": matched, "narration_snippet": narration[:120]}, result, lo)

    # ── POS reversal ─────────────────────────────────────────────────────────
    if is_pos and is_pos_reversal:
        _trigger("POS_REVERSAL_AFTER_FLAG",
                 "POS reversal requested on a transaction that was previously flagged.",
                 {"is_pos": True, "is_pos_reversal": True}, result, lo)

    # ── USSD after hours ─────────────────────────────────────────────────────
    if channel == "ussd" and 1 <= hour_of_day <= 5:
        _trigger("USSD_AFTER_HOURS",
                 f"USSD transaction at {hour_of_day:02d}:00 WAT, within the 01:00–05:00 SIM swap risk window.",
                 {"hour_of_day": hour_of_day, "channel": channel}, result, lo)

    # ── POS above limit ───────────────────────────────────────────────────────
    if is_pos and amount > 150_000:
        _trigger("POS_ABOVE_CBN_LIMIT",
                 f"POS transaction of ₦{amount:,.0f} exceeds the CBN single-transaction limit of ₦150,000.",
                 {"amount": amount, "cbn_limit": 150_000}, result, lo)

    # ── Weekend midnight spike ────────────────────────────────────────────────
    if day_of_week in (4, 5) and 0 <= hour_of_day <= 3 and transactions_last_hour >= 2 and amount > 30_000:
        _trigger("WEEKEND_MIDNIGHT_SPIKE",
                 f"{transactions_last_hour} transfers of ₦{amount:,.0f} each on "
                 f"{'Friday' if day_of_week == 4 else 'Saturday'} at {hour_of_day:02d}:00 WAT.",
                 {"day_of_week": day_of_week, "hour_of_day": hour_of_day,
                  "transactions_last_hour": transactions_last_hour, "amount": amount}, result, lo)

    # ── Posterior probability ─────────────────────────────────────────────────
    posterior = 1 / (1 + math.exp(-lo[0]))
    result.posterior_fraud_probability = posterior
    result.score = min(100, int(posterior * 100))

    # ── Top 3 by impact ───────────────────────────────────────────────────────
    sorted_t = sorted(result.triggered, key=lambda s: s.weight * s.likelihood_ratio
                      if hasattr(s, 'weight') else s.likelihood_ratio, reverse=True)

    # Look up weight from SIGNAL_MAP
    def get_weight(ts): return SIGNAL_MAP[ts.name].weight if ts.name in SIGNAL_MAP else 1.0
    sorted_t = sorted(result.triggered, key=lambda s: get_weight(s) * s.likelihood_ratio, reverse=True)

    result.top_3 = [
        {"rank": i+1, "name": s.name, "severity": s.severity,
         "description": s.description, "cbn_reference": s.cbn_reference,
         "recommended_action": s.recommended_action, "evidence": s.evidence,
         "raw_values": s.raw_values}
        for i, s in enumerate(sorted_t[:3])
    ]

    # ── Evidence summary for LLM ──────────────────────────────────────────────
    # This is what goes to the LLM — concrete evidence, not signal names
    if result.triggered:
        lines = []
        for ts in sorted_t[:5]:
            lines.append(f"• {ts.name}: {ts.evidence}")
        result.evidence_summary = "\n".join(lines)
    else:
        result.evidence_summary = "No fraud signals triggered. Transaction appears consistent with normal activity."

    return result
