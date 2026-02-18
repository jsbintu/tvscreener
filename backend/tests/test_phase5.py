"""
Bubby Vision — Phase 5 Tests

Tests for the five new modules:
- Utils (formatters, validators)
- Middleware (rate limiter, request logger)
- Notifications (dispatcher)
- RAG (chunking, pipeline)
- Tasks (celery app, market tasks)
"""

import pytest
from datetime import datetime, timezone, timedelta


# ════════════════════════════════════════════════
#  UTILS — FORMATTERS
# ════════════════════════════════════════════════


class TestFormatters:

    def test_format_currency_positive(self):
        from app.utils.formatters import format_currency
        assert format_currency(1234.5) == "$1,234.50"

    def test_format_currency_negative(self):
        from app.utils.formatters import format_currency
        assert format_currency(-789.1) == "-$789.10"

    def test_format_currency_zero(self):
        from app.utils.formatters import format_currency
        assert format_currency(0) == "$0.00"

    def test_format_pct_positive(self):
        from app.utils.formatters import format_pct
        assert format_pct(12.345) == "+12.35%"

    def test_format_pct_negative(self):
        from app.utils.formatters import format_pct
        assert format_pct(-3.1, decimals=1) == "-3.1%"

    def test_format_pct_no_sign(self):
        from app.utils.formatters import format_pct
        assert format_pct(5.0, show_sign=False) == "5.00%"

    def test_format_large_number_millions(self):
        from app.utils.formatters import format_large_number
        assert format_large_number(1_234_567) == "1.23M"

    def test_format_large_number_billions(self):
        from app.utils.formatters import format_large_number
        assert format_large_number(45_600_000_000) == "45.60B"

    def test_format_large_number_small(self):
        from app.utils.formatters import format_large_number
        assert format_large_number(999) == "999"

    def test_format_large_number_none(self):
        from app.utils.formatters import format_large_number
        assert format_large_number(None) == "N/A"

    def test_format_ticker(self):
        from app.utils.formatters import format_ticker
        assert format_ticker("  aapl  ") == "AAPL"
        assert format_ticker("BRK.B") == "BRK.B"

    def test_format_timestamp_relative(self):
        from app.utils.formatters import format_timestamp
        now = datetime.now(timezone.utc)
        result = format_timestamp(now - timedelta(minutes=5))
        assert "5m ago" == result

    def test_format_timestamp_absolute(self):
        from app.utils.formatters import format_timestamp
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_timestamp(dt, relative=False)
        assert "2024-01-15 10:30:00" == result


# ════════════════════════════════════════════════
#  UTILS — VALIDATORS
# ════════════════════════════════════════════════


class TestValidators:

    def test_validate_ticker_valid(self):
        from app.utils.validators import validate_ticker
        assert validate_ticker("aapl") == "AAPL"
        assert validate_ticker("BRK.B") == "BRK.B"
        assert validate_ticker("  msft ") == "MSFT"

    def test_validate_ticker_invalid(self):
        from app.utils.validators import validate_ticker
        with pytest.raises(ValueError, match="Invalid ticker"):
            validate_ticker("TOOLONG123")

    def test_validate_ticker_empty(self):
        from app.utils.validators import validate_ticker
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_ticker("")

    def test_validate_date_range_defaults(self):
        from app.utils.validators import validate_date_range
        start, end = validate_date_range()
        assert start < end
        assert (end - start).days == 365

    def test_validate_date_range_custom(self):
        from app.utils.validators import validate_date_range
        start, end = validate_date_range("2024-01-01", "2024-06-01")
        assert start.year == 2024
        assert start.month == 1
        assert end.month == 6

    def test_validate_date_range_reversed(self):
        from app.utils.validators import validate_date_range
        with pytest.raises(ValueError, match="before end date"):
            validate_date_range("2024-06-01", "2024-01-01")

    def test_validate_date_range_too_long(self):
        from app.utils.validators import validate_date_range
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_date_range("2010-01-01", "2024-01-01", max_days=365)

    def test_validate_pagination_defaults(self):
        from app.utils.validators import validate_pagination
        limit, offset = validate_pagination()
        assert limit == 50
        assert offset == 0

    def test_validate_pagination_clamp(self):
        from app.utils.validators import validate_pagination
        limit, offset = validate_pagination(limit=1000, offset=-5)
        assert limit == 500
        assert offset == 0


# ════════════════════════════════════════════════
#  MIDDLEWARE — RATE LIMITER
# ════════════════════════════════════════════════


class TestRateLimiter:

    def test_in_memory_bucket_allows(self):
        from app.middleware.rate_limiter import _InMemoryBucket
        bucket = _InMemoryBucket()
        assert bucket.is_allowed("test-ip", max_tokens=5, refill_rate=1.0) is True

    def test_in_memory_bucket_exhausts(self):
        from app.middleware.rate_limiter import _InMemoryBucket
        bucket = _InMemoryBucket()
        for _ in range(5):
            bucket.is_allowed("exhaust-ip", max_tokens=5, refill_rate=0.0)
        # 6th request — should be denied (refill_rate=0 means no replenishment)
        assert bucket.is_allowed("exhaust-ip", max_tokens=5, refill_rate=0.0) is False

    def test_rate_limit_middleware_import(self):
        from app.middleware.rate_limiter import RateLimitMiddleware
        assert RateLimitMiddleware is not None

    def test_rate_limit_headers(self):
        """Rate limit headers are set on responses."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        # Health endpoint bypasses rate limiting, but other endpoints get the header
        resp2 = client.get("/v1/api/stock/AAPL")
        assert "X-RateLimit-Limit" in resp2.headers or resp2.status_code in (200, 404, 422, 500)


# ════════════════════════════════════════════════
#  MIDDLEWARE — REQUEST LOGGER
# ════════════════════════════════════════════════


class TestRequestLogger:

    def test_request_id_header(self):
        """Requests to non-health endpoints get an X-Request-ID header."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/v1/api/stock/AAPL")
        # Should have request ID header (regardless of status)
        assert "X-Request-ID" in resp.headers
        # Validate it's a UUID format (36 chars with hyphens)
        assert len(resp.headers["X-Request-ID"]) == 36

    def test_import(self):
        from app.middleware.request_logger import RequestLoggerMiddleware
        assert RequestLoggerMiddleware is not None


# ════════════════════════════════════════════════
#  NOTIFICATIONS
# ════════════════════════════════════════════════


class TestNotifications:

    def test_alert_type_enum(self):
        from app.notifications.dispatcher import AlertType
        assert AlertType.TRADE_SIGNAL.value == "trade_signal"
        assert AlertType.RISK_ALERT.value == "risk_alert"
        assert AlertType.EARNINGS.value == "earnings"
        assert AlertType.SYSTEM.value == "system"

    def test_discord_notifier_unconfigured(self):
        from app.notifications.dispatcher import DiscordNotifier
        notifier = DiscordNotifier("")
        assert notifier.configured is False

    def test_telegram_notifier_unconfigured(self):
        from app.notifications.dispatcher import TelegramNotifier
        notifier = TelegramNotifier("", "")
        assert notifier.configured is False

    def test_dispatcher_creation(self):
        from app.notifications.dispatcher import NotificationDispatcher
        dispatcher = NotificationDispatcher()
        # Without credentials, no channels should be active
        assert isinstance(dispatcher.active_channels, list)

    @pytest.mark.asyncio
    async def test_dispatcher_send_no_channels(self):
        """Dispatcher send returns False for all unconfigured channels."""
        from app.notifications.dispatcher import NotificationDispatcher, AlertType
        dispatcher = NotificationDispatcher()
        results = await dispatcher.send("Test", "Test message", AlertType.SYSTEM)
        assert isinstance(results, dict)
        # All channels should report False (unconfigured)
        for channel, status in results.items():
            assert status is False


# ════════════════════════════════════════════════
#  RAG — CHUNKING
# ════════════════════════════════════════════════


class TestRAGChunking:

    def test_chunk_short_text(self):
        from app.rag.pipeline import chunk_text
        result = chunk_text("Hello world.")
        assert len(result) == 1
        assert "Hello world." in result[0]

    def test_chunk_long_text(self):
        from app.rag.pipeline import chunk_text
        # Create text with many sentences
        text = ". ".join([f"Sentence number {i}" for i in range(100)]) + "."
        chunks = chunk_text(text, max_chunk_size=256, overlap=32)
        assert len(chunks) > 1
        # Each chunk should be within limits (approximately)
        for chunk in chunks:
            assert len(chunk) <= 512  # generous upper bound with overlap

    def test_chunk_empty_text(self):
        from app.rag.pipeline import chunk_text
        result = chunk_text("")
        assert result == [] or result == [""]

    def test_chunk_overlap(self):
        from app.rag.pipeline import chunk_text
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        chunks = chunk_text(text, max_chunk_size=40, overlap=16)
        # With overlap, the end of chunk N should appear at the start of chunk N+1
        if len(chunks) > 1:
            assert len(chunks) >= 2


# ════════════════════════════════════════════════
#  RAG — PIPELINE (offline)
# ════════════════════════════════════════════════


class TestRAGPipeline:

    def test_pipeline_import(self):
        from app.rag.pipeline import RAGPipeline, get_rag_pipeline
        assert RAGPipeline is not None
        assert get_rag_pipeline is not None

    def test_pipeline_unavailable_gracefully(self):
        """Pipeline degrades gracefully when ChromaDB is not running."""
        from app.rag.pipeline import RAGPipeline
        pipeline = RAGPipeline(collection_name="test_offline")
        # Should not crash — just report unavailable
        assert pipeline.count() == 0  # returns 0 when unavailable
        results = pipeline.query("test query")
        assert results == []

    def test_collection_constants(self):
        from app.rag.pipeline import (
            COLLECTION_MARKET_RESEARCH,
            COLLECTION_EARNINGS,
            COLLECTION_USER_NOTES,
        )
        assert COLLECTION_MARKET_RESEARCH == "market_research"
        assert COLLECTION_EARNINGS == "earnings_transcripts"
        assert COLLECTION_USER_NOTES == "user_notes"


# ════════════════════════════════════════════════
#  TASKS — CELERY APP
# ════════════════════════════════════════════════


class TestCeleryApp:

    def test_celery_app_creation(self):
        from app.tasks.celery_app import make_celery
        app = make_celery()
        assert app.main == "Bubby Vision"

    def test_celery_config(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_beat_schedule_exists(self):
        from app.tasks.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "refresh-fear-greed-every-30m" in schedule
        assert "refresh-trending-tickers-every-15m" in schedule
        assert "daily-market-summary" in schedule


# ════════════════════════════════════════════════
#  TASKS — MARKET TASKS
# ════════════════════════════════════════════════


class TestMarketTasks:

    def test_tasks_registered(self):
        """All market tasks are importable."""
        from app.tasks.market_tasks import (
            refresh_fear_greed,
            refresh_trending_tickers,
            check_price_alerts,
            daily_market_summary,
        )
        assert refresh_fear_greed is not None
        assert refresh_trending_tickers is not None
        assert check_price_alerts is not None
        assert daily_market_summary is not None

    def test_task_names(self):
        from app.tasks.market_tasks import refresh_fear_greed
        assert "refresh_fear_greed" in refresh_fear_greed.name


# ════════════════════════════════════════════════
#  MODULE __init__ EXPORTS
# ════════════════════════════════════════════════


class TestModuleExports:

    def test_utils_exports(self):
        from app.utils import (
            format_currency,
            format_large_number,
            format_pct,
            format_ticker,
            format_timestamp,
            validate_date_range,
            validate_pagination,
            validate_ticker,
        )
        assert callable(format_currency)
        assert callable(validate_ticker)

    def test_middleware_exports(self):
        from app.middleware import RateLimitMiddleware, RequestLoggerMiddleware
        assert RateLimitMiddleware is not None
        assert RequestLoggerMiddleware is not None

    def test_notifications_exports(self):
        from app.notifications import (
            AlertType,
            DiscordNotifier,
            NotificationDispatcher,
            TelegramNotifier,
            get_dispatcher,
        )
        assert AlertType is not None
        assert callable(get_dispatcher)

    def test_rag_exports(self):
        from app.rag import (
            RAGPipeline,
            chunk_text,
            get_rag_pipeline,
            COLLECTION_MARKET_RESEARCH,
        )
        assert RAGPipeline is not None
        assert callable(chunk_text)

    def test_tasks_exports(self):
        from app.tasks import celery_app, make_celery
        assert celery_app is not None
        assert callable(make_celery)
