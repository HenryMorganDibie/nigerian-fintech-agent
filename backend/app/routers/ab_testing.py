"""
A/B Testing Router
===================
Routes fraud analysis requests between different scoring strategies
to measure which performs best in production.

Experiments:
  A — Rule-based only (legacy baseline)
  B — Bayesian scorer only
  C — Full 4-layer (Bayesian + Behavioral + Graph + Overrides)  ← current default

Traffic split is configurable per experiment.
Results tracked per variant for comparison.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Optional
from collections import defaultdict
from datetime import datetime, timezone
from app.models.schemas import Transaction
from app.core.config import settings
import random
import uuid

router = APIRouter(prefix="/api/ab", tags=["A/B Testing"])


# ── Experiment Registry ───────────────────────────────────────────────────────

EXPERIMENTS = {
    "fraud_scoring_strategy": {
        "name": "Fraud Scoring Strategy",
        "description": "Compare rule-based vs Bayesian vs full 4-layer scoring",
        "variants": {
            "A": {"name": "Rule-Based Only",       "weight": 0.20, "strategy": "rules_only"},
            "B": {"name": "Bayesian Only",          "weight": 0.30, "strategy": "bayesian_only"},
            "C": {"name": "Full 4-Layer (Current)", "weight": 0.50, "strategy": "full_pipeline"},
        },
        "active": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    "llm_provider_quality": {
        "name": "LLM Narrative Quality",
        "description": "Compare Groq primary vs fallback model for narrative generation",
        "variants": {
            "A": {"name": "llama-3.3-70b-versatile", "weight": 0.70, "strategy": "groq_primary"},
            "B": {"name": "llama-3.1-8b-instant",    "weight": 0.30, "strategy": "groq_fallback"},
        },
        "active": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
}

# ── Results Store ─────────────────────────────────────────────────────────────
# In production: persist to PostgreSQL or Redis

_results: dict[str, list] = defaultdict(list)


def _assign_variant(experiment_id: str) -> tuple[str, dict]:
    """Randomly assign a variant based on traffic weights."""
    exp = EXPERIMENTS.get(experiment_id)
    if not exp or not exp["active"]:
        return "C", exp["variants"]["C"] if exp else {}

    variants = exp["variants"]
    keys = list(variants.keys())
    weights = [variants[k]["weight"] for k in keys]
    chosen = random.choices(keys, weights=weights, k=1)[0]
    return chosen, variants[chosen]


def _record_result(experiment_id: str, variant: str, result: dict):
    _results[f"{experiment_id}:{variant}"].append({
        **result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 500 per variant
    if len(_results[f"{experiment_id}:{variant}"]) > 500:
        _results[f"{experiment_id}:{variant}"] = _results[f"{experiment_id}:{variant}"][-500:]


# ── Schemas ───────────────────────────────────────────────────────────────────

class ABFraudRequest(BaseModel):
    transaction: Transaction
    experiment_id: str = "fraud_scoring_strategy"
    provider: Optional[str] = None
    force_variant: Optional[Literal["A", "B", "C"]] = None


class ABResultFeedback(BaseModel):
    experiment_id: str
    variant: str
    run_id: str
    outcome: Literal["correct_fraud", "correct_approve", "false_positive", "false_negative"]
    analyst_notes: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/experiments")
async def list_experiments():
    """List all active A/B experiments with current traffic splits."""
    return {
        "experiments": [
            {
                "id": exp_id,
                "name": exp["name"],
                "description": exp["description"],
                "active": exp["active"],
                "variants": {
                    k: {**v, "sample_count": len(_results.get(f"{exp_id}:{k}", []))}
                    for k, v in exp["variants"].items()
                },
            }
            for exp_id, exp in EXPERIMENTS.items()
        ]
    }


@router.post("/fraud/analyze")
async def ab_fraud_analyze(req: ABFraudRequest):
    """
    Run fraud analysis through A/B experiment routing.
    Returns result + variant assignment for comparison.
    """
    provider = req.provider or settings.default_llm_provider
    tx = req.transaction

    # Assign variant
    variant_key, variant_info = _assign_variant(req.experiment_id)
    if req.force_variant:
        variant_key = req.force_variant
        variant_info = EXPERIMENTS[req.experiment_id]["variants"].get(variant_key, variant_info)

    strategy = variant_info.get("strategy", "full_pipeline")
    run_id = str(uuid.uuid4())[:12]

    # ── Run the assigned strategy ─────────────────────────────────────────
    if strategy == "rules_only":
        # Variant A: pure Nigerian rule engine, no Bayesian weighting
        from app.core.nigeria_intelligence import evaluate_transaction
        result = evaluate_transaction(
            amount=tx.amount, channel=tx.channel,
            hour_of_day=tx.timestamp.hour, day_of_week=tx.timestamp.weekday(),
            is_new_recipient=tx.is_new_recipient, is_new_device=tx.is_new_device,
            device_changed_hours_ago=tx.device_changed_hours_ago,
            sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
            transactions_last_hour=tx.transactions_last_hour,
            bvn_verified=tx.bvn_verified, nin_bvn_match=tx.nin_bvn_match,
            narration=tx.narration,
            is_post_loan_disbursement=tx.is_post_loan_disbursement,
            is_agent_terminal=tx.is_agent_terminal,
            agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
            is_pos=tx.is_pos,
            recent_outbound_ngn=tx.recent_outbound_ngn,
            recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
        )
        score_result = {
            "risk_score": result.total_score,
            "risk_level": result.risk_level,
            "recommended_action": result.recommended_action,
            "strategy": "rules_only",
            "signals": [s.name for s in result.triggered_signals],
        }

    elif strategy == "bayesian_only":
        # Variant B: Bayesian scorer only, no behavioral or graph layers
        from app.core.nigeria_intelligence import evaluate_transaction
        from app.core.bayesian_scorer import bayesian_fraud_score
        heuristic = evaluate_transaction(
            amount=tx.amount, channel=tx.channel,
            hour_of_day=tx.timestamp.hour, day_of_week=tx.timestamp.weekday(),
            is_new_recipient=tx.is_new_recipient, is_new_device=tx.is_new_device,
            device_changed_hours_ago=tx.device_changed_hours_ago,
            sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
            transactions_last_hour=tx.transactions_last_hour,
            bvn_verified=tx.bvn_verified, nin_bvn_match=tx.nin_bvn_match,
            narration=tx.narration,
            is_post_loan_disbursement=tx.is_post_loan_disbursement,
            is_agent_terminal=tx.is_agent_terminal,
            agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
            is_pos=tx.is_pos,
            recent_outbound_ngn=tx.recent_outbound_ngn,
            recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
        )
        bayes = bayesian_fraud_score([s.name for s in heuristic.triggered_signals])
        score_result = {
            "risk_score": bayes.risk_score,
            "posterior_fraud_probability": bayes.posterior_fraud_probability,
            "risk_level": bayes.risk_level,
            "recommended_action": bayes.recommended_action,
            "strategy": "bayesian_only",
            "top_3_signals": bayes.top_3_signals,
        }

    else:
        # Variant C: Full 4-layer pipeline (production default)
        from app.core.nigeria_intelligence import evaluate_transaction
        from app.core.bayesian_scorer import bayesian_fraud_score
        from app.core.feature_store import compute_behavioral_deviation
        from app.core.fraud_graph import analyze_graph_risk, record_transaction_edge
        from app.core.decision_engine import apply_decision_engine
        heuristic = evaluate_transaction(
            amount=tx.amount, channel=tx.channel,
            hour_of_day=tx.timestamp.hour, day_of_week=tx.timestamp.weekday(),
            is_new_recipient=tx.is_new_recipient, is_new_device=tx.is_new_device,
            device_changed_hours_ago=tx.device_changed_hours_ago,
            sim_replaced_hours_ago=tx.sim_replaced_hours_ago,
            transactions_last_hour=tx.transactions_last_hour,
            bvn_verified=tx.bvn_verified, nin_bvn_match=tx.nin_bvn_match,
            narration=tx.narration,
            is_post_loan_disbursement=tx.is_post_loan_disbursement,
            is_agent_terminal=tx.is_agent_terminal,
            agent_tx_count_last_hour=tx.agent_tx_count_last_hour,
            is_pos=tx.is_pos,
            recent_outbound_ngn=tx.recent_outbound_ngn,
            recent_inbound_from_same_ngn=tx.recent_inbound_from_same_ngn,
        )
        triggered = [s.name for s in heuristic.triggered_signals]
        bayes    = bayesian_fraud_score(triggered)
        behav    = compute_behavioral_deviation(
            user_id=tx.sender_account, amount=tx.amount, channel=tx.channel,
            device_fingerprint=None, beneficiary_account=tx.recipient_account,
            hour_of_day=tx.timestamp.hour,
        )
        graph = analyze_graph_risk(tx.sender_account, tx.recipient_account, amount=tx.amount)
        record_transaction_edge(tx.sender_account, tx.recipient_account, tx.amount)
        decision = apply_decision_engine(
            bayesian_score=bayes.risk_score,
            bayesian_signals=triggered,
            behavioral_score=behav["behavioral_deviation_score"],
            graph_score=graph["graph_risk_score"],
            amount=tx.amount,
        )
        score_result = {
            "composite_score": decision.composite_score,
            "risk_level": decision.risk_level,
            "decision": decision.decision,
            "action": decision.action,
            "hard_override": decision.hard_override,
            "strategy": "full_pipeline",
            "layer_breakdown": decision.layer_breakdown,
        }

    # Record result for comparison
    _record_result(req.experiment_id, variant_key, {
        "run_id": run_id,
        "variant": variant_key,
        "score": score_result.get("composite_score") or score_result.get("risk_score"),
        "risk_level": score_result.get("risk_level"),
        "amount": tx.amount,
        "channel": tx.channel,
    })

    return {
        "run_id": run_id,
        "experiment_id": req.experiment_id,
        "variant_assigned": variant_key,
        "variant_name": variant_info.get("name"),
        "strategy": strategy,
        "result": score_result,
        "ab_meta": {
            "traffic_weight": variant_info.get("weight"),
            "sample_count_this_variant": len(_results.get(f"{req.experiment_id}:{variant_key}", [])),
        }
    }


@router.get("/results/{experiment_id}")
async def get_experiment_results(experiment_id: str):
    """
    Compare results across variants for an experiment.
    Shows risk score distributions and decision breakdowns per variant.
    """
    exp = EXPERIMENTS.get(experiment_id)
    if not exp:
        return {"error": f"Experiment '{experiment_id}' not found"}

    summary = {}
    for variant_key, variant_info in exp["variants"].items():
        key = f"{experiment_id}:{variant_key}"
        samples = _results.get(key, [])
        if not samples:
            summary[variant_key] = {"name": variant_info["name"], "samples": 0}
            continue

        scores = [s["score"] for s in samples if s.get("score") is not None]
        risk_levels = defaultdict(int)
        for s in samples:
            risk_levels[s.get("risk_level", "unknown")] += 1

        summary[variant_key] = {
            "name": variant_info["name"],
            "strategy": variant_info["strategy"],
            "samples": len(samples),
            "avg_risk_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "risk_level_distribution": dict(risk_levels),
            "critical_rate": round(risk_levels.get("critical", 0) / len(samples), 3),
            "low_rate":      round(risk_levels.get("low", 0) / len(samples), 3),
        }

    return {
        "experiment_id": experiment_id,
        "experiment_name": exp["name"],
        "total_samples": sum(v.get("samples", 0) for v in summary.values()),
        "variants": summary,
        "winner": max(summary.items(), key=lambda x: x[1].get("samples", 0))[0] if summary else None,
    }


@router.post("/feedback")
async def record_ab_feedback(req: ABResultFeedback):
    """Record analyst outcome for a specific A/B run."""
    key = f"{req.experiment_id}:{req.variant}"
    for result in _results.get(key, []):
        if result.get("run_id") == req.run_id:
            result["outcome"] = req.outcome
            result["analyst_notes"] = req.analyst_notes
            break
    return {"status": "recorded", "experiment_id": req.experiment_id, "variant": req.variant}
