#!/usr/bin/env python3
"""
MarketPilot — Market Data Seeder

Fetches 1-year daily OHLCV data for top S&P 500 tickers using yfinance
and batch-inserts into QuestDB. Idempotent via dedup on (ticker, ts).

Usage:
    python -m scripts.seed_market_data
    python -m scripts.seed_market_data --tickers AAPL MSFT GOOGL --period 6mo
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import structlog

log = structlog.get_logger("seed_market_data")

# Top 50 S&P 500 tickers by weight
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B",
    "UNH", "XOM", "JNJ", "JPM", "V", "PG", "MA", "AVGO", "HD", "CVX",
    "MRK", "ABBV", "LLY", "COST", "PEP", "KO", "WMT", "ADBE", "MCD",
    "CRM", "TMO", "CSCO", "ACN", "ABT", "NFLX", "AMD", "DHR", "LIN",
    "WFC", "TXN", "PM", "NEE", "ORCL", "CMCSA", "BMY", "UPS", "COP",
    "BA", "RTX", "INTC", "QCOM", "AMGN",
]


def seed(tickers: list[str], period: str = "1y") -> dict:
    """Fetch OHLCV from yfinance and insert into QuestDB.

    Args:
        tickers: List of ticker symbols.
        period: yfinance period string (e.g., '1y', '6mo', '2y').

    Returns:
        Dict with 'success', 'failed', and 'total_rows' counts.
    """
    import yfinance as yf
    from app.db.questdb_client import get_questdb

    db = get_questdb()
    if not db.available:
        log.error("questdb.unavailable", detail="Cannot seed without database")
        return {"success": 0, "failed": len(tickers), "total_rows": 0}

    db.ensure_tables()

    results = {"success": 0, "failed": 0, "total_rows": 0}

    for i, ticker in enumerate(tickers, 1):
        log.info("seeding", ticker=ticker, progress=f"{i}/{len(tickers)}")

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval="1d")

            if hist.empty:
                log.warning("no_data", ticker=ticker)
                results["failed"] += 1
                continue

            bars = []
            for ts, row in hist.iterrows():
                bars.append({
                    "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })

            inserted = db.insert_ohlcv(ticker, bars)
            results["success"] += 1
            results["total_rows"] += inserted
            log.info("seeded", ticker=ticker, rows=inserted)

        except Exception as exc:
            log.error("seed_failed", ticker=ticker, error=str(exc))
            results["failed"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="Seed QuestDB with historical OHLCV data")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker symbols to seed (default: top 50 S&P 500)",
    )
    parser.add_argument(
        "--period",
        default="1y",
        choices=["1mo", "3mo", "6mo", "1y", "2y", "5y"],
        help="Historical period to fetch (default: 1y)",
    )
    args = parser.parse_args()

    log.info("starting", tickers=len(args.tickers), period=args.period)
    results = seed(args.tickers, args.period)

    log.info(
        "complete",
        success=results["success"],
        failed=results["failed"],
        total_rows=results["total_rows"],
    )

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
