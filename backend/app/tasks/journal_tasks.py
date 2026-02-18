"""
Bubby Vision — Trading Journal Celery Task

Runs at 4:30 PM EST (market close) via Celery Beat.
Generates a daily trading journal entry summarizing the day's activity.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_daily_journal(self):
    """Generate end-of-day trading journal entry.

    Steps:
    1. Fetch today's watchlist performance
    2. Evaluate pattern outcomes (which patterns played out)
    3. Compute daily P&L if positions exist
    4. Generate AI narrative summary
    5. Store in Redis for API retrieval
    """
    try:
        import redis
        from app.config import get_settings
        from app.engines.ta_engine import TAEngine
        from app.engines.pattern_engine import PatternEngine
        from app.services.data_engine import DataEngine

        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        _ta = TAEngine()
        _pat = PatternEngine()
        _data = DataEngine()

        today = datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Get today's morning briefing tickers (if available)
        briefing_raw = r.get("bubby:briefing:latest")
        tickers = {"SPY", "QQQ"}
        if briefing_raw:
            briefing = json.loads(briefing_raw)
            for scan in briefing.get("watchlist_scans", []):
                tickers.add(scan.get("ticker", ""))

        # 2. End-of-day snapshot for each ticker
        eod_data = []
        for ticker in sorted(tickers)[:15]:
            if not ticker:
                continue
            try:
                data = _data.get_stock(ticker, period="5d", interval="1d")
                bars = data.history
                if len(bars) < 2:
                    continue

                today_bar = bars[-1]
                prev_bar = bars[-2]
                change_pct = round(((today_bar.close - prev_bar.close) / prev_bar.close) * 100, 2)

                # Check if any patterns from morning briefing played out
                indicators = _ta.compute_indicators(bars, timeframe="1d", ticker=ticker)
                ind = indicators.model_dump(mode="json")

                eod_data.append({
                    "ticker": ticker,
                    "open": round(float(today_bar.open), 2),
                    "close": round(float(today_bar.close), 2),
                    "high": round(float(today_bar.high), 2),
                    "low": round(float(today_bar.low), 2),
                    "change_pct": change_pct,
                    "volume": int(today_bar.volume),
                    "rsi": ind.get("rsi"),
                    "overall_signal": ind.get("overall_signal"),
                })
            except Exception as e:
                logger.warning(f"Journal: {ticker} failed: {e}")
                continue

        # 3. Check pattern outcomes from Redis log
        pattern_outcomes = []
        pattern_keys = r.keys("bubby:pattern_log:*")
        for key in pattern_keys[:10]:
            raw = r.get(key)
            if raw:
                try:
                    log_data = json.loads(raw)
                    if isinstance(log_data, list):
                        for p in log_data:
                            if isinstance(p, dict) and p.get("outcome") in ("success", "failed"):
                                pattern_outcomes.append({
                                    "ticker": p.get("ticker", ""),
                                    "pattern": p.get("name", ""),
                                    "outcome": p.get("outcome"),
                                    "pnl_pct": p.get("pnl_at_expiry_pct", 0),
                                })
                except Exception:
                    pass

        # 4. Generate AI narrative
        journal_text = _generate_journal_narrative(eod_data, pattern_outcomes)

        # 5. Store in Redis
        journal_payload = {
            "date": today,
            "generated_at": datetime.utcnow().isoformat(),
            "tickers_tracked": len(eod_data),
            "eod_snapshots": eod_data,
            "pattern_outcomes": pattern_outcomes,
            "narrative": journal_text,
            "summary_stats": {
                "winners": sum(1 for d in eod_data if d.get("change_pct", 0) > 0),
                "losers": sum(1 for d in eod_data if d.get("change_pct", 0) < 0),
                "avg_change_pct": round(
                    sum(d.get("change_pct", 0) for d in eod_data) / max(len(eod_data), 1), 2
                ),
                "pattern_wins": sum(1 for p in pattern_outcomes if p.get("outcome") == "success"),
                "pattern_losses": sum(1 for p in pattern_outcomes if p.get("outcome") == "failed"),
            },
        }

        r.set("bubby:journal:latest", json.dumps(journal_payload, default=str))
        r.expire("bubby:journal:latest", 86400 * 7)  # 7-day TTL

        date_key = f"bubby:journal:{today}"
        r.set(date_key, json.dumps(journal_payload, default=str))
        r.expire(date_key, 86400 * 30)  # 30-day TTL

        logger.info(f"Daily journal generated for {today}: {len(eod_data)} tickers")
        return {"status": "success", "date": today, "tickers": len(eod_data)}

    except Exception as exc:
        logger.error(f"Daily journal failed: {exc}")
        raise self.retry(exc=exc)


def _generate_journal_narrative(eod_data: list[dict], pattern_outcomes: list[dict]) -> str:
    """Generate journal narrative via Gemini 3 Flash, with fallback."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.config import get_settings

        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.3,
            max_output_tokens=1024,
        )

        prompt = f"""Generate a concise end-of-day trading journal entry.

## Today's Performance
{json.dumps(eod_data, indent=2, default=str)}

## Pattern Outcomes
{json.dumps(pattern_outcomes, indent=2, default=str)}

Write a 200-word journal entry summarizing:
1. Overall market tone
2. Best/worst performers from watchlist
3. Which patterns worked and which failed
4. Key lesson or observation for tomorrow
"""

        response = llm.invoke([
            SystemMessage(content="You are a professional trading journal writer. Be concise and actionable."),
            HumanMessage(content=prompt),
        ])
        return response.content

    except Exception as e:
        # Fallback: structured text
        winners = sorted([d for d in eod_data if d.get("change_pct", 0) > 0],
                        key=lambda x: x.get("change_pct", 0), reverse=True)
        losers = sorted([d for d in eod_data if d.get("change_pct", 0) < 0],
                       key=lambda x: x.get("change_pct", 0))

        lines = [f"📝 Daily Journal — {datetime.utcnow().strftime('%Y-%m-%d')}", ""]
        if winners:
            lines.append(f"**Top Winner**: {winners[0]['ticker']} +{winners[0].get('change_pct', 0):.1f}%")
        if losers:
            lines.append(f"**Top Loser**: {losers[0]['ticker']} {losers[0].get('change_pct', 0):.1f}%")

        if pattern_outcomes:
            wins = sum(1 for p in pattern_outcomes if p.get("outcome") == "success")
            total = len(pattern_outcomes)
            lines.append(f"**Patterns**: {wins}/{total} hit target")

        return "\n".join(lines)
