"""
Case Queue — Fraud Investigation Workflow
==========================================
Turns NaijaFinAI from a detector into a fraud operations platform.

Features:
- Case creation from fraud analysis results
- Assign to investigator
- Notes and comments
- Approve / Reject / Escalate actions
- STR draft generation
- Resolution tracking
- Export case summary
- In-memory store (swap for PostgreSQL in production)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional
from collections import defaultdict
import uuid
import json


CaseStatus = Literal["open", "under_review", "escalated", "resolved_fraud", "resolved_false_positive", "closed"]
CaseAction = Literal["approve", "reject", "escalate", "assign", "add_note", "resolve_fraud", "resolve_fp"]


@dataclass
class CaseNote:
    note_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    author: str = "analyst"
    content: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FraudCase:
    case_id: str
    transaction_id: str
    risk_score: int
    risk_level: str
    composite_score: int
    amount_ngn: float
    channel: str
    narration: str
    top_signals: list[dict]
    recommended_action: str
    regulatory_filings: list[dict]
    audit_log_id: str
    explainability: dict

    status: CaseStatus = "open"
    assigned_to: Optional[str] = None
    notes: list[CaseNote] = field(default_factory=list)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolution: Optional[str] = None
    str_draft: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "transaction_id": self.transaction_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "composite_score": self.composite_score,
            "amount_ngn": self.amount_ngn,
            "channel": self.channel,
            "narration": self.narration,
            "top_signals": self.top_signals,
            "recommended_action": self.recommended_action,
            "regulatory_filings": self.regulatory_filings,
            "audit_log_id": self.audit_log_id,
            "explainability": self.explainability,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "notes": [{"note_id": n.note_id, "author": n.author, "content": n.content, "timestamp": n.timestamp} for n in self.notes],
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
            "resolution": self.resolution,
            "str_draft": self.str_draft,
        }


class CaseQueue:
    def __init__(self):
        self._cases: dict[str, FraudCase] = {}
        self._by_status: dict[str, list[str]] = defaultdict(list)

    def create_case(self, fraud_analysis_result: dict) -> FraudCase:
        """Create a case from a fraud analysis result."""
        explain = fraud_analysis_result.get("explainability", {})
        risk_level = fraud_analysis_result.get("risk_level", "medium")

        priority_map = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}

        case = FraudCase(
            case_id=f"CASE-{str(uuid.uuid4())[:8].upper()}",
            transaction_id=fraud_analysis_result.get("transaction_id", ""),
            risk_score=fraud_analysis_result.get("composite_score", 0),
            risk_level=risk_level,
            composite_score=fraud_analysis_result.get("composite_score", 0),
            amount_ngn=fraud_analysis_result.get("amount_ngn", 0),
            channel=fraud_analysis_result.get("channel", ""),
            narration=fraud_analysis_result.get("narration", ""),
            top_signals=explain.get("top_reason_codes", []),
            recommended_action=explain.get("recommended_action", ""),
            regulatory_filings=fraud_analysis_result.get("regulatory_filings", []),
            audit_log_id=fraud_analysis_result.get("audit_log_id", ""),
            explainability=explain,
            priority=priority_map.get(risk_level, "medium"),
            status="open" if risk_level in ("medium",) else "escalated" if risk_level == "critical" else "open",
        )
        self._cases[case.case_id] = case
        self._by_status[case.status].append(case.case_id)
        return case

    def get_case(self, case_id: str) -> Optional[FraudCase]:
        return self._cases.get(case_id)

    def list_cases(self, status: Optional[str] = None, assigned_to: Optional[str] = None,
                   priority: Optional[str] = None, limit: int = 50) -> list[dict]:
        cases = list(self._cases.values())
        if status:
            cases = [c for c in cases if c.status == status]
        if assigned_to:
            cases = [c for c in cases if c.assigned_to == assigned_to]
        if priority:
            cases = [c for c in cases if c.priority == priority]
        # Sort by priority then created_at
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        cases.sort(key=lambda c: (priority_order.get(c.priority, 2), c.created_at))
        return [c.to_dict() for c in cases[:limit]]

    def assign(self, case_id: str, analyst_id: str) -> Optional[FraudCase]:
        case = self._cases.get(case_id)
        if not case: return None
        case.assigned_to = analyst_id
        case.status = "under_review"
        case.updated_at = datetime.now(timezone.utc).isoformat()
        case.notes.append(CaseNote(author="system", content=f"Case assigned to {analyst_id}"))
        return case

    def add_note(self, case_id: str, author: str, content: str) -> Optional[CaseNote]:
        case = self._cases.get(case_id)
        if not case: return None
        note = CaseNote(author=author, content=content)
        case.notes.append(note)
        case.updated_at = datetime.now(timezone.utc).isoformat()
        return note

    def escalate(self, case_id: str, reason: str, analyst_id: str = "system") -> Optional[FraudCase]:
        case = self._cases.get(case_id)
        if not case: return None
        case.status = "escalated"
        case.priority = "critical"
        case.updated_at = datetime.now(timezone.utc).isoformat()
        case.notes.append(CaseNote(author=analyst_id, content=f"ESCALATED: {reason}"))
        return case

    def resolve(self, case_id: str, outcome: Literal["fraud", "false_positive"],
                analyst_id: str, resolution_notes: str = "") -> Optional[FraudCase]:
        case = self._cases.get(case_id)
        if not case: return None
        case.status = "resolved_fraud" if outcome == "fraud" else "resolved_false_positive"
        case.resolved_at = datetime.now(timezone.utc).isoformat()
        case.updated_at = case.resolved_at
        case.resolution = f"{outcome.upper()}: {resolution_notes}"
        case.notes.append(CaseNote(author=analyst_id, content=f"Resolved as {outcome}. {resolution_notes}"))
        return case

    def generate_str_draft(self, case_id: str) -> Optional[str]:
        """Generate a CBN-compliant STR draft for the case."""
        case = self._cases.get(case_id)
        if not case: return None

        signals_text = "\n".join(
            f"  - {s.get('label', s.get('signal', ''))} (score contribution: {s.get('score_contribution', 0)})"
            for s in case.top_signals[:3]
        )
        cbn_refs = [s.get("cbn_reference", "") for s in case.top_signals if s.get("cbn_reference")]

        str_draft = f"""
SUSPICIOUS TRANSACTION REPORT (STR)
Filed pursuant to CBN AML/CFT Regulations 2022, Section 4.1
Nigerian Financial Intelligence Unit (NFIU) — goaml.nfiu.gov.ng

FILING DETAILS
──────────────────────────────────────────
Date of Filing:        {datetime.now(timezone.utc).strftime('%d %B %Y')}
Case Reference:        {case.case_id}
Reporting Institution: [INSTITUTION NAME]
Report Prepared By:    {case.assigned_to or '[ANALYST NAME]'}

TRANSACTION DETAILS
──────────────────────────────────────────
Transaction ID:        {case.transaction_id}
Amount:                ₦{case.amount_ngn:,.2f}
Channel:               {case.channel.upper()}
Narration:             {case.narration or 'Not provided'}
Risk Score:            {case.composite_score}/100 ({case.risk_level.upper()})
Audit Log ID:          {case.audit_log_id}

SUSPICIOUS ACTIVITY DESCRIPTION
──────────────────────────────────────────
The above transaction was identified as suspicious by the NaijaFinAI
automated fraud intelligence system. The following indicators were detected:

{signals_text}

The transaction was flagged based on Nigerian-specific fraud typologies
consistent with {', '.join([s.get('signal', '') for s in case.top_signals[:2]])} patterns.

REGULATORY REFERENCES
──────────────────────────────────────────
{chr(10).join(f'  - {r}' for r in cbn_refs if r)}

RECOMMENDED ACTION
──────────────────────────────────────────
{case.recommended_action}

ANALYST NOTES
──────────────────────────────────────────
{chr(10).join(f'[{n.timestamp[:10]}] {n.author}: {n.content}' for n in case.notes[-3:])}

──────────────────────────────────────────
This report is filed in compliance with the Money Laundering (Prevention
and Prohibition) Act 2022 and CBN AML/CFT Regulations 2022.
Confidential — Not for public disclosure.
""".strip()

        case.str_draft = str_draft
        case.updated_at = datetime.now(timezone.utc).isoformat()
        return str_draft

    def get_stats(self) -> dict:
        cases = list(self._cases.values())
        total = len(cases)
        status_counts = defaultdict(int)
        for c in cases:
            status_counts[c.status] += 1
        fraud_confirmed = sum(1 for c in cases if c.status == "resolved_fraud")
        false_positives = sum(1 for c in cases if c.status == "resolved_false_positive")
        total_resolved = fraud_confirmed + false_positives
        return {
            "total_cases": total,
            "open": status_counts["open"],
            "under_review": status_counts["under_review"],
            "escalated": status_counts["escalated"],
            "resolved_fraud": fraud_confirmed,
            "resolved_false_positive": false_positives,
            "precision": round(fraud_confirmed / total_resolved, 3) if total_resolved > 0 else 0,
            "false_positive_rate": round(false_positives / total_resolved, 3) if total_resolved > 0 else 0,
        }


# Singleton
case_queue = CaseQueue()
