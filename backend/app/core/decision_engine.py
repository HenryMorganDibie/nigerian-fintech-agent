"""
Multi-Layer Decision Engine + Drift Monitor
============================================
Layer 5: Combines all scoring layers into a final risk decision
Layer 7: Tracks signal performance and detects pattern drift

Final Risk Score =
  Bayesian Signal Score (weighted 0.45)
+ Behavioral Deviation Score (weighted 0.30)
+ Graph Risk Score (weighted 0.25)
+ Rule-Based Hard Overrides (can override to CRITICAL regardless)

Analyst Workflow:
  0–25   → auto approve
  26–50  → review queue
  51–75  → compliance escalation
  76–100 → freeze + STR suggestion
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict, deque
from typing import Literal
import statistics


# ── Decision Tiers ────────────────────────────────────────────────────────────

DECISION_TIERS = {
    "auto_approve":   (0, 25),
    "review_queue":   (26, 50),
    "escalate":       (51, 75),
    "freeze_and_str": (76, 100),
}


@dataclass
class FinalDecision:
    composite_score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    decision: Literal["auto_approve", "review_queue", "escalate", "freeze_and_str"]
    action: str
    bayesian_score: int
    behavioral_score: int
    graph_score: int
    hard_override: bool
    override_reason: str
    layer_breakdown: dict
    analyst_notes: list[str] = field(default_factory=list)


# ── Hard Override Rules ───────────────────────────────────────────────────────
# These ALWAYS escalate to CRITICAL regardless of composite score

HARD_OVERRIDE_RULES = [
    {
        "name": "BVN_MISMATCH_HIGH_VALUE",
        "condition": lambda signals, amount: "NIN_BVN_MISMATCH" in signals and amount > 50_000,
        "action": "🚨 Auto-escalate: NIN-BVN mismatch + high value — block and file STR with NFIU",
        "severity": "critical",
    },
    {
        "name": "SIM_SWAP_RAPID_TRANSFER",
        "condition": lambda signals, amount: "SIM_SWAP_HIGH_VALUE_USSD" in signals,
        "action": "🚨 Auto-escalate: SIM swap + USSD transfer — freeze account, require in-person BVN re-verification",
        "severity": "critical",
    },
    {
        "name": "CIRCULAR_FLOW_ANY_AMOUNT",
        "condition": lambda signals, amount: "ROUND_TRIP_TRANSFER" in signals and amount > 100_000,
        "action": "🚨 Auto-escalate: Round-trip layering detected — freeze both ends, file STR immediately",
        "severity": "critical",
    },
    {
        "name": "MULE_CLUSTER_RECIPIENT",
        "condition": lambda signals, amount: any("MULE" in s for s in signals),
        "action": "🚨 Auto-escalate: Mule account cluster — suspend recipient account, escalate to EFCC",
        "severity": "critical",
    },
    {
        "name": "STRUCTURING_REPEAT",
        "condition": lambda signals, amount: "CBN_STRUCTURING" in signals and "SPLIT_TRANSACTION_PATTERN" in signals,
        "action": "🚨 Auto-escalate: Structuring + split pattern — file STR and CTR with NFIU immediately",
        "severity": "critical",
    },
]


def apply_decision_engine(
    bayesian_score: int,
    bayesian_signals: list[str],
    behavioral_score: int,
    graph_score: int,
    amount: float,
    graph_patterns: list[dict] = None,
) -> FinalDecision:
    """
    Combine all three scoring layers into a final weighted decision.
    Apply hard override rules regardless of composite score.
    """
    # Weighted composite
    composite = int(
        bayesian_score    * 0.45 +
        behavioral_score  * 0.30 +
        graph_score       * 0.25
    )
    composite = max(0, min(100, composite))

    # Check hard overrides
    override = False
    override_reason = ""
    override_action = ""
    all_signals = bayesian_signals + [p.get("type", "") for p in (graph_patterns or [])]

    for rule in HARD_OVERRIDE_RULES:
        if rule["condition"](all_signals, amount):
            override = True
            override_reason = rule["name"]
            override_action = rule["action"]
            composite = max(composite, 85)  # ensure critical threshold
            break

    # Determine tier
    if composite <= 25:
        risk_level, decision = "low",      "auto_approve"
        action = f"✅ Auto-approve — composite risk {composite}/100"
    elif composite <= 50:
        risk_level, decision = "medium",   "review_queue"
        action = f"🟡 Add to review queue — analyst to verify within 2 hours. Score {composite}/100"
    elif composite <= 75:
        risk_level, decision = "high",     "escalate"
        action = f"🔴 Escalate to compliance — hold transaction. Score {composite}/100"
    else:
        risk_level, decision = "critical", "freeze_and_str"
        action = override_action or f"🚨 Freeze account — file STR with NFIU within 24 hours. Score {composite}/100"

    notes = []
    if behavioral_score > bayesian_score:
        notes.append("Behavioral deviation is the primary driver — user acting outside their normal pattern")
    if graph_score > 50:
        notes.append("Graph-level risk is elevated — check for network-level fraud connections")
    if override:
        notes.append(f"Hard override triggered: {override_reason}")

    return FinalDecision(
        composite_score=composite,
        risk_level=risk_level,
        decision=decision,
        action=action,
        bayesian_score=bayesian_score,
        behavioral_score=behavioral_score,
        graph_score=graph_score,
        hard_override=override,
        override_reason=override_reason,
        layer_breakdown={
            "bayesian":    {"score": bayesian_score,    "weight": "45%"},
            "behavioral":  {"score": behavioral_score,  "weight": "30%"},
            "graph":       {"score": graph_score,       "weight": "25%"},
            "composite":   composite,
            "hard_override": override,
        },
        analyst_notes=notes,
    )


# ── Drift Monitor (Layer 7) ───────────────────────────────────────────────────

class DriftMonitor:
    """
    Tracks signal performance and detects pattern drift.
    Uses a rolling window of recent decisions.
    """

    def __init__(self, window_size: int = 500):
        self.window_size = window_size
        self.decisions: deque = deque(maxlen=window_size)
        self.signal_hits: dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.confirmed_fraud: deque = deque(maxlen=window_size)
        self.false_positives: deque = deque(maxlen=window_size)
        self.baseline_fraud_rate: float = 0.023  # CBN baseline ~2.3%
        self._score_history: deque = deque(maxlen=window_size)

    def record_decision(self, composite_score: int, signals: list[str],
                        risk_level: str, amount: float):
        ts = datetime.now(timezone.utc).isoformat()
        self.decisions.append({
            "score": composite_score, "risk_level": risk_level,
            "amount": amount, "signals": signals, "ts": ts,
        })
        self._score_history.append(composite_score)
        for sig in signals:
            self.signal_hits[sig].append(1)

    def record_feedback(self, outcome: Literal["fraud_confirmed", "fraud_rejected",
                                                "false_positive", "chargeback_confirmed"]):
        """Record analyst/reality feedback to update signal weights and monitor drift."""
        if outcome in ("fraud_confirmed", "chargeback_confirmed"):
            self.confirmed_fraud.append(1)
        elif outcome == "false_positive":
            self.false_positives.append(1)

    def get_drift_report(self) -> dict:
        if len(self._score_history) < 20:
            return {"status": "insufficient_data", "message": "Need at least 20 decisions for drift analysis"}

        scores = list(self._score_history)
        recent_50 = scores[-50:] if len(scores) >= 50 else scores
        baseline_50 = scores[:50] if len(scores) >= 100 else scores[:len(scores)//2]

        recent_mean  = statistics.mean(recent_50)
        recent_std   = statistics.stdev(recent_50) if len(recent_50) > 1 else 0

        drift_alerts = []
        psi_score = 0.0

        # Simple PSI-style drift: compare recent vs baseline mean
        if baseline_50:
            baseline_mean = statistics.mean(baseline_50)
            psi_score = abs(recent_mean - baseline_mean) / max(baseline_mean, 1)
            if psi_score > 0.25:
                drift_alerts.append({
                    "type": "SCORE_DISTRIBUTION_DRIFT",
                    "severity": "high",
                    "detail": f"Risk score distribution shifted significantly — PSI {psi_score:.2f} (threshold: 0.25)",
                    "recommendation": "Review recent fraud patterns. New attack vector may be emerging.",
                })
            elif psi_score > 0.10:
                drift_alerts.append({
                    "type": "SCORE_DISTRIBUTION_SHIFT",
                    "severity": "medium",
                    "detail": f"Moderate distribution shift detected — PSI {psi_score:.2f}",
                    "recommendation": "Monitor closely. Consider re-calibrating signal weights.",
                })

        # Fraud rate drift
        recent_decisions = list(self.decisions)[-100:]
        if recent_decisions:
            recent_high_risk = sum(1 for d in recent_decisions if d["risk_level"] in ("high", "critical"))
            recent_fraud_rate = recent_high_risk / len(recent_decisions)
            if recent_fraud_rate > self.baseline_fraud_rate * 3:
                drift_alerts.append({
                    "type": "FRAUD_RATE_SPIKE",
                    "severity": "critical",
                    "detail": f"Fraud rate {recent_fraud_rate:.1%} is {recent_fraud_rate/self.baseline_fraud_rate:.1f}× baseline — possible coordinated attack",
                    "recommendation": "Tighten all thresholds. Alert compliance team immediately.",
                })

        # Signal frequency drift
        signal_alerts = []
        for sig, hits in self.signal_hits.items():
            if len(hits) >= 20:
                recent_rate = sum(list(hits)[-20:]) / 20
                if recent_rate > 0.5:
                    signal_alerts.append({
                        "signal": sig,
                        "recent_hit_rate": round(recent_rate, 3),
                        "alert": f"{sig} triggering on {recent_rate:.0%} of recent transactions — investigate if signal has degraded",
                    })

        # False positive rate
        fp_count = len(self.false_positives)
        total = len(self.decisions)
        fp_rate = fp_count / total if total > 0 else 0

        return {
            "status": "ok",
            "window_size": len(self._score_history),
            "recent_mean_score": round(recent_mean, 1),
            "recent_std_score": round(recent_std, 1),
            "psi_score": round(psi_score, 3),
            "false_positive_rate": round(fp_rate, 3),
            "confirmed_fraud_count": len(self.confirmed_fraud),
            "drift_alerts": drift_alerts,
            "signal_frequency_alerts": signal_alerts,
            "overall_drift_status": "DRIFT_DETECTED" if drift_alerts else "STABLE",
        }


# ── Feedback Loop ─────────────────────────────────────────────────────────────

class FeedbackStore:
    """
    Layer 6: Analyst-in-the-loop feedback.
    Stores outcomes that update signal weights and Bayesian priors.
    """

    def __init__(self):
        self.feedback_log: list[dict] = []

    def record(self, transaction_id: str, audit_id: str,
               outcome: Literal["fraud_confirmed", "fraud_rejected", "false_positive", "chargeback_confirmed"],
               analyst_id: str = "system",
               notes: str = ""):
        entry = {
            "transaction_id": transaction_id,
            "audit_id": audit_id,
            "outcome": outcome,
            "analyst_id": analyst_id,
            "notes": notes,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.feedback_log.append(entry)
        return entry

    def get_signal_accuracy(self, signal_name: str) -> dict:
        """How accurate has a specific signal been based on confirmed outcomes?"""
        relevant = [f for f in self.feedback_log if signal_name in f.get("signals", [])]
        if not relevant:
            return {"signal": signal_name, "status": "no_feedback_yet"}
        confirmed = sum(1 for f in relevant if f["outcome"] in ("fraud_confirmed", "chargeback_confirmed"))
        return {
            "signal": signal_name,
            "total_triggers": len(relevant),
            "confirmed_fraud": confirmed,
            "precision": round(confirmed / len(relevant), 3) if relevant else 0,
        }

    def summary(self) -> dict:
        total = len(self.feedback_log)
        if total == 0:
            return {"total": 0, "message": "No feedback recorded yet"}
        outcomes = defaultdict(int)
        for f in self.feedback_log:
            outcomes[f["outcome"]] += 1
        return {
            "total_feedback": total,
            "breakdown": dict(outcomes),
            "false_positive_rate": round(outcomes.get("false_positive", 0) / total, 3),
        }


# ── Singletons ────────────────────────────────────────────────────────────────
drift_monitor = DriftMonitor()
feedback_store = FeedbackStore()
