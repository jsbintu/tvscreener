"""
Bubby Vision — Morning Briefing Celery Task

Runs at 8:00 AM EST via Celery Beat. Scans watchlist tickers,
computes TA + breakout analysis, and generates an AI-narrated morning briefing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_morning_briefing(self):
    """Generate the daily morning briefing for the trader's watchlist.

    Steps:
    1. Fetch watchlist tickers from Redis
    2. Run TA + breakout + pattern scan on each ticker
    3. Build data bundle
    4. Generate AI narrative via Gemini 3 Flash
    5. Store in Redis for API retrieval + broadcast via WebSocket
    """
    try:
        import redis
        from app.config import get_settings
        from app.engines.ta_engine import TAEngine
        from app.engines.pattern_engine import PatternEngine
        from app.engines.breakout_engine import BreakoutEngine
        from app.services.data_engine import DataEngine

        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        _ta = TAEngine()
        _pat = PatternEngine()
        _bo = BreakoutEngine()
        _data = DataEngine()

        # 1. Get watchlist from Redis
        watchlist_keys = r.keys("bubby:watchlist:*")
        tickers = set()
        for key in watchlist_keys:
            items = r.smembers(key) if r.type(key) == "set" else r.lrange(key, 0, -1)
            for item in items:
                tickers.add(item.upper())

        # Fallback: default tickers if watchlist empty
        if not tickers:
            tickers = {"SPY", "QQQ", "AAPL", "NVDA", "TSLA"}

        logger.info(f"Morning briefing: scanning {len(tickers)} tickers")

        # 2. Scan each ticker
        watchlist_data = []
        for ticker in sorted(tickers)[:15]:  # Cap at 15 tickers
            try:
                data = _data.get_stock(ticker, period="3mo", interval="1d")
                bars = data.history
                if len(bars) < 20:
                    continue

                indicators = _ta.compute_indicators(bars, timeframe="1d", ticker=ticker)
                ind = indicators.model_dump(mode="json")
                precursors = _bo.scan_precursors(bars, indicators)
                structure = _pat.detect_market_structure(bars)
                patterns = _pat.scan_all_patterns(bars)

                ticker_summary = {
                    "ticker": ticker,
                    "price": round(float(bars[-1].close), 2),
                    "change_pct": round(((bars[-1].close - bars[-2].close) / bars[-2].close) * 100, 2) if len(bars) >= 2 else 0,
                    "rsi": ind.get("rsi"),
                    "overall_signal": ind.get("overall_signal"),
                    "structure": structure.get("structure", "unknown") if isinstance(structure, dict) else "unknown",
                    "precursor_count": len(precursors),
                    "pattern_count": patterns.pattern_count if hasattr(patterns, "pattern_count") else 0,
                    "pattern_bias": patterns.overall_bias if hasattr(patterns, "overall_bias") else "neutral",
                }
                watchlist_data.append(ticker_summary)
            except Exception as e:
                logger.warning(f"Morning briefing: {ticker} failed: {e}")
                continue

        # 3. Get market context
        fear_greed = {"value": 50, "label": "Neutral"}
        try:
            fg = _data.get_fear_greed()
            if fg:
                fear_greed = fg
        except Exception:
            pass

        spy_change = 0.0
        vix = 20.0
        treasury_10y = 4.0
        try:
            spy_data = _data.get_stock("SPY", period="5d", interval="1d")
            if spy_data.history and len(spy_data.history) >= 2:
                spy_change = round(
                    ((spy_data.history[-1].close - spy_data.history[-2].close) / spy_data.history[-2].close) * 100, 2
                )
        except Exception:
            pass

        # 4. Generate AI narrative
        briefing_text = _generate_briefing_narrative(
            watchlist_data=watchlist_data,
            fear_greed=fear_greed,
            spy_change=spy_change,
            vix=vix,
            treasury_10y=treasury_10y,
        )

        # 5. Store in Redis
        briefing_payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "market_context": {
                "fear_greed": fear_greed,
                "spy_change": spy_change,
                "vix": vix,
                "treasury_10y": treasury_10y,
            },
            "watchlist_scans": watchlist_data,
            "narrative": briefing_text,
            "tickers_scanned": len(watchlist_data),
        }

        r.set("bubby:briefing:latest", json.dumps(briefing_payload, default=str))
        r.expire("bubby:briefing:latest", 86400)  # 24h TTL

        # Also store by date
        date_key = f"bubby:briefing:{datetime.utcnow().strftime('%Y-%m-%d')}"
        r.set(date_key, json.dumps(briefing_payload, default=str))
        r.expire(date_key, 86400 * 7)  # 7-day TTL

        logger.info(f"Morning briefing generated: {len(watchlist_data)} tickers scanned")
        return {"status": "success", "tickers": len(watchlist_data)}

    except Exception as exc:
        logger.error(f"Morning briefing failed: {exc}")
        raise self.retry(exc=exc)


def _generate_briefing_narrative(
    watchlist_data: list[dict],
    fear_greed: dict,
    spy_change: float,
    vix: float,
    treasury_10y: float,
) -> str:
    """Generate briefing narrative via Gemini 3 Flash, with fallback."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.config import get_settings
        from app.agents.prompts import MORNING_BRIEFING_PROMPT

        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.4,
            max_output_tokens=2048,
        )

        # Format watchlist data for prompt
        watchlist_text = json.dumps(watchlist_data, indent=2, default=str)
        prompt = MORNING_BRIEFING_PROMPT.format(
            fear_greed=json.dumps(fear_greed, default=str),
            spy_change=spy_change,
            vix=vix,
            treasury_10y=treasury_10y,
            watchlist_data=watchlist_text,
        )

        response = llm.invoke([
            SystemMessage(content="You are a professional day trading assistant generating a morning briefing."),
            HumanMessage(content=prompt),
        ])
        return response.content

    except Exception as e:
        # Fallback: structured text without LLM
        lines = [f"📊 Morning Briefing — {datetime.utcnow().strftime('%Y-%m-%d')}", ""]
        lines.append(f"**Fear & Greed**: {fear_greed.get('value', 50)} ({fear_greed.get('label', 'Neutral')})")
        lines.append(f"**SPY**: {spy_change:+.2f}%")
        lines.append("")

        for scan in sorted(watchlist_data, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)[:5]:
            signal_emoji = "🟢" if scan.get("overall_signal", "").upper() in ("BUY", "BULLISH") else "🔴" if scan.get("overall_signal", "").upper() in ("SELL", "BEARISH") else "⚪"
            lines.append(
                f"{signal_emoji} **{scan['ticker']}** ${scan['price']} ({scan.get('change_pct', 0):+.1f}%) "
                f"— RSI {scan.get('rsi', '?')}, {scan.get('structure', '?')}, "
                f"{scan.get('precursor_count', 0)} precursors"
            )

        return "\n".join(lines)
