"""
Bubby Vision — Celery Application Factory

Creates a Celery app with Redis broker and result backend.
Includes a beat schedule for periodic market data refresh tasks.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings


def make_celery() -> Celery:
    """Create and configure the Celery application.

    Uses Redis from settings as both broker and result backend.
    Registers the beat schedule for periodic data refresh tasks.
    """
    settings = get_settings()

    app = Celery(
        "Bubby Vision",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )

    app.conf.update(
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,

        # Reliability
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_reject_on_worker_lost=True,

        # Result expiry
        result_expires=3600,  # 1 hour

        # Beat schedule — periodic tasks
        beat_schedule={
            "refresh-fear-greed-every-30m": {
                "task": "app.tasks.market_tasks.refresh_fear_greed",
                "schedule": 60 * 30,  # every 30 minutes
            },
            "refresh-trending-tickers-every-15m": {
                "task": "app.tasks.market_tasks.refresh_trending_tickers",
                "schedule": 60 * 15,  # every 15 minutes
            },
            "daily-market-summary": {
                "task": "app.tasks.market_tasks.daily_market_summary",
                "schedule": crontab(hour=16, minute=30),  # 4:30 PM UTC (market close)
            },
            # ── OptionStrats Scraping (always active) ──
            "scrape-optionstrats-flow": {
                "task": "app.tasks.scrape_tasks.scrape_optionstrats_flow",
                "schedule": settings.optionstrats_scrape_interval,  # default: 300s
            },
            "scrape-optionstrats-iv-surface": {
                "task": "app.tasks.scrape_tasks.scrape_optionstrats_iv_surface",
                "schedule": settings.optionstrats_iv_scrape_interval,  # default: 1800s
            },
            "scrape-optionstrats-congress": {
                "task": "app.tasks.scrape_tasks.scrape_optionstrats_congress",
                "schedule": crontab(minute=0),  # every hour on the hour
            },
            "scrape-optionstrats-insider": {
                "task": "app.tasks.scrape_tasks.scrape_optionstrats_insider",
                "schedule": settings.optionstrats_insider_scrape_interval,  # default: 900s (15 min)
            },
            # ── Pattern Alert Scanning ──
            "scan-pattern-alerts-every-5m": {
                "task": "app.tasks.pattern_tasks.scan_pattern_alerts",
                "schedule": 60 * 5,  # every 5 minutes
            },
            # ── Morning Briefing & Trading Journal ──
            "morning-briefing-8am": {
                "task": "app.tasks.briefing_tasks.generate_morning_briefing",
                "schedule": crontab(hour=13, minute=0),  # 8:00 AM EST = 13:00 UTC
            },
            "daily-trading-journal": {
                "task": "app.tasks.journal_tasks.generate_daily_journal",
                "schedule": crontab(hour=21, minute=30),  # 4:30 PM EST = 21:30 UTC
            },
            # ── Weekly Model Optimization ──
            "weekly-model-optimization": {
                "task": "app.tasks.optimizer_tasks.run_weekly_optimization",
                "schedule": crontab(day_of_week=0, hour=0, minute=0),  # Sunday midnight UTC
            },
            # ── QuestDB Backup ──
            "daily-questdb-backup": {
                "task": "app.tasks.backup_tasks.backup_questdb",
                "schedule": crontab(hour=2, minute=0),  # 2:00 AM UTC daily
            },
        },
    )

    # Auto-discover tasks in the tasks module
    app.autodiscover_tasks(["app.tasks"])

    return app


# Module-level instance for imports
celery_app = make_celery()
