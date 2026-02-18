"""
Bubby Vision — OptionStrats Scraper

Playwright-based headless browser scraper for OptionStrats.com.
Extracts options flow data, IV surface, congressional flow, and insider flow.
Also provides deep-link URLs for all OptionStrats pages (Strategy Builder,
Optimizer, Flow tabs) to be embedded via iframe in the frontend.

Always active — scrapes on every Celery beat cycle.
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import get_settings

_log = structlog.get_logger(__name__)

_BASE_URL = "https://optionstrat.com"

# Realistic user agents for anti-detection
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Randomized viewport dimensions for fingerprint diversity
_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1680, "height": 1050},
]

# ── Strategy Catalog (static reference data) ──
# Complete taxonomy of options strategies supported by OptionStrats.
# Organized by skill level → category → list of strategy names.
# Maps directly to the Build menu on the site.

STRATEGY_CATALOG = {
    "novice": {
        "basic": ["Long Call", "Long Put"],
        "income": ["Covered Call", "Cash-Secured Put"],
        "other": ["Protective Put"],
    },
    "intermediate": {
        "credit_spreads": ["Bull Put Spread", "Bear Call Spread"],
        "debit_spreads": ["Bull Call Spread", "Bear Put Spread"],
        "neutral": [
            "Iron Butterfly", "Iron Condor",
            "Long Put Butterfly", "Long Call Butterfly",
        ],
        "directional": [
            "Inverse Iron Butterfly", "Inverse Iron Condor",
            "Short Put Butterfly", "Short Call Butterfly",
            "Straddle", "Strangle",
        ],
        "calendar_spreads": [
            "Calendar Call Spread", "Calendar Put Spread",
            "Diagonal Call Spread", "Diagonal Put Spread",
        ],
        "other": ["Collar"],
    },
    "advanced": {
        "naked": ["Short Put", "Short Call"],
        "neutral": [
            "Short Straddle", "Short Strangle",
            "Long Call Condor", "Long Put Condor",
        ],
        "income": ["Covered Short Straddle", "Covered Short Strangle"],
        "directional": ["Short Call Condor", "Short Put Condor"],
        "ratio_spreads": [
            "Call Ratio Backspread", "Put Broken Wing",
            "Inverse Call Broken Wing", "Put Ratio Backspread",
            "Call Broken Wing", "Inverse Put Broken Wing",
        ],
        "ladders": [
            "Bull Call Ladder", "Bear Call Ladder",
            "Bull Put Ladder", "Bear Put Ladder",
        ],
        "other": ["Jade Lizard", "Reverse Jade Lizard"],
    },
    "expert": {
        "ratio_spreads": ["Call Ratio Spread", "Put Ratio Spread"],
        "synthetic": [
            "Long Synthetic Future", "Short Synthetic Future",
            "Synthetic Put",
        ],
        "arbitrage": ["Long Combo", "Short Combo"],
        "other": ["Strip", "Strap", "Guts", "Short Guts", "Double Diagonal"],
    },
}

# Flat list of all strategy slugs for URL generation
_STRATEGY_SLUGS = {
    "Long Call": "long-call",
    "Long Put": "long-put",
    "Covered Call": "covered-call",
    "Cash-Secured Put": "cash-secured-put",
    "Protective Put": "protective-put",
    "Bull Put Spread": "bull-put-spread",
    "Bear Call Spread": "bear-call-spread",
    "Bull Call Spread": "bull-call-spread",
    "Bear Put Spread": "bear-put-spread",
    "Iron Butterfly": "iron-butterfly",
    "Iron Condor": "iron-condor",
    "Long Put Butterfly": "long-put-butterfly",
    "Long Call Butterfly": "long-call-butterfly",
    "Inverse Iron Butterfly": "inverse-iron-butterfly",
    "Inverse Iron Condor": "inverse-iron-condor",
    "Short Put Butterfly": "short-put-butterfly",
    "Short Call Butterfly": "short-call-butterfly",
    "Straddle": "straddle",
    "Strangle": "strangle",
    "Calendar Call Spread": "calendar-call-spread",
    "Calendar Put Spread": "calendar-put-spread",
    "Diagonal Call Spread": "diagonal-call-spread",
    "Diagonal Put Spread": "diagonal-put-spread",
    "Collar": "collar",
    "Short Put": "short-put",
    "Short Call": "short-call",
    "Short Straddle": "short-straddle",
    "Short Strangle": "short-strangle",
    "Long Call Condor": "long-call-condor",
    "Long Put Condor": "long-put-condor",
    "Covered Short Straddle": "covered-short-straddle",
    "Covered Short Strangle": "covered-short-strangle",
    "Short Call Condor": "short-call-condor",
    "Short Put Condor": "short-put-condor",
    "Call Ratio Backspread": "call-ratio-backspread",
    "Put Broken Wing": "put-broken-wing",
    "Inverse Call Broken Wing": "inverse-call-broken-wing",
    "Put Ratio Backspread": "put-ratio-backspread",
    "Call Broken Wing": "call-broken-wing",
    "Inverse Put Broken Wing": "inverse-put-broken-wing",
    "Bull Call Ladder": "bull-call-ladder",
    "Bear Call Ladder": "bear-call-ladder",
    "Bull Put Ladder": "bull-put-ladder",
    "Bear Put Ladder": "bear-put-ladder",
    "Jade Lizard": "jade-lizard",
    "Reverse Jade Lizard": "reverse-jade-lizard",
    "Call Ratio Spread": "call-ratio-spread",
    "Put Ratio Spread": "put-ratio-spread",
    "Long Synthetic Future": "long-synthetic-future",
    "Short Synthetic Future": "short-synthetic-future",
    "Synthetic Put": "synthetic-put",
    "Long Combo": "long-combo",
    "Short Combo": "short-combo",
    "Strip": "strip",
    "Strap": "strap",
    "Guts": "guts",
    "Short Guts": "short-guts",
    "Double Diagonal": "double-diagonal",
}


class OptionStratsScraper:
    """Playwright-based scraper for OptionStrats.com.

    Data extraction targets:
    - Options flow feed (large/unusual trades with strategy classification)
    - IV surface data per ticker
    - Congressional and insider flow summaries

    Anti-detection measures:
    - Randomized delays between actions (1-3s)
    - Realistic user-agent rotation
    - Viewport randomization
    - Headless mode configurable for debugging

    Caching:
    - All scraped data is cached in Redis
    - Flow data: 5-minute TTL (default)
    - IV surface: 30-minute TTL (default)
    - Congressional flow: 1-hour TTL
    """

    def __init__(self):
        settings = get_settings()
        self._headless = settings.playwright_headless
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        """Launch browser if not already running."""
        if self._browser and self._browser.is_connected():
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            _log.error(
                "optionstrats.playwright_missing",
                msg="playwright not installed — run: pip install playwright && playwright install chromium",
            )
            raise RuntimeError("Playwright not installed")

        self._playwright = await async_playwright().start()
        viewport = random.choice(_VIEWPORTS)
        user_agent = random.choice(_USER_AGENTS)

        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
        )
        self._context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
        )

        _log.info(
            "optionstrats.browser_launched",
            headless=self._headless,
            viewport=f"{viewport['width']}x{viewport['height']}",
        )

    async def _random_delay(self, min_s: float = 1.0, max_s: float = 3.0):
        """Human-like random delay between actions."""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def close(self):
        """Clean up browser resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ── Flow Data Extraction ──

    async def get_flow(
        self,
        ticker: Optional[str] = None,
        min_premium: int = 50_000,
        limit: int = 50,
    ) -> list[dict]:
        """Scrape options flow data from OptionStrats.

        Returns list of flow entries with:
        - contract_symbol, ticker, strategy_type (single_leg, spread, condor, etc.)
        - sentiment (bullish/bearish/neutral)
        - premium, volume, open_interest
        - strike, expiration, option_type
        - timestamp

        Args:
            ticker: Filter by ticker (optional).
            min_premium: Minimum premium filter.
            limit: Max entries to return.
        """

        try:
            await self._ensure_browser()
            page = await self._context.new_page()

            url = f"{_BASE_URL}/flow"
            if ticker:
                url += f"?symbol={ticker.upper()}"

            _log.info("optionstrats.scraping_flow", url=url)
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await self._random_delay(2.0, 4.0)

            # Wait for the flow table to render
            try:
                await page.wait_for_selector(
                    "[class*='flow'], [class*='table'], [data-testid*='flow'], table",
                    timeout=15000,
                )
            except Exception:
                _log.warning("optionstrats.flow_table_not_found", url=url)
                await page.close()
                return []

            await self._random_delay(1.0, 2.0)

            # Extract flow data from the rendered page
            flow_data = await page.evaluate("""() => {
                const rows = [];

                // Try finding table rows — OptionStrats uses a custom table
                const tableRows = document.querySelectorAll(
                    'tr, [class*="row"], [class*="trade"], [class*="flow-item"]'
                );

                for (const row of tableRows) {
                    const cells = row.querySelectorAll('td, [class*="cell"], [class*="col"]');
                    if (cells.length < 4) continue;  // Skip header or invalid rows

                    const cellTexts = Array.from(cells).map(c => c.textContent?.trim() || '');

                    // Try to extract structured data
                    const rowData = {
                        raw_cells: cellTexts,
                        sentiment_classes: row.className || '',
                        inner_html: row.innerHTML.substring(0, 500),
                    };

                    // Check for sentiment indicators (color classes, icons)
                    const greenEls = row.querySelectorAll('[class*="green"], [class*="bull"], [class*="positive"]');
                    const redEls = row.querySelectorAll('[class*="red"], [class*="bear"], [class*="negative"]');
                    if (greenEls.length > 0) rowData['detected_sentiment'] = 'bullish';
                    else if (redEls.length > 0) rowData['detected_sentiment'] = 'bearish';
                    else rowData['detected_sentiment'] = 'neutral';

                    rows.push(rowData);
                }

                return rows.slice(0, """ + str(limit) + """);
            }""")

            await page.close()

            # Normalize raw scraped data into our schema
            entries = []
            for raw in flow_data:
                entry = self._parse_flow_row(raw, ticker)
                if entry and (entry.get("premium", 0) >= min_premium or min_premium == 0):
                    entries.append(entry)

            _log.info(
                "optionstrats.flow_scraped",
                count=len(entries),
                ticker=ticker,
            )
            return entries[:limit]

        except Exception as exc:
            _log.error("optionstrats.flow_error", error=str(exc), ticker=ticker)
            return []

    def _parse_flow_row(self, raw: dict, default_ticker: Optional[str] = None) -> Optional[dict]:
        """Parse a raw scraped flow row into a normalized dict."""
        cells = raw.get("raw_cells", [])
        if len(cells) < 4:
            return None

        # Best-effort field extraction — layout may vary
        # Common OptionStrats flow columns: Time, Ticker, Exp, Strike, C/P, Spot, Type, Premium, Vol/OI
        entry = {
            "source": "optionstrats",
            "ticker": default_ticker or "",
            "sentiment": raw.get("detected_sentiment", "neutral"),
            "strategy_type": "single_leg",  # Default, refined below
            "premium": 0,
            "volume": 0,
            "open_interest": 0,
            "strike": 0.0,
            "expiration": "",
            "option_type": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Try to extract ticker from cells
        for cell in cells:
            # Ticker detection (1-5 uppercase letters)
            if len(cell) <= 5 and cell.isalpha() and cell.isupper():
                entry["ticker"] = cell
                break

        # Try to extract numeric fields
        for cell in cells:
            cleaned = cell.replace(",", "").replace("$", "").replace("K", "000").replace("M", "000000")
            try:
                val = float(cleaned)
                if val > 10000 and entry["premium"] == 0:
                    entry["premium"] = val
                elif 0 < val < 1000 and entry["strike"] == 0.0:
                    entry["strike"] = val
            except (ValueError, TypeError):
                pass

        # Detect option type
        for cell in cells:
            cell_lower = cell.lower()
            if "call" in cell_lower or cell == "C":
                entry["option_type"] = "call"
            elif "put" in cell_lower or cell == "P":
                entry["option_type"] = "put"

        # Detect strategy type from class names or text
        html = raw.get("inner_html", "").lower()
        if "spread" in html:
            entry["strategy_type"] = "spread"
        elif "condor" in html or "iron" in html:
            entry["strategy_type"] = "iron_condor"
        elif "butterfly" in html:
            entry["strategy_type"] = "butterfly"
        elif "straddle" in html:
            entry["strategy_type"] = "straddle"
        elif "strangle" in html:
            entry["strategy_type"] = "strangle"

        return entry

    # ── IV Surface Data ──

    async def get_iv_surface(self, ticker: str) -> dict:
        """Scrape IV surface data for a ticker.

        Returns:
            Dict with iv_current, iv_history (list of date->iv points),
            iv_percentile, and per-expiration IV adjustments.
        """

        try:
            await self._ensure_browser()
            page = await self._context.new_page()

            url = f"{_BASE_URL}/optimize/{ticker.upper()}"
            _log.info("optionstrats.scraping_iv", url=url, ticker=ticker)

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await self._random_delay(2.0, 4.0)

            # Extract IV data from the page
            iv_data = await page.evaluate("""() => {
                const result = {
                    iv_current: null,
                    iv_elements: [],
                    expiration_ivs: [],
                };

                // Look for IV display elements
                const ivEls = document.querySelectorAll(
                    '[class*="iv"], [class*="volatility"], [class*="vol"]'
                );

                for (const el of ivEls) {
                    const text = el.textContent?.trim() || '';
                    if (text.includes('%')) {
                        result.iv_elements.push(text);
                    }
                }

                // Look for expiration-specific IV data
                const expEls = document.querySelectorAll(
                    '[class*="expiration"], [class*="exp-row"]'
                );

                for (const el of expEls) {
                    const text = el.textContent?.trim() || '';
                    const ivMatch = text.match(/(\\d+\\.?\\d*)%/);
                    const dateMatch = text.match(/(\\d{1,2}\\/\\d{1,2}|\\w{3}\\s+\\d{1,2})/);

                    if (ivMatch) {
                        result.expiration_ivs.push({
                            expiration: dateMatch ? dateMatch[1] : 'unknown',
                            iv: parseFloat(ivMatch[1]),
                        });
                    }
                }

                return result;
            }""")

            await page.close()

            # Parse IV values from extracted elements
            iv_values = []
            for text in iv_data.get("iv_elements", []):
                try:
                    # Extract percentage value
                    import re
                    match = re.search(r"(\d+\.?\d*)%", text)
                    if match:
                        iv_values.append(float(match.group(1)))
                except (ValueError, TypeError):
                    pass

            result = {
                "ticker": ticker.upper(),
                "source": "optionstrats",
                "iv_current": iv_values[0] / 100 if iv_values else None,
                "iv_percentile": None,
                "expiration_ivs": iv_data.get("expiration_ivs", []),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            _log.info(
                "optionstrats.iv_scraped",
                ticker=ticker,
                iv_current=result["iv_current"],
                expirations=len(result["expiration_ivs"]),
            )
            return result

        except Exception as exc:
            _log.error("optionstrats.iv_error", error=str(exc), ticker=ticker)
            return {}

    # ── Congressional Flow ──

    async def get_congressional_flow(self, limit: int = 25) -> list[dict]:
        """Scrape congressional trading activity from OptionStrats.

        Returns list of entries with member name, ticker, trade type,
        amount, and filing date.
        """

        try:
            await self._ensure_browser()
            page = await self._context.new_page()

            url = f"{_BASE_URL}/flow/congress"
            _log.info("optionstrats.scraping_congress", url=url)

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await self._random_delay(2.0, 4.0)

            # Wait for congress flow table
            try:
                await page.wait_for_selector(
                    "table, [class*='table'], [class*='congress']",
                    timeout=15000,
                )
            except Exception:
                _log.warning("optionstrats.congress_table_not_found")
                await page.close()
                return []

            congress_data = await page.evaluate("""() => {
                const rows = [];
                const tableRows = document.querySelectorAll(
                    'tr, [class*="row"], [class*="congress-item"]'
                );

                for (const row of tableRows) {
                    const cells = row.querySelectorAll('td, [class*="cell"], [class*="col"]');
                    if (cells.length < 3) continue;

                    const cellTexts = Array.from(cells).map(c => c.textContent?.trim() || '');
                    rows.push({
                        raw_cells: cellTexts,
                    });
                }

                return rows.slice(0, """ + str(limit) + """);
            }""")

            await page.close()

            entries = []
            for raw in congress_data:
                cells = raw.get("raw_cells", [])
                if len(cells) < 3:
                    continue

                entry = {
                    "source": "optionstrats",
                    "member": cells[0] if len(cells) > 0 else "",
                    "ticker": "",
                    "trade_type": "",
                    "amount": "",
                    "filing_date": "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Extract ticker (uppercase 1-5 letters)
                for cell in cells:
                    if len(cell) <= 5 and cell.isalpha() and cell.isupper():
                        entry["ticker"] = cell
                        break

                # Extract trade type
                for cell in cells:
                    cell_lower = cell.lower()
                    if "purchase" in cell_lower or "buy" in cell_lower:
                        entry["trade_type"] = "purchase"
                    elif "sale" in cell_lower or "sell" in cell_lower:
                        entry["trade_type"] = "sale"

                # Extract amount range
                for cell in cells:
                    if "$" in cell:
                        entry["amount"] = cell

                entries.append(entry)

            _log.info("optionstrats.congress_scraped", count=len(entries))
            return entries[:limit]

        except Exception as exc:
            _log.error("optionstrats.congress_error", error=str(exc))
            return []

    # ── Deep-Link URL Generator (Builder / Optimizer) ──

    def get_optionstrats_urls(
        self,
        ticker: str,
        strategy: Optional[str] = None,
    ) -> dict:
        """Generate deep-link URLs for OptionStrats pages.

        Used by the frontend to embed OptionStrats via iframe or open
        in new tab. Includes:
        - optimizer: Strategy Optimizer with interactive builders below
        - builder: Strategy Builder with P&L matrix for a specific strategy
        - info: Strategy info/learn page (slug without ticker)
        - flow tabs: summary, live, historical, news, congress, insider
        - all_builders: Dict of builder URLs for all 50+ strategies
        - all_info_pages: Dict of info/learn URLs for all strategies

        Args:
            ticker: Stock symbol.
            strategy: Optional strategy name (e.g. 'Covered Call').
        """
        ticker_upper = ticker.upper()
        urls = {
            "ticker": ticker_upper,
            # ── Optimizer & Builder ──
            "optimizer": f"{_BASE_URL}/optimize?symbol={ticker_upper}",
            # ── All Flow Tabs (iframe targets) ──
            "flow_summary": f"{_BASE_URL}/flow?symbol={ticker_upper}",
            "flow_live": f"{_BASE_URL}/flow?symbol={ticker_upper}",
            "flow_historical": f"{_BASE_URL}/flow/historical?symbol={ticker_upper}",
            "flow_news": f"{_BASE_URL}/flow/news",
            "flow_congress": f"{_BASE_URL}/flow/congress",
            "flow_insider": f"{_BASE_URL}/flow/insider",
        }

        # Specific strategy builder URL (with ticker → P&L matrix)
        if strategy:
            slug = _STRATEGY_SLUGS.get(strategy)
            if slug:
                urls["builder"] = f"{_BASE_URL}/build/{slug}/{ticker_upper}"
                urls["info"] = f"{_BASE_URL}/build/{slug}"
            else:
                urls["builder"] = f"{_BASE_URL}/build?symbol={ticker_upper}"
                urls["info"] = f"{_BASE_URL}/build"
        else:
            urls["builder"] = f"{_BASE_URL}/build/covered-call/{ticker_upper}"
            urls["info"] = f"{_BASE_URL}/build/covered-call"

        # All builder URLs for this ticker (slug + ticker → P&L)
        urls["all_builders"] = {
            name: f"{_BASE_URL}/build/{slug}/{ticker_upper}"
            for name, slug in _STRATEGY_SLUGS.items()
        }

        # All info/learn page URLs (slug only → strategy description)
        urls["all_info_pages"] = {
            name: f"{_BASE_URL}/build/{slug}"
            for name, slug in _STRATEGY_SLUGS.items()
        }

        return urls

    # ── Insider Flow (background task for LLM context) ──

    async def get_insider_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Scrape insider trading flow from OptionStrats.

        SEC insider buying/selling data — unique to OptionStrats,
        not available from Alpaca, QuantData, or TradingView.
        Runs as a background Celery task every 15 min, cached in Redis.
        The LLM reads from cache for near-zero latency.

        Args:
            ticker: Filter by ticker (optional).
            limit: Max entries.
        """
        try:
            await self._ensure_browser()
            page = await self._context.new_page()

            url = f"{_BASE_URL}/flow/insider"
            if ticker:
                url += f"?symbol={ticker.upper()}"

            _log.info("optionstrats.scraping_insider_flow", url=url)
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await self._random_delay(2.0, 4.0)

            # Extract insider trade rows
            raw_rows = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr, [class*="insider"] [class*="row"]');
                    return Array.from(rows).map(row => {
                        const cells = Array.from(row.querySelectorAll('td, [class*="cell"]'));
                        return cells.map(c => c.textContent?.trim() || '');
                    });
                }
            """)

            entries = []
            for cells in raw_rows[:limit]:
                if len(cells) < 3:
                    continue

                entry = {
                    "source": "optionstrats",
                    "flow_type": "insider",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }

                # Parse cells — typical insider flow columns:
                # Ticker, Insider Name, Title, Trade Type, Shares, Price, Value, Date
                for i, cell in enumerate(cells):
                    cell_stripped = cell.strip()
                    if not cell_stripped:
                        continue

                    # Detect ticker (short uppercase, usually first)
                    if i == 0 and cell_stripped.isupper() and len(cell_stripped) <= 5:
                        entry["ticker"] = cell_stripped
                    # Detect trade type
                    elif cell_stripped.lower() in ("purchase", "buy", "sale", "sell", "exercise"):
                        entry["trade_type"] = cell_stripped.lower()
                    # Detect dollar amounts
                    elif "$" in cell_stripped:
                        if "value" not in entry:
                            entry["value"] = cell_stripped
                        else:
                            entry["price"] = cell_stripped
                    # Detect dates
                    elif "/" in cell_stripped or "-" in cell_stripped:
                        entry["filing_date"] = cell_stripped
                    # Names usually contain spaces
                    elif " " in cell_stripped and "name" not in entry:
                        entry["insider_name"] = cell_stripped
                    # Remaining might be title or shares
                    elif cell_stripped.replace(",", "").isdigit():
                        entry["shares"] = cell_stripped

                # Only include if we got meaningful data
                if entry.get("ticker") or entry.get("insider_name"):
                    entries.append(entry)

            await page.close()
            _log.info("optionstrats.insider_flow_scraped", count=len(entries))
            return entries

        except Exception as exc:
            _log.error("optionstrats.insider_flow_error", error=str(exc))
            return []
