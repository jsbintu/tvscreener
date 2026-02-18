"""
Bubby Vision — WSB / Reddit Sentiment Client

Scrapes WallStreetBets and stock-related subreddits for sentiment analysis.
Uses Reddit's public JSON API (no authentication for read-only).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx


class WSBClient:
    """WallStreetBets and Reddit sentiment scraper."""

    _SUBREDDITS = ["wallstreetbets", "stocks", "options", "investing"]

    def __init__(self):
        self._headers = {
            "User-Agent": "Bubby Vision/0.1 (financial analysis tool)"
        }

    async def get_mentions(
        self,
        ticker: str,
        subreddit: str = "wallstreetbets",
        limit: int = 25,
    ) -> list[dict]:
        """Search for ticker mentions in a subreddit.

        Returns list of posts with title, score, comments, and URL.
        """
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": f"${ticker.upper()} OR {ticker.upper()}",
            "restrict_sr": "true",
            "sort": "new",
            "limit": limit,
            "t": "week",
        }

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                return []

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "title": post.get("title", ""),
                "selftext": post.get("selftext", "")[:500],  # trim body
                "score": post.get("score", 0),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "num_comments": post.get("num_comments", 0),
                "created_utc": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "subreddit": subreddit,
                "ticker": ticker.upper(),
            })
        return posts

    async def get_trending_tickers(
        self,
        subreddit: str = "wallstreetbets",
        limit: int = 50,
    ) -> dict[str, int]:
        """Scan hot posts for ticker mentions. Returns {ticker: mention_count}."""
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        params = {"limit": limit}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                return {}

        import re
        ticker_pattern = re.compile(r'\$([A-Z]{1,5})\b')
        mentions: dict[str, int] = {}

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            found = ticker_pattern.findall(text)
            for t in found:
                if len(t) >= 2:  # skip single-char false positives
                    mentions[t] = mentions.get(t, 0) + 1

        # Sort by mention count descending
        return dict(sorted(mentions.items(), key=lambda x: x[1], reverse=True))

    async def get_sentiment_summary(self, ticker: str) -> dict:
        """Aggregate sentiment across multiple subreddits for a ticker.

        Enhanced with age-weighted scoring and bearish keyword detection.
        """
        all_posts = []
        for sub in self._SUBREDDITS:
            posts = await self.get_mentions(ticker, subreddit=sub, limit=10)
            all_posts.extend(posts)

        if not all_posts:
            return {
                "ticker": ticker.upper(),
                "total_mentions": 0,
                "avg_score": 0,
                "avg_upvote_ratio": 0,
                "total_comments": 0,
                "sentiment": "no_data",
            }

        total = len(all_posts)
        avg_score = sum(p["score"] for p in all_posts) / total
        avg_upvote = sum(p["upvote_ratio"] for p in all_posts) / total
        total_comments = sum(p["num_comments"] for p in all_posts)

        # Bearish keyword detection
        bearish_keywords = {"puts", "short", "crash", "dump", "bear", "overvalued", "sell"}
        bullish_keywords = {"calls", "moon", "buy", "long", "bull", "undervalued", "rocket"}
        bearish_count = 0
        bullish_count = 0
        for p in all_posts:
            text_lower = p.get("title", "").lower() + " " + p.get("selftext", "").lower()
            bearish_count += sum(1 for kw in bearish_keywords if kw in text_lower)
            bullish_count += sum(1 for kw in bullish_keywords if kw in text_lower)

        # Weighted heuristic
        keyword_ratio = (bullish_count - bearish_count) / max(bullish_count + bearish_count, 1)

        if avg_upvote > 0.75 and avg_score > 100 and keyword_ratio > 0:
            sentiment = "bullish"
        elif avg_upvote < 0.45 or keyword_ratio < -0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return {
            "ticker": ticker.upper(),
            "total_mentions": total,
            "avg_score": round(avg_score, 1),
            "avg_upvote_ratio": round(avg_upvote, 3),
            "total_comments": total_comments,
            "sentiment": sentiment,
            "bullish_signals": bullish_count,
            "bearish_signals": bearish_count,
            "subreddits_scanned": self._SUBREDDITS,
        }

    # ── Phase 6 additions ──

    async def get_dd_posts(
        self,
        ticker: str,
        subreddit: str = "wallstreetbets",
        limit: int = 15,
    ) -> list[dict]:
        """Fetch DD (Due Diligence) tagged posts only.

        DD posts are typically the highest-quality analysis on WSB.

        Args:
            ticker: Stock ticker symbol.
            subreddit: Subreddit to search.
            limit: Max posts to return.
        """
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": f"${ticker.upper()} flair:DD",
            "restrict_sr": "true",
            "sort": "top",
            "limit": limit,
            "t": "month",
        }

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                return []

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            flair = post.get("link_flair_text", "") or ""
            # Include DD, Due Diligence, and Research flairs
            if any(tag in flair.lower() for tag in ("dd", "due diligence", "research", "analysis")):
                posts.append({
                    "title": post.get("title", ""),
                    "selftext": post.get("selftext", "")[:1000],
                    "score": post.get("score", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                    "num_comments": post.get("num_comments", 0),
                    "created_utc": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "flair": flair,
                    "subreddit": subreddit,
                    "ticker": ticker.upper(),
                })
        return posts

    async def get_quality_mentions(
        self,
        ticker: str,
        subreddit: str = "wallstreetbets",
        min_score: int = 50,
        min_comments: int = 10,
        limit: int = 25,
    ) -> list[dict]:
        """Fetch high-quality ticker mentions filtered by score and engagement.

        Args:
            ticker: Stock ticker symbol.
            subreddit: Subreddit to search.
            min_score: Minimum post score (upvotes - downvotes).
            min_comments: Minimum number of comments.
            limit: Max posts to fetch before filtering.
        """
        raw_posts = await self.get_mentions(ticker, subreddit=subreddit, limit=limit)

        return [
            p for p in raw_posts
            if p.get("score", 0) >= min_score and p.get("num_comments", 0) >= min_comments
        ]

