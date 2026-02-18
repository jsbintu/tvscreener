"""
Bubby Vision — TradingView Screener Client

Uses the tvscreener MCP server (already available in this workspace)
to screen stocks, crypto, and forex.
"""

from __future__ import annotations

from typing import Optional


class ScreenerClient:
    """Interface to the tvscreener MCP server for market screening.

    This client is designed to be called from LangGraph agents via
    tool functions that invoke the MCP server directly. The methods
    below provide structured access patterns.
    """

    @staticmethod
    def build_stock_screen_params(
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_market_cap_billions: Optional[float] = None,
        sectors: Optional[str] = None,
        sort_by: str = "market_cap",
        limit: int = 25,
    ) -> dict:
        """Build parameters for a stock screen query.

        These params are passed to the tvscreener MCP `search_stocks` tool.
        """
        params = {"sort_by": sort_by, "limit": limit}
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if min_market_cap_billions is not None:
            params["min_market_cap_billions"] = min_market_cap_billions
        if sectors:
            params["sectors"] = sectors
        return params

    @staticmethod
    def build_custom_query_params(
        fields: str,
        filters: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = False,
        limit: int = 25,
        asset_type: str = "stock",
    ) -> dict:
        """Build parameters for a custom screener query.

        These params are passed to the tvscreener MCP `custom_query` tool.
        """
        params = {
            "asset_type": asset_type,
            "fields": fields,
            "ascending": ascending,
            "limit": limit,
        }
        if filters:
            params["filters"] = filters
        if sort_by:
            params["sort_by"] = sort_by
        return params

    @staticmethod
    def build_top_movers_params(
        asset_type: str = "stock",
        direction: str = "gainers",
        limit: int = 10,
    ) -> dict:
        """Build parameters for top movers query."""
        return {
            "asset_type": asset_type,
            "direction": direction,
            "limit": limit,
        }
