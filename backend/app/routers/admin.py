"""
/v1/admin — operator endpoints for onboarding tenants and managing keys.
Disabled unless ADMIN_TOKEN is set; authenticated with the X-Admin-Token header.
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import append_event
from app.core.config import settings
from app.core.security import issue_api_key, require_admin
from app.db import ApiKey, Tenant, get_session, utcnow

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mode: Optional[Literal["shadow", "live"]] = None


class TenantUpdate(BaseModel):
    mode: Optional[Literal["shadow", "live"]] = None
    active: Optional[bool] = None


class KeyCreate(BaseModel):
    name: str = Field(default="default", max_length=200)


def _tenant_or_404(db: Session, tenant_id: str) -> Tenant:
    t = db.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "No such tenant."})
    return t


def _tenant_out(t: Tenant) -> dict:
    return {"id": t.id, "name": t.name, "mode": t.mode, "active": t.active, "created_at": t.created_at.isoformat()}


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "conflict", "message": "Concurrent update; retry."})


@router.post("/tenants", status_code=201)
def create_tenant(req: TenantCreate, db: Session = Depends(get_session)):
    tenant = Tenant(name=req.name, mode=req.mode or settings.default_tenant_mode)
    db.add(tenant)
    db.flush()
    key, raw = issue_api_key(db, tenant.id)
    append_event(db, tenant.id, "tenant.created", tenant.id, {"name": tenant.name, "mode": tenant.mode})
    append_event(db, tenant.id, "api_key.created", key.id, {"key_id": key.id, "prefix": key.prefix, "name": key.name})
    _commit(db)
    return {"tenant": _tenant_out(tenant),
            "api_key": {"id": key.id, "key": raw, "prefix": key.prefix,
                        "warning": "Store this key now. It cannot be shown again."}}


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_session)):
    return {"data": [_tenant_out(t) for t in db.scalars(select(Tenant).order_by(Tenant.created_at)).all()]}


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: str, req: TenantUpdate, db: Session = Depends(get_session)):
    t = _tenant_or_404(db, tenant_id)
    changes = req.model_dump(exclude_none=True)
    before = {k: getattr(t, k) for k in changes}
    for k, v in changes.items():
        setattr(t, k, v)
    if changes:
        append_event(db, t.id, "tenant.updated", t.id, {"before": before, "after": changes})
    _commit(db)
    return _tenant_out(t)


@router.post("/tenants/{tenant_id}/keys", status_code=201)
def create_key(tenant_id: str, req: KeyCreate, db: Session = Depends(get_session)):
    _tenant_or_404(db, tenant_id)
    key, raw = issue_api_key(db, tenant_id, req.name)
    append_event(db, tenant_id, "api_key.created", key.id, {"key_id": key.id, "prefix": key.prefix, "name": key.name})
    _commit(db)
    return {"id": key.id, "key": raw, "prefix": key.prefix, "name": key.name,
            "warning": "Store this key now. It cannot be shown again."}


@router.get("/tenants/{tenant_id}/keys")
def list_keys(tenant_id: str, db: Session = Depends(get_session)):
    _tenant_or_404(db, tenant_id)
    keys = db.scalars(select(ApiKey).where(ApiKey.tenant_id == tenant_id).order_by(ApiKey.created_at)).all()
    return {"data": [{"id": k.id, "name": k.name, "prefix": k.prefix,
                      "created_at": k.created_at.isoformat(),
                      "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                      "revoked": k.revoked_at is not None} for k in keys]}


@router.delete("/tenants/{tenant_id}/keys/{key_id}")
def revoke_key(tenant_id: str, key_id: str, db: Session = Depends(get_session)):
    key = db.get(ApiKey, key_id)
    if key is None or key.tenant_id != tenant_id:
        raise HTTPException(404, detail={"code": "key_not_found", "message": "No such key."})
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        append_event(db, tenant_id, "api_key.revoked", key.id, {"key_id": key.id, "prefix": key.prefix})
        _commit(db)
    return {"id": key.id, "revoked": True}
