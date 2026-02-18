"""
Bubby Vision — FastAPI Application Entry Point

The central API server. All agent, data, and real-time endpoints are mounted here.
"""

import time as _time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import chat_router, data_router, health_router, links_router, options_live_router, alpaca_data_router, extended_data_router

log = structlog.get_logger("Bubby Vision.startup")

# Track server start time for uptime calculations
APP_START_TIME: float = _time.monotonic()


def _validate_config(settings) -> None:
    """Warn on missing critical API keys at startup."""
    checks = {
        "google_api_key": "Google Gemini (AI agents will not work)",
        "finnhub_api_key": "Finnhub (news, earnings, analyst data unavailable)",
        "alpaca_api_key": "Alpaca (live market data unavailable)",
        "quantdata_api_key": "QuantData (options flow, dark pool unavailable)",
    }
    for attr, description in checks.items():
        if not getattr(settings, attr, ""):
            log.warning("config.missing_key", key=attr, impact=description)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle hooks."""
    settings = get_settings()
    log.info(
        "startup",
        env=settings.app_env,
        questdb=settings.questdb_dsn,
        redis=settings.redis_url,
        chromadb=settings.chromadb_url,
    )

    # ── Config validation ──
    _validate_config(settings)

    # ── QuestDB: ensure schema ──
    try:
        from app.db.questdb_client import get_questdb
        db = get_questdb()
        if db.ensure_tables():
            log.info("questdb.ready")
        else:
            log.warning("questdb.unavailable", detail="running without persistence")
    except Exception as exc:
        log.warning("questdb.init_failed", error=str(exc))

    # ── QuestDB: outcome tracker table ──
    try:
        from app.engines.outcome_tracker import get_outcome_tracker
        tracker = get_outcome_tracker()
        if tracker.ensure_table():
            log.info("outcome_tracker.ready")
    except Exception as exc:
        log.warning("outcome_tracker.init_failed", error=str(exc))

    # ── Redis: warm cache connection ──
    try:
        from app.cache import get_cache
        cache = get_cache()
        if cache.available:
            log.info("redis.ready", url=settings.redis_url)
        else:
            log.warning("redis.unavailable", detail="running without cache")
            # ── Multi-worker safety warning ──
            import os
            workers = os.environ.get("WEB_CONCURRENCY") or os.environ.get("UVICORN_WORKERS")
            if workers and int(workers) > 1:
                log.warning(
                    "multi_worker.no_redis",
                    workers=int(workers),
                    detail=(
                        "Redis is unavailable but multiple workers are configured. "
                        "In-process caches will NOT be shared across workers, "
                        "leading to inconsistent data and wasted memory. "
                        "Either enable Redis or run with a single worker."
                    ),
                )
    except Exception as exc:
        log.warning("redis.init_failed", error=str(exc))

    yield

    # ── Shutdown ──
    try:
        from app.db.questdb_client import get_questdb
        get_questdb().close()
    except Exception:
        pass
    log.info("shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Bubby Vision",
        description="""# Bubby Vision API

AI-powered trading analysis platform with multi-agent architecture.

## Features
- **Real-time Market Data** — Stock quotes, options chains, sentiment
- **AI Analysis** — LangGraph-powered chat with multi-agent orchestration
- **WebSocket Streams** — Live price feeds and alert notifications
- **Watchlists & Alerts** — Custom watchlists with price alert triggers
- **OWASP Hardened** — Input sanitization, rate limiting, audit logging

## Authentication
All endpoints accept an optional `X-API-Key` header.
In development mode, authentication is bypassed.
""",
        version="1.0.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        contact={"name": "Bubby Vision Team", "url": "https://github.com/Bubby Vision"},
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "Health", "description": "Service health and readiness checks"},
            {"name": "Authentication", "description": "User registration, login, and token management"},
            {"name": "Data", "description": "Stock, options, and sentiment data"},
            {"name": "Chat", "description": "AI agent conversation endpoint"},
            {"name": "Market Data", "description": "Sentiment, flow, TradingView, and WSB data"},
            {"name": "Live Options", "description": "Real-time options from Alpaca"},
            {"name": "Alpaca Market Data", "description": "Snapshots, news, and account info"},
            {"name": "Extended Data", "description": "Financials, earnings, analyst, insider, dark pool"},
            {"name": "Watchlist & Alerts", "description": "User watchlists and price alerts"},
            {"name": "External Links", "description": "Quick links to third-party tools"},
            {"name": "WebSocket", "description": "Real-time price and alert streams"},
            {"name": "Metrics", "description": "Prometheus-compatible metrics exposition"},
            {"name": "Audit", "description": "Request audit trail and logging"},
        ],
        swagger_ui_parameters={
            "deepLinking": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "filter": True,
            "syntaxHighlight.theme": "monokai",
        },
    )

    # ── Global Error Handlers ──
    from app.error_handlers import register_error_handlers
    register_error_handlers(app)

    # ── CORS (configurable from settings) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom Middleware ──
    from app.middleware.request_logger import RequestLoggerMiddleware
    from app.middleware.rate_limiter import RateLimitMiddleware
    from app.middleware.auth import AuthMiddleware

    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=60,
        window_seconds=60,
        redis_url=settings.redis_url,
    )
    app.add_middleware(AuthMiddleware)

    # ── Security Headers ──
    from app.middleware.security import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # ── Metrics Collection (outermost → captures full lifecycle) ──
    from app.metrics import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)

    # ── Audit Logging ──
    from app.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)

    # ── GZip Response Compression ──
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # ── Routes (unversioned) ──
    app.include_router(health_router, tags=["Health"])

    # ── Routes (v1 API) ──
    API_V1 = "/v1/api"
    app.include_router(data_router, prefix=API_V1, tags=["Data"])
    app.include_router(chat_router, prefix=API_V1, tags=["Chat"])
    app.include_router(links_router, prefix=API_V1, tags=["External Links"])
    app.include_router(options_live_router, prefix=API_V1, tags=["Live Options"])
    app.include_router(alpaca_data_router, prefix=API_V1, tags=["Alpaca Market Data"])
    app.include_router(extended_data_router, prefix=API_V1, tags=["Extended Data"])

    # ── Authentication (v1) ──
    from app.auth import auth_router
    app.include_router(auth_router, prefix=API_V1, tags=["Authentication"])

    # ── WebSocket (unversioned) ──
    from app.websocket import ws_router
    app.include_router(ws_router, tags=["WebSocket"])

    # ── Watchlist & Alerts (v1) ──
    from app.routes_watchlist import watchlist_router
    app.include_router(watchlist_router, prefix=API_V1, tags=["Watchlist & Alerts"])

    # ── Chat History Persistence (v1) ──
    from app.routes_chat_history import chat_history_router
    app.include_router(chat_history_router, prefix=API_V1, tags=["Chat History"])

    # ── User Preferences (v1) ──
    from app.routes_preferences import preferences_router
    app.include_router(preferences_router, prefix=API_V1, tags=["Preferences"])

    # ── Filter Presets (v1) ──
    from app.routes_presets import presets_router
    app.include_router(presets_router, prefix=API_V1, tags=["Presets"])

    # ── Market Data (v1) ──
    from app.routes_market import market_router
    app.include_router(market_router, prefix=API_V1, tags=["Market Data"])

    # ── Metrics (unversioned) ──
    from app.metrics import metrics_router
    app.include_router(metrics_router, tags=["Metrics"])

    # ── Audit Log (v1) ──
    from app.middleware.audit import audit_router
    app.include_router(audit_router, prefix=API_V1, tags=["Audit"])

    # ── API Version Header ──
    @app.middleware("http")
    async def add_api_version_header(request, call_next):
        response = await call_next(request)
        response.headers["X-API-Version"] = "v1"
        return response

    return app


app = create_app()
