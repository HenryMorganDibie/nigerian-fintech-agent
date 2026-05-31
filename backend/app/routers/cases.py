from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Optional
from app.core.case_queue import CaseQueue

router = APIRouter(prefix="/api/cases", tags=["case queue"])

_queue = CaseQueue()


class CreateCaseRequest(BaseModel):
    """Pass the full fraud analysis result dict."""
    transaction_id: str
    audit_log_id: str
    risk_level: str
    composite_score: int
    signals_triggered: list[str] = []
    amount_ngn: float = 0
    recommended_action: str = ""
    channel: str = "transfer"
    narration: str = ""


class AssignRequest(BaseModel):
    analyst_id: str


class NoteRequest(BaseModel):
    author: str = "analyst"
    content: str


class EscalateRequest(BaseModel):
    reason: str
    analyst_id: str = "system"


class ResolveRequest(BaseModel):
    outcome: Literal["fraud", "false_positive"]
    analyst_id: str
    resolution_notes: str = ""


@router.post("/create")
async def create_case(req: CreateCaseRequest):
    """Create a fraud investigation case from an analysis result."""
    case = _queue.create_case({
        "transaction_id": req.transaction_id,
        "audit_log_id":   req.audit_log_id,
        "risk_level":     req.risk_level,
        "composite_score": req.composite_score,
        "amount_ngn":     req.amount_ngn,
        "channel":        req.channel,
        "narration":      req.narration,
        "recommended_action": req.recommended_action,
        "regulatory_filings": [],
        "explainability": {
            "top_reason_codes": [{"signal": s} for s in req.signals_triggered[:3]],
            "recommended_action": req.recommended_action,
        },
    })
    return case.to_dict()


@router.get("/list")
async def list_cases(status: Optional[str] = None, priority: Optional[str] = None, limit: int = 50):
    cases = _queue.list_cases(status=status, priority=priority, limit=limit)
    return {"cases": cases, "total": len(cases)}


@router.get("/stats/summary")
async def case_stats():
    all_cases = _queue.list_cases(limit=1000)
    from collections import Counter
    statuses  = Counter(c["status"]   for c in all_cases)
    priorities = Counter(c["priority"] for c in all_cases)
    return {
        "total": len(all_cases),
        "by_status":   dict(statuses),
        "by_priority": dict(priorities),
        "open":      statuses.get("open", 0),
        "escalated": statuses.get("escalated", 0),
        "resolved":  sum(v for k, v in statuses.items() if k.startswith("resolved")),
    }


@router.get("/{case_id}")
async def get_case(case_id: str):
    case = _queue.get_case(case_id)
    if not case:
        return {"error": f"Case {case_id} not found"}
    return case.to_dict()


@router.post("/{case_id}/assign")
async def assign_case(case_id: str, req: AssignRequest):
    case = _queue.assign(case_id, req.analyst_id)
    if not case:
        return {"error": f"Case {case_id} not found"}
    return {"status": "assigned", "case": case.to_dict()}


@router.post("/{case_id}/note")
async def add_note(case_id: str, req: NoteRequest):
    note = _queue.add_note(case_id, req.author, req.content)
    if not note:
        return {"error": f"Case {case_id} not found"}
    return {"status": "note added", "note": {"author": note.author, "content": note.content}}


@router.post("/{case_id}/escalate")
async def escalate_case(case_id: str, req: EscalateRequest):
    case = _queue.escalate(case_id, req.reason, req.analyst_id)
    if not case:
        return {"error": f"Case {case_id} not found"}
    return {"status": "escalated", "case_id": case_id}


@router.post("/{case_id}/resolve")
async def resolve_case(case_id: str, req: ResolveRequest):
    case = _queue.resolve(case_id, req.outcome, req.analyst_id, req.resolution_notes)
    if not case:
        return {"error": f"Case {case_id} not found"}
    return {"status": "resolved", "outcome": req.outcome, "case_id": case_id}


@router.get("/{case_id}/str-draft")
async def str_draft(case_id: str):
    draft = _queue.generate_str_draft(case_id)
    if not draft:
        return {"error": f"Case {case_id} not found"}
    return {"case_id": case_id, "str_draft": draft}
