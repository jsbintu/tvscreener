"""
Bubby Vision — Filter Presets Routes

REST endpoints for persisting named screener filter configurations.
Backed by Redis hash with graceful in-memory fallback.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import structlog

log = structlog.get_logger(__name__)

presets_router = APIRouter()


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────


class CreatePresetRequest(BaseModel):
    """Create a named filter preset."""
    name: str = Field(..., min_length=1, max_length=100)
    filters: dict[str, Any] = Field(..., description="The screener filter configuration")


class PresetResponse(BaseModel):
    """A saved filter preset."""
    id: str
    name: str
    filters: dict[str, Any]
    created_at: float


# ──────────────────────────────────────────────
# In-Memory Fallback
# ──────────────────────────────────────────────


_fallback_presets: dict[str, dict[str, dict]] = {}  # user_id -> {preset_id -> preset_data}

_PRESETS_KEY = "presets:{user_id}:screener"
_PRESETS_TTL = 60 * 60 * 24 * 365  # 1 year


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


@presets_router.get("/presets/screener")
async def list_presets(
    user_id: str = Query(DEFAULT_USER, description="User ID"),
):
    """List all saved screener filter presets."""
    r = _get_redis()
    if r:
        try:
            key = _PRESETS_KEY.format(user_id=user_id)
            raw = r.hgetall(key)
            presets = []
            for pid, data_json in raw.items():
                p = json.loads(data_json)
                p["id"] = pid
                presets.append(p)
            presets.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return {"presets": presets, "count": len(presets)}
        except Exception as exc:
            log.warning("presets.redis_error", error=str(exc))

    # Fallback
    user_presets = _fallback_presets.get(user_id, {})
    presets = [{"id": pid, **data} for pid, data in user_presets.items()]
    presets.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return {"presets": presets, "count": len(presets)}


@presets_router.post("/presets/screener", status_code=201)
async def create_preset(
    body: CreatePresetRequest,
    user_id: str = Query(DEFAULT_USER),
):
    """Save a named screener filter preset."""
    preset_id = str(uuid.uuid4())[:8]
    preset_data = {
        "name": body.name,
        "filters": body.filters,
        "created_at": time.time(),
    }

    r = _get_redis()
    if r:
        try:
            key = _PRESETS_KEY.format(user_id=user_id)
            r.hset(key, preset_id, json.dumps(preset_data, default=str))
            r.expire(key, _PRESETS_TTL)
            log.info("presets.created", preset_id=preset_id, name=body.name)
            return {"id": preset_id, **preset_data}
        except Exception as exc:
            log.warning("presets.redis_error", error=str(exc))

    # Fallback
    if user_id not in _fallback_presets:
        _fallback_presets[user_id] = {}
    _fallback_presets[user_id][preset_id] = preset_data
    return {"id": preset_id, **preset_data}


@presets_router.delete("/presets/screener/{preset_id}")
async def delete_preset(
    preset_id: str,
    user_id: str = Query(DEFAULT_USER),
):
    """Delete a screener filter preset."""
    r = _get_redis()
    if r:
        try:
            key = _PRESETS_KEY.format(user_id=user_id)
            removed = r.hdel(key, preset_id)
            if removed:
                log.info("presets.deleted", preset_id=preset_id)
                return {"message": "preset deleted", "id": preset_id}
            raise HTTPException(status_code=404, detail="Preset not found")
        except HTTPException:
            raise
        except Exception as exc:
            log.warning("presets.redis_error", error=str(exc))

    # Fallback
    user_presets = _fallback_presets.get(user_id, {})
    if preset_id in user_presets:
        del user_presets[preset_id]
        return {"message": "preset deleted", "id": preset_id}
    raise HTTPException(status_code=404, detail="Preset not found")
