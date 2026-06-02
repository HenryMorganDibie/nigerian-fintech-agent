"""
Decision Engine (separated from Scoring Engine)
================================================
Takes scores, applies business logic, returns decisions + actions.

Rules:
  1. Behavioral score dominates when >= 70 (user acting WAY outside baseline)
  2. Hard overrides — specific signal combos always → CRITICAL
  3. Composite = Bayesian(0.45) + Behavioral(0.30) + Graph(0.25)
  4. Analyst tiers: auto_approve / review_queue / escalate / freeze_and_str
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict, deque
from typing import Literal, Optional
import statistics


@dataclass
class FinalDecision:
    composite_score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    decision: Literal["auto_approve", "review_queue", "escalate", "freeze_and_str"]
    action: str
    signal_score: int
    behavioral_score: int
    graph_score: int
    behavioral_dominated: bool
    hard_override: bool
    override_reason: str
    layer_breakdown: dict
    analyst_notes: list[str] = field(default_factory=list)


# ── Hard Override Rules ───────────────────────────────────────────────────────

HARD_OVERRIDES = [
    {
        "name": "NIN_BVN_HIGH_VALUE",
        "check": lambda sigs, amt: "NIN_BVN_MISMATCH" in sigs and amt > 50_000,
        "action": "🚨 Block + file STR (NFIU) + refer to EFCC Cybercrime — NIN/BVN mismatch is synthetic identity",
    },
    {
        "name": "SIM_SWAP_USSD",
        "check": lambda sigs, amt: "SIM_SWAP_HIGH_VALUE_USSD" in sigs,
        "action": "🚨 Freeze account — require in-person BVN re-verification before any transfer",
    },
    {
        "name": "CIRCULAR_FLOW_LARGE",
        "check": lambda sigs, amt: "ROUND_TRIP_TRANSFER" in sigs and amt > 100_000,
        "action": "🚨 Freeze both accounts — layering detected. File STR with NFIU immediately",
    },
    {
        "name": "CARD_TESTING_DETECTED",
        "check": lambda sigs, amt: "CARD_TESTING" in sigs,
        "action": "🚨 Block card immediately — card testing pattern. Alert card issuer and block card number",
    },
    {
        "name": "MULE_CLUSTER",
        "check": lambda sigs, amt: any("MULE" in s for s in sigs),
        "action": "🚨 Suspend recipient account — mule cluster detected. Escalate to EFCC",
    },
    {
        "name": "STRUCTURING_PLUS_SPLIT",
        "check": lambda sigs, amt: "CBN_STRUCTURING" in sigs and "SPLIT_TRANSACTION_PATTERN" in sigs,
        "action": "🚨 File STR + CTR immediately — structuring with split pattern is deliberate CTR avoidance",
    },
    {
        "name": "NEW_ACCOUNT_EXPLOSION",
        "check": lambda sigs, amt: "NEW_ACCOUNT_HIGH_VALUE" in sigs and "BENEFICIARY_EXPLOSION" in sigs,
        "action": "🚨 Freeze account — new account with rapid beneficiary fan-out. Synthetic account pattern",
    },
]


def apply_decision(
    signal_score: int,
    signal_names: list[str],
    behavioral_score: int,
    graph_score: int,
    amount: float,
    graph_patterns: Optional[list[dict]] = None,
) -> FinalDecision:

    graph_patterns = graph_patterns or []
    all_signals = signal_names + [p.get("type", "") for p in graph_patterns]

    # Rule 1: Behavioral dominance — if user is acting WAY outside baseline
    behavioral_dominated = behavioral_score >= 70
    if behavioral_dominated:
        # Behavioral score takes 60% weight when dominant
        composite = int(signal_score * 0.25 + behavioral_score * 0.60 + graph_score * 0.15)
    else:
        composite = int(signal_score * 0.45 + behavioral_score * 0.30 + graph_score * 0.25)

    composite = max(0, min(100, composite))

    # Rule 2: Hard overrides
    override = False
    override_reason = ""
    override_action = ""
    for rule in HARD_OVERRIDES:
        if rule["check"](all_signals, amount):
            override = True
            override_reason = rule["name"]
            override_action = rule["action"]
            composite = max(composite, 82)
            break

    # Tier assignment
    if composite <= 25:
        risk_level, decision = "low",      "auto_approve"
        action = f"✅ Auto-approve — composite {composite}/100"
    elif composite <= 50:
        risk_level, decision = "medium",   "review_queue"
        action = f"🟡 Review queue — hold for analyst. Score {composite}/100"
    elif composite <= 75:
        risk_level, decision = "high",     "escalate"
        action = f"🔴 Compliance escalation — hold transaction. Score {composite}/100"
    else:
        risk_level, decision = "critical", "freeze_and_str"
        action = override_action or f"🚨 Freeze + STR — score {composite}/100"

    notes = []
    if behavioral_dominated:
        notes.append(f"Behavioral deviation ({behavioral_score}/100) dominated scoring — user acting outside their baseline")
    if override:
        notes.append(f"Hard override: {override_reason}")
    if graph_score > 50:
        notes.append("Graph-level risk elevated — check network fraud connections")

    return FinalDecision(
        composite_score=composite,
        risk_level=risk_level,
        decision=decision,
        action=action,
        signal_score=signal_score,
        behavioral_score=behavioral_score,
        graph_score=graph_score,
        behavioral_dominated=behavioral_dominated,
        hard_override=override,
        override_reason=override_reason,
        layer_breakdown={
            "signal":     {"score": signal_score,     "weight": "60%" if behavioral_dominated else "45%"},
            "behavioral": {"score": behavioral_score, "weight": "15%" if behavioral_dominated else "30%", "dominated": behavioral_dominated},
            "graph":      {"score": graph_score,      "weight": "25%"},
            "composite":  composite,
        },
        analyst_notes=notes,
    )


# ── Drift Monitor ─────────────────────────────────────────────────────────────

class DriftMonitor:
    def __init__(self, window: int = 500):
        self.window = window
        self.decisions: deque = deque(maxlen=window)
        self.signal_hits: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self.confirmed_fraud: deque = deque(maxlen=window)
        self.false_positives: deque = deque(maxlen=window)
        self._scores: deque = deque(maxlen=window)
        self.baseline_fraud_rate = 0.023

    def record(self, score: int, signals: list[str], risk_level: str, amount: float):
        self._scores.append(score)
        self.decisions.append({"score": score, "risk_level": risk_level, "amount": amount, "signals": signals})
        for s in signals:
            self.signal_hits[s].append(1)

    def record_feedback(self, outcome: str):
        if outcome in ("fraud_confirmed", "chargeback_confirmed"):
            self.confirmed_fraud.append(1)
        elif outcome == "false_positive":
            self.false_positives.append(1)

    def report(self) -> dict:
        scores = list(self._scores)
        if len(scores) < 20:
            return {"status": "insufficient_data", "need": 20 - len(scores)}

        recent = scores[-50:] if len(scores) >= 50 else scores
        baseline = scores[:50] if len(scores) >= 100 else scores[:max(1, len(scores)//2)]
        recent_mean = statistics.mean(recent)
        baseline_mean = statistics.mean(baseline)
        psi = abs(recent_mean - baseline_mean) / max(baseline_mean, 1)

        alerts = []
        if psi > 0.25:
            alerts.append({"type": "SCORE_DRIFT", "severity": "high", "psi": round(psi, 3), "detail": "Risk score distribution shifted — new fraud pattern may be emerging"})
        elif psi > 0.10:
            alerts.append({"type": "SCORE_SHIFT", "severity": "medium", "psi": round(psi, 3), "detail": "Moderate score shift — monitor closely"})

        recent_100 = list(self.decisions)[-100:]
        if recent_100:
            high_risk_rate = sum(1 for d in recent_100 if d["risk_level"] in ("high", "critical")) / len(recent_100)
            if high_risk_rate > self.baseline_fraud_rate * 3:
                alerts.append({"type": "FRAUD_RATE_SPIKE", "severity": "critical", "rate": round(high_risk_rate, 3), "detail": f"Fraud rate {high_risk_rate:.1%} is {high_risk_rate/self.baseline_fraud_rate:.1f}× baseline — possible coordinated attack"})

        total = len(self.decisions)
        fp_count = len(self.false_positives)
        return {
            "status": "ok",
            "window": len(scores),
            "recent_mean_score": round(recent_mean, 1),
            "psi": round(psi, 3),
            "false_positive_rate": round(fp_count / total, 3) if total > 0 else 0,
            "confirmed_fraud": len(self.confirmed_fraud),
            "drift_status": "DRIFT_DETECTED" if alerts else "STABLE",
            "alerts": alerts,
        }


class FeedbackStore:
    def __init__(self):
        self.log: list[dict] = []

    def record(self, transaction_id: str, audit_id: str, outcome: str,
               analyst_id: str = "system", notes: str = "") -> dict:
        entry = {"transaction_id": transaction_id, "audit_id": audit_id,
                 "outcome": outcome, "analyst_id": analyst_id, "notes": notes,
                 "recorded_at": datetime.now(timezone.utc).isoformat()}
        self.log.append(entry)
        return entry

    def summary(self) -> dict:
        total = len(self.log)
        if not total:
            return {"total": 0}
        from collections import Counter
        outcomes = Counter(e["outcome"] for e in self.log)
        return {"total": total, "breakdown": dict(outcomes),
                "false_positive_rate": round(outcomes.get("false_positive", 0) / total, 3)}


drift_monitor = DriftMonitor()
feedback_store = FeedbackStore()
