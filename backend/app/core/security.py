"""
API-key authentication and tenant resolution
==============================================
Keys look like `nfa_live_<43 url-safe chars>`. Only the SHA-256 hash is stored;
the plaintext is returned exactly once, at creation. Keys carry ~256 bits of
entropy, so a fast hash is appropriate (no password-style KDF needed).

Clients send the key as `Authorization: Bearer <key>` or `X-API-Key: <key>`.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import ApiKey, Tenant, get_session, utcnow

KEY_PREFIX = "nfa_live_"
_LAST_USED_RESOLUTION = timedelta(minutes=1)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def issue_api_key(db: Session, tenant_id: str, name: str = "default") -> tuple[ApiKey, str]:
    raw = generate_key()
    key = ApiKey(tenant_id=tenant_id, name=name, prefix=raw[:16], key_hash=hash_key(raw))
    db.add(key)
    db.flush()
    return key, raw


def customer_ref(tenant_id: str, account_id: str) -> str:
    """Keyed, tenant-scoped pseudonym for an account id (NDPA data minimisation)."""
    msg = f"{tenant_id}:{account_id}".encode()
    return hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()


def _extract_key(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def require_tenant(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_session),
) -> Tenant:
    raw = _extract_key(authorization, x_api_key)
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_api_key", "message": "Missing, invalid or revoked API key."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not raw:
        raise unauthorized
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
    if key is None or key.revoked_at is not None:
        raise unauthorized
    tenant = db.get(Tenant, key.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"code": "tenant_disabled", "message": "This tenant is disabled."})
    now = utcnow()
    last = key.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)
    if last is None or now - last > _LAST_USED_RESOLUTION:
        key.last_used_at = now
        db.commit()
    return tenant


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"code": "invalid_admin_token", "message": "Invalid admin token."})
