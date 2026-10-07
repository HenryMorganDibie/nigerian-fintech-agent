"""
/v1 — authenticated, multi-tenant decisioning API
===================================================
The production integration surface. Every route requires an API key and only
ever reads or writes the calling tenant's data.

  POST /v1/decisions                     score a transaction (idempotent, no LLM)
  GET  /v1/decisions                     list recent decisions
  GET  /v1/decisions/{id}                fetch one decision
  POST /v1/decisions/{id}/labels         record the confirmed outcome (fraud | legit)
  POST /v1/decisions/{id}/explanation    generate the analyst narrative (LLM, off the hot path)
  GET  /v1/metrics/summary               volumes, actions, latency, label agreement
  GET  /v1/audit/verify                  verify the tenant's audit hash chain
  GET  /v1/tenant                        who am I, which mode am I in
"""

import hashlib
import json
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import append_event, verify_chain
from app.core.config import settings
from app.core.pipeline import run_pipeline
from app.core.security import customer_ref, require_tenant
from app.db import Decision, Tenant, advisory_lock, get_session, utcnow
from app.models.schemas import Transaction

router = APIRouter(prefix="/v1", tags=["v1"])

_PERSIST_ATTEMPTS = 5


class DecisionRequest(BaseModel):
    transaction: Transaction
    # Per-request override. A live tenant may force shadow for a single call,
    # but a shadow tenant cannot force enforcement.
    mode: Optional[Literal["shadow", "live"]] = None


class LabelRequest(BaseModel):
    label: Literal["fraud", "legit"]
    source: Literal["analyst", "chargeback", "customer_report", "investigation", "other"] = "analyst"
    notes: str = Field(default="", max_length=2000)


def _request_hash(req: DecisionRequest) -> str:
    body = req.model_dump(mode="json")
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _get_owned(db: Session, tenant: Tenant, decision_id: str) -> Decision:
    d = db.get(Decision, decision_id)
    # A decision belonging to another tenant is indistinguishable from a missing one.
    if d is None or d.tenant_id != tenant.id:
        raise _error(404, "decision_not_found", "No such decision.")
    return d


def _effective_mode(tenant: Tenant, requested: Optional[str]) -> str:
    if tenant.mode == "shadow":
        return "shadow"
    return requested or "live"


@router.post("/decisions")
def create_decision(
    req: DecisionRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, max_length=255),
    tenant: Tenant = Depends(require_tenant),
    db: Session = Depends(get_session),
):
    started = time.perf_counter()
    tx = req.transaction
    key = idempotency_key or f"txn:{tx.transaction_id}"
    req_hash = _request_hash(req)

    existing = _find(db, tenant.id, key)
    if existing is not None:
        return _replay(existing, req_hash, response)
    # Serialise concurrent retries of the same request, then look again: the
    # winner may have committed while we waited. Scoring runs once per key, so
    # behavioural baselines are never double-counted.
    advisory_lock(db, "idempotency", tenant.id, key)
    existing = _find(db, tenant.id, key)
    if existing is not None:
        return _replay(existing, req_hash, response)

    mode = _effective_mode(tenant, req.mode)
    result = run_pipeline(tx, tenant_id=tenant.id)
    recommended = result.action
    enforced = recommended if mode == "live" else "allow"
    sig, dec = result.signals, result.decision

    reason_codes = [
        {"code": t["name"], "severity": t["severity"], "description": t["description"],
         "evidence": t["evidence"], "reference": t["cbn_reference"],
         "recommended_action": t["recommended_action"]}
        for t in sig.top_3
    ]
    # Any triggered signals beyond the top three are still reported, in rank order.
    ranked = {t["name"] for t in sig.top_3}
    reason_codes += [
        {"code": t.name, "severity": t.severity, "description": t.description,
         "evidence": t.evidence, "reference": t.cbn_reference,
         "recommended_action": t.recommended_action}
        for t in sig.triggered if t.name not in ranked
    ]

    payload = {
        "object": "decision",
        "transaction_id": tx.transaction_id,
        "mode": mode,
        "action": enforced,
        "recommended_action": recommended,
        "risk_level": dec.risk_level,
        "score": dec.composite_score,
        "fraud_probability": round(sig.posterior_fraud_probability, 4),
        "reason_codes": reason_codes,
        "hard_override": dec.override_reason or None,
        "layers": {
            "signals": {"score": dec.signal_score},
            "behavioral": {"score": dec.behavioral_score, "factors": result.behavioral.get("factors", []),
                           "dominated": dec.behavioral_dominated},
            "graph": {"score": dec.graph_score, "patterns": result.graph["patterns_detected"]},
        },
        "regulatory_filings": [
            {"filing_type": f.filing_type, "regulatory_body": f.regulatory_body,
             "deadline": f.deadline_description, "urgency_hours": f.urgency_hours}
            for f in result.filings
        ],
        "evaluated_at_wat": result.local_time.isoformat(),
        "model_version": settings.model_version,
    }

    cref = customer_ref(tenant.id, tx.sender_account)
    for _ in range(_PERSIST_ATTEMPTS):
        # A rollback releases transaction-scoped locks, so take it again each attempt.
        advisory_lock(db, "idempotency", tenant.id, key)
        decision = Decision(
            tenant_id=tenant.id, idempotency_key=key, request_hash=req_hash,
            transaction_id=tx.transaction_id, customer_ref=cref, amount_ngn=tx.amount,
            channel=tx.channel, score=dec.composite_score, risk_level=dec.risk_level,
            recommended_action=recommended, enforced_action=enforced, mode=mode,
            model_version=settings.model_version, latency_ms=0.0, response={},
        )
        db.add(decision)
        db.flush()
        audit = append_event(db, tenant.id, "decision.created", decision.id, {
            "decision_id": decision.id, "transaction_id": tx.transaction_id, "customer_ref": cref,
            "amount_ngn": tx.amount, "score": dec.composite_score, "risk_level": dec.risk_level,
            "recommended_action": recommended, "enforced_action": enforced, "mode": mode,
            "reason_codes": [r["code"] for r in reason_codes], "model_version": settings.model_version,
        })
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        body = {"id": decision.id, **payload, "latency_ms": latency_ms,
                "audit": {"seq": audit.seq, "hash": audit.hash},
                "created_at": decision.created_at.isoformat()}
        decision.latency_ms = latency_ms
        decision.response = body
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Either a concurrent request with the same idempotency key won,
            # or another writer took this audit sequence number. Re-check.
            existing = _find(db, tenant.id, key)
            if existing is not None:
                return _replay(existing, req_hash, response)
            continue
        response.status_code = 201
        return body
    raise _error(503, "persist_conflict", "Could not persist the decision; retry with the same Idempotency-Key.")


def _find(db: Session, tenant_id: str, key: str) -> Optional[Decision]:
    return db.scalar(select(Decision).where(Decision.tenant_id == tenant_id, Decision.idempotency_key == key))


def _replay(existing: Decision, req_hash: str, response: Response) -> dict:
    if existing.request_hash != req_hash:
        raise _error(409, "idempotency_conflict",
                     "This Idempotency-Key (or transaction_id) was already used with a different request body.")
    response.headers["Idempotent-Replayed"] = "true"
    return existing.response


@router.get("/decisions")
def list_decisions(
    limit: int = Query(default=50, ge=1, le=500),
    action: Optional[Literal["allow", "review", "hold", "block"]] = None,
    tenant: Tenant = Depends(require_tenant),
    db: Session = Depends(get_session),
):
    q = select(Decision).where(Decision.tenant_id == tenant.id)
    if action:
        q = q.where(Decision.recommended_action == action)
    rows = db.scalars(q.order_by(Decision.created_at.desc()).limit(limit)).all()
    return {"object": "list", "data": [_with_label(d) for d in rows]}


@router.get("/decisions/{decision_id}")
def get_decision(decision_id: str, tenant: Tenant = Depends(require_tenant), db: Session = Depends(get_session)):
    return _with_label(_get_owned(db, tenant, decision_id))


def _with_label(d: Decision) -> dict:
    return {**d.response, "label": d.label, "explanation": d.explanation}


@router.post("/decisions/{decision_id}/labels")
def label_decision(decision_id: str, req: LabelRequest,
                   tenant: Tenant = Depends(require_tenant), db: Session = Depends(get_session)):
    for _ in range(_PERSIST_ATTEMPTS):
        d = _get_owned(db, tenant, decision_id)
        previous = d.label
        d.label = req.label
        d.labelled_at = utcnow()
        audit = append_event(db, tenant.id, "decision.labelled", d.id, {
            "decision_id": d.id, "label": req.label, "previous_label": previous,
            "source": req.source, "notes": req.notes,
        })
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return {"id": d.id, "label": d.label, "previous_label": previous,
                "audit": {"seq": audit.seq, "hash": audit.hash}}
    raise _error(503, "persist_conflict", "Could not record the label; retry.")


@router.post("/decisions/{decision_id}/explanation")
def explain_decision(decision_id: str, tenant: Tenant = Depends(require_tenant),
                     db: Session = Depends(get_session)):
    """
    Analyst-facing narrative. Runs only on request, never inside scoring, and
    only sees the stored, pseudonymised decision (no account numbers or BVN/NIN).
    """
    d = _get_owned(db, tenant, decision_id)
    if d.explanation:
        return {"id": d.id, "explanation": d.explanation, "cached": True}

    from app.core.compliance import scrub_pii_for_llm
    from app.core.llm_factory import get_llm_with_fallback
    from app.core.prompts import FRAUD_SYSTEM_PROMPT
    from langchain_core.messages import HumanMessage, SystemMessage

    r = d.response
    context = scrub_pii_for_llm({
        "amount_ngn": d.amount_ngn, "channel": d.channel, "score": r["score"],
        "risk_level": r["risk_level"], "recommended_action": r["recommended_action"],
        "reason_codes": [{"code": c["code"], "evidence": c["evidence"], "reference": c["reference"]}
                         for c in r["reason_codes"]],
        "behavioral_factors": r["layers"]["behavioral"]["factors"],
        "graph_patterns": [p.get("type", "") + ": " + p.get("detail", "") for p in r["layers"]["graph"]["patterns"]],
        "regulatory_filings": r["regulatory_filings"],
    })
    try:
        llm = get_llm_with_fallback(provider=settings.default_llm_provider)
        out = llm.invoke([
            SystemMessage(content=FRAUD_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Fraud decision {d.id}:\n\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
                "Write the compliance officer report using ONLY the evidence above. "
                "Do not add signals or evidence that are not listed."
            )),
        ])
    except Exception as exc:
        raise _error(503, "explanation_unavailable", f"No LLM provider available: {type(exc).__name__}")

    d.explanation = out.content.strip()
    append_event(db, tenant.id, "decision.explained", d.id,
                 {"decision_id": d.id, "provider": settings.default_llm_provider,
                  "explanation_sha256": hashlib.sha256(d.explanation.encode()).hexdigest()})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"id": d.id, "explanation": d.explanation, "cached": False}


@router.get("/metrics/summary")
def metrics_summary(tenant: Tenant = Depends(require_tenant), db: Session = Depends(get_session)):
    base = select(Decision).where(Decision.tenant_id == tenant.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    by_action = dict(db.execute(
        select(Decision.recommended_action, func.count()).where(Decision.tenant_id == tenant.id)
        .group_by(Decision.recommended_action)).all())
    latencies = sorted(db.scalars(
        select(Decision.latency_ms).where(Decision.tenant_id == tenant.id)
        .order_by(Decision.created_at.desc()).limit(5000)).all())

    def pct(p: float) -> Optional[float]:
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, int(round(p * (len(latencies) - 1))))]

    # Label agreement: a flag is any recommendation other than allow.
    rows = db.execute(select(Decision.recommended_action, Decision.label)
                      .where(Decision.tenant_id == tenant.id, Decision.label.is_not(None))).all()
    tp = sum(1 for a, l in rows if a != "allow" and l == "fraud")
    fp = sum(1 for a, l in rows if a != "allow" and l == "legit")
    fn = sum(1 for a, l in rows if a == "allow" and l == "fraud")
    tn = sum(1 for a, l in rows if a == "allow" and l == "legit")
    labelled = len(rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None

    return {
        "tenant_id": tenant.id, "mode": tenant.mode, "model_version": settings.model_version,
        "decisions": total,
        "recommended_actions": {a: by_action.get(a, 0) for a in ("allow", "review", "hold", "block")},
        "latency_ms": {"p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99), "sample": len(latencies)},
        "labels": {
            "labelled": labelled,
            "confusion": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "note": "Measured only on decisions your team has labelled; not a population estimate.",
        },
    }


@router.get("/audit/verify")
def audit_verify(tenant: Tenant = Depends(require_tenant), db: Session = Depends(get_session)):
    return {"tenant_id": tenant.id, **verify_chain(db, tenant.id)}


@router.get("/tenant")
def whoami(tenant: Tenant = Depends(require_tenant)):
    return {"id": tenant.id, "name": tenant.name, "mode": tenant.mode,
            "created_at": tenant.created_at.isoformat()}
