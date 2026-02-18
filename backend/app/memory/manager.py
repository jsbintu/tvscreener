"""
Bubby Vision — Memory System

Multi-layer memory for the multi-agent system:

1. **Session Memory** (Redis) — Short-term conversation state, user context within a session.
2. **Semantic Memory** (Redis + fallback) — Long-term facts about user preferences, portfolio,
   past interactions. Persists across restarts via Redis.
3. **Working Memory** (dict) — Per-request scratchpad for agent coordination.

This module provides a unified interface that agents use regardless of backend.
Redis is optional — the system degrades gracefully to in-process storage.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Memory Item Model
# ──────────────────────────────────────────────

class MemoryItem:
    """Single memory fact."""

    __slots__ = ("key", "value", "category", "created_at", "ttl", "metadata")

    def __init__(
        self,
        key: str,
        value: Any,
        category: str = "general",
        ttl: Optional[int] = None,
        metadata: Optional[dict] = None,
    ):
        self.key = key
        self.value = value
        self.category = category
        self.created_at = datetime.utcnow().isoformat()
        self.ttl = ttl  # seconds, None = permanent
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        item = cls(
            key=data["key"],
            value=data["value"],
            category=data.get("category", "general"),
            ttl=data.get("ttl"),
            metadata=data.get("metadata", {}),
        )
        item.created_at = data.get("created_at", item.created_at)
        return item


# ──────────────────────────────────────────────
# Session Memory (Redis-backed with fallback)
# ──────────────────────────────────────────────

class SessionMemory:
    """Short-term session memory backed by Redis (or in-process fallback).

    Stores conversation context, recent queries, and ephemeral state.
    TTL defaults to 2 hours for session data.
    """

    DEFAULT_TTL = 7200  # 2 hours

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        self._fallback: dict[str, dict] = {}

        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("session_memory_redis_connected", url=redis_url)
            except Exception as e:
                logger.warning("session_memory_redis_failed", error=str(e))
                self._redis = None

        if self._redis is None:
            logger.info("session_memory_using_fallback")

    def _session_key(self, conversation_id: str, key: str) -> str:
        return f"mp:session:{conversation_id}:{key}"

    def store(
        self,
        conversation_id: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ):
        """Store a value in session memory."""
        ttl = ttl or self.DEFAULT_TTL
        full_key = self._session_key(conversation_id, key)

        if self._redis:
            try:
                self._redis.setex(full_key, ttl, json.dumps(value, default=str))
                return
            except Exception as e:
                logger.warning("session_store_redis_error", error=str(e))

        # Fallback
        self._fallback[full_key] = {
            "value": value,
            "expires_at": time.time() + ttl,
        }

    def retrieve(self, conversation_id: str, key: str) -> Optional[Any]:
        """Retrieve a value from session memory."""
        full_key = self._session_key(conversation_id, key)

        if self._redis:
            try:
                raw = self._redis.get(full_key)
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.warning("session_retrieve_redis_error", error=str(e))

        # Fallback
        entry = self._fallback.get(full_key)
        if entry and time.time() < entry["expires_at"]:
            return entry["value"]
        elif entry:
            del self._fallback[full_key]
        return None

    def delete(self, conversation_id: str, key: str):
        """Delete a value from session memory."""
        full_key = self._session_key(conversation_id, key)
        if self._redis:
            try:
                self._redis.delete(full_key)
                return
            except Exception:
                pass
        self._fallback.pop(full_key, None)

    def get_session_context(self, conversation_id: str) -> dict:
        """Get all context for a conversation session."""
        return {
            "last_ticker": self.retrieve(conversation_id, "last_ticker"),
            "last_agent": self.retrieve(conversation_id, "last_agent"),
            "preferences": self.retrieve(conversation_id, "preferences") or {},
            "query_count": self.retrieve(conversation_id, "query_count") or 0,
        }

    def update_session_context(
        self,
        conversation_id: str,
        ticker: Optional[str] = None,
        agent: Optional[str] = None,
    ):
        """Update session context after a query."""
        if ticker:
            self.store(conversation_id, "last_ticker", ticker)
        if agent:
            self.store(conversation_id, "last_agent", agent)

        count = self.retrieve(conversation_id, "query_count") or 0
        self.store(conversation_id, "query_count", count + 1)


# ──────────────────────────────────────────────
# Semantic Memory (Long-term facts)
# ──────────────────────────────────────────────

class SemanticMemory:
    """Long-term semantic fact memory backed by Redis.

    Stores user preferences, portfolio details, past analyses, and learned patterns.
    Uses Redis hashes for persistence across restarts, with in-memory fallback.

    Categories:
      - "preference": User preferences (risk tolerance, favorite indicators)
      - "portfolio": Portfolio positions, watchlist
      - "analysis": Past analysis results for reference
      - "pattern": Learned market patterns
    """

    REDIS_PREFIX = "bubby:semantic"

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        self._fallback: dict[str, MemoryItem] = {}

        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("semantic_memory_redis_connected", url=redis_url)
            except Exception as e:
                logger.warning("semantic_memory_redis_failed", error=str(e))
                self._redis = None

        if self._redis is None:
            logger.info("semantic_memory_using_fallback")

    def _redis_key(self, key: str) -> str:
        return f"{self.REDIS_PREFIX}:{key}"

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        metadata: Optional[dict] = None,
    ):
        """Store a fact in semantic memory (Redis-persisted)."""
        item = MemoryItem(key=key, value=value, category=category, metadata=metadata)

        if self._redis:
            try:
                self._redis.set(
                    self._redis_key(key),
                    json.dumps(item.to_dict(), default=str),
                )
                logger.debug("semantic_remember_redis", key=key, category=category)
                return
            except Exception as e:
                logger.warning("semantic_remember_redis_error", error=str(e))

        # Fallback to in-memory
        self._fallback[key] = item
        logger.debug("semantic_remember_fallback", key=key, category=category)

    def recall(self, key: str) -> Optional[Any]:
        """Recall a specific fact by key."""
        if self._redis:
            try:
                raw = self._redis.get(self._redis_key(key))
                if raw:
                    data = json.loads(raw)
                    return data.get("value")
            except Exception as e:
                logger.warning("semantic_recall_redis_error", error=str(e))

        # Fallback
        item = self._fallback.get(key)
        return item.value if item else None

    def search(self, category: Optional[str] = None, limit: int = 20) -> list[dict]:
        """Search memories by category."""
        results = []

        if self._redis:
            try:
                cursor = 0
                while len(results) < limit:
                    cursor, keys = self._redis.scan(
                        cursor=cursor, match=f"{self.REDIS_PREFIX}:*", count=100,
                    )
                    for rkey in keys:
                        if len(results) >= limit:
                            break
                        raw = self._redis.get(rkey)
                        if raw:
                            data = json.loads(raw)
                            if category and data.get("category") != category:
                                continue
                            results.append(data)
                    if cursor == 0:
                        break
                return results
            except Exception as e:
                logger.warning("semantic_search_redis_error", error=str(e))

        # Fallback
        for item in self._fallback.values():
            if category and item.category != category:
                continue
            results.append(item.to_dict())
            if len(results) >= limit:
                break
        return results

    def forget(self, key: str) -> bool:
        """Remove a fact from memory."""
        if self._redis:
            try:
                deleted = self._redis.delete(self._redis_key(key))
                if deleted:
                    logger.debug("semantic_forget_redis", key=key)
                    return True
            except Exception as e:
                logger.warning("semantic_forget_redis_error", error=str(e))

        # Fallback
        if key in self._fallback:
            del self._fallback[key]
            logger.debug("semantic_forget_fallback", key=key)
            return True
        return False

    def get_user_profile(self) -> dict:
        """Get aggregated user profile from memory."""
        return {
            "risk_tolerance": self.recall("risk_tolerance") or "moderate",
            "favorite_indicators": self.recall("favorite_indicators") or ["RSI", "MACD"],
            "watchlist": self.recall("watchlist") or [],
            "account_size": self.recall("account_size"),
            "max_risk_per_trade": self.recall("max_risk_per_trade") or 0.01,
            "preferred_style": self.recall("preferred_style") or "swing",
        }

    def update_user_preference(self, key: str, value: Any):
        """Update a specific user preference."""
        self.remember(key, value, category="preference")

    def get_all_facts_context(self) -> str:
        """Get all facts formatted as context string for LLM injection."""
        facts = self.search(limit=50)
        if not facts:
            return "No user history available."

        lines = ["## Known User Context"]
        for f in facts:
            lines.append(f"- **{f['key']}** ({f['category']}): {f['value']}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Working Memory (Per-request scratchpad)
# ──────────────────────────────────────────────

class WorkingMemory:
    """Per-request working memory for agent coordination.

    Used by the supervisor to pass context between agents
    within a single multi-agent run.
    """

    def __init__(self):
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def clear(self):
        self._data.clear()

    def as_context(self) -> str:
        """Format working memory as context for agents."""
        if not self._data:
            return ""
        lines = ["## Working Context"]
        for k, v in self._data.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Unified Memory Manager
# ──────────────────────────────────────────────

class MemoryManager:
    """Unified interface to all memory layers.

    Usage:
        memory = get_memory_manager()
        memory.session.store(conv_id, "last_ticker", "AAPL")
        memory.semantic.remember("risk_tolerance", "aggressive")
        memory.working.set("current_analysis", {...})
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.session = SessionMemory(redis_url=redis_url)
        self.semantic = SemanticMemory(redis_url=redis_url)
        self.working = WorkingMemory()
        logger.info("memory_manager_initialized")

    def get_full_context(self, conversation_id: Optional[str] = None) -> str:
        """Get combined context from all memory layers for LLM injection."""
        parts = []

        if conversation_id:
            ctx = self.session.get_session_context(conversation_id)
            if ctx.get("last_ticker"):
                parts.append(f"**Recent ticker:** {ctx['last_ticker']}")
            if ctx.get("last_agent"):
                parts.append(f"**Last agent:** {ctx['last_agent']}")

        facts = self.semantic.get_all_facts_context()
        if facts != "No user history available.":
            parts.append(facts)

        working = self.working.as_context()
        if working:
            parts.append(working)

        return "\n\n".join(parts) if parts else ""


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create the global memory manager."""
    global _memory_manager
    if _memory_manager is None:
        from app.config import get_settings
        settings = get_settings()
        redis_url = getattr(settings, "redis_url", None)
        _memory_manager = MemoryManager(redis_url=redis_url)
    return _memory_manager
