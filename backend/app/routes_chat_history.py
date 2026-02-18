"""
Bubby Vision — Chat History Persistence Routes

REST endpoints for persisting chat conversations and messages.
Backed by Redis hashes with graceful fallback to in-memory store.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import structlog

log = structlog.get_logger(__name__)

chat_history_router = APIRouter()


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────


class MessagePayload(BaseModel):
    """A single chat message to persist."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=50000)
    agent: Optional[str] = None
    tools: Optional[list[str]] = None
    timestamp: Optional[str] = None


class ConversationSummary(BaseModel):
    """Lightweight conversation list entry."""
    id: str
    title: str
    timestamp: float
    message_count: int


class SaveConversationRequest(BaseModel):
    """Bulk save: conversation metadata + all messages."""
    title: str = Field(..., min_length=1, max_length=200)
    messages: list[MessagePayload] = Field(..., max_length=200)


# ──────────────────────────────────────────────
# In-Memory Fallback (when Redis is unavailable)
# ──────────────────────────────────────────────


class _InMemoryConvoStore:
    """Development fallback — data lost on restart."""

    def __init__(self):
        # user_id -> {conv_id -> {meta, messages}}
        self.store: dict[str, dict[str, dict]] = {}

    def _user(self, uid: str) -> dict:
        if uid not in self.store:
            self.store[uid] = {}
        return self.store[uid]

    def list_conversations(self, user_id: str) -> list[dict]:
        convos = self._user(user_id)
        result = []
        for cid, data in convos.items():
            result.append({
                "id": cid,
                "title": data.get("title", "Untitled"),
                "timestamp": data.get("timestamp", 0),
                "message_count": len(data.get("messages", [])),
            })
        result.sort(key=lambda x: x["timestamp"], reverse=True)
        return result

    def get_messages(self, user_id: str, conv_id: str) -> list[dict] | None:
        convos = self._user(user_id)
        if conv_id not in convos:
            return None
        return convos[conv_id].get("messages", [])

    def save_conversation(self, user_id: str, conv_id: str, title: str, messages: list[dict]) -> None:
        convos = self._user(user_id)
        convos[conv_id] = {
            "title": title,
            "timestamp": time.time(),
            "messages": messages[-200:],  # cap
        }

    def save_message(self, user_id: str, conv_id: str, message: dict) -> None:
        convos = self._user(user_id)
        if conv_id not in convos:
            # Auto-create conversation
            title = message.get("content", "Chat")[:50]
            convos[conv_id] = {"title": title, "timestamp": time.time(), "messages": []}
        convos[conv_id]["messages"].append(message)
        convos[conv_id]["timestamp"] = time.time()
        # Cap stored messages
        if len(convos[conv_id]["messages"]) > 200:
            convos[conv_id]["messages"] = convos[conv_id]["messages"][-200:]

    def delete_conversation(self, user_id: str, conv_id: str) -> bool:
        convos = self._user(user_id)
        if conv_id in convos:
            del convos[conv_id]
            return True
        return False


_fallback = _InMemoryConvoStore()


# ──────────────────────────────────────────────
# Redis Store (primary)
# ──────────────────────────────────────────────

# Key schemes:
#   chat:convos:{user_id}       → Hash {conv_id -> JSON(meta)}
#   chat:msgs:{user_id}:{cid}   → List of JSON(message)

_CONVO_KEY = "chat:convos:{user_id}"
_MSGS_KEY = "chat:msgs:{user_id}:{conv_id}"
_CONVO_TTL = 60 * 60 * 24 * 90  # 90 days


def _get_redis():
    """Get raw Redis client if available, else None."""
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


@chat_history_router.get("/conversations")
async def list_conversations(
    user_id: str = Query(DEFAULT_USER, description="User ID"),
):
    """List all conversations for a user (most recent first)."""
    r = _get_redis()
    if r:
        try:
            key = _CONVO_KEY.format(user_id=user_id)
            raw = r.hgetall(key)
            result = []
            for cid, meta_json in raw.items():
                meta = json.loads(meta_json)
                meta["id"] = cid
                result.append(meta)
            result.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return {"conversations": result, "count": len(result)}
        except Exception as exc:
            log.warning("chat_history.redis_error", error=str(exc))

    # Fallback
    convos = _fallback.list_conversations(user_id)
    return {"conversations": convos, "count": len(convos)}


@chat_history_router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: str,
    user_id: str = Query(DEFAULT_USER),
):
    """Get all messages for a specific conversation."""
    r = _get_redis()
    if r:
        try:
            key = _MSGS_KEY.format(user_id=user_id, conv_id=conv_id)
            raw_list = r.lrange(key, 0, -1)
            messages = [json.loads(m) for m in raw_list]
            return {"conversation_id": conv_id, "messages": messages, "count": len(messages)}
        except Exception as exc:
            log.warning("chat_history.redis_error", error=str(exc))

    # Fallback
    msgs = _fallback.get_messages(user_id, conv_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation_id": conv_id, "messages": msgs, "count": len(msgs)}


@chat_history_router.post("/conversations/{conv_id}/messages", status_code=201)
async def save_message(
    conv_id: str,
    message: MessagePayload,
    user_id: str = Query(DEFAULT_USER),
):
    """Append a single message to a conversation."""
    msg_dict = message.model_dump()
    if not msg_dict.get("timestamp"):
        msg_dict["timestamp"] = time.time()

    r = _get_redis()
    if r:
        try:
            msgs_key = _MSGS_KEY.format(user_id=user_id, conv_id=conv_id)
            r.rpush(msgs_key, json.dumps(msg_dict, default=str))
            # Cap at 200 messages
            r.ltrim(msgs_key, -200, -1)
            r.expire(msgs_key, _CONVO_TTL)

            # Update conversation meta
            convo_key = _CONVO_KEY.format(user_id=user_id)
            existing = r.hget(convo_key, conv_id)
            if existing:
                meta = json.loads(existing)
                meta["timestamp"] = time.time()
                meta["message_count"] = meta.get("message_count", 0) + 1
            else:
                # Auto-create conversation entry
                meta = {
                    "title": msg_dict["content"][:50],
                    "timestamp": time.time(),
                    "message_count": 1,
                }
            r.hset(convo_key, conv_id, json.dumps(meta))
            r.expire(convo_key, _CONVO_TTL)

            log.debug("chat_history.message_saved", conv_id=conv_id, role=msg_dict["role"])
            return {"message": "saved", "conversation_id": conv_id}
        except Exception as exc:
            log.warning("chat_history.redis_error", error=str(exc))

    # Fallback
    _fallback.save_message(user_id, conv_id, msg_dict)
    return {"message": "saved", "conversation_id": conv_id}


@chat_history_router.put("/conversations/{conv_id}")
async def save_conversation(
    conv_id: str,
    body: SaveConversationRequest,
    user_id: str = Query(DEFAULT_USER),
):
    """Bulk save/overwrite a conversation (metadata + all messages)."""
    messages = [m.model_dump() for m in body.messages]

    r = _get_redis()
    if r:
        try:
            # Save messages (replace entire list)
            msgs_key = _MSGS_KEY.format(user_id=user_id, conv_id=conv_id)
            pipe = r.pipeline()
            pipe.delete(msgs_key)
            for m in messages[-200:]:
                if not m.get("timestamp"):
                    m["timestamp"] = time.time()
                pipe.rpush(msgs_key, json.dumps(m, default=str))
            pipe.expire(msgs_key, _CONVO_TTL)

            # Save conversation meta
            convo_key = _CONVO_KEY.format(user_id=user_id)
            meta = {
                "title": body.title,
                "timestamp": time.time(),
                "message_count": len(messages),
            }
            pipe.hset(convo_key, conv_id, json.dumps(meta))
            pipe.expire(convo_key, _CONVO_TTL)
            pipe.execute()

            log.info("chat_history.conversation_saved", conv_id=conv_id, msg_count=len(messages))
            return {"message": "conversation saved", "conversation_id": conv_id}
        except Exception as exc:
            log.warning("chat_history.redis_error", error=str(exc))

    # Fallback
    _fallback.save_conversation(user_id, conv_id, body.title, messages)
    return {"message": "conversation saved", "conversation_id": conv_id}


@chat_history_router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    user_id: str = Query(DEFAULT_USER),
):
    """Delete a conversation and its messages."""
    r = _get_redis()
    if r:
        try:
            convo_key = _CONVO_KEY.format(user_id=user_id)
            msgs_key = _MSGS_KEY.format(user_id=user_id, conv_id=conv_id)
            pipe = r.pipeline()
            pipe.hdel(convo_key, conv_id)
            pipe.delete(msgs_key)
            pipe.execute()
            log.info("chat_history.deleted", conv_id=conv_id)
            return {"message": "conversation deleted", "id": conv_id}
        except Exception as exc:
            log.warning("chat_history.redis_error", error=str(exc))

    # Fallback
    ok = _fallback.delete_conversation(user_id, conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "conversation deleted", "id": conv_id}
