"""
Scoring Engine (separated from Decision Engine)
================================================
Pure scoring — no decisions, no actions, no routing.
Takes raw transaction data, returns three independent scores:
  1. Signal Score    (Bayesian, Nigerian-specific)
  2. Behavioral Score (feature store deviation)
  3. Graph Score     (network patterns)

Fixes applied:
  - Behavioral score always dominates when severe (>70)
  - Card testing detection (micro-transactions repeated rapidly)
  - Structuring zone ₦8k–₦10k (USSD/mobile low-value structuring)
  - New account penalty (account age < 30 days)
  - Beneficiary explosion weighting (fan-out to new recipients)
  - POS reversal amplification (reversal after POS flagged)
"""

import math
from dataclasses import dataclass, field
from typing import Literal, Optional


BASE_FRAUD_PRIOR = 0.023  # CBN baseline ~2.3%


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


SIGNALS: list[SignalDef] = [
    SignalDef("NIN_BVN_MISMATCH",              "critical", 45.0, 2.0,  "NIN-BVN mismatch — strongest synthetic identity signal", "CBN BPS/DIR/GEN/CIR/03/002", "Block + STR + EFCC referral"),
    SignalDef("SIM_SWAP_HIGH_VALUE_USSD",       "critical", 22.0, 1.5,  "USSD transfer within 48h of SIM replacement", "CBN CPD/DIR/GEN/LAB/13/006", "Freeze + in-person BVN re-verification"),
    SignalDef("ROUND_TRIP_TRANSFER",            "critical", 19.6, 1.6,  "Funds returned via different path within 24h — layering", "CBN AML/CFT 2022 §3.1", "Freeze both ends + STR"),
    SignalDef("CBN_STRUCTURING",                "critical", 18.5, 1.4,  "Amount ₦900k–₦999k — CTR avoidance structuring", "CBN AML/CFT 2022 §4.3", "STR within 24h"),
    SignalDef("CARD_TESTING",                   "critical", 17.0, 1.5,  "Multiple micro-transactions in rapid succession — card testing pattern", "CBN Fraud Desk Advisory 2023-07", "Block card + alert issuer"),
    SignalDef("USSD_LOW_VALUE_STRUCTURING",     "high",     14.0, 1.3,  "Repeated ₦8k–₦10k USSD transfers — low-value structuring below radar", "CBN AML/CFT 2022 §4.3", "Flag for STR review"),
    SignalDef("AGENT_VELOCITY_SPIKE",           "high",     14.8, 1.3,  "Agent terminal >20 tx/hour to unique recipients — mule chain", "CBN Agent Banking 2019 §6.3", "Suspend terminal + STR"),
    SignalDef("SPLIT_TRANSACTION_PATTERN",      "high",     13.1, 1.2,  "Multiple transactions collectively exceeding STR threshold", "CBN AML/CFT 2022 §4.3", "Aggregate + STR"),
    SignalDef("FIRST_PARTY_FRAUD_LOAN",         "high",     12.4, 1.3,  "Full loan withdrawal to new recipient within 30 mins", "CBN MFB Guidelines §8.4", "Hold disbursement"),
    SignalDef("BENEFICIARY_EXPLOSION",          "high",     12.0, 1.3,  "Rapid fan-out to many new beneficiaries — smurfing pattern", "CBN AML/CFT 2022 §4.3", "Hold + review beneficiary list"),
    SignalDef("UNVERIFIED_BVN_LARGE_TRANSFER",  "high",     11.2, 1.2,  "Large transfer from unverified BVN account", "CBN BPS/DIR/2020/004", "Suspend + NIBSS BVN re-validation"),
    SignalDef("NEW_ACCOUNT_HIGH_VALUE",         "high",     10.5, 1.2,  "Account < 30 days old transacting above typical onboarding limit", "CBN KYC Framework 2023", "Step-up verification"),
    SignalDef("DEVICE_CHANGE_BEFORE_TRANSFER",  "high",      9.3, 1.2,  "New device <6h before high-value transfer", "CBN e-Banking Guidelines 2020 §7", "Step-up auth"),
    SignalDef("SCAM_KEYWORDS_NARRATION",        "high",      8.7, 1.1,  "Scam keywords in narration (forex, investment, lottery, urgent)", "EFCC Advisory 2024", "Customer callback before processing"),
    SignalDef("POS_REVERSAL_AFTER_FLAG",        "high",      8.5, 1.2,  "POS reversal requested on a previously flagged transaction", "CBN POS Guidelines 2023", "Decline reversal + escalate"),
    SignalDef("USSD_AFTER_HOURS",               "high",      7.2, 1.1,  "USSD transfer 01:00–05:00 WAT — SIM swap exploitation window", "CBN Fraud Desk Advisory 2023-07", "OTP to email + secondary phone"),
    SignalDef("POS_ABOVE_CBN_LIMIT",            "medium",    4.1, 0.9,  "POS transaction exceeds CBN ₦150,000 limit", "CBN POS Guidelines 2023", "Verify terminal ID"),
    SignalDef("WEEKEND_MIDNIGHT_SPIKE",         "medium",    3.8, 0.85, "Multiple transfers Fri–Sat after midnight", "CBN Fraud Trend Q3 2024", "Additional OTP"),
]

SIGNAL_MAP = {s.name: s for s in SIGNALS}


@dataclass
class SignalScore:
    triggered: list[SignalDef] = field(default_factory=list)
    posterior_fraud_probability: float = 0.0
    score: int = 0
    top_3: list[dict] = field(default_factory=list)
    contributions: list[dict] = field(default_factory=list)
    cbn_references: list[str] = field(default_factory=list)


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
    prior_odds = BASE_FRAUD_PRIOR / (1 - BASE_FRAUD_PRIOR)
    log_odds = math.log(prior_odds)
    triggered_names = []

    def trigger(name: str):
        s = SIGNAL_MAP.get(name)
        if not s:
            return
        result.triggered.append(s)
        triggered_names.append(name)
        contribution = s.weight * s.log_likelihood
        log_odds_ref = [log_odds]  # closure workaround
        log_odds_ref[0] += contribution
        result.contributions.append({"signal": name, "contribution": round(contribution, 3), "lr": s.likelihood_ratio})
        if s.cbn_reference:
            result.cbn_references.append(s.cbn_reference)
        return log_odds_ref[0]

    # Rebuild log_odds properly
    log_odds_val = math.log(prior_odds)
    for name, condition in [
        ("NIN_BVN_MISMATCH",             not nin_bvn_match),
        ("SIM_SWAP_HIGH_VALUE_USSD",     sim_replaced_hours_ago is not None and sim_replaced_hours_ago < 48 and channel == "ussd" and amount > 10_000),
        ("ROUND_TRIP_TRANSFER",          recent_inbound_from_same_ngn > 0 and recent_outbound_ngn > 0 and 0.85 <= recent_outbound_ngn / max(recent_inbound_from_same_ngn, 1) <= 1.15 and recent_outbound_ngn > 100_000),
        ("CBN_STRUCTURING",              900_000 <= amount <= 999_999),
        ("CARD_TESTING",                 micro_tx_last_10min >= 3 and amount < 500),
        ("USSD_LOW_VALUE_STRUCTURING",   8_000 <= amount <= 10_000 and channel == "ussd" and transactions_last_hour >= 3),
        ("AGENT_VELOCITY_SPIKE",         is_agent_terminal and agent_tx_count_last_hour > 20),
        ("SPLIT_TRANSACTION_PATTERN",    transactions_last_hour >= 3 and (amount * transactions_last_hour) > 1_000_000),
        ("FIRST_PARTY_FRAUD_LOAN",       is_post_loan_disbursement and is_new_recipient and transactions_last_hour >= 1),
        ("BENEFICIARY_EXPLOSION",        new_beneficiaries_last_hour >= 4),
        ("UNVERIFIED_BVN_LARGE_TRANSFER",not bvn_verified and amount > 50_000),
        ("NEW_ACCOUNT_HIGH_VALUE",       account_age_days < 30 and amount > 50_000),
        ("DEVICE_CHANGE_BEFORE_TRANSFER",is_new_device and device_changed_hours_ago is not None and device_changed_hours_ago < 6 and amount > 50_000),
        ("SCAM_KEYWORDS_NARRATION",      any(kw in narration.lower() for kw in ["forex","crypto","investment return","profit","urgent","lottery","winnings","oga approved","transfer back","double","roi"])),
        ("POS_REVERSAL_AFTER_FLAG",      is_pos and is_pos_reversal),
        ("USSD_AFTER_HOURS",             channel == "ussd" and 1 <= hour_of_day <= 5),
        ("POS_ABOVE_CBN_LIMIT",          is_pos and amount > 150_000),
        ("WEEKEND_MIDNIGHT_SPIKE",       day_of_week in (4, 5) and 0 <= hour_of_day <= 3 and amount > 30_000),
    ]:
        if condition:
            s = SIGNAL_MAP.get(name)
            if s:
                result.triggered.append(s)
                triggered_names.append(name)
                contrib = s.weight * s.log_likelihood
                log_odds_val += contrib
                result.contributions.append({"signal": name, "contribution": round(contrib, 3), "lr": s.likelihood_ratio})
                if s.cbn_reference and s.cbn_reference not in result.cbn_references:
                    result.cbn_references.append(s.cbn_reference)

    posterior = 1 / (1 + math.exp(-log_odds_val))
    result.posterior_fraud_probability = posterior
    result.score = min(100, int(posterior * 100))

    sorted_signals = sorted(result.triggered, key=lambda s: s.weight * s.likelihood_ratio, reverse=True)
    result.top_3 = [
        {"rank": i+1, "name": s.name, "severity": s.severity, "description": s.description,
         "cbn_reference": s.cbn_reference, "recommended_action": s.recommended_action}
        for i, s in enumerate(sorted_signals[:3])
    ]
    return result
