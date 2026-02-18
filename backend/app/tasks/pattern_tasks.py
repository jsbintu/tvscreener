"""
Bubby Vision — Pattern Alert Tasks (Phase 9)

Celery tasks for real-time pattern scanning:
- Periodic watchlist scan for new pattern formations
- Pattern outcome tracking (success/failure/expired)
- Alert broadcasting via WebSocket

Redis keys used:
  Bubby Vision:pattern_watchlist          — set of tickers to scan
  Bubby Vision:pattern_scan:{ticker}      — latest scan result (JSON)
  Bubby Vision:pattern_log:{ticker}       — active pattern log for outcome tracking (JSON list)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger(__name__)


def _get_redis():
    """Get Redis connection (best-effort)."""
    try:
        import redis as _redis
        from app.config import get_settings
        return _redis.from_url(get_settings().redis_url, decode_responses=True)
    except Exception:
        return None


def _get_watchlist_tickers(r) -> list[str]:
    """Read the pattern scan watchlist from Redis."""
    if r is None:
        return []
    try:
        tickers = r.smembers("Bubby Vision:pattern_watchlist")
        return sorted(tickers) if tickers else []
    except Exception:
        return []


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scan_pattern_alerts(self) -> dict:
    """Periodic scan of watchlist tickers for new pattern formations.

    Runs every 5 minutes via beat schedule during market hours.
    Compares current scan with previous results; broadcasts alerts
    for any NEW patterns detected since last scan.
    """
    try:
        from app.engines.data_engine import DataEngine
        from app.engines.pattern_engine import PatternEngine

        r = _get_redis()
        tickers = _get_watchlist_tickers(r)

        if not tickers:
            log.debug("pattern_scan.no_watchlist")
            return {"scanned": 0, "alerts": 0}

        data_engine = DataEngine()
        pattern_engine = PatternEngine()

        total_alerts = 0
        scan_results = {}

        for ticker in tickers[:20]:  # Cap at 20 to avoid overload
            try:
                data = data_engine.get_stock(ticker, period="3mo", interval="1d")
                current_scan = pattern_engine.scan_all_patterns(data.history)

                # Get previous scan from Redis
                prev_key = f"Bubby Vision:pattern_scan:{ticker}"
                prev_scan_raw = r.get(prev_key) if r else None
                prev_patterns = set()

                if prev_scan_raw:
                    try:
                        prev_data = json.loads(prev_scan_raw)
                        for p in prev_data.get("candlestick_patterns", []) + prev_data.get("chart_patterns", []):
                            if isinstance(p, dict):
                                prev_patterns.add(p.get("name", ""))
                    except json.JSONDecodeError:
                        pass

                # Find new patterns
                current_pattern_names = set()
                new_patterns = []

                for p in current_scan.get("candlestick_patterns", []) + current_scan.get("chart_patterns", []):
                    if isinstance(p, dict):
                        name = p.get("name", "")
                        current_pattern_names.add(name)
                        if name and name not in prev_patterns:
                            new_patterns.append(p)

                # Broadcast alerts for new patterns
                if new_patterns:
                    total_alerts += len(new_patterns)
                    for pattern in new_patterns:
                        alert_data = {
                            "alert_type": "pattern_detected",
                            "ticker": ticker,
                            "pattern": pattern.get("name"),
                            "direction": pattern.get("direction"),
                            "confidence": pattern.get("confidence"),
                            "description": pattern.get("description"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }

                        # Store alert for API retrieval
                        if r:
                            alert_key = f"Bubby Vision:pattern_alerts:{ticker}"
                            r.lpush(alert_key, json.dumps(alert_data))
                            r.ltrim(alert_key, 0, 49)  # Keep last 50 alerts
                            r.expire(alert_key, 86400)  # 24h TTL

                        log.info(
                            "pattern_scan.new_pattern",
                            ticker=ticker,
                            pattern=pattern.get("name"),
                            direction=pattern.get("direction"),
                        )

                # Update pattern log for outcome tracking
                _update_pattern_log(r, ticker, current_scan, data.history, pattern_engine)

                # Cache current scan
                if r:
                    r.setex(prev_key, 600, json.dumps(current_scan, default=str))

                scan_results[ticker] = {
                    "patterns_found": current_scan.get("pattern_count", 0),
                    "new_patterns": len(new_patterns),
                    "bias": current_scan.get("overall_bias"),
                }

            except Exception as e:
                log.warning("pattern_scan.ticker_failed", ticker=ticker, error=str(e))
                scan_results[ticker] = {"error": str(e)}

        result = {
            "scanned": len(tickers),
            "alerts": total_alerts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": scan_results,
        }

        log.info("pattern_scan.complete", scanned=len(tickers), alerts=total_alerts)
        return result

    except Exception as exc:
        log.error("pattern_scan.failed", error=str(exc))
        raise self.retry(exc=exc)


def _update_pattern_log(r, ticker: str, scan_result: dict, bars, pattern_engine):
    """Update the pattern log and evaluate outcomes of previous patterns."""
    if r is None:
        return

    log_key = f"Bubby Vision:pattern_log:{ticker}"

    # Get existing pattern log
    existing_log_raw = r.get(log_key)
    existing_log = []
    if existing_log_raw:
        try:
            existing_log = json.loads(existing_log_raw)
        except json.JSONDecodeError:
            existing_log = []

    # Evaluate outcomes of existing patterns
    if existing_log and bars:
        evaluated = pattern_engine.evaluate_pattern_outcomes(bars, existing_log)

        # Filter: keep only active/too_recent; archive resolved ones
        still_active = []
        resolved = []
        for p in evaluated:
            outcome = p.get("outcome", "active")
            if outcome in ("active", "too_recent"):
                still_active.append(p)
            else:
                resolved.append(p)

        # Persist resolved outcomes to QuestDB for long-term accuracy tracking
        if resolved:
            try:
                from app.engines.outcome_tracker import get_outcome_tracker
                tracker = get_outcome_tracker()
                for p in resolved:
                    p["ticker"] = ticker
                recorded = tracker.record_batch(resolved)
                log.info("pattern_scan.outcomes_persisted", ticker=ticker, count=recorded)
            except Exception as e:
                log.warning("pattern_scan.outcomes_persist_failed", error=str(e))

        # Broadcast failure alerts
        for p in resolved:
            if p.get("outcome") == "failed":
                alert_data = {
                    "alert_type": "pattern_failed",
                    "ticker": ticker,
                    "pattern": p.get("name"),
                    "direction": p.get("direction"),
                    "outcome": "failed",
                    "max_adverse_pct": p.get("max_adverse_pct"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                alert_key = f"Bubby Vision:pattern_alerts:{ticker}"
                r.lpush(alert_key, json.dumps(alert_data))
                r.ltrim(alert_key, 0, 49)
                r.expire(alert_key, 86400)

                log.info(
                    "pattern_scan.pattern_failed",
                    ticker=ticker,
                    pattern=p.get("name"),
                    max_adverse=p.get("max_adverse_pct"),
                )

        existing_log = still_active

    # Add new patterns with targets to the log (for future outcome tracking)
    all_current = scan_result.get("candlestick_patterns", []) + scan_result.get("chart_patterns", [])
    existing_names = {p.get("name") for p in existing_log}

    for p in all_current:
        if isinstance(p, dict) and p.get("name") not in existing_names:
            if p.get("target") or p.get("stop_loss"):  # Only track patterns with actionable levels
                p["detected_at"] = datetime.now(timezone.utc).isoformat()
                existing_log.append(p)

    # Save updated log (keep max 30 active patterns per ticker)
    r.setex(log_key, 604800, json.dumps(existing_log[:30], default=str))  # 7-day TTL


@celery_app.task(bind=True, max_retries=1)
def add_to_pattern_watchlist(self, tickers: list[str]) -> dict:
    """Add tickers to the pattern scan watchlist."""
    r = _get_redis()
    if r is None:
        return {"error": "Redis unavailable"}

    added = 0
    for t in tickers:
        r.sadd("Bubby Vision:pattern_watchlist", t.upper())
        added += 1

    return {"added": added, "tickers": [t.upper() for t in tickers]}


@celery_app.task(bind=True, max_retries=1)
def remove_from_pattern_watchlist(self, tickers: list[str]) -> dict:
    """Remove tickers from the pattern scan watchlist."""
    r = _get_redis()
    if r is None:
        return {"error": "Redis unavailable"}

    removed = 0
    for t in tickers:
        r.srem("Bubby Vision:pattern_watchlist", t.upper())
        removed += 1

    return {"removed": removed, "tickers": [t.upper() for t in tickers]}
