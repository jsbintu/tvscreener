"""
Bubby Vision — Options P&L Calculator

Multi-leg options strategy P&L engine powered by Questrade exchange data.
Calculates payoff curves at expiration, current P&L with live Greeks,
breakevens, max profit/loss, and probability analysis.

Strategies supported:
  - Single calls/puts (long/short)
  - Verticals (bull/bear call/put spreads)
  - Iron condors, iron butterflies
  - Straddles, strangles
  - Butterflies, condors
  - Calendar spreads (requires two expirations)
  - Custom multi-leg (any combination)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import structlog

_log = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────


@dataclass
class OptionLeg:
    """A single leg of an options strategy."""

    option_type: str  # "call" or "put"
    strike: float
    premium: float  # price paid/received per share (positive = debit, negative = credit)
    quantity: int  # positive = long, negative = short
    expiration: str = ""  # YYYY-MM-DD
    # Live Greeks (optional, populated from Questrade)
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0


@dataclass
class PnLPoint:
    """A single point on the P&L curve."""

    underlying_price: float
    pnl: float  # Total P&L at this price (per contract unit)
    pnl_pct: float  # P&L as percentage of max risk


@dataclass
class PnLResult:
    """Full result of a P&L calculation."""

    strategy_name: str
    legs: list[OptionLeg]
    underlying_price: float
    # P&L curve
    pnl_curve: list[PnLPoint]
    # Key metrics
    max_profit: float
    max_loss: float
    breakevens: list[float]
    net_debit_credit: float  # positive = net debit, negative = net credit
    # Current position Greeks (aggregated)
    position_delta: float = 0.0
    position_gamma: float = 0.0
    position_theta: float = 0.0
    position_vega: float = 0.0
    # Risk/reward
    risk_reward_ratio: float = 0.0
    probability_profit: float = 0.0  # Estimated from delta (rough proxy)

    def to_dict(self) -> dict:
        """Serialize for JSON response."""
        return {
            "strategy_name": self.strategy_name,
            "underlying_price": self.underlying_price,
            "legs": [
                {
                    "option_type": leg.option_type,
                    "strike": leg.strike,
                    "premium": leg.premium,
                    "quantity": leg.quantity,
                    "expiration": leg.expiration,
                    "delta": leg.delta,
                    "gamma": leg.gamma,
                    "theta": leg.theta,
                    "vega": leg.vega,
                    "iv": leg.iv,
                }
                for leg in self.legs
            ],
            "pnl_curve": [
                {
                    "price": p.underlying_price,
                    "pnl": round(p.pnl, 2),
                    "pnl_pct": round(p.pnl_pct, 2),
                }
                for p in self.pnl_curve
            ],
            "max_profit": round(self.max_profit, 2),
            "max_loss": round(self.max_loss, 2),
            "breakevens": [round(b, 2) for b in self.breakevens],
            "net_debit_credit": round(self.net_debit_credit, 2),
            "position_delta": round(self.position_delta, 4),
            "position_gamma": round(self.position_gamma, 4),
            "position_theta": round(self.position_theta, 4),
            "position_vega": round(self.position_vega, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "probability_profit": round(self.probability_profit, 2),
        }


# ──────────────────────────────────────────────
# P&L Calculator Engine
# ──────────────────────────────────────────────


class PnLCalculator:
    """Multi-leg options P&L calculator.

    Uses Questrade exchange data for live Greeks and pricing.
    All calculations assume standard US equity options (100 shares/contract).
    """

    SHARES_PER_CONTRACT = 100

    def _leg_pnl_at_expiry(self, leg: OptionLeg, underlying_price: float) -> float:
        """Calculate P&L for a single leg at expiration.

        P&L = (intrinsic_value - premium) * quantity * 100
        """
        if leg.option_type.lower() == "call":
            intrinsic = max(0, underlying_price - leg.strike)
        else:  # put
            intrinsic = max(0, leg.strike - underlying_price)

        pnl_per_share = (intrinsic - leg.premium) * leg.quantity
        return pnl_per_share * self.SHARES_PER_CONTRACT

    def calculate_pnl(
        self,
        legs: list[OptionLeg],
        underlying_price: float,
        price_range_pct: float = 0.30,
        num_points: int = 200,
        strategy_name: str = "Custom Strategy",
    ) -> PnLResult:
        """Calculate complete P&L analysis for a multi-leg options strategy.

        Args:
            legs: List of OptionLeg objects defining the strategy.
            underlying_price: Current price of the underlying stock.
            price_range_pct: Range around current price to calculate (0.30 = ±30%).
            num_points: Number of points on the P&L curve.
            strategy_name: Human-readable name for the strategy.

        Returns:
            PnLResult with full curve, metrics, and Greeks.
        """
        if not legs:
            return PnLResult(
                strategy_name=strategy_name,
                legs=[],
                underlying_price=underlying_price,
                pnl_curve=[],
                max_profit=0.0,
                max_loss=0.0,
                breakevens=[],
                net_debit_credit=0.0,
            )

        # Calculate price range
        low = underlying_price * (1 - price_range_pct)
        high = underlying_price * (1 + price_range_pct)

        # Include strikes in the range for accuracy
        all_strikes = [leg.strike for leg in legs]
        low = min(low, min(all_strikes) * 0.90)
        high = max(high, max(all_strikes) * 1.10)

        step = (high - low) / num_points

        # Net debit/credit for the position
        net_debit_credit = sum(
            leg.premium * leg.quantity * self.SHARES_PER_CONTRACT for leg in legs
        )

        # Calculate P&L at each price point
        pnl_curve: list[PnLPoint] = []
        for i in range(num_points + 1):
            price = low + (step * i)
            total_pnl = sum(self._leg_pnl_at_expiry(leg, price) for leg in legs)
            pnl_curve.append(
                PnLPoint(
                    underlying_price=round(price, 2),
                    pnl=total_pnl,
                    pnl_pct=0.0,  # Will set after we know max_loss
                )
            )

        # Extract key metrics
        all_pnls = [p.pnl for p in pnl_curve]
        max_profit = max(all_pnls)
        max_loss = min(all_pnls)

        # Set pnl_pct relative to max risk
        max_risk = abs(max_loss) if max_loss < 0 else abs(net_debit_credit) or 1.0
        for p in pnl_curve:
            p.pnl_pct = (p.pnl / max_risk) * 100 if max_risk > 0 else 0.0

        # Find breakevens (where P&L crosses zero)
        breakevens = self._find_breakevens(pnl_curve)

        # Calculate risk/reward ratio
        risk_reward = (
            abs(max_profit / max_loss) if max_loss != 0 else float("inf")
        )

        # Aggregate position Greeks
        pos_delta = sum(leg.delta * leg.quantity * self.SHARES_PER_CONTRACT for leg in legs)
        pos_gamma = sum(leg.gamma * leg.quantity * self.SHARES_PER_CONTRACT for leg in legs)
        pos_theta = sum(leg.theta * leg.quantity * self.SHARES_PER_CONTRACT for leg in legs)
        pos_vega = sum(leg.vega * leg.quantity * self.SHARES_PER_CONTRACT for leg in legs)

        # Rough probability of profit estimate (from aggregate delta)
        # For long calls: prob profit ≈ delta
        # For complex strategies, sum delta gives a rough proxy
        prob_profit = self._estimate_probability_profit(legs, underlying_price, breakevens)

        result = PnLResult(
            strategy_name=strategy_name,
            legs=legs,
            underlying_price=underlying_price,
            pnl_curve=pnl_curve,
            max_profit=max_profit,
            max_loss=max_loss,
            breakevens=breakevens,
            net_debit_credit=net_debit_credit,
            position_delta=pos_delta,
            position_gamma=pos_gamma,
            position_theta=pos_theta,
            position_vega=pos_vega,
            risk_reward_ratio=risk_reward,
            probability_profit=prob_profit,
        )

        _log.info(
            "pnl.calculated",
            strategy=strategy_name,
            legs=len(legs),
            max_profit=round(max_profit, 2),
            max_loss=round(max_loss, 2),
            breakevens=[round(b, 2) for b in breakevens],
        )

        return result

    def _find_breakevens(self, curve: list[PnLPoint]) -> list[float]:
        """Find price points where P&L crosses zero."""
        breakevens = []
        for i in range(1, len(curve)):
            prev_pnl = curve[i - 1].pnl
            curr_pnl = curve[i].pnl

            # Check for zero crossing
            if (prev_pnl <= 0 < curr_pnl) or (prev_pnl >= 0 > curr_pnl):
                # Linear interpolation for more accurate breakeven
                if curr_pnl != prev_pnl:
                    fraction = abs(prev_pnl) / abs(curr_pnl - prev_pnl)
                    breakeven = curve[i - 1].underlying_price + fraction * (
                        curve[i].underlying_price - curve[i - 1].underlying_price
                    )
                    breakevens.append(round(breakeven, 2))

        return breakevens

    def _estimate_probability_profit(
        self,
        legs: list[OptionLeg],
        underlying_price: float,
        breakevens: list[float],
    ) -> float:
        """Rough probability of profit estimation using IV and log-normal distribution.

        Uses the average IV of the legs and assumes log-normal price distribution.
        This is a simplified Black-Scholes-like approach, not an exact calculation.
        """
        if not breakevens or not legs:
            return 50.0  # No breakeven = unknown

        # Use average IV from legs (or default 30%)
        ivs = [leg.iv for leg in legs if leg.iv > 0]
        avg_iv = sum(ivs) / len(ivs) if ivs else 0.30

        # Assume ~30 DTE for simplification if not specified
        # A more accurate version would use actual DTE
        dte_years = 30 / 365.0

        # For single breakeven, calculate probability of being above/below
        if len(breakevens) == 1:
            be = breakevens[0]
            d2 = (math.log(underlying_price / be) + (0 - 0.5 * avg_iv**2) * dte_years) / (
                avg_iv * math.sqrt(dte_years)
            )
            prob = self._normal_cdf(d2)
            # If strategy profits when price goes UP past breakeven
            if sum(leg.delta * leg.quantity for leg in legs) > 0:
                return round(prob * 100, 1)
            else:
                return round((1 - prob) * 100, 1)

        if len(breakevens) == 2:
            # For two breakevens (straddle, iron condor, etc.)
            be_low, be_high = sorted(breakevens)
            d2_low = (math.log(underlying_price / be_low) + (0 - 0.5 * avg_iv**2) * dte_years) / (
                avg_iv * math.sqrt(dte_years)
            )
            d2_high = (math.log(underlying_price / be_high) + (0 - 0.5 * avg_iv**2) * dte_years) / (
                avg_iv * math.sqrt(dte_years)
            )
            prob_between = self._normal_cdf(d2_high) - self._normal_cdf(d2_low)

            # Determine if strategy profits between or outside breakevens
            # Check P&L at current price (mid-point)
            mid_pnl = sum(self._leg_pnl_at_expiry(leg, underlying_price) for leg in legs)
            if mid_pnl > 0:
                return round(prob_between * 100, 1)
            else:
                return round((1 - prob_between) * 100, 1)

        return 50.0

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate standard normal CDF using error function."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    # ──────────────────────────────────────────
    # Pre-built Strategy Helpers
    # ──────────────────────────────────────────

    def build_vertical_spread(
        self,
        option_type: str,
        long_strike: float,
        short_strike: float,
        long_premium: float,
        short_premium: float,
        expiration: str = "",
        long_greeks: dict | None = None,
        short_greeks: dict | None = None,
    ) -> list[OptionLeg]:
        """Build a vertical spread (bull call, bear put, etc.)."""
        lg = long_greeks or {}
        sg = short_greeks or {}
        return [
            OptionLeg(
                option_type=option_type,
                strike=long_strike,
                premium=long_premium,
                quantity=1,
                expiration=expiration,
                delta=lg.get("delta", 0),
                gamma=lg.get("gamma", 0),
                theta=lg.get("theta", 0),
                vega=lg.get("vega", 0),
                iv=lg.get("iv", 0),
            ),
            OptionLeg(
                option_type=option_type,
                strike=short_strike,
                premium=short_premium,
                quantity=-1,
                expiration=expiration,
                delta=sg.get("delta", 0),
                gamma=sg.get("gamma", 0),
                theta=sg.get("theta", 0),
                vega=sg.get("vega", 0),
                iv=sg.get("iv", 0),
            ),
        ]

    def build_iron_condor(
        self,
        put_long_strike: float,
        put_short_strike: float,
        call_short_strike: float,
        call_long_strike: float,
        put_long_premium: float,
        put_short_premium: float,
        call_short_premium: float,
        call_long_premium: float,
        expiration: str = "",
    ) -> list[OptionLeg]:
        """Build an iron condor (sell OTM put spread + sell OTM call spread)."""
        return [
            OptionLeg("put", put_long_strike, put_long_premium, 1, expiration),
            OptionLeg("put", put_short_strike, put_short_premium, -1, expiration),
            OptionLeg("call", call_short_strike, call_short_premium, -1, expiration),
            OptionLeg("call", call_long_strike, call_long_premium, 1, expiration),
        ]

    def build_straddle(
        self,
        strike: float,
        call_premium: float,
        put_premium: float,
        direction: int = 1,  # 1 = long, -1 = short
        expiration: str = "",
    ) -> list[OptionLeg]:
        """Build a straddle (buy/sell ATM call + put same strike)."""
        return [
            OptionLeg("call", strike, call_premium, direction, expiration),
            OptionLeg("put", strike, put_premium, direction, expiration),
        ]

    def build_strangle(
        self,
        call_strike: float,
        put_strike: float,
        call_premium: float,
        put_premium: float,
        direction: int = 1,
        expiration: str = "",
    ) -> list[OptionLeg]:
        """Build a strangle (buy/sell OTM call + OTM put different strikes)."""
        return [
            OptionLeg("call", call_strike, call_premium, direction, expiration),
            OptionLeg("put", put_strike, put_premium, direction, expiration),
        ]

    def build_butterfly(
        self,
        option_type: str,
        lower_strike: float,
        middle_strike: float,
        upper_strike: float,
        lower_premium: float,
        middle_premium: float,
        upper_premium: float,
        expiration: str = "",
    ) -> list[OptionLeg]:
        """Build a butterfly spread (buy 1 lower, sell 2 middle, buy 1 upper)."""
        return [
            OptionLeg(option_type, lower_strike, lower_premium, 1, expiration),
            OptionLeg(option_type, middle_strike, middle_premium, -2, expiration),
            OptionLeg(option_type, upper_strike, upper_premium, 1, expiration),
        ]
