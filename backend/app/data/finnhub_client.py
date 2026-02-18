"""
Bubby Vision — Finnhub Data Client

Provides earnings data, company news with sentiment, insider transactions,
and analyst recommendations via the Finnhub API.

Free tier: 60 calls/min.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog

from app.config import get_settings
from app.models import NewsItem

log = structlog.get_logger(__name__)


_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubClient:
    """Wrapper around Finnhub REST API."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.finnhub_api_key
        self._headers = {"X-Finnhub-Token": self._api_key}

    @property
    def _is_configured(self) -> bool:
        return bool(self._api_key)

    async def get_company_news(
        self,
        ticker: str,
        days_back: int = 7,
        limit: int = 20,
    ) -> list[NewsItem]:
        """Fetch company news articles with sentiment."""
        if not self._is_configured:
            return self._news_fallback(ticker, limit)

        end = datetime.utcnow()
        start = end - timedelta(days=days_back)

        params = {
            "symbol": ticker.upper(),
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
        }

        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
                resp = await client.get(f"{_BASE_URL}/company-news", params=params)
                resp.raise_for_status()
                articles = resp.json()
        except Exception as e:
            log.warning("finnhub_news_failed_trying_openbb", ticker=ticker, error=str(e))
            return self._news_fallback(ticker, limit)

        items = []
        for article in articles[:limit]:
            dt = datetime.fromtimestamp(article.get("datetime", 0))
            items.append(
                NewsItem(
                    headline=article.get("headline", ""),
                    summary=article.get("summary", ""),
                    source=article.get("source", ""),
                    url=article.get("url", ""),
                    datetime_published=dt,
                    ticker=ticker.upper(),
                )
            )
        return items

    def _news_fallback(self, ticker: str, limit: int = 20) -> list[NewsItem]:
        """OpenBB fallback for company news."""
        try:
            from app.data.openbb_client import OpenBBClient
            data = OpenBBClient().get_news_fallback(ticker, limit=limit)
            if data and data.get("articles"):
                items = []
                for a in data["articles"]:
                    items.append(
                        NewsItem(
                            headline=a.get("title", ""),
                            summary=a.get("summary", ""),
                            source=a.get("source", "openbb"),
                            url=a.get("url", ""),
                            datetime_published=datetime.now(),
                            ticker=ticker.upper(),
                        )
                    )
                return items
        except Exception as e:
            log.warning("openbb_news_fallback_failed", ticker=ticker, error=str(e))
        return []

    async def get_sentiment(self, ticker: str) -> dict:
        """Fetch social sentiment (Reddit + Twitter mention counts and scores)."""
        if not self._is_configured:
            return {"error": "Finnhub API key not configured"}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/social-sentiment",
                params={"symbol": ticker.upper()},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_insider_transactions(self, ticker: str) -> list[dict]:
        """Fetch insider transactions for a company."""
        if not self._is_configured:
            return []

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/insider-transactions",
                params={"symbol": ticker.upper()},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def get_earnings_calendar(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[dict]:
        """Fetch earnings calendar. Default: next 7 days."""
        if not self._is_configured:
            return []

        if not from_date:
            from_date = datetime.utcnow().strftime("%Y-%m-%d")
        if not to_date:
            to_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        params = {"from": from_date, "to": to_date}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(f"{_BASE_URL}/calendar/earnings", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("earningsCalendar", [])

    async def get_recommendation_trends(self, ticker: str) -> list[dict]:
        """Fetch analyst recommendation trends."""
        if not self._is_configured:
            return []

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/recommendation",
                params={"symbol": ticker.upper()},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Phase 6 additions ──

    async def get_earnings_estimates(self, ticker: str, freq: str = "quarterly") -> list[dict]:
        """Fetch forward EPS estimates.

        Args:
            ticker: Stock ticker symbol.
            freq: 'quarterly' or 'annual'.
        """
        if not self._is_configured:
            return self._earnings_fallback(ticker)

        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
                resp = await client.get(
                    f"{_BASE_URL}/stock/eps-estimate",
                    params={"symbol": ticker.upper(), "freq": freq},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            log.warning("finnhub_earnings_failed_trying_openbb", ticker=ticker, error=str(e))
            return self._earnings_fallback(ticker)

    def _earnings_fallback(self, ticker: str) -> list[dict]:
        """OpenBB fallback for earnings estimates."""
        try:
            from app.data.openbb_client import OpenBBClient
            data = OpenBBClient().get_earnings_fallback(ticker)
            if data and data.get("earnings"):
                return data["earnings"]
        except Exception as e:
            log.warning("openbb_earnings_fallback_failed", ticker=ticker, error=str(e))
        return []

    async def get_price_target(self, ticker: str) -> dict:
        """Fetch analyst price target consensus (high, low, mean, median).

        Args:
            ticker: Stock ticker symbol.
        """
        if not self._is_configured:
            return {}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/price-target",
                params={"symbol": ticker.upper()},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_basic_financials(self, ticker: str) -> dict:
        """Fetch 100+ fundamental metrics (PE, PB, ROE, margins, debt ratios, etc.).

        Args:
            ticker: Stock ticker symbol.
        """
        if not self._is_configured:
            return {}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/metric",
                params={"symbol": ticker.upper(), "metric": "all"},
            )
            resp.raise_for_status()
            data = resp.json()
            # Flatten — 'metric' contains the actual data
            return data.get("metric", {})

    async def get_insider_sentiment(self, ticker: str) -> dict:
        """Fetch aggregated insider sentiment (net buy/sell ratio).

        Shows monthly insider purchase activity ratio (MSPR).
        Positive = net insider buying. Negative = net selling.

        Args:
            ticker: Stock ticker symbol.
        """
        if not self._is_configured:
            return {}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/insider-sentiment",
                params={"symbol": ticker.upper()},
            )
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("data", [])

            if not entries:
                return {"ticker": ticker.upper(), "months": []}

            return {
                "ticker": data.get("symbol", ticker.upper()),
                "months": [
                    {
                        "year": e.get("year"),
                        "month": e.get("month"),
                        "change": e.get("change", 0),
                        "mspr": e.get("mspr", 0),
                    }
                    for e in entries
                ],
            }

    async def get_earnings_transcripts(
        self,
        ticker: str,
        quarter: Optional[int] = None,
        year: Optional[int] = None,
    ) -> dict:
        """Fetch earnings call transcript.

        Covers the Octagon AI use case — 10+ years of earnings call transcripts.

        Args:
            ticker: Stock ticker symbol.
            quarter: Quarter number (1-4). Omit for latest.
            year: Year. Omit for latest.
        """
        if not self._is_configured:
            return {}

        # Determine quarter/year if not provided
        if quarter is None or year is None:
            now = datetime.utcnow()
            if year is None:
                year = now.year
            if quarter is None:
                quarter = (now.month - 1) // 3  # Previous quarter
                if quarter == 0:
                    quarter = 4
                    year -= 1

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(
                f"{_BASE_URL}/stock/transcripts",
                params={"symbol": ticker.upper(), "quarter": quarter, "year": year},
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "ticker": data.get("symbol", ticker.upper()),
                "quarter": data.get("quarter"),
                "year": data.get("year"),
                "title": data.get("title", ""),
                "participants": data.get("participant", []),
                "transcript": data.get("transcript", []),
            }

