"""
Bubby Vision — OptionStrats Scraping Tasks

Celery periodic tasks for scheduled OptionStrats data extraction.
Always active — scrapes on every Celery beat cycle.

Tasks:
  - scrape_optionstrats_flow: Scrape options flow every 5 min
  - scrape_optionstrats_iv_surface: Scrape IV surface every 30 min
  - scrape_optionstrats_congress: Scrape congressional trades every hour
  - scrape_optionstrats_insider: Scrape insider trades every 15 min
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog

from app.config import get_settings
from app.tasks.celery_app import celery_app

_log = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.scrape_tasks.scrape_optionstrats_flow", bind=True)
def scrape_optionstrats_flow(self):
    """Scrape options flow from OptionStrats and cache in Redis.

    Runs at the interval configured by OPTIONSTRATS_SCRAPE_INTERVAL.
    Stores results in Redis with keys like 'optionstrats:flow:latest'.
    """
    import asyncio

    settings = get_settings()

    async def _scrape():
        from app.data.optionstrats_scraper import OptionStratsScraper

        scraper = OptionStratsScraper()
        try:
            flow_data = await scraper.get_flow(limit=100)

            # Cache in Redis
            if flow_data:
                import redis

                r = redis.from_url(settings.redis_url)
                cache_key = "optionstrats:flow:latest"
                cache_value = json.dumps({
                    "data": flow_data,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(flow_data),
                })
                r.setex(cache_key, settings.optionstrats_scrape_interval + 60, cache_value)
                _log.info(
                    "scrape_tasks.flow_cached",
                    count=len(flow_data),
                    ttl=settings.optionstrats_scrape_interval + 60,
                )

            return {
                "status": "success",
                "count": len(flow_data),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            _log.error("scrape_tasks.flow_error", error=str(exc))
            return {"status": "error", "error": str(exc)}
        finally:
            await scraper.close()

    return asyncio.run(_scrape())


@celery_app.task(name="app.tasks.scrape_tasks.scrape_optionstrats_iv_surface", bind=True)
def scrape_optionstrats_iv_surface(self, tickers: list[str] | None = None):
    """Scrape IV surface data for specified tickers (or defaults).

    Runs at the interval configured by OPTIONSTRATS_IV_SCRAPE_INTERVAL.
    Stores results per-ticker in Redis with keys like 'optionstrats:iv:AAPL'.

    Args:
        tickers: List of tickers to scrape IV for. Defaults to top watchlist.
    """
    import asyncio

    settings = get_settings()

    # Default tickers if none specified
    if not tickers:
        tickers = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]

    async def _scrape():
        from app.data.optionstrats_scraper import OptionStratsScraper

        scraper = OptionStratsScraper()
        results = {}
        try:
            for ticker in tickers:
                iv_data = await scraper.get_iv_surface(ticker)
                if iv_data:
                    # Cache in Redis
                    import redis

                    r = redis.from_url(settings.redis_url)
                    cache_key = f"optionstrats:iv:{ticker.upper()}"
                    cache_value = json.dumps({
                        "data": iv_data,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    })
                    r.setex(
                        cache_key,
                        settings.optionstrats_iv_scrape_interval + 120,
                        cache_value,
                    )
                    results[ticker] = "cached"
                else:
                    results[ticker] = "empty"

                # Delay between tickers to avoid detection
                import asyncio as _aio
                await _aio.sleep(5)

            _log.info(
                "scrape_tasks.iv_cached",
                tickers=list(results.keys()),
                results=results,
            )
            return {
                "status": "success",
                "results": results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            _log.error("scrape_tasks.iv_error", error=str(exc))
            return {"status": "error", "error": str(exc), "partial_results": results}
        finally:
            await scraper.close()

    return asyncio.run(_scrape())


@celery_app.task(name="app.tasks.scrape_tasks.scrape_optionstrats_congress", bind=True)
def scrape_optionstrats_congress(self):
    """Scrape congressional trading flow from OptionStrats.

    Runs once per hour. Stores results in Redis with key
    'optionstrats:congress:latest'.
    """
    import asyncio

    settings = get_settings()

    async def _scrape():
        from app.data.optionstrats_scraper import OptionStratsScraper

        scraper = OptionStratsScraper()
        try:
            congress_data = await scraper.get_congressional_flow(limit=50)

            if congress_data:
                import redis

                r = redis.from_url(settings.redis_url)
                cache_key = "optionstrats:congress:latest"
                cache_value = json.dumps({
                    "data": congress_data,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(congress_data),
                })
                r.setex(cache_key, 3600 + 120, cache_value)  # 1 hour + buffer
                _log.info("scrape_tasks.congress_cached", count=len(congress_data))

            return {
                "status": "success",
                "count": len(congress_data),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            _log.error("scrape_tasks.congress_error", error=str(exc))
            return {"status": "error", "error": str(exc)}
        finally:
            await scraper.close()

    return asyncio.run(_scrape())


@celery_app.task(name="app.tasks.scrape_tasks.scrape_optionstrats_insider", bind=True)
def scrape_optionstrats_insider(self):
    """Scrape insider trading flow from OptionStrats and cache in Redis.

    SEC insider buying/selling data — unique to OptionStrats.
    Runs every 15 min. Cached in Redis for LLM context.
    """
    import asyncio

    settings = get_settings()

    async def _scrape():
        from app.data.optionstrats_scraper import OptionStratsScraper

        scraper = OptionStratsScraper()
        try:
            insider_data = await scraper.get_insider_flow(limit=50)

            if insider_data:
                import redis

                r = redis.from_url(settings.redis_url)
                cache_key = "optionstrats:insider:latest"
                cache_value = json.dumps({
                    "data": insider_data,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(insider_data),
                })
                r.setex(
                    cache_key,
                    settings.optionstrats_insider_scrape_interval + 120,
                    cache_value,
                )
                _log.info("scrape_tasks.insider_cached", count=len(insider_data))

            return {
                "status": "success",
                "count": len(insider_data),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            _log.error("scrape_tasks.insider_error", error=str(exc))
            return {"status": "error", "error": str(exc)}
        finally:
            await scraper.close()

    return asyncio.run(_scrape())
