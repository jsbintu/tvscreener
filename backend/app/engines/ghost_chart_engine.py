"""
Bubby Vision — Ghost Chart Engine

Uses ChromaDB similarity search to find historical patterns that match
current chart setups, enabling overlay of past price trajectories
("ghost paths") for predictive visualization.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)


class GhostChartEngine:
    """Find and overlay historical pattern matches using vector similarity."""

    def __init__(self, chroma_collection_name: str = "pattern_ghosts"):
        self._collection = None
        self._collection_name = chroma_collection_name

    def _get_collection(self):
        """Lazy-init ChromaDB collection."""
        if self._collection is None:
            try:
                import chromadb
                client = chromadb.Client()
                self._collection = client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except ImportError:
                log.warning("chromadb_not_available")
                raise RuntimeError("chromadb is required for ghost charts")
        return self._collection

    # ── Core Methods ──────────────────────────────────

    def store_pattern(
        self,
        ticker: str,
        pattern_name: str,
        bars: list[dict],
        outcome: str = "unknown",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store a detected pattern in ChromaDB for future similarity search.

        Normalizes the price series to a 0-1 range and stores as embedding
        alongside pattern metadata for retrieval.

        Args:
            ticker: Ticker symbol.
            pattern_name: Name of the pattern (e.g., 'bull_flag').
            bars: OHLCV bars covering the pattern and aftermath.
            outcome: Pattern outcome ('success', 'failed', 'unknown').
            metadata: Additional context.

        Returns:
            Dict with storage confirmation.
        """
        if len(bars) < 10:
            return {"error": "Need at least 10 bars to store a pattern."}

        # Extract close prices and normalize to 0-1
        closes = [b.get("close", 0) for b in bars]
        embedding = self._normalize_series(closes)

        # Create unique ID
        pattern_id = hashlib.md5(
            f"{ticker}:{pattern_name}:{bars[0].get('timestamp', '')}".encode()
        ).hexdigest()

        # Store in ChromaDB
        collection = self._get_collection()
        collection.upsert(
            ids=[pattern_id],
            embeddings=[embedding],
            metadatas=[{
                "ticker": ticker.upper(),
                "pattern_name": pattern_name,
                "outcome": outcome,
                "bar_count": len(bars),
                "start_date": str(bars[0].get("timestamp", "")),
                "end_date": str(bars[-1].get("timestamp", "")),
                "start_price": closes[0],
                "end_price": closes[-1],
                "price_change_pct": round((closes[-1] - closes[0]) / max(closes[0], 0.01) * 100, 2),
                **(metadata or {}),
            }],
            documents=[json.dumps({
                "closes": [round(c, 4) for c in closes],
                "volumes": [b.get("volume", 0) for b in bars],
            })],
        )

        log.info("ghost_pattern_stored", ticker=ticker, pattern=pattern_name, bars=len(bars))
        return {
            "id": pattern_id,
            "stored": True,
            "ticker": ticker.upper(),
            "pattern": pattern_name,
            "bar_count": len(bars),
        }

    def find_similar_patterns(
        self,
        bars: list[dict],
        top_k: int = 5,
        pattern_filter: Optional[str] = None,
    ) -> dict:
        """Find historical patterns similar to the current price action.

        Normalizes current bars and searches ChromaDB for cosine-similar
        historical patterns.

        Args:
            bars: Current OHLCV bars to match against.
            top_k: Number of matches to return.
            pattern_filter: Optional filter by pattern name.

        Returns:
            Dict with matched patterns, similarity scores, and overlay data.
        """
        if len(bars) < 10:
            return {"error": "Need at least 10 bars for similarity search."}

        closes = [b.get("close", 0) for b in bars]
        query_embedding = self._normalize_series(closes)

        collection = self._get_collection()

        where_filter = {"pattern_name": pattern_filter} if pattern_filter else None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["metadatas", "documents", "distances"],
        )

        matches = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            doc = json.loads(results["documents"][0][i]) if results["documents"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0

            # Convert distance to similarity (cosine distance → similarity)
            similarity = round(1 - distance, 4)

            matches.append({
                "id": results["ids"][0][i],
                "similarity": similarity,
                "ticker": meta.get("ticker"),
                "pattern": meta.get("pattern_name"),
                "outcome": meta.get("outcome"),
                "bar_count": meta.get("bar_count"),
                "price_change_pct": meta.get("price_change_pct"),
                "start_date": meta.get("start_date"),
                "end_date": meta.get("end_date"),
                "ghost_closes": doc.get("closes", []),
            })

        # Aggregate outcome statistics from matches
        outcomes = [m["outcome"] for m in matches if m["outcome"] != "unknown"]
        success_rate = (
            round(sum(1 for o in outcomes if o == "success") / max(len(outcomes), 1) * 100, 1)
            if outcomes else None
        )

        return {
            "query_bars": len(bars),
            "matches_found": len(matches),
            "matches": matches,
            "outcome_summary": {
                "success_count": sum(1 for o in outcomes if o == "success"),
                "failed_count": sum(1 for o in outcomes if o == "failed"),
                "success_rate": success_rate,
            } if outcomes else None,
            "avg_similarity": round(
                sum(m["similarity"] for m in matches) / max(len(matches), 1), 4
            ),
        }

    def get_ghost_overlay(
        self,
        pattern_id: str,
        current_price: float,
    ) -> dict:
        """Get historical price path scaled to current price for chart overlay.

        Retrieves the stored pattern and scales its price trajectory
        to start from the current price, creating a "ghost" path.

        Args:
            pattern_id: ID of the stored pattern.
            current_price: Current price to anchor the ghost path.

        Returns:
            Dict with scaled ghost path coordinates for charting.
        """
        collection = self._get_collection()

        results = collection.get(
            ids=[pattern_id],
            include=["metadatas", "documents"],
        )

        if not results["ids"]:
            return {"error": f"Pattern {pattern_id} not found."}

        doc = json.loads(results["documents"][0])
        meta = results["metadatas"][0]
        historical_closes = doc.get("closes", [])

        if not historical_closes:
            return {"error": "No price data stored for this pattern."}

        # Scale historical path to start from current price
        start_price = historical_closes[0]
        scale_factor = current_price / max(start_price, 0.01)
        scaled_path = [round(c * scale_factor, 4) for c in historical_closes]

        # Calculate projected targets from the scaled path
        max_price = max(scaled_path)
        min_price = min(scaled_path)
        final_price = scaled_path[-1]

        return {
            "pattern_id": pattern_id,
            "pattern_name": meta.get("pattern_name"),
            "original_ticker": meta.get("ticker"),
            "current_price": current_price,
            "ghost_path": scaled_path,
            "bar_count": len(scaled_path),
            "projected_high": round(max_price, 4),
            "projected_low": round(min_price, 4),
            "projected_final": round(final_price, 4),
            "projected_change_pct": round(
                (final_price - current_price) / max(current_price, 0.01) * 100, 2
            ),
            "outcome": meta.get("outcome"),
        }

    def get_pattern_library_stats(self) -> dict:
        """Get statistics about stored patterns in the library.

        Returns:
            Dict with pattern counts, outcome distribution, and coverage.
        """
        collection = self._get_collection()
        total = collection.count()

        if total == 0:
            return {
                "total_patterns": 0,
                "message": "Pattern library is empty. Patterns are stored as they are detected.",
            }

        # Sample patterns to get distribution
        results = collection.get(
            limit=min(total, 1000),
            include=["metadatas"],
        )

        pattern_counts: dict[str, int] = {}
        ticker_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}

        for meta in results["metadatas"]:
            pn = meta.get("pattern_name", "unknown")
            tk = meta.get("ticker", "unknown")
            oc = meta.get("outcome", "unknown")
            pattern_counts[pn] = pattern_counts.get(pn, 0) + 1
            ticker_counts[tk] = ticker_counts.get(tk, 0) + 1
            outcome_counts[oc] = outcome_counts.get(oc, 0) + 1

        return {
            "total_patterns": total,
            "unique_pattern_types": len(pattern_counts),
            "unique_tickers": len(ticker_counts),
            "pattern_distribution": dict(sorted(pattern_counts.items(), key=lambda x: -x[1])[:15]),
            "outcome_distribution": outcome_counts,
            "top_tickers": dict(sorted(ticker_counts.items(), key=lambda x: -x[1])[:10]),
        }

    # ── Helpers ───────────────────────────────────────

    @staticmethod
    def _normalize_series(values: list[float], target_len: int = 50) -> list[float]:
        """Normalize a price series to 0-1 range and resample to fixed length.

        This ensures patterns of different durations can be compared by
        resampling to a common length and normalizing to 0-1.

        Args:
            values: Raw price values.
            target_len: Target number of points (default 50).

        Returns:
            Normalized list of floats, length = target_len.
        """
        arr = np.array(values, dtype=float)

        # Resample to target length via linear interpolation
        if len(arr) != target_len:
            x_old = np.linspace(0, 1, len(arr))
            x_new = np.linspace(0, 1, target_len)
            arr = np.interp(x_new, x_old, arr)

        # Normalize to 0-1
        mn, mx = arr.min(), arr.max()
        if mx - mn > 0:
            arr = (arr - mn) / (mx - mn)
        else:
            arr = np.zeros(target_len)

        return arr.tolist()
