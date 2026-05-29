"""
Feature Store — Layer 2 (Behavioral Memory)
=============================================
Stores per-user behavioral features over time windows.
Enables context-aware fraud scoring:
  - ₦500k is normal for User A → low risk
  - ₦500k is anomalous for User B → high risk

In-memory by default. Redis if REDIS_URL is set.
"""

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings


# ── In-memory store (thread-safe enough for single-instance Railway) ─────────
_store: dict[str, dict] = defaultdict(dict)


def _redis():
    """Lazy Redis client — only connects if REDIS_URL is configured."""
    if not settings.redis_url:
        return None
    try:
        import redis
        return redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


def _get(key: str) -> Optional[dict]:
    r = _redis()
    if r:
        val = r.get(key)
        return json.loads(val) if val else None
    return _store.get(key)


def _set(key: str, value: dict, ttl_seconds: int = 86400 * 30):
    r = _redis()
    if r:
        r.setex(key, ttl_seconds, json.dumps(value))
    else:
        _store[key] = value


# ── Feature Schema ────────────────────────────────────────────────────────────

def _default_profile() -> dict:
    return {
        "user_id": "",
        "tx_count_7d": 0,
        "tx_count_30d": 0,
        "tx_volume_7d": 0.0,
        "tx_volume_30d": 0.0,
        "avg_tx_amount": 0.0,
        "max_tx_amount": 0.0,
        "std_tx_amount": 0.0,
        "known_devices": [],
        "known_beneficiaries": [],
        "typical_hours": [],          # hours of day with prior activity
        "geo_patterns": [],           # location strings seen before
        "channels_used": [],          # ussd, pos, transfer, etc.
        "last_tx_timestamp": None,
        "account_age_days": 0,
        "total_tx_count": 0,
        "_amounts_window": [],        # raw amounts for std calculation
        "_updated_at": None,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_profile(user_id: str) -> dict:
    profile = _get(f"feature:{user_id}")
    if not profile:
        profile = _default_profile()
        profile["user_id"] = user_id
    return profile


def update_user_profile(
    user_id: str,
    amount: float,
    channel: str,
    device_fingerprint: Optional[str],
    beneficiary_account: Optional[str],
    hour_of_day: int,
    location: Optional[str],
    timestamp: Optional[str] = None,
    is_confirmed_legit: bool = False,
):
    """
    Update behavioral features after a transaction.
    Call this AFTER a transaction is approved or confirmed.
    """
    profile = get_user_profile(user_id)
    now_ts = time.time()

    profile["tx_count_7d"]    = profile.get("tx_count_7d", 0) + 1
    profile["tx_count_30d"]   = profile.get("tx_count_30d", 0) + 1
    profile["tx_volume_7d"]   = profile.get("tx_volume_7d", 0.0) + amount
    profile["tx_volume_30d"]  = profile.get("tx_volume_30d", 0.0) + amount
    profile["total_tx_count"] = profile.get("total_tx_count", 0) + 1
    profile["max_tx_amount"]  = max(profile.get("max_tx_amount", 0.0), amount)
    profile["last_tx_timestamp"] = timestamp or datetime.now(timezone.utc).isoformat()

    # Rolling amount window for mean/std (keep last 100)
    window = profile.get("_amounts_window", [])
    window.append(amount)
    if len(window) > 100:
        window = window[-100:]
    profile["_amounts_window"] = window
    if len(window) > 1:
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        profile["avg_tx_amount"] = round(mean, 2)
        profile["std_tx_amount"] = round(math.sqrt(variance), 2)
    elif len(window) == 1:
        profile["avg_tx_amount"] = window[0]

    # Known devices (keep last 5)
    if device_fingerprint:
        devices = profile.get("known_devices", [])
        if device_fingerprint not in devices:
            devices.append(device_fingerprint)
        profile["known_devices"] = devices[-5:]

    # Known beneficiaries (keep last 20)
    if beneficiary_account:
        bens = profile.get("known_beneficiaries", [])
        if beneficiary_account not in bens:
            bens.append(beneficiary_account)
        profile["known_beneficiaries"] = bens[-20:]

    # Typical hours
    hours = profile.get("typical_hours", [])
    if hour_of_day not in hours:
        hours.append(hour_of_day)
    profile["typical_hours"] = hours

    # Geo patterns
    if location:
        geos = profile.get("geo_patterns", [])
        if location not in geos:
            geos.append(location)
        profile["geo_patterns"] = geos[-10:]

    # Channels used
    channels = profile.get("channels_used", [])
    if channel not in channels:
        channels.append(channel)
    profile["channels_used"] = channels

    profile["_updated_at"] = datetime.now(timezone.utc).isoformat()
    _set(f"feature:{user_id}", profile)


def compute_behavioral_deviation(user_id: str, amount: float, channel: str,
                                  device_fingerprint: Optional[str],
                                  beneficiary_account: Optional[str],
                                  hour_of_day: int,
                                  location: Optional[str] = None) -> dict:
    """
    Compare current transaction against user's behavioral baseline.
    Returns deviation score (0-100) and contributing factors.
    """
    profile = get_user_profile(user_id)
    factors = []
    deviation_score = 0

    # Amount deviation — z-score from user's typical range
    avg = profile.get("avg_tx_amount", 0)
    std = profile.get("std_tx_amount", 0)
    if avg > 0 and std > 0:
        z_score = abs(amount - avg) / std
        if z_score > 3:
            deviation_score += 30
            factors.append(f"Amount ₦{amount:,.0f} is {z_score:.1f}σ above user's mean (₦{avg:,.0f})")
        elif z_score > 2:
            deviation_score += 15
            factors.append(f"Amount slightly above typical range (₦{avg:,.0f} avg)")
    elif profile.get("total_tx_count", 0) == 0:
        # New account — any transaction is slightly elevated
        deviation_score += 10
        factors.append("New account — no behavioral baseline yet")

    # Device deviation
    known_devices = profile.get("known_devices", [])
    if device_fingerprint and known_devices and device_fingerprint not in known_devices:
        deviation_score += 20
        factors.append("Unrecognised device not in user's history")

    # Beneficiary deviation
    known_bens = profile.get("known_beneficiaries", [])
    if beneficiary_account and known_bens and beneficiary_account not in known_bens:
        deviation_score += 15
        factors.append("New beneficiary not in user's known recipients")

    # Time deviation
    typical_hours = profile.get("typical_hours", [])
    if typical_hours and hour_of_day not in typical_hours:
        # Check if hour is within 2 hours of any known hour
        near = any(abs(hour_of_day - h) <= 2 or abs(hour_of_day - h + 24) <= 2 for h in typical_hours)
        if not near:
            deviation_score += 10
            factors.append(f"Unusual hour {hour_of_day}:00 — user typically transacts at {typical_hours[:3]}")

    # Channel deviation
    channels_used = profile.get("channels_used", [])
    if channels_used and channel not in channels_used:
        deviation_score += 10
        factors.append(f"Unusual channel '{channel}' — user typically uses {channels_used}")

    # Location deviation
    geo_patterns = profile.get("geo_patterns", [])
    if location and geo_patterns and location not in geo_patterns:
        deviation_score += 10
        factors.append(f"Unfamiliar location: {location}")

    return {
        "behavioral_deviation_score": min(deviation_score, 100),
        "factors": factors,
        "profile_age_tx_count": profile.get("total_tx_count", 0),
        "user_avg_tx_amount": profile.get("avg_tx_amount", 0),
        "user_max_tx_amount": profile.get("max_tx_amount", 0),
    }
