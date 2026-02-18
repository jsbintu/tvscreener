"""
Bubby Vision — External Quick Links

Pre-configured links to external tools that don't have APIs.
Served via API endpoint for frontend consumption.
"""

from __future__ import annotations


EXTERNAL_LINKS = [
    {
        "name": "QuantData Options Flow",
        "url": "https://quantdata.us/scanner",
        "description": "Live institutional options flow scanner — sweeps, blocks, unusual activity",
        "icon": "chart-bar",
        "category": "options",
    },
    {
        "name": "OptionStrat",
        "url": "https://optionstrat.com/",
        "description": "Options strategy builder — P/L visualization, multi-leg strategies",
        "icon": "calculator",
        "category": "options",
    },
    {
        "name": "TradingView Options",
        "url": "https://www.tradingview.com/options/",
        "description": "TradingView options chain and flow — uses your Ultimate plan",
        "icon": "tv",
        "category": "options",
    },
    {
        "name": "TradingView Charts",
        "url": "https://www.tradingview.com/chart/",
        "description": "Advanced charting — all indicators and drawing tools",
        "icon": "chart-line",
        "category": "charting",
    },
    {
        "name": "TradingView Screener",
        "url": "https://www.tradingview.com/screener/",
        "description": "TradingView stock screener — 3000+ fields, custom filters",
        "icon": "filter",
        "category": "screener",
    },
    {
        "name": "TradingView Heatmap",
        "url": "https://www.tradingview.com/heatmap/stock/",
        "description": "Market heatmap — S&P 500, sector performance visualization",
        "icon": "grid",
        "category": "market",
    },
]


def get_links(category: str | None = None) -> list[dict]:
    """Return external links, optionally filtered by category."""
    if category:
        return [link for link in EXTERNAL_LINKS if link["category"] == category]
    return EXTERNAL_LINKS


def get_link_for_ticker(service: str, ticker: str) -> str | None:
    """Generate a ticker-specific URL for known services.

    Args:
        service: One of 'tradingview_chart', 'tradingview_options'.
        ticker: Stock symbol.
    """
    urls = {
        "tradingview_chart": f"https://www.tradingview.com/chart/?symbol={ticker.upper()}",
        "tradingview_options": f"https://www.tradingview.com/symbols/{ticker.upper()}/options/",
        "tradingview_technicals": f"https://www.tradingview.com/symbols/{ticker.upper()}/technicals/",
        "tradingview_financials": f"https://www.tradingview.com/symbols/{ticker.upper()}/financials-overview/",
    }
    return urls.get(service)
