"""
Bubby Vision — Risk Engine

Position sizing, Kelly criterion, risk/reward analysis, and portfolio risk.
Pure domain logic — no LLM dependency.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models import PositionSize


class RiskEngine:
    """Position sizing and risk management calculations."""

    def compute_position_size(
        self,
        account_size: float,
        entry_price: float,
        stop_price: float,
        target_price: Optional[float] = None,
        risk_pct: float = 0.01,
        win_rate: Optional[float] = None,
    ) -> PositionSize:
        """Calculate position size based on risk management rules.

        The 1% Rule: Never risk more than 1% of account on a single trade.

        Args:
            account_size: Total account value in dollars.
            entry_price: Planned entry price.
            stop_price: Stop-loss price.
            target_price: Take-profit price (optional).
            risk_pct: Maximum risk per trade (default 1%).
            win_rate: Historical win rate (for Kelly calculation).
        """
        dollar_risk = account_size * risk_pct
        per_share_risk = abs(entry_price - stop_price)

        if per_share_risk <= 0:
            return PositionSize(
                ticker="",
                account_size=account_size,
                risk_pct=risk_pct,
                entry_price=entry_price,
                stop_price=stop_price,
            )

        shares = int(dollar_risk / per_share_risk)

        # Risk/Reward
        rr_ratio = None
        expected_value = None
        if target_price is not None:
            reward = abs(target_price - entry_price)
            rr_ratio = round(reward / per_share_risk, 2) if per_share_risk > 0 else None

            if win_rate is not None and rr_ratio is not None:
                # EV = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
                expected_value = round(
                    (win_rate * reward * shares) - ((1 - win_rate) * per_share_risk * shares), 2
                )

        # Kelly Criterion
        kelly = None
        if win_rate is not None and rr_ratio is not None and rr_ratio > 0:
            # f* = (bp - q) / b
            # b = win/loss ratio, p = probability of win, q = probability of loss
            b = rr_ratio
            p = win_rate
            q = 1 - p
            kelly_raw = (b * p - q) / b
            kelly = round(max(0, min(kelly_raw, 0.25)), 4)  # Cap at 25%

        # Option contracts (assuming $1 per share = $100 per contract)
        contracts = max(1, shares // 100) if shares >= 100 else 0

        return PositionSize(
            ticker="",
            account_size=account_size,
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            shares=shares,
            contracts=contracts,
            dollar_risk=round(dollar_risk, 2),
            risk_reward_ratio=rr_ratio,
            expected_value=expected_value,
            kelly_fraction=kelly,
        )

    def trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        atr: float,
        multiplier: float = 2.0,
    ) -> dict:
        """Calculate trailing stop based on ATR.

        ATR-based stops adapt to volatility — wider in volatile markets,
        tighter in calm ones.
        """
        stop = current_price - (atr * multiplier)
        distance_pct = round((current_price - stop) / current_price * 100, 2)
        profit_pct = round((current_price - entry_price) / entry_price * 100, 2)

        return {
            "trailing_stop": round(stop, 2),
            "distance_pct": distance_pct,
            "atr": round(atr, 2),
            "multiplier": multiplier,
            "current_price": current_price,
            "entry_price": entry_price,
            "unrealized_profit_pct": profit_pct,
            "locked_profit": round(max(0, stop - entry_price), 2),
        }

    def portfolio_heat(
        self,
        positions: list[dict],
        account_size: float,
    ) -> dict:
        """Calculate total portfolio risk (heat).

        Args:
            positions: List of {'ticker': str, 'shares': int,
                               'entry_price': float, 'stop_price': float}
            account_size: Total account value.

        Returns:
            Total open risk as % of account and per-position breakdown.
        """
        total_risk = 0.0
        breakdown = []

        for pos in positions:
            per_share_risk = abs(pos["entry_price"] - pos["stop_price"])
            position_risk = per_share_risk * pos["shares"]
            risk_pct = (position_risk / account_size * 100) if account_size > 0 else 0

            total_risk += position_risk
            breakdown.append({
                "ticker": pos["ticker"],
                "position_risk": round(position_risk, 2),
                "risk_pct": round(risk_pct, 2),
            })

        total_heat = round(total_risk / account_size * 100, 2) if account_size > 0 else 0

        # Traffic light
        if total_heat > 6:
            status = "critical"
            message = f"Portfolio heat {total_heat}% — REDUCE EXPOSURE. Max recommended: 6%"
        elif total_heat > 4:
            status = "warning"
            message = f"Portfolio heat {total_heat}% — approaching limit. Max recommended: 6%"
        else:
            status = "healthy"
            message = f"Portfolio heat {total_heat}% — within healthy range"

        return {
            "total_heat_pct": total_heat,
            "total_risk_dollars": round(total_risk, 2),
            "account_size": account_size,
            "status": status,
            "message": message,
            "positions": breakdown,
        }

    @staticmethod
    def score_trade_quality(
        risk_reward: Optional[float],
        win_rate: Optional[float],
        relative_volume: Optional[float],
        rsi: Optional[float],
        adx: Optional[float],
        multi_tf_alignment: Optional[float] = None,
    ) -> dict:
        """Score a trade setup on a 0-100 scale (from daily_stock_analysis pattern).

        | Score | Verdict     |
        |-------|-------------|
        | 80+   | Strong Buy  |
        | 60-79 | Buy         |
        | 40-59 | Hold/Watch  |
        | 0-39  | Sell/Reduce |
        """
        score = 50  # baseline

        # Risk/Reward (+/-20)
        if risk_reward is not None:
            if risk_reward >= 3:
                score += 20
            elif risk_reward >= 2:
                score += 10
            elif risk_reward >= 1:
                score += 0
            else:
                score -= 15

        # Win Rate (+/-10)
        if win_rate is not None:
            if win_rate >= 0.65:
                score += 10
            elif win_rate >= 0.50:
                score += 5
            else:
                score -= 10

        # Volume confirmation (+/-10)
        if relative_volume is not None:
            if relative_volume >= 2.0:
                score += 10
            elif relative_volume >= 1.5:
                score += 5
            elif relative_volume < 0.7:
                score -= 10

        # Trend Strength (+/-10)
        if adx is not None:
            if adx >= 25:
                score += 10
            elif adx >= 20:
                score += 5
            elif adx < 15:
                score -= 5

        # Multi-TF alignment (+/-10)
        if multi_tf_alignment is not None:
            if multi_tf_alignment >= 80:
                score += 10
            elif multi_tf_alignment >= 60:
                score += 5

        score = max(0, min(100, score))

        if score >= 80:
            verdict = "Strong Buy"
        elif score >= 60:
            verdict = "Buy"
        elif score >= 40:
            verdict = "Hold/Watch"
        else:
            verdict = "Sell/Reduce"

        return {
            "score": score,
            "verdict": verdict,
            "components": {
                "risk_reward": risk_reward,
                "win_rate": win_rate,
                "relative_volume": relative_volume,
                "adx": adx,
                "multi_tf_alignment": multi_tf_alignment,
            },
        }

    @staticmethod
    def score_trade(
        risk_reward: float = 0.0,
        win_rate: float = 0.5,
        volume_confirmation: bool = False,
        trend_alignment: bool = False,
        support_nearby: bool = False,
    ) -> int:
        """Simplified trade scoring with boolean flags.

        Returns an integer score 0-100. This is a convenience wrapper around
        score_trade_quality() for cases where detailed indicator values aren't
        available.
        """
        result = RiskEngine.score_trade_quality(
            risk_reward=risk_reward,
            win_rate=win_rate,
            relative_volume=2.0 if volume_confirmation else 1.0,
            rsi=None,
            adx=30.0 if trend_alignment else 10.0,
            multi_tf_alignment=80.0 if support_nearby else None,
        )
        return result["score"]
