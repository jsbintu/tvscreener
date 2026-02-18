"""
Bubby Vision — Watchlist & Price Alerts Routes

REST endpoints for managing user watchlists and configurable price alerts.
Persisted to QuestDB when available, falls back to in-memory for dev.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import structlog

log = structlog.get_logger(__name__)

watchlist_router = APIRouter()


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────


class WatchlistItem(BaseModel):
    ticker: str
    added_at: Optional[str] = None


class AddWatchlistRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")


class CreateAlertRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    threshold: float = Field(..., gt=0, description="Price threshold")
    direction: str = Field("above", pattern="^(above|below)$")


class AlertItem(BaseModel):
    id: str
    ticker: str
    threshold: float
    direction: str
    created_at: Optional[str] = None


# ──────────────────────────────────────────────
# In-Memory Fallback (dev mode when QuestDB is down)
# ──────────────────────────────────────────────


class _InMemoryStore:
    """Simple fallback store for development without QuestDB."""

    def __init__(self):
        self.watchlists: dict[str, list[dict]] = {}
        self.alerts: dict[str, list[dict]] = {}

    def get_watchlist(self, user_id: str) -> list[dict]:
        return self.watchlists.get(user_id, [])

    def add_to_watchlist(self, user_id: str, ticker: str) -> bool:
        if user_id not in self.watchlists:
            self.watchlists[user_id] = []
        # Prevent duplicates
        if any(w["ticker"] == ticker.upper() for w in self.watchlists[user_id]):
            return False
        from datetime import datetime, timezone
        self.watchlists[user_id].append({
            "ticker": ticker.upper(),
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def remove_from_watchlist(self, user_id: str, ticker: str) -> bool:
        if user_id not in self.watchlists:
            return False
        before = len(self.watchlists[user_id])
        self.watchlists[user_id] = [
            w for w in self.watchlists[user_id] if w["ticker"] != ticker.upper()
        ]
        return len(self.watchlists[user_id]) < before

    def get_alerts(self, user_id: str) -> list[dict]:
        return [a for a in self.alerts.get(user_id, []) if a.get("active", True)]

    def add_alert(self, user_id: str, alert: dict) -> None:
        if user_id not in self.alerts:
            self.alerts[user_id] = []
        self.alerts[user_id].append(alert)

    def remove_alert(self, user_id: str, alert_id: str) -> bool:
        if user_id not in self.alerts:
            return False
        before = len(self.alerts[user_id])
        self.alerts[user_id] = [
            a for a in self.alerts[user_id] if a["id"] != alert_id
        ]
        return len(self.alerts[user_id]) < before


_fallback = _InMemoryStore()


def _get_store():
    """Get QuestDB client or fallback to in-memory store."""
    try:
        from app.db.questdb_client import get_questdb
        db = get_questdb()
        if db.available:
            return db, True
    except Exception:
        pass
    return _fallback, False


# ──────────────────────────────────────────────
# Watchlist Endpoints
# ──────────────────────────────────────────────

DEFAULT_USER = "default"


@watchlist_router.get("/watchlist")
async def get_watchlist(
    user_id: str = Query(DEFAULT_USER, description="User ID"),
):
    """List all tickers on the user's watchlist."""
    store, is_db = _get_store()
    items = store.get_watchlist(user_id)
    return {"user_id": user_id, "watchlist": items, "count": len(items)}


@watchlist_router.post("/watchlist", status_code=201)
async def add_to_watchlist(
    request: AddWatchlistRequest,
    user_id: str = Query(DEFAULT_USER),
):
    """Add a ticker to the user's watchlist."""
    from app.utils.validators import validate_ticker
    try:
        ticker = validate_ticker(request.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    store, is_db = _get_store()
    result = store.add_to_watchlist(user_id, ticker)

    if not result:
        raise HTTPException(status_code=409, detail=f"{ticker} is already on your watchlist")

    log.info("watchlist.added", user_id=user_id, ticker=ticker)
    return {"message": f"{ticker} added to watchlist", "ticker": ticker}


@watchlist_router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    user_id: str = Query(DEFAULT_USER),
):
    """Remove a ticker from the user's watchlist."""
    ticker = ticker.upper()
    store, is_db = _get_store()
    result = store.remove_from_watchlist(user_id, ticker)

    if not result:
        raise HTTPException(status_code=404, detail=f"{ticker} not found on watchlist")

    log.info("watchlist.removed", user_id=user_id, ticker=ticker)
    return {"message": f"{ticker} removed from watchlist", "ticker": ticker}


# ──────────────────────────────────────────────
# Alert Endpoints
# ──────────────────────────────────────────────


@watchlist_router.post("/alerts", status_code=201)
async def create_alert(
    request: CreateAlertRequest,
    user_id: str = Query(DEFAULT_USER),
):
    """Create a price alert for a ticker."""
    from app.utils.validators import validate_ticker
    try:
        ticker = validate_ticker(request.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    alert_id = str(uuid.uuid4())
    store, is_db = _get_store()

    if is_db:
        success = store.insert_alert(
            alert_id=alert_id,
            user_id=user_id,
            ticker=ticker,
            threshold=request.threshold,
            direction=request.direction,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create alert")
    else:
        from datetime import datetime, timezone
        store.add_alert(user_id, {
            "id": alert_id,
            "ticker": ticker,
            "threshold": request.threshold,
            "direction": request.direction,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    log.info("alert.created", alert_id=alert_id, ticker=ticker, threshold=request.threshold)
    return {
        "id": alert_id,
        "ticker": ticker,
        "threshold": request.threshold,
        "direction": request.direction,
        "message": f"Alert: {ticker} {request.direction} ${request.threshold}",
    }


@watchlist_router.get("/alerts")
async def get_alerts(
    user_id: str = Query(DEFAULT_USER),
):
    """List all active price alerts for the user."""
    store, is_db = _get_store()

    if is_db:
        alerts = store.get_active_alerts(user_id)
    else:
        alerts = store.get_alerts(user_id)

    return {"user_id": user_id, "alerts": alerts, "count": len(alerts)}


@watchlist_router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: str,
    user_id: str = Query(DEFAULT_USER),
):
    """Delete a price alert."""
    store, is_db = _get_store()

    if is_db:
        success = store.deactivate_alert(alert_id)
    else:
        success = store.remove_alert(user_id, alert_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    log.info("alert.deleted", alert_id=alert_id)
    return {"message": "Alert deleted", "id": alert_id}
