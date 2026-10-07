"""
Tamper-evident audit log
=========================
Each tenant has an append-only chain of events. Every event stores the hash of
its predecessor, so altering, deleting or reordering any past event breaks
verification from that point on. This gives examiners (CBN, NFIU, NDPC) a
verifiable record of every automated decision and every human label.

hash_n = SHA-256(prev_hash || canonical_json(tenant_id, seq, event_type, subject_id, payload, created_at))
"""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import AuditEvent, advisory_lock, utcnow

GENESIS_HASH = "0" * 64


def _canonical(tenant_id: str, seq: int, event_type: str, subject_id: str, payload: dict, created_at: str) -> bytes:
    body = {"tenant_id": tenant_id, "seq": seq, "event_type": event_type,
            "subject_id": subject_id, "payload": payload, "created_at": created_at}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def compute_hash(prev_hash: str, tenant_id: str, seq: int, event_type: str,
                 subject_id: str, payload: dict, created_at: str) -> str:
    h = hashlib.sha256()
    h.update(prev_hash.encode())
    h.update(_canonical(tenant_id, seq, event_type, subject_id, payload, created_at))
    return h.hexdigest()


def append_event(db: Session, tenant_id: str, event_type: str, subject_id: str, payload: dict) -> AuditEvent:
    """
    Add the next event in the tenant's chain to the session (caller commits).
    Appends are serialised per tenant by an advisory lock held until commit;
    the (tenant_id, seq) unique constraint remains as a backstop.
    """
    advisory_lock(db, "audit", tenant_id)
    last = db.scalar(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.seq.desc()).limit(1)
    )
    seq = (last.seq + 1) if last else 1
    prev_hash = last.hash if last else GENESIS_HASH
    created_at = utcnow().isoformat()
    # Round-trip through JSON so the hashed payload equals what the DB returns later.
    payload = json.loads(json.dumps(payload, default=str))
    event = AuditEvent(
        tenant_id=tenant_id, seq=seq, event_type=event_type, subject_id=subject_id,
        payload=payload, created_at=created_at, prev_hash=prev_hash,
        hash=compute_hash(prev_hash, tenant_id, seq, event_type, subject_id, payload, created_at),
    )
    db.add(event)
    return event


def verify_chain(db: Session, tenant_id: str) -> dict:
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.seq)
    ).all()
    prev = GENESIS_HASH
    for expected_seq, e in enumerate(events, start=1):
        if e.seq != expected_seq:
            return {"valid": False, "events_checked": expected_seq - 1, "broken_at_seq": expected_seq,
                    "reason": "sequence gap (event deleted or reordered)"}
        if e.prev_hash != prev:
            return {"valid": False, "events_checked": expected_seq - 1, "broken_at_seq": e.seq,
                    "reason": "prev_hash does not match predecessor"}
        recomputed = compute_hash(e.prev_hash, e.tenant_id, e.seq, e.event_type, e.subject_id, e.payload, e.created_at)
        if recomputed != e.hash:
            return {"valid": False, "events_checked": expected_seq - 1, "broken_at_seq": e.seq,
                    "reason": "event contents altered"}
        prev = e.hash
    return {"valid": True, "events_checked": len(events), "head_hash": prev}
