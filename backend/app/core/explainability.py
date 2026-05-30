"""
Explainability Engine
======================
Produces human-readable reason codes for every fraud decision.

Output format:
  Risk Score: 84 — HIGH RISK
  Main contributors:
    1. SIM swap detected (+22 pts) — CBN circular CPD/DIR/GEN/LAB/13/006
    2. New device fingerprint (+17 pts) — user's 3rd device in 6 hours
    3. Amount 9× normal behaviour (+21 pts) — avg ₦8,500, this: ₦80,000
    4. Transfer at 02:30 WAT (+10 pts) — outside user's typical 08:00–20:00

  Confidence: 87%
  Recommended action: Freeze account — require in-person BVN re-verification
  Escalation path: Compliance → NFIU STR within 24 hours
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReasonCode:
    rank: int
    signal_name: str
    human_label: str
    score_contribution: int
    context: str          # personalised context (e.g. "9× normal behaviour")
    cbn_reference: str
    severity: str


@dataclass
class ExplainabilityReport:
    risk_score: int
    risk_level: str
    posterior_fraud_probability: float
    confidence_label: str
    top_reason_codes: list[ReasonCode]
    recommended_action: str
    escalation_path: str
    summary_sentence: str
    safe_to_auto_approve: bool
    requires_human_review: bool
    regulatory_filing_required: bool

    def to_dict(self) -> dict:
        return {
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "posterior_fraud_probability": self.posterior_fraud_probability,
            "confidence": self.confidence_label,
            "summary": self.summary_sentence,
            "top_reason_codes": [
                {
                    "rank": r.rank,
                    "signal": r.signal_name,
                    "label": r.human_label,
                    "score_contribution": r.score_contribution,
                    "context": r.context,
                    "cbn_reference": r.cbn_reference,
                    "severity": r.severity,
                }
                for r in self.top_reason_codes
            ],
            "recommended_action": self.recommended_action,
            "escalation_path": self.escalation_path,
            "safe_to_auto_approve": self.safe_to_auto_approve,
            "requires_human_review": self.requires_human_review,
            "regulatory_filing_required": self.regulatory_filing_required,
        }


# ── Human-readable labels for each signal ────────────────────────────────────

SIGNAL_LABELS = {
    "SIM_SWAP_HIGH_VALUE_USSD":        "SIM replacement + high-value USSD transfer",
    "CBN_STRUCTURING":                 "Amount near ₦1M CBN reporting threshold",
    "NIN_BVN_MISMATCH":               "NIN and BVN do not match NIMC records",
    "USSD_AFTER_HOURS":               "USSD transfer in high-risk hours (01:00–05:00 WAT)",
    "DEVICE_CHANGE_BEFORE_TRANSFER":  "New device fingerprint before large transfer",
    "POS_ABOVE_CBN_LIMIT":            "POS amount exceeds ₦150,000 CBN limit",
    "AGENT_VELOCITY_SPIKE":           "Agent terminal velocity spike — possible mule chain",
    "UNVERIFIED_BVN_LARGE_TRANSFER":  "Unverified BVN on high-value transfer",
    "SCAM_KEYWORDS_NARRATION":        "Scam keywords detected in transaction narration",
    "FIRST_PARTY_FRAUD_LOAN":         "Loan disbursement immediately followed by full withdrawal",
    "WEEKEND_MIDNIGHT_SPIKE":         "Multiple transfers Fri–Sat after midnight",
    "ROUND_TRIP_TRANSFER":            "Funds sent and returned within 24h — layering pattern",
    "SPLIT_TRANSACTION_PATTERN":      "Multiple transactions collectively exceed STR threshold",
    "SHARED_DEVICE":                  "Device shared across multiple accounts",
    "MULE_CLUSTER":                   "Recipient linked to known mule account cluster",
    "CIRCULAR_FLOW":                  "Circular money flow detected — possible layering",
    "FLAGGED_RECIPIENT":              "Recipient account previously flagged for fraud",
    "FAN_OUT":                        "Funds distributed to many recipients rapidly",
}

ESCALATION_PATHS = {
    "low":      "No escalation required",
    "medium":   "Analyst review queue → resolve within 2 hours",
    "high":     "Compliance team → hold transaction → customer callback",
    "critical": "Compliance → freeze account → NFIU STR within 24h → consider EFCC referral",
}


def build_explainability_report(
    risk_score: int,
    risk_level: str,
    posterior_probability: float,
    triggered_signals: list[dict],       # from bayesian_scorer.signal_contributions
    top_3_signals: list[dict],           # from bayesian_scorer.top_3_signals
    recommended_action: str,
    hard_override: bool = False,
    behavioral_factors: list[str] = None,
    graph_patterns: list[dict] = None,
    amount: float = 0,
    user_avg_amount: float = 0,
) -> ExplainabilityReport:
    """Build a full explainability report from all scoring layer outputs."""

    # Build ranked reason codes
    reason_codes = []
    rank = 1

    for sig in top_3_signals:
        name = sig.get("name", "")
        label = SIGNAL_LABELS.get(name, name.replace("_", " ").title())

        # Build personalised context
        context = sig.get("description", "")[:80]
        if name == "DEVICE_CHANGE_BEFORE_TRANSFER" and amount > 0 and user_avg_amount > 0:
            context = f"New device + ₦{amount:,.0f} transfer ({amount/user_avg_amount:.1f}× user average)"
        elif name == "CBN_STRUCTURING":
            context = f"₦{amount:,.0f} falls in ₦900k–₦999k structuring zone"
        elif name in ("SIM_SWAP_HIGH_VALUE_USSD",):
            context = "SIM replaced within 48 hours — account takeover window"

        # Get contribution from bayesian scorer
        contrib_entry = next(
            (s for s in triggered_signals if s.get("signal") == name), {}
        )
        contribution = int(contrib_entry.get("contribution", 0) * 10) or sig.get("score_delta", 10)

        reason_codes.append(ReasonCode(
            rank=rank,
            signal_name=name,
            human_label=label,
            score_contribution=contribution,
            context=context,
            cbn_reference=sig.get("cbn_reference", ""),
            severity=sig.get("severity", "medium"),
        ))
        rank += 1

    # Add behavioral factors as reason codes
    if behavioral_factors:
        for factor in behavioral_factors[:2]:
            reason_codes.append(ReasonCode(
                rank=rank,
                signal_name="BEHAVIORAL_DEVIATION",
                human_label="Behavioural anomaly vs user baseline",
                score_contribution=10,
                context=factor,
                cbn_reference="",
                severity="medium",
            ))
            rank += 1

    # Add graph patterns
    if graph_patterns:
        for pattern in graph_patterns[:1]:
            ptype = pattern.get("type", "")
            reason_codes.append(ReasonCode(
                rank=rank,
                signal_name=ptype,
                human_label=SIGNAL_LABELS.get(ptype, ptype.replace("_", " ").title()),
                score_contribution=15,
                context=pattern.get("detail", ""),
                cbn_reference="",
                severity=pattern.get("severity", "high"),
            ))
            rank += 1

    # Confidence label
    p = posterior_probability
    if p > 0.85: confidence = "Very High (>85%)"
    elif p > 0.65: confidence = "High (65–85%)"
    elif p > 0.40: confidence = "Moderate (40–65%)"
    elif p > 0.20: confidence = "Low (20–40%)"
    else: confidence = "Very Low (<20%)"

    # Summary sentence
    top_signal = reason_codes[0].human_label if reason_codes else "no specific signals"
    summary = (
        f"{'⚠️ Hard override applied. ' if hard_override else ''}"
        f"Transaction scored {risk_score}/100 ({risk_level.upper()}) with {p:.0%} posterior fraud probability. "
        f"Primary driver: {top_signal}."
    )

    return ExplainabilityReport(
        risk_score=risk_score,
        risk_level=risk_level,
        posterior_fraud_probability=round(p, 4),
        confidence_label=confidence,
        top_reason_codes=reason_codes[:5],
        recommended_action=recommended_action,
        escalation_path=ESCALATION_PATHS.get(risk_level, ""),
        summary_sentence=summary,
        safe_to_auto_approve=(risk_level == "low" and not hard_override),
        requires_human_review=(risk_level in ("medium", "high")),
        regulatory_filing_required=(risk_level in ("high", "critical")),
    )
