"""
Persistence layer
==================
SQLAlchemy 2.x models for the platform API. SQLite for local development,
Postgres in production (DATABASE_URL=postgresql+psycopg://...).

Tables:
  tenants       — one row per fintech customer, carries shadow/live mode
  api_keys      — SHA-256 hashes only; the plaintext key is shown once at creation
  decisions     — every scored transaction, unique per (tenant, idempotency_key)
  audit_events  — append-only, hash-chained per tenant (tamper-evident)
"""

from __future__ import annotations

import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, create_engine, select, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ten"))
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(10), default="shadow")   # shadow | live
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("key"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="default")
    prefix: Mapped[str] = mapped_column(String(20))                    # shown in dashboards, not secret
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_decision_idempotency"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("dec"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[str] = mapped_column(String(255), index=True)
    customer_ref: Mapped[str] = mapped_column(String(64), index=True)   # keyed hash, never raw account id
    amount_ngn: Mapped[float] = mapped_column(Float)
    channel: Mapped[str] = mapped_column(String(50))
    score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(10))
    recommended_action: Mapped[str] = mapped_column(String(10))
    enforced_action: Mapped[str] = mapped_column(String(10))
    mode: Mapped[str] = mapped_column(String(10))
    model_version: Mapped[str] = mapped_column(String(50))
    latency_ms: Mapped[float] = mapped_column(Float)
    response: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # fraud | legit
    labelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (UniqueConstraint("tenant_id", "seq", name="uq_audit_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(40), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(50))
    subject_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))   # ISO string: hashed verbatim, so no tz round-trip drift
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


# ── Engine / session management ──────────────────────────────────────────────

_engine = None
_SessionLocal: Optional[sessionmaker] = None


def normalise_url(url: str) -> str:
    """Hosting platforms hand out postgres:// URLs; route them to the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def configure(database_url: Optional[str] = None) -> None:
    """(Re)initialise the engine. Called at startup and by tests."""
    global _engine, _SessionLocal
    url = normalise_url(database_url or settings.database_url)
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    _engine = create_engine(url, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


def engine():
    if _engine is None:
        configure()
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    if _SessionLocal is None:
        configure()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        configure()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def advisory_lock(session: Session, *parts: str) -> None:
    """
    Transaction-scoped mutual exclusion keyed on `parts`, released at commit or
    rollback. Postgres only; SQLite already serialises writers, so it is a no-op.
    Callers must always take locks in the same order to avoid deadlocks:
    idempotency key first, then the tenant's audit chain.
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.sha256("\x1f".join(parts).encode()).digest()
    key = int.from_bytes(digest[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})


def ping() -> bool:
    try:
        with engine().connect() as conn:
            conn.execute(select(1))
        return True
    except Exception:
        return False
