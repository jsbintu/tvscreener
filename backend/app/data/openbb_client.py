"""
Bubby Vision — OpenBB Data Client

Secondary data provider using OpenBB Platform SDK.
Provides:
  1. Net-new data not covered by other clients (institutional ownership,
     economic calendar, dividend history, ETF holdings, analyst estimates)
  2. Fallback methods when primary clients (yfinance, Finnhub) fail

The OpenBB SDK is LAZY-LOADED to avoid startup overhead and Python 3.14
compatibility issues (scipy deadlock). The SDK only loads on first call.
"""

from __future__ import annotations

import structlog
from datetime import datetime, timedelta
from typing import Optional

log = structlog.get_logger(__name__)

# ── Lazy OpenBB SDK loading ──────────────────────────────────────────────
# OpenBB and its dependencies (scipy, pandas) can deadlock on Python 3.14
# at module import time. We defer loading until first actual use.
_obb = None
_obb_available = True  # Assumed available; set False on first-use failure


def _get_obb():
    """Lazy-load the OpenBB SDK on first call."""
    global _obb, _obb_available
    if _obb is not None:
        return _obb
    if not _obb_available:
        return None
    try:
        from openbb import obb
        _obb = obb
        log.info("openbb_sdk_loaded")
        return _obb
    except Exception as e:
        _obb_available = False
        log.warning("openbb_sdk_unavailable", error=str(e))
        return None


class OpenBBClient:
    """OpenBB Platform data client with lazy SDK loading."""

    # ──────────────────────────────────────────────
    # Institutional Ownership (13F)
    # ──────────────────────────────────────────────

    def get_institutional_ownership(
        self,
        ticker: str,
        limit: int = 20,
    ) -> Optional[dict]:
        """
        Top institutional holders from SEC 13F filings.
        Returns dict with 'holders' list, 'total_institutional_pct', and metadata.
        """
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.equity.ownership.institutional(
                symbol=ticker.upper(),
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            holders = []
            for row in result.results[:limit]:
                holders.append({
                    "name": getattr(row, "investor", None) or getattr(row, "name", "Unknown"),
                    "shares": getattr(row, "shares", 0) or 0,
                    "value": getattr(row, "value", None),
                    "weight_pct": getattr(row, "weight", None) or getattr(row, "pct_held", None),
                    "change_shares": getattr(row, "change", None),
                    "change_pct": getattr(row, "change_pct", None),
                    "date_reported": str(getattr(row, "date_reported", "")) or None,
                })

            return {
                "ticker": ticker.upper(),
                "holders": holders,
                "total_count": len(result.results),
                "source": "openbb_yfinance",
            }
        except Exception as e:
            log.warning("openbb_institutional_error", ticker=ticker, error=str(e))
            return None

    # ──────────────────────────────────────────────
    # Economic Calendar
    # ──────────────────────────────────────────────

    def get_economic_calendar(
        self,
        days_ahead: int = 7,
    ) -> Optional[dict]:
        """
        Upcoming economic events (GDP, CPI, FOMC, NFP, etc).
        Returns dict with 'events' list.
        """
        obb = _get_obb()
        if obb is None:
            return None
        try:
            start = datetime.now().strftime("%Y-%m-%d")
            end = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

            result = obb.economy.calendar(
                start_date=start,
                end_date=end,
                provider="fmp",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            events = []
            for row in result.results:
                country = getattr(row, "country", "") or ""
                # Filter to US events only
                if country and country.upper() not in ("US", "USA", "UNITED STATES"):
                    continue
                events.append({
                    "date": str(getattr(row, "date", "")),
                    "event": getattr(row, "event", "Unknown"),
                    "country": "US",
                    "actual": getattr(row, "actual", None),
                    "forecast": getattr(row, "consensus", None) or getattr(row, "forecast", None),
                    "previous": getattr(row, "previous", None),
                    "importance": getattr(row, "importance", "medium") or "medium",
                    "unit": getattr(row, "unit", None),
                })

            return {
                "events": events,
                "period": f"{start} to {end}",
                "source": "openbb_fmp",
            }
        except Exception as e:
            log.warning("openbb_calendar_error", error=str(e))
            return None

    # ──────────────────────────────────────────────
    # Dividend History
    # ──────────────────────────────────────────────

    def get_dividend_history(
        self,
        ticker: str,
        limit: int = 20,
    ) -> Optional[dict]:
        """
        Historical dividend payments for a ticker.
        Returns dict with 'dividends' list and summary stats.
        """
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.equity.fundamental.dividends(
                symbol=ticker.upper(),
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            dividends = []
            for row in result.results[:limit]:
                dividends.append({
                    "ex_date": str(getattr(row, "ex_dividend_date", "") or getattr(row, "date", "")),
                    "pay_date": str(getattr(row, "payment_date", "") or ""),
                    "record_date": str(getattr(row, "record_date", "") or ""),
                    "amount": getattr(row, "amount", 0.0) or 0.0,
                })

            # Compute annualized yield from last 4 dividends
            annual_div = sum(d["amount"] for d in dividends[:4]) if dividends else 0
            last_amount = dividends[0]["amount"] if dividends else 0

            return {
                "ticker": ticker.upper(),
                "dividends": dividends,
                "total_records": len(result.results),
                "trailing_annual_dividend": round(annual_div, 4),
                "last_dividend": round(last_amount, 4),
                "source": "openbb_yfinance",
            }
        except Exception as e:
            log.warning("openbb_dividends_error", ticker=ticker, error=str(e))
            return None

    # ──────────────────────────────────────────────
    # ETF Holdings
    # ──────────────────────────────────────────────

    def get_etf_holdings(
        self,
        ticker: str,
        limit: int = 25,
    ) -> Optional[dict]:
        """
        Top holdings of an ETF by weight.
        Returns dict with 'holdings' list and metadata.
        """
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.etf.holdings(
                symbol=ticker.upper(),
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            holdings = []
            for row in result.results[:limit]:
                holdings.append({
                    "symbol": getattr(row, "symbol", None),
                    "name": getattr(row, "name", "") or getattr(row, "symbol", "Unknown"),
                    "weight_pct": round((getattr(row, "weight", 0) or 0) * 100, 4),
                    "shares": getattr(row, "shares", None),
                    "market_value": getattr(row, "market_value", None),
                })

            return {
                "ticker": ticker.upper(),
                "holdings": holdings,
                "total_holdings": len(result.results),
                "source": "openbb_yfinance",
            }
        except Exception as e:
            log.warning("openbb_etf_holdings_error", ticker=ticker, error=str(e))
            return None

    # ──────────────────────────────────────────────
    # Analyst Estimates
    # ──────────────────────────────────────────────

    def get_analyst_estimates(
        self,
        ticker: str,
    ) -> Optional[dict]:
        """
        Forward revenue and EPS consensus estimates.
        Returns dict with 'estimates' list.
        """
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.equity.estimates.consensus(
                symbol=ticker.upper(),
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            estimates = []
            for row in result.results:
                estimates.append({
                    "period": getattr(row, "period", "") or str(getattr(row, "date", "")),
                    "revenue_estimate": getattr(row, "revenue_avg", None) or getattr(row, "estimated_revenue_avg", None),
                    "revenue_low": getattr(row, "revenue_low", None) or getattr(row, "estimated_revenue_low", None),
                    "revenue_high": getattr(row, "revenue_high", None) or getattr(row, "estimated_revenue_high", None),
                    "eps_estimate": getattr(row, "eps_avg", None) or getattr(row, "estimated_eps_avg", None),
                    "eps_low": getattr(row, "eps_low", None) or getattr(row, "estimated_eps_low", None),
                    "eps_high": getattr(row, "eps_high", None) or getattr(row, "estimated_eps_high", None),
                    "num_analysts": getattr(row, "number_of_analysts", None) or getattr(row, "num_analysts", None),
                })

            return {
                "ticker": ticker.upper(),
                "estimates": estimates,
                "source": "openbb_yfinance",
            }
        except Exception as e:
            log.warning("openbb_estimates_error", ticker=ticker, error=str(e))
            return None

    # ──────────────────────────────────────────────
    # World / Market-Wide News (Bloomberg's killer feature)
    # ──────────────────────────────────────────────

    def get_world_news(
        self,
        limit: int = 50,
        topic: str | None = None,
    ) -> Optional[dict]:
        """
        Global market news — macro, geopolitical, central bank, earnings.
        This is the Bloomberg Terminal equivalent: the unified news wire.

        Tries multiple providers in priority order:
          1. benzinga (requires API key)
          2. biztoc (free)
          3. tiingo (requires API key)
          4. yfinance (always available)
        """
        obb = _get_obb()
        if obb is None:
            return None

        providers = ["benzinga", "biztoc", "tiingo", "yfinance"]
        result = None
        source_provider = None

        for provider in providers:
            try:
                kwargs: dict = {
                    "limit": limit,
                    "provider": provider,
                }
                result = obb.news.world(**kwargs)
                if result and hasattr(result, 'results') and result.results:
                    source_provider = provider
                    break
            except Exception:
                continue

        if result is None or not hasattr(result, 'results') or not result.results:
            return None

        articles = []
        for row in result.results[:limit]:
            title = getattr(row, "title", "") or ""
            if topic and topic.lower() not in title.lower():
                continue
            articles.append({
                "title": title,
                "url": getattr(row, "url", "") or getattr(row, "link", ""),
                "published": str(getattr(row, "date", "") or getattr(row, "published", "")),
                "source": getattr(row, "source", "") or getattr(row, "publisher", "") or source_provider,
                "summary": getattr(row, "text", "") or getattr(row, "description", ""),
                "images": getattr(row, "images", None),
                "symbols": getattr(row, "symbols", []) or [],
                "tags": getattr(row, "tags", []) or [],
            })

        return {
            "articles": articles,
            "total_count": len(articles),
            "provider": source_provider,
            "source": f"openbb_{source_provider}",
        }

    # ──────────────────────────────────────────────
    # Dedicated Company News (aggregated from multiple providers)
    # ──────────────────────────────────────────────

    def get_company_news_dedicated(
        self,
        ticker: str,
        limit: int = 30,
    ) -> Optional[dict]:
        """
        Aggregated company-specific news from OpenBB.
        Unlike the fallback method, this tries multiple providers
        and merges results for richer coverage.
        """
        obb = _get_obb()
        if obb is None:
            return None

        providers = ["benzinga", "tiingo", "yfinance"]
        all_articles: list[dict] = []
        seen_urls: set[str] = set()
        sources_used: list[str] = []

        for provider in providers:
            try:
                result = obb.news.company(
                    symbol=ticker.upper(),
                    limit=limit,
                    provider=provider,
                )
                if result and hasattr(result, 'results') and result.results:
                    sources_used.append(provider)
                    for row in result.results:
                        url = getattr(row, "url", "") or getattr(row, "link", "")
                        # Deduplicate by URL
                        if url and url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)
                        all_articles.append({
                            "title": getattr(row, "title", ""),
                            "url": url,
                            "published": str(getattr(row, "date", "") or getattr(row, "published", "")),
                            "source": getattr(row, "source", "") or getattr(row, "publisher", "") or provider,
                            "summary": getattr(row, "text", "") or getattr(row, "description", ""),
                            "images": getattr(row, "images", None),
                            "symbols": getattr(row, "symbols", []) or [],
                            "tags": getattr(row, "tags", []) or [],
                            "provider": provider,
                        })
            except Exception as e:
                log.debug("openbb_company_news_provider_skip", provider=provider, error=str(e))
                continue

        if not all_articles:
            return None

        # Sort by published date, newest first
        all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)

        return {
            "ticker": ticker.upper(),
            "articles": all_articles[:limit],
            "total_count": len(all_articles),
            "providers_used": sources_used,
            "source": "openbb_multi",
        }

    # ──────────────────────────────────────────────
    # Fallback Methods
    # ──────────────────────────────────────────────

    def get_quote_fallback(self, ticker: str) -> Optional[dict]:
        """Fallback quote when yfinance primary fails."""
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.equity.price.quote(
                symbol=ticker.upper(),
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results') or not result.results:
                return None

            r = result.results[0]
            return {
                "ticker": ticker.upper(),
                "price": getattr(r, "last_price", None) or getattr(r, "close", 0),
                "change": getattr(r, "change", 0),
                "change_pct": getattr(r, "change_percent", 0),
                "volume": getattr(r, "volume", 0),
                "open": getattr(r, "open", None),
                "high": getattr(r, "high", None),
                "low": getattr(r, "low", None),
                "prev_close": getattr(r, "prev_close", None),
                "source": "openbb_fallback",
            }
        except Exception as e:
            log.warning("openbb_quote_fallback_error", ticker=ticker, error=str(e))
            return None

    def get_earnings_fallback(self, ticker: str) -> Optional[dict]:
        """Fallback earnings data when Finnhub primary fails."""
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.equity.fundamental.historical_eps(
                symbol=ticker.upper(),
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            earnings = []
            for row in result.results[:8]:
                earnings.append({
                    "date": str(getattr(row, "date", "")),
                    "eps_actual": getattr(row, "eps_actual", None) or getattr(row, "actual_eps", None),
                    "eps_estimate": getattr(row, "eps_estimated", None) or getattr(row, "estimated_eps", None),
                    "surprise": getattr(row, "surprise", None) or getattr(row, "eps_surprise", None),
                    "surprise_pct": getattr(row, "surprise_pct", None),
                })

            return {
                "ticker": ticker.upper(),
                "earnings": earnings,
                "source": "openbb_fallback",
            }
        except Exception as e:
            log.warning("openbb_earnings_fallback_error", ticker=ticker, error=str(e))
            return None

    def get_news_fallback(
        self,
        ticker: str,
        limit: int = 20,
    ) -> Optional[dict]:
        """Fallback news when Finnhub/QuantData primary fails."""
        obb = _get_obb()
        if obb is None:
            return None
        try:
            result = obb.news.company(
                symbol=ticker.upper(),
                limit=limit,
                provider="yfinance",
            )
            if result is None or not hasattr(result, 'results'):
                return None

            articles = []
            for row in result.results:
                articles.append({
                    "title": getattr(row, "title", ""),
                    "url": getattr(row, "url", "") or getattr(row, "link", ""),
                    "published": str(getattr(row, "date", "") or getattr(row, "published", "")),
                    "source": getattr(row, "source", "") or getattr(row, "publisher", ""),
                    "summary": getattr(row, "text", "") or getattr(row, "description", ""),
                })

            return {
                "ticker": ticker.upper(),
                "articles": articles,
                "source": "openbb_fallback",
            }
        except Exception as e:
            log.warning("openbb_news_fallback_error", ticker=ticker, error=str(e))
            return None

    # ──────────────────────────────────────────────
    # Health / Status
    # ──────────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """Check if OpenBB SDK is loaded and available."""
        return _obb is not None

    @staticmethod
    def get_status() -> dict:
        """Return SDK status for health checks."""
        return {
            "available": _obb is not None,
            "loaded": _obb is not None,
            "deferred": _obb_available and _obb is None,
        }
