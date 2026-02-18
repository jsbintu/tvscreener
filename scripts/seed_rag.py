#!/usr/bin/env python3
"""
MarketPilot — RAG Data Seeder

Fetches SEC filings and earnings data for key tickers and ingests them
into ChromaDB via the RAG pipeline for AI chat context retrieval.

Usage:
    python -m scripts.seed_rag
    python -m scripts.seed_rag --tickers AAPL MSFT --max-filings 5
"""

from __future__ import annotations

import argparse
import sys

import structlog

log = structlog.get_logger("seed_rag")

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA",
    "JPM", "V", "UNH", "JNJ", "XOM", "LLY", "AVGO", "MA",
]


def _fetch_edgar_filings(ticker: str, max_filings: int = 3) -> list[dict]:
    """Fetch recent SEC filings (10-K, 10-Q) for a ticker.

    Returns:
        List of dicts with 'doc_id', 'text', and 'metadata'.
    """
    documents = []

    try:
        from edgartools import Company

        company = Company(ticker)
        filings = company.get_filings(
            form=["10-K", "10-Q"],
        ).latest(max_filings)

        for filing in filings:
            try:
                doc_text = str(filing.text())[:50000]  # Cap at 50k chars
                if len(doc_text) < 100:
                    continue

                doc_id = f"sec_{ticker}_{filing.form}_{filing.filing_date}"
                documents.append({
                    "doc_id": doc_id,
                    "text": doc_text,
                    "metadata": {
                        "source": "sec_edgar",
                        "ticker": ticker,
                        "form_type": filing.form,
                        "filing_date": str(filing.filing_date),
                    },
                })
                log.info("filing_fetched", ticker=ticker, form=filing.form, length=len(doc_text))

            except Exception as exc:
                log.warning("filing_parse_failed", ticker=ticker, error=str(exc))

    except Exception as exc:
        log.warning("edgar_fetch_failed", ticker=ticker, error=str(exc))

    return documents


def _fetch_news_summaries(ticker: str) -> list[dict]:
    """Fetch recent news articles for a ticker via Finnhub.

    Returns:
        List of dicts with 'doc_id', 'text', and 'metadata'.
    """
    documents = []

    try:
        from datetime import datetime, timedelta
        import finnhub

        from app.config import get_settings
        settings = get_settings()

        if not settings.finnhub_api_key:
            return documents

        client = finnhub.Client(api_key=settings.finnhub_api_key)
        end = datetime.now()
        start = end - timedelta(days=30)

        news = client.company_news(
            ticker,
            _from=start.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
        )

        for article in news[:20]:  # Limit to 20 articles
            summary = article.get("summary", "")
            headline = article.get("headline", "")
            text = f"{headline}\n\n{summary}" if summary else headline

            if len(text) < 50:
                continue

            doc_id = f"news_{ticker}_{article.get('id', article.get('datetime', ''))}"
            documents.append({
                "doc_id": doc_id,
                "text": text,
                "metadata": {
                    "source": "finnhub_news",
                    "ticker": ticker,
                    "headline": headline[:200],
                    "published": str(article.get("datetime", "")),
                    "url": article.get("url", ""),
                },
            })

    except Exception as exc:
        log.warning("news_fetch_failed", ticker=ticker, error=str(exc))

    return documents


def seed(tickers: list[str], max_filings: int = 3) -> dict:
    """Fetch documents and ingest into ChromaDB.

    Args:
        tickers: List of ticker symbols.
        max_filings: Max SEC filings per ticker.

    Returns:
        Dict with ingestion stats.
    """
    from app.rag.pipeline import get_rag_pipeline

    rag = get_rag_pipeline()
    if not rag.available:
        log.error("chromadb.unavailable", detail="Cannot seed without ChromaDB")
        return {"tickers": 0, "documents": 0, "chunks": 0}

    stats = {"tickers": 0, "documents": 0, "chunks": 0}

    for i, ticker in enumerate(tickers, 1):
        log.info("seeding_rag", ticker=ticker, progress=f"{i}/{len(tickers)}")

        # Fetch SEC filings
        docs = _fetch_edgar_filings(ticker, max_filings=max_filings)

        # Fetch news
        docs.extend(_fetch_news_summaries(ticker))

        if not docs:
            log.warning("no_documents", ticker=ticker)
            continue

        # Ingest all documents
        ticker_chunks = 0
        for doc in docs:
            chunks = rag.ingest(
                doc_id=doc["doc_id"],
                text=doc["text"],
                metadata=doc["metadata"],
            )
            ticker_chunks += chunks
            stats["documents"] += 1

        stats["chunks"] += ticker_chunks
        stats["tickers"] += 1
        log.info("rag_seeded", ticker=ticker, documents=len(docs), chunks=ticker_chunks)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed ChromaDB with SEC filings and news")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker symbols to seed (default: top 15)",
    )
    parser.add_argument(
        "--max-filings",
        type=int,
        default=3,
        help="Max SEC filings per ticker (default: 3)",
    )
    args = parser.parse_args()

    log.info("starting_rag_seed", tickers=len(args.tickers), max_filings=args.max_filings)
    stats = seed(args.tickers, args.max_filings)

    log.info(
        "rag_seed_complete",
        tickers=stats["tickers"],
        documents=stats["documents"],
        chunks=stats["chunks"],
        total_in_collection=get_rag_pipeline_count(),
    )


def get_rag_pipeline_count() -> int:
    """Get total chunk count from the RAG pipeline."""
    try:
        from app.rag.pipeline import get_rag_pipeline
        return get_rag_pipeline().count()
    except Exception:
        return -1


if __name__ == "__main__":
    main()
