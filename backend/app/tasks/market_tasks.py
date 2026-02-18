"""
Bubby Vision — Background Market Tasks

Celery tasks for periodic data refresh:
- Fear & Greed index updates
- Trending ticker refresh
- Price alert checks
- End-of-day market summary compilation
"""

from __future__ import annotations

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_fear_greed(self) -> dict:
    """Fetch the latest CNN Fear & Greed Index and cache it.

    Runs every 30 minutes via beat schedule.
    """
    try:
        from app.data.fear_greed import FearGreedClient

        client = FearGreedClient()
        data = client.get_index()
        result = {
            "score": data.score,
            "label": data.label,
            "timestamp": data.timestamp.isoformat() if data.timestamp else None,
        }

        # Cache in Redis (optional — best-effort)
        try:
            import redis as _redis
            from app.config import get_settings
            r = _redis.from_url(get_settings().redis_url, decode_responses=True)
            import json
            r.setex("Bubby Vision:fear_greed", 1800, json.dumps(result))
        except Exception:
            pass

        log.info("task.fear_greed.refreshed", score=result["score"])
        return result

    except Exception as exc:
        log.error("task.fear_greed.failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_trending_tickers(self) -> dict:
    """Refresh WSB trending tickers and cache them.

    Runs every 15 minutes via beat schedule.
    """
    try:
        from app.data.wsb_client import WSBClient

        client = WSBClient()
        trending = client.get_trending_tickers(limit=25)
        result = {
            "tickers": [t.model_dump() if hasattr(t, "model_dump") else t for t in trending],
            "count": len(trending),
        }

        # Cache in Redis
        try:
            import redis as _redis
            from app.config import get_settings
            import json
            r = _redis.from_url(get_settings().redis_url, decode_responses=True)
            r.setex("Bubby Vision:trending_tickers", 900, json.dumps(result, default=str))
        except Exception:
            pass

        log.info("task.trending_tickers.refreshed", count=len(trending))
        return result

    except Exception as exc:
        log.error("task.trending_tickers.failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def check_price_alerts(self, ticker: str, threshold: float, direction: str = "above") -> dict:
    """Check if a ticker's price has crossed a threshold.

    On-demand task — triggered by user alert creation.

    Args:
        ticker: Stock ticker symbol.
        threshold: Price threshold to check against.
        direction: "above" or "below".

    Returns:
        Dict with triggered status and current price.
    """
    try:
        from app.data.yfinance_client import YFinanceClient

        client = YFinanceClient()
        stock = client.get_stock_data(ticker)
        current_price = stock.current_price

        triggered = False
        if direction == "above" and current_price >= threshold:
            triggered = True
        elif direction == "below" and current_price <= threshold:
            triggered = True

        result = {
            "ticker": ticker,
            "current_price": current_price,
            "threshold": threshold,
            "direction": direction,
            "triggered": triggered,
        }

        if triggered:
            log.info(
                "task.price_alert.triggered",
                ticker=ticker,
                price=current_price,
                threshold=threshold,
            )
            # Send notification (async context not available in Celery,
            # so we just log for now — notification dispatch happens via API)

        return result

    except Exception as exc:
        log.error("task.price_alert.failed", ticker=ticker, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def daily_market_summary(self) -> dict:
    """Compile an end-of-day market digest.

    Runs at 4:30 PM UTC (after US market close) via beat schedule.
    Collects Fear & Greed, trending tickers, and market breadth.
    """
    try:
        summary_parts: dict = {}

        # Fear & Greed
        try:
            from app.data.fear_greed import FearGreedClient
            fg = FearGreedClient().get_index()
            summary_parts["fear_greed"] = {"score": fg.score, "label": fg.label}
        except Exception:
            summary_parts["fear_greed"] = None

        # Trending tickers
        try:
            from app.data.wsb_client import WSBClient
            trending = WSBClient().get_trending_tickers(limit=10)
            summary_parts["trending"] = [
                t.model_dump() if hasattr(t, "model_dump") else t for t in trending
            ]
        except Exception:
            summary_parts["trending"] = []

        log.info("task.daily_summary.compiled", sections=list(summary_parts.keys()))

        # Cache summary
        try:
            import redis as _redis
            from app.config import get_settings
            import json
            r = _redis.from_url(get_settings().redis_url, decode_responses=True)
            r.setex("Bubby Vision:daily_summary", 86400, json.dumps(summary_parts, default=str))
        except Exception:
            pass

        return summary_parts

    except Exception as exc:
        log.error("task.daily_summary.failed", error=str(exc))
        raise self.retry(exc=exc)
