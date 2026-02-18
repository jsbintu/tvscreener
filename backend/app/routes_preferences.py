"""
Bubby Vision — User Preferences Routes

REST endpoints for persisting user preferences (theme, sound, compact mode, etc.).
Backed by Redis hash with graceful in-memory fallback.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

import structlog

log = structlog.get_logger(__name__)

preferences_router = APIRouter()


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────


class PreferencesUpdate(BaseModel):
    """Bulk update preferences (partial merge)."""
    preferences: dict[str, Any]


class SinglePreference(BaseModel):
    """Update a single preference key."""
    value: Any


# ──────────────────────────────────────────────
# In-Memory Fallback
# ──────────────────────────────────────────────


_fallback_prefs: dict[str, dict[str, Any]] = {}

_PREFS_KEY = "prefs:{user_id}"
_PREFS_TTL = 60 * 60 * 24 * 365  # 1 year

DEFAULT_PREFS = {
    "theme": "dark",
    "notify_sound": True,
    "compact_mode": False,
}


def _get_redis():
    """Get raw Redis client if available."""
    try:
        from app.cache import get_cache
        cache = get_cache()
        if cache.available:
            return cache._client
    except Exception:
        pass
    return None


DEFAULT_USER = "default"


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@preferences_router.get("/preferences")
async def get_preferences(
    user_id: str = Query(DEFAULT_USER, description="User ID"),
):
    """Get all user preferences, merged with defaults."""
    r = _get_redis()
    if r:
        try:
            key = _PREFS_KEY.format(user_id=user_id)
            raw = r.hgetall(key)
            prefs = dict(DEFAULT_PREFS)
            for k, v in raw.items():
                try:
                    prefs[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    prefs[k] = v
            return {"preferences": prefs}
        except Exception as exc:
            log.warning("preferences.redis_error", error=str(exc))

    # Fallback
    prefs = dict(DEFAULT_PREFS)
    prefs.update(_fallback_prefs.get(user_id, {}))
    return {"preferences": prefs}


@preferences_router.put("/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    user_id: str = Query(DEFAULT_USER),
):
    """Bulk update preferences (merges with existing)."""
    r = _get_redis()
    if r:
        try:
            key = _PREFS_KEY.format(user_id=user_id)
            pipe = r.pipeline()
            for k, v in body.preferences.items():
                pipe.hset(key, k, json.dumps(v))
            pipe.expire(key, _PREFS_TTL)
            pipe.execute()
            log.info("preferences.updated", user_id=user_id, keys=list(body.preferences.keys()))
            # Return merged
            raw = r.hgetall(key)
            merged = dict(DEFAULT_PREFS)
            for k, v in raw.items():
                try:
                    merged[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    merged[k] = v
            return {"preferences": merged}
        except Exception as exc:
            log.warning("preferences.redis_error", error=str(exc))

    # Fallback
    if user_id not in _fallback_prefs:
        _fallback_prefs[user_id] = {}
    _fallback_prefs[user_id].update(body.preferences)
    merged = dict(DEFAULT_PREFS)
    merged.update(_fallback_prefs[user_id])
    return {"preferences": merged}


@preferences_router.patch("/preferences/{key}")
async def set_preference(
    key: str,
    body: SinglePreference,
    user_id: str = Query(DEFAULT_USER),
):
    """Set a single preference key."""
    r = _get_redis()
    if r:
        try:
            redis_key = _PREFS_KEY.format(user_id=user_id)
            r.hset(redis_key, key, json.dumps(body.value))
            r.expire(redis_key, _PREFS_TTL)
            log.debug("preferences.set", user_id=user_id, key=key)
            return {"key": key, "value": body.value}
        except Exception as exc:
            log.warning("preferences.redis_error", error=str(exc))

    # Fallback
    if user_id not in _fallback_prefs:
        _fallback_prefs[user_id] = {}
    _fallback_prefs[user_id][key] = body.value
    return {"key": key, "value": body.value}


@preferences_router.delete("/preferences")
async def reset_preferences(
    user_id: str = Query(DEFAULT_USER),
):
    """Reset all preferences to defaults."""
    r = _get_redis()
    if r:
        try:
            key = _PREFS_KEY.format(user_id=user_id)
            r.delete(key)
            log.info("preferences.reset", user_id=user_id)
            return {"preferences": DEFAULT_PREFS}
        except Exception as exc:
            log.warning("preferences.redis_error", error=str(exc))

    # Fallback
    _fallback_prefs.pop(user_id, None)
    return {"preferences": DEFAULT_PREFS}
