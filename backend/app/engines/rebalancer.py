"""
Bubby Vision — Portfolio Rebalancer

Portfolio rebalancing engine powered by Questrade account data.
Reads current positions and balances, compares against user-defined
target allocations, and calculates the trades needed to rebalance.

Features:
  - Target allocation comparison with drift analysis
  - Buy-only rebalancing (avoids sell commissions on Questrade)
  - Sells-allowed rebalancing for full drift correction
  - Sector-level allocation analysis
  - Cash deployment optimization
  - Multi-account support
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

_log = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────


@dataclass
class TargetAllocation:
    """User-defined target allocation for a single holding."""

    ticker: str
    target_pct: float  # 0-100
    sector: str = ""


@dataclass
class CurrentHolding:
    """A current position in the portfolio."""

    ticker: str
    symbol_id: int = 0
    quantity: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    sector: str = ""
    weight_pct: float = 0.0  # Current weight in portfolio (0-100)


@dataclass
class RebalanceTrade:
    """A single trade required to rebalance the portfolio."""

    ticker: str
    action: str  # "BUY" or "SELL"
    quantity: int  # Number of shares (always positive; action determines direction)
    estimated_cost: float  # Dollar amount of the trade
    current_weight: float  # Current weight % before trade
    target_weight: float  # Target weight %
    new_weight: float  # Estimated weight % after trade
    drift: float  # Drift from target (percentage points)


@dataclass
class RebalanceResult:
    """Full result of a rebalancing analysis."""

    # Portfolio summary
    total_value: float
    cash_available: float
    num_holdings: int
    # Holdings analysis
    holdings: list[CurrentHolding]
    # Drift analysis
    max_drift: float  # Largest absolute drift from target
    avg_drift: float  # Average absolute drift
    # Proposed trades
    trades: list[RebalanceTrade]
    buy_only: bool  # Whether this was a buy-only rebal
    total_buy_amount: float
    total_sell_amount: float
    # Sector breakdown
    sector_allocation: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for JSON response."""
        return {
            "total_value": round(self.total_value, 2),
            "cash_available": round(self.cash_available, 2),
            "num_holdings": self.num_holdings,
            "holdings": [
                {
                    "ticker": h.ticker,
                    "quantity": h.quantity,
                    "current_price": round(h.current_price, 2),
                    "market_value": round(h.market_value, 2),
                    "cost_basis": round(h.cost_basis, 2),
                    "unrealized_pnl": round(h.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(h.unrealized_pnl_pct, 2),
                    "sector": h.sector,
                    "weight_pct": round(h.weight_pct, 2),
                }
                for h in self.holdings
            ],
            "max_drift": round(self.max_drift, 2),
            "avg_drift": round(self.avg_drift, 2),
            "trades": [
                {
                    "ticker": t.ticker,
                    "action": t.action,
                    "quantity": t.quantity,
                    "estimated_cost": round(t.estimated_cost, 2),
                    "current_weight": round(t.current_weight, 2),
                    "target_weight": round(t.target_weight, 2),
                    "new_weight": round(t.new_weight, 2),
                    "drift": round(t.drift, 2),
                }
                for t in self.trades
            ],
            "buy_only": self.buy_only,
            "total_buy_amount": round(self.total_buy_amount, 2),
            "total_sell_amount": round(self.total_sell_amount, 2),
            "sector_allocation": {
                k: round(v, 2) for k, v in self.sector_allocation.items()
            },
        }


# ──────────────────────────────────────────────
# Rebalancer Engine
# ──────────────────────────────────────────────


class PortfolioRebalancer:
    """Portfolio rebalancing engine using Questrade account data.

    Supports buy-only and full rebalancing modes.
    Buy-only is preferred on Questrade since ETF buys are commission-free.
    """

    def __init__(self, questrade_client=None):
        """Initialize with optional Questrade client for live data."""
        self._qt = questrade_client

    async def analyze_portfolio(
        self,
        positions: list[dict],
        balances: dict,
        target_allocations: list[TargetAllocation] | None = None,
    ) -> RebalanceResult:
        """Analyze current portfolio and compute rebalancing trades.

        Args:
            positions: List of position dicts from Questrade API.
            balances: Balance dict from Questrade API.
            target_allocations: User-defined target allocations.
                If None, returns portfolio analysis without rebal trades.

        Returns:
            RebalanceResult with holdings, drift, and proposed trades.
        """
        # Parse positions into holdings
        holdings = []
        total_market_value = 0.0

        for pos in positions:
            mv = pos.get("currentMarketValue", 0) or 0
            cost = pos.get("totalCost", 0) or 0
            qty = pos.get("openQuantity", 0) or 0
            price = pos.get("currentPrice", 0) or 0

            if qty == 0 or price == 0:
                continue

            unrealized = mv - cost
            unrealized_pct = (unrealized / cost * 100) if cost else 0

            holdings.append(
                CurrentHolding(
                    ticker=pos.get("symbol", "UNKNOWN"),
                    symbol_id=pos.get("symbolId", 0),
                    quantity=qty,
                    current_price=price,
                    market_value=mv,
                    cost_basis=cost,
                    unrealized_pnl=unrealized,
                    unrealized_pnl_pct=unrealized_pct,
                )
            )
            total_market_value += mv

        # Get cash balance
        cash = 0.0
        combined_balances = balances.get("combinedBalances", [])
        for bal in combined_balances:
            if bal.get("currency") == "USD":
                cash = bal.get("cash", 0) or 0
                break
        # Fallback to CAD if no USD
        if cash == 0 and combined_balances:
            cash = combined_balances[0].get("cash", 0) or 0

        total_value = total_market_value + cash

        # Calculate current weights
        for h in holdings:
            h.weight_pct = (h.market_value / total_value * 100) if total_value else 0

        # Sector enrichment (if Questrade client available)
        if self._qt:
            await self._enrich_sectors(holdings)

        # Sector allocation summary
        sector_allocation: dict[str, float] = {}
        for h in holdings:
            sector = h.sector or "Unknown"
            sector_allocation[sector] = sector_allocation.get(sector, 0) + h.weight_pct

        # If no target allocations, return analysis only
        if not target_allocations:
            return RebalanceResult(
                total_value=total_value,
                cash_available=cash,
                num_holdings=len(holdings),
                holdings=holdings,
                max_drift=0.0,
                avg_drift=0.0,
                trades=[],
                buy_only=True,
                total_buy_amount=0.0,
                total_sell_amount=0.0,
                sector_allocation=sector_allocation,
            )

        # Compute rebalancing trades
        return self._compute_rebalance(
            holdings=holdings,
            target_allocations=target_allocations,
            total_value=total_value,
            cash_available=cash,
            sector_allocation=sector_allocation,
        )

    def _compute_rebalance(
        self,
        holdings: list[CurrentHolding],
        target_allocations: list[TargetAllocation],
        total_value: float,
        cash_available: float,
        sector_allocation: dict[str, float],
        buy_only: bool = True,
    ) -> RebalanceResult:
        """Compute trades needed to rebalance to target allocation.

        Args:
            buy_only: If True, only generate BUY trades using available cash.
                     If False, generate both BUY and SELL trades.
        """
        # Build lookup maps
        holdings_map = {h.ticker: h for h in holdings}
        target_map = {t.ticker: t for t in target_allocations}

        trades: list[RebalanceTrade] = []
        drifts: list[float] = []

        for target in target_allocations:
            current = holdings_map.get(target.ticker)
            current_weight = current.weight_pct if current else 0.0
            target_weight = target.target_pct
            drift = current_weight - target_weight
            drifts.append(abs(drift))

            if abs(drift) < 0.5:
                # Within tolerance, skip
                continue

            current_price = current.current_price if current else 0
            if current_price <= 0:
                continue

            target_value = total_value * (target_weight / 100)
            current_value = current.market_value if current else 0
            diff_value = target_value - current_value

            if diff_value > 0:
                # Need to BUY
                shares_to_buy = int(diff_value / current_price)
                if shares_to_buy > 0:
                    cost = shares_to_buy * current_price
                    if buy_only and cost > cash_available:
                        # Cap to available cash
                        shares_to_buy = int(cash_available / current_price)
                        cost = shares_to_buy * current_price

                    if shares_to_buy > 0:
                        new_value = current_value + cost
                        new_weight = (new_value / total_value * 100) if total_value else 0

                        trades.append(
                            RebalanceTrade(
                                ticker=target.ticker,
                                action="BUY",
                                quantity=shares_to_buy,
                                estimated_cost=cost,
                                current_weight=current_weight,
                                target_weight=target_weight,
                                new_weight=new_weight,
                                drift=drift,
                            )
                        )
                        if buy_only:
                            cash_available -= cost

            elif diff_value < 0 and not buy_only:
                # Need to SELL (only in full rebal mode)
                shares_to_sell = int(abs(diff_value) / current_price)
                if shares_to_sell > 0 and current:
                    shares_to_sell = min(shares_to_sell, int(current.quantity))
                    proceeds = shares_to_sell * current_price
                    new_value = current_value - proceeds
                    new_weight = (new_value / total_value * 100) if total_value else 0

                    trades.append(
                        RebalanceTrade(
                            ticker=target.ticker,
                            action="SELL",
                            quantity=shares_to_sell,
                            estimated_cost=proceeds,
                            current_weight=current_weight,
                            target_weight=target_weight,
                            new_weight=new_weight,
                            drift=drift,
                        )
                    )

        total_buy = sum(t.estimated_cost for t in trades if t.action == "BUY")
        total_sell = sum(t.estimated_cost for t in trades if t.action == "SELL")

        max_drift = max(drifts) if drifts else 0.0
        avg_drift = sum(drifts) / len(drifts) if drifts else 0.0

        _log.info(
            "rebalancer.computed",
            holdings=len(holdings),
            targets=len(target_allocations),
            trades=len(trades),
            max_drift=round(max_drift, 2),
            buy_only=buy_only,
        )

        return RebalanceResult(
            total_value=total_value,
            cash_available=cash_available,
            num_holdings=len(holdings),
            holdings=holdings,
            max_drift=max_drift,
            avg_drift=avg_drift,
            trades=trades,
            buy_only=buy_only,
            total_buy_amount=total_buy,
            total_sell_amount=total_sell,
            sector_allocation=sector_allocation,
        )

    async def _enrich_sectors(self, holdings: list[CurrentHolding]) -> None:
        """Enrich holdings with sector info from Questrade symbol data."""
        if not self._qt:
            return

        for h in holdings:
            try:
                info = await self._qt.get_symbol_enriched(h.ticker)
                if info:
                    h.sector = info.get("industrySector", "") or info.get("industryGroup", "")
            except Exception as e:
                _log.debug(
                    "rebalancer.sector_enrichment_failed",
                    ticker=h.ticker,
                    error=str(e),
                )
