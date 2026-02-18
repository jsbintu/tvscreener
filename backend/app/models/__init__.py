"""
Bubby Vision — Pydantic Models

All I/O schemas for the application. Engines and data clients return these,
agents consume these, API routes serialize these.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class TimeFrame(str, Enum):
    """Supported chart timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1wk"
    MO = "1mo"


class Sentiment(str, Enum):
    """Market sentiment levels."""
    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


class SignalStrength(str, Enum):
    """Technical signal strength."""
    STRONG_SELL = "strong_sell"
    SELL = "sell"
    NEUTRAL = "neutral"
    BUY = "buy"
    STRONG_BUY = "strong_buy"


class BreakoutStage(str, Enum):
    """Breakout lifecycle stage (from P.1 spec)."""
    ACCUMULATION = "accumulation"
    PRE_BREAKOUT = "pre_breakout"
    BREAKOUT = "breakout"
    CONFIRMATION = "confirmation"
    FOLLOW_THROUGH = "follow_through"
    FAILED = "failed"


# ──────────────────────────────────────────────
# Market Data Models
# ──────────────────────────────────────────────

class OHLCV(BaseModel):
    """Single OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockQuote(BaseModel):
    """Real-time stock quote."""
    ticker: str
    price: float
    change: float
    change_pct: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    avg_volume: Optional[int] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StockData(BaseModel):
    """Complete stock data bundle."""
    ticker: str
    quote: StockQuote
    history: list[OHLCV] = []
    fundamentals: dict = {}


# ──────────────────────────────────────────────
# Options Models
# ──────────────────────────────────────────────

class OptionGreeks(BaseModel):
    """Option Greeks for a single contract."""
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    implied_volatility: Optional[float] = None


class HigherGreeks(BaseModel):
    """2nd and 3rd order option Greeks."""
    # 2nd order
    charm: Optional[float] = None       # dDelta/dTime
    vanna: Optional[float] = None       # dDelta/dVol = dVega/dSpot
    vomma: Optional[float] = None       # dVega/dVol (aka volga)
    veta: Optional[float] = None        # dVega/dTime
    # 3rd order
    color: Optional[float] = None       # dGamma/dTime
    speed: Optional[float] = None       # dGamma/dSpot
    ultima: Optional[float] = None      # dVomma/dVol
    zomma: Optional[float] = None       # dGamma/dVol


class OptionContract(BaseModel):
    """Single option contract."""
    contract_symbol: str
    strike: float
    expiration: datetime
    option_type: str  # "call" or "put"
    last_price: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    greeks: OptionGreeks = Field(default_factory=OptionGreeks)
    in_the_money: bool = False


class OptionsChain(BaseModel):
    """Full options chain for a ticker."""
    ticker: str
    underlying_price: float
    expirations: list[str] = []
    calls: list[OptionContract] = []
    puts: list[OptionContract] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Sentiment & News Models
# ──────────────────────────────────────────────

class FearGreedIndex(BaseModel):
    """CNN Fear & Greed Index."""
    value: int = Field(ge=0, le=100)
    label: Sentiment
    previous_close: Optional[int] = None
    one_week_ago: Optional[int] = None
    one_month_ago: Optional[int] = None
    one_year_ago: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SubIndicator(BaseModel):
    """Single CNN Fear & Greed sub-indicator."""
    name: str
    value: float
    rating: str  # e.g. "Fear", "Greed", "Extreme Greed"


class FearGreedDetailed(BaseModel):
    """CNN Fear & Greed Index with all 7 sub-indicators."""
    value: int = Field(ge=0, le=100)
    label: Sentiment
    previous_close: Optional[int] = None
    one_week_ago: Optional[int] = None
    one_month_ago: Optional[int] = None
    one_year_ago: Optional[int] = None
    sub_indicators: list[SubIndicator] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EarningsEstimate(BaseModel):
    """Forward earnings estimate from Finnhub."""
    ticker: str
    period: str  # e.g. "2025-Q1"
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    surprise_pct: Optional[float] = None
    analysts: Optional[int] = None
    report_date: Optional[str] = None


class PriceTarget(BaseModel):
    """Analyst price target consensus from Finnhub."""
    ticker: str
    target_high: Optional[float] = None
    target_low: Optional[float] = None
    target_mean: Optional[float] = None
    target_median: Optional[float] = None
    last_updated: Optional[str] = None


class BacktestResult(BaseModel):
    """Backtest strategy result from VectorBT."""
    strategy: str
    ticker: str
    period: str
    total_return: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: float
    win_rate: float
    total_trades: int
    avg_trade_duration: Optional[str] = None
    equity_final: Optional[float] = None
    benchmark_return: Optional[float] = None


class NewsItem(BaseModel):
    """Single news article with sentiment."""
    headline: str
    summary: Optional[str] = None
    source: str
    url: str
    datetime_published: datetime
    ticker: Optional[str] = None
    sentiment_score: Optional[float] = None  # -1.0 to 1.0
    sentiment_label: Optional[str] = None


class FilingData(BaseModel):
    """SEC filing from EDGAR."""
    ticker: str
    form_type: str  # "10-K", "10-Q", "8-K", "4"
    filed_date: datetime
    period_of_report: Optional[datetime] = None
    description: Optional[str] = None
    url: str
    is_insider_trade: bool = False
    insider_name: Optional[str] = None
    insider_title: Optional[str] = None
    transaction_type: Optional[str] = None  # "Buy" / "Sell"
    shares: Optional[int] = None
    price_per_share: Optional[float] = None


# ──────────────────────────────────────────────
# Technical Analysis Models
# ──────────────────────────────────────────────

class SupportResistance(BaseModel):
    """Support or resistance level."""
    price: float
    strength: int = Field(ge=1, le=5, description="Touches/confirmations")
    level_type: str  # "support" or "resistance"
    timeframe: TimeFrame = TimeFrame.D1


class TechnicalIndicators(BaseModel):
    """Computed technical indicators for a ticker."""
    ticker: str
    timeframe: TimeFrame
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_8: Optional[float] = None
    ema_21: Optional[float] = None
    atr_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    adx: Optional[float] = None
    obv: Optional[float] = None
    vwap: Optional[float] = None
    volume_sma_20: Optional[float] = None
    relative_volume: Optional[float] = None
    # ── Extended indicators (Phase 7b audit) ──
    williams_r: Optional[float] = None
    cci: Optional[float] = None
    mfi: Optional[float] = None
    cmf: Optional[float] = None
    roc: Optional[float] = None
    tsi: Optional[float] = None
    force_index: Optional[float] = None
    ultimate_osc: Optional[float] = None
    keltner_upper: Optional[float] = None
    keltner_lower: Optional[float] = None
    donchian_upper: Optional[float] = None
    donchian_lower: Optional[float] = None
    aroon_up: Optional[float] = None
    aroon_down: Optional[float] = None
    ichimoku_a: Optional[float] = None
    ichimoku_b: Optional[float] = None
    ichimoku_base: Optional[float] = None
    psar: Optional[float] = None
    supertrend: Optional[float] = None
    supertrend_direction: Optional[str] = None  # "up" or "down"
    squeeze_on: Optional[bool] = None
    # ── Finta-sourced unique indicators ──
    kama: Optional[float] = None           # Kaufman Adaptive MA
    zlema: Optional[float] = None          # Zero-Lag EMA
    hma: Optional[float] = None            # Hull MA
    frama: Optional[float] = None          # Fractal Adaptive MA
    ppo: Optional[float] = None            # Percentage Price Oscillator
    ppo_signal: Optional[float] = None     # PPO signal line
    awesome_oscillator: Optional[float] = None  # Awesome Oscillator
    pivot: Optional[float] = None          # Pivot point
    pivot_r1: Optional[float] = None       # Resistance 1
    pivot_s1: Optional[float] = None       # Support 1
    overall_signal: SignalStrength = SignalStrength.NEUTRAL
    support_levels: list[SupportResistance] = []
    resistance_levels: list[SupportResistance] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Breakout Models
# ──────────────────────────────────────────────

class BreakoutSignal(BaseModel):
    """Pre-breakout or breakout detection signal."""
    ticker: str
    stage: BreakoutStage
    quality_score: int = Field(ge=0, le=100)
    volume_score: int = Field(ge=0, le=20)
    pattern_score: int = Field(ge=0, le=15)
    trend_score: int = Field(ge=0, le=10)
    multi_tf_score: int = Field(ge=0, le=15)
    options_score: int = Field(ge=0, le=15)
    candle_score: int = Field(ge=0, le=10)
    institutional_score: int = Field(ge=0, le=10)
    sector_score: int = Field(ge=0, le=5)
    precursor_signals: list[str] = []
    breakout_level: Optional[float] = None
    expected_timeframe: Optional[str] = None
    recommended_play: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Risk & Position Models
# ──────────────────────────────────────────────

class PositionSize(BaseModel):
    """Position sizing calculation output."""
    ticker: str
    account_size: float
    risk_pct: float = 0.01
    entry_price: float
    stop_price: float
    target_price: Optional[float] = None
    shares: int = 0
    contracts: int = 0
    dollar_risk: float = 0.0
    risk_reward_ratio: Optional[float] = None
    expected_value: Optional[float] = None
    kelly_fraction: Optional[float] = None


# ──────────────────────────────────────────────
# API Models (Request / Response)
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    """Chat message for the AI agent."""
    role: str = "user"  # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Incoming chat request."""
    message: str = ""
    messages: list[ChatMessage] = []
    conversation_id: Optional[str] = None
    context: dict = {}

    def get_last_user_message(self) -> str:
        """Get the last user message from either message or messages."""
        if self.messages:
            return self.messages[-1].content
        return self.message


class ChatResponse(BaseModel):
    """Chat response from the AI agent."""
    message: str
    conversation_id: str
    agent_used: Optional[str] = None
    tools_called: list[str] = []
    confidence: Optional[float] = None
    warnings: Optional[list[str]] = None
    data: dict = {}


class HealthCheck(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    environment: str = "development"
    services: dict = {}


class PaginatedResponse(BaseModel):
    """Standardized paginated response for list endpoints."""
    data: list = Field(default_factory=list, description="Array of result items")
    page: int = Field(1, ge=1, description="Current page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    total: int = Field(0, ge=0, description="Total items available")
    has_more: bool = Field(False, description="Whether more pages exist")


# ──────────────────────────────────────────────
# OpenBB Enhanced Data Models
# ──────────────────────────────────────────────

class InstitutionalHolder(BaseModel):
    """13F institutional holder from SEC filings."""
    name: str = Field(..., description="Institution name")
    shares: int = Field(0, description="Number of shares held")
    value: Optional[float] = Field(None, description="Market value in USD")
    weight_pct: Optional[float] = Field(None, description="Weight in portfolio (%)")
    change_shares: Optional[int] = Field(None, description="Change in shares from prior filing")
    change_pct: Optional[float] = Field(None, description="Percent change from prior filing")
    date_reported: Optional[datetime] = Field(None, description="Filing date")


class EconomicEvent(BaseModel):
    """Upcoming economic calendar event."""
    date: datetime = Field(..., description="Event date/time")
    event: str = Field(..., description="Event name")
    country: str = Field("US", description="Country code")
    actual: Optional[float] = Field(None, description="Actual value (if released)")
    forecast: Optional[float] = Field(None, description="Consensus forecast")
    previous: Optional[float] = Field(None, description="Previous value")
    importance: str = Field("medium", description="low, medium, or high")
    unit: Optional[str] = Field(None, description="Value unit (%, bps, etc)")


class DividendRecord(BaseModel):
    """Historical dividend payment record."""
    ex_date: datetime = Field(..., description="Ex-dividend date")
    pay_date: Optional[datetime] = Field(None, description="Payment date")
    record_date: Optional[datetime] = Field(None, description="Record date")
    amount: float = Field(..., description="Dividend per share")
    currency: str = Field("USD", description="Currency")
    frequency: Optional[str] = Field(None, description="quarterly, semi-annual, annual")


class ETFHolding(BaseModel):
    """Single holding within an ETF."""
    symbol: Optional[str] = Field(None, description="Ticker symbol")
    name: str = Field(..., description="Holding name")
    weight_pct: float = Field(..., description="Weight in ETF (%)")
    shares: Optional[int] = Field(None, description="Number of shares")
    market_value: Optional[float] = Field(None, description="Market value in USD")


class AnalystEstimate(BaseModel):
    """Forward revenue/EPS consensus estimates."""
    period: str = Field(..., description="Fiscal period (e.g., FY2025, Q1 2025)")
    revenue_estimate: Optional[float] = Field(None, description="Consensus revenue estimate")
    revenue_low: Optional[float] = Field(None, description="Low revenue estimate")
    revenue_high: Optional[float] = Field(None, description="High revenue estimate")
    eps_estimate: Optional[float] = Field(None, description="Consensus EPS estimate")
    eps_low: Optional[float] = Field(None, description="Low EPS estimate")
    eps_high: Optional[float] = Field(None, description="High EPS estimate")
    num_analysts: Optional[int] = Field(None, description="Number of analysts")
