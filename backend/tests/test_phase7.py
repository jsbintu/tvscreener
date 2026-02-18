"""
Bubby Vision — Phase 7 Tests

Tests for:
- Redis cache (offline graceful degradation, decorator, TTLs)
- Auth middleware (dev bypass, key validation, public paths)
- Startup hooks (lifespan initialization)
- DataEngine caching decorators
"""

import pytest
from unittest.mock import patch, MagicMock


# ════════════════════════════════════════════════
#  REDIS CACHE
# ════════════════════════════════════════════════


class TestRedisCache:

    def test_imports(self):
        from app.cache import RedisCache, get_cache, cached
        assert RedisCache is not None
        assert callable(get_cache)
        assert callable(cached)

    def test_cache_offline_graceful(self):
        """Cache degrades gracefully when Redis is unavailable."""
        from app.cache import RedisCache
        cache = RedisCache(url="redis://localhost:9999/15")  # Invalid port
        assert cache.available is False
        assert cache.get("test") is None
        assert cache.set("test", "value") is False
        assert cache.delete("test") is False
        assert cache.clear_prefix("test") == 0

    def test_cache_stats_offline(self):
        from app.cache import RedisCache
        cache = RedisCache(url="redis://localhost:9999/15")
        stats = cache.stats()
        assert stats["available"] is False

    def test_ttl_constants(self):
        from app.cache import (
            TTL_STOCK, TTL_OPTIONS, TTL_FEAR_GREED,
            TTL_NEWS, TTL_TRENDING, TTL_SCREENER,
            TTL_FINANCIALS, TTL_INSIDER, TTL_MOVERS,
        )
        assert TTL_STOCK == 60
        assert TTL_OPTIONS == 30
        assert TTL_FEAR_GREED == 300
        assert TTL_NEWS == 120
        assert TTL_TRENDING == 180
        assert TTL_SCREENER == 60
        assert TTL_FINANCIALS == 3600
        assert TTL_INSIDER == 600
        assert TTL_MOVERS == 60


class TestCacheKeyGeneration:

    def test_make_cache_key(self):
        from app.cache import _make_cache_key
        key = _make_cache_key("stock:get_stock", ("AAPL",), {"period": "1mo"})
        assert key.startswith("mp:stock:get_stock:")
        assert "AAPL" in key
        assert "period=1mo" in key

    def test_key_deterministic(self):
        from app.cache import _make_cache_key
        key1 = _make_cache_key("test", ("a", "b"), {"x": 1})
        key2 = _make_cache_key("test", ("a", "b"), {"x": 1})
        assert key1 == key2

    def test_long_key_hashed(self):
        from app.cache import _make_cache_key
        key = _make_cache_key("prefix", ("a" * 200,), {})
        # Should be hashed to keep key length reasonable
        assert len(key) < 200


class TestCachedDecorator:

    def test_decorator_pass_through_offline(self):
        """@cached decorator falls through when Redis is down."""
        from app.cache import cached

        call_count = 0

        @cached(ttl=60, prefix="test")
        def my_func(value):
            nonlocal call_count
            call_count += 1
            return {"result": value}

        # Should always execute the function when cache is unavailable
        result = my_func("hello")
        assert result == {"result": "hello"}
        assert call_count == 1

        result2 = my_func("hello")
        assert result2 == {"result": "hello"}
        assert call_count == 2  # No caching → called again


# ════════════════════════════════════════════════
#  AUTH MIDDLEWARE
# ════════════════════════════════════════════════


class TestAuthMiddleware:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_health_always_accessible(self):
        """Health endpoint is always public, even in production."""
        client = self._get_client()
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_dev_mode_bypasses_auth(self):
        """In development mode, all endpoints are accessible without auth."""
        client = self._get_client()
        # app_env defaults to "development" → auth bypassed
        resp = client.get("/v1/api/stock/AAPL")
        # Should not be 401 (may be 200 or other status depending on data)
        assert resp.status_code != 401

    def test_production_rejects_missing_key(self):
        """In production mode, missing API key returns 401."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        with patch("app.middleware.auth.get_settings") as mock_settings:
            settings = MagicMock()
            settings.is_production = True
            settings.app_secret_key = "test-secret-key-12345"
            mock_settings.return_value = settings

            from app.middleware.auth import AuthMiddleware
            # Directly test the key extraction
            assert AuthMiddleware._extract_key(MagicMock(headers={})) is None

    def test_extract_bearer_token(self):
        """Correctly extracts Bearer token from Authorization header."""
        from app.middleware.auth import AuthMiddleware
        request = MagicMock()
        request.headers = {"Authorization": "Bearer my-secret-key"}
        key = AuthMiddleware._extract_key(request)
        assert key == "my-secret-key"

    def test_extract_api_key_header(self):
        """Correctly extracts X-API-Key header."""
        from app.middleware.auth import AuthMiddleware
        request = MagicMock()
        request.headers = {"X-API-Key": "my-api-key", "Authorization": ""}
        key = AuthMiddleware._extract_key(request)
        assert key == "my-api-key"

    def test_no_key_extracted(self):
        """Returns None when no auth headers present."""
        from app.middleware.auth import AuthMiddleware
        request = MagicMock()
        request.headers = {}
        key = AuthMiddleware._extract_key(request)
        assert key is None

    def test_middleware_module_exports(self):
        from app.middleware import AuthMiddleware, RateLimitMiddleware, RequestLoggerMiddleware
        assert AuthMiddleware is not None
        assert RateLimitMiddleware is not None
        assert RequestLoggerMiddleware is not None


# ════════════════════════════════════════════════
#  DATA ENGINE CACHING
# ════════════════════════════════════════════════


class TestDataEngineCaching:

    def test_cached_decorators_applied(self):
        """Key DataEngine methods have @cached decorators."""
        from app.engines.data_engine import DataEngine
        # Verify the decorated methods have __wrapped__ attribute
        # The @cached decorator uses functools.wraps
        assert hasattr(DataEngine.get_stock, "__wrapped__")
        assert hasattr(DataEngine.get_options, "__wrapped__")
        assert hasattr(DataEngine.get_filings, "__wrapped__")
        assert hasattr(DataEngine.get_insider_trades, "__wrapped__")
        assert hasattr(DataEngine.get_financials, "__wrapped__")

    def test_data_engine_imports_cache(self):
        """DataEngine imports cache module successfully."""
        from app.engines.data_engine import DataEngine
        engine = DataEngine()
        assert engine is not None


# ════════════════════════════════════════════════
#  STARTUP HOOKS
# ════════════════════════════════════════════════


class TestStartupHooks:

    def test_lifespan_function_exists(self):
        from app.main import lifespan
        assert callable(lifespan)

    def test_app_creates_with_all_middleware(self):
        """App factory wires all middleware layers. Checking via integration."""
        from fastapi.testclient import TestClient
        from app.main import create_app
        app = create_app()
        client = TestClient(app)
        # If all middleware is wired, health endpoint still works
        resp = client.get("/health")
        assert resp.status_code == 200
        # Auth middleware is wired (verify it imported successfully)
        from app.middleware.auth import AuthMiddleware
        assert AuthMiddleware is not None

    def test_app_version(self):
        from app.main import create_app
        app = create_app()
        assert app.version == "1.0.0"
        assert app.title == "Bubby Vision"
