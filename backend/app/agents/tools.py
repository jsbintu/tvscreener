"""
Bubby Vision — LangGraph Tool Definitions

Wraps engines and data clients as LangChain tools for agent use.
Each tool is a function callable by the LLM via function calling.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from app.engines.data_engine import DataEngine
from app.engines.ta_engine import TAEngine
from app.engines.options_engine import OptionsEngine
from app.engines.risk_engine import RiskEngine
from app.engines.breakout_engine import BreakoutEngine
from app.engines.pattern_engine import PatternEngine
from app.engines.vision_engine import VisionEngine
from app.engines.coaching_engine import CoachingEngine
from app.engines.opening_range_engine import OpeningRangeEngine
from app.engines.ghost_chart_engine import GhostChartEngine
from app.engines.optimizer_engine import OptimizerEngine

# ── Singleton Instances ──
_data = DataEngine()
_ta = TAEngine()
_options = OptionsEngine()
_risk = RiskEngine()
_breakout = BreakoutEngine()
_patterns = PatternEngine()
_vision = VisionEngine()
_coach = CoachingEngine()
_opening_range = OpeningRangeEngine()
_ghosts = GhostChartEngine()
_optimizer = OptimizerEngine()


# ──────────────────────────────────────────────
# Data Tools
# ──────────────────────────────────────────────

@tool
def get_stock_data(ticker: str, period: str = "3mo", interval: str = "1d") -> dict:
    """Fetch stock data: quote, OHLCV history, and fundamentals.

    Args:
        ticker: Stock ticker symbol (e.g. AAPL, TSLA, SPY).
        period: Data period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max.
        interval: Candle interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk.
    """
    data = _data.get_stock(ticker, period=period, interval=interval)
    return data.model_dump(mode="json")


@tool
def get_options_chain(ticker: str, expiration: Optional[str] = None) -> dict:
    """Fetch options chain with implied volatility for a ticker.

    Args:
        ticker: Stock ticker symbol.
        expiration: Expiration date (YYYY-MM-DD). Omit for nearest.
    """
    chain = _data.get_options(ticker, expiration=expiration)
    return chain.model_dump(mode="json")


@tool
async def get_fear_greed_index() -> dict:
    """Fetch the current CNN Fear & Greed Index (0-100).

    Returns market-wide sentiment: extreme_fear, fear, neutral, greed, extreme_greed.
    """
    fg = await _data.get_fear_greed()
    return fg.model_dump(mode="json")


@tool
async def get_company_news(ticker: str, limit: int = 15) -> list[dict]:
    """Fetch recent company news articles from Finnhub.

    Args:
        ticker: Stock ticker symbol.
        limit: Max articles to return (default 15).
    """
    news = await _data.get_news(ticker, limit=limit)
    return [n.model_dump(mode="json") for n in news]


@tool
async def get_sentiment_bundle(ticker: str) -> dict:
    """Fetch fused sentiment from Fear & Greed, Finnhub, and WSB Reddit.

    Combines market-wide and ticker-specific sentiment from 3 sources.

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_sentiment_bundle(ticker)


@tool
def get_sec_filings(ticker: str, form_type: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Fetch SEC filings from EDGAR.

    Args:
        ticker: Stock ticker symbol.
        form_type: Filter by type: 10-K, 10-Q, 8-K, 4 (insider trades).
        limit: Max filings to return.
    """
    filings = _data.get_filings(ticker, form_type=form_type, limit=limit)
    return [f.model_dump(mode="json") for f in filings]


@tool
async def get_options_flow(ticker: Optional[str] = None, min_premium: int = 100_000) -> list[dict]:
    """Fetch live options flow data from QuantData.us.

    Shows institutional-size options orders in real-time.

    Args:
        ticker: Filter by ticker (optional). None = all tickers.
        min_premium: Minimum premium in dollars (default $100K).
    """
    return await _data.get_options_flow(ticker, min_premium=min_premium)


@tool
async def get_market_clock() -> dict:
    """Check if the market is currently open and when it opens/closes next."""
    return await _data.get_market_clock()


@tool
async def get_trending_tickers() -> dict:
    """Get trending tickers from WallStreetBets by mention count."""
    return await _data.get_trending_tickers()


@tool
def get_financials(ticker: str) -> dict:
    """Fetch XBRL financial data from the latest 10-K filing via SEC EDGAR.

    Returns revenue, net income, total assets, liabilities, equity,
    EPS (basic/diluted), and shares outstanding.

    Args:
        ticker: Stock ticker symbol.
    """
    return _data.get_financials(ticker)


@tool
def get_insider_trades(ticker: str, limit: int = 20) -> list[dict]:
    """Fetch insider trading activity (Form 4 filings) from SEC EDGAR.

    Shows insider buys and sells filed with the SEC.

    Args:
        ticker: Stock ticker symbol.
        limit: Max filings to return.
    """
    filings = _data.get_insider_trades(ticker, limit=limit)
    return [f.model_dump(mode="json") for f in filings]


@tool
async def get_insider_transactions(ticker: str) -> list[dict]:
    """Fetch insider transactions from Finnhub (buys, sells, exercises).

    Shows transaction amounts, shares, and filing dates.
    Complements EDGAR Form 4 data with faster updates.

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_insider_transactions(ticker)


@tool
async def get_earnings_calendar(days: int = 7) -> list[dict]:
    """Fetch upcoming earnings announcements from Finnhub.

    Args:
        days: How many days ahead to look (default 7).
    """
    return await _data.get_earnings_calendar(days=days)


@tool
async def get_analyst_recommendations(ticker: str) -> list[dict]:
    """Fetch analyst buy/sell/hold recommendation trends from Finnhub.

    Returns monthly aggregates: strong_buy, buy, hold, sell, strong_sell counts.

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_analyst_recommendations(ticker)


@tool
async def get_darkpool(ticker: str, limit: int = 25) -> list[dict]:
    """Fetch dark pool prints for a ticker from QuantData.us.

    Shows large institutional block trades executed off-exchange.

    Args:
        ticker: Stock ticker symbol.
        limit: Max prints to return.
    """
    return await _data.get_darkpool(ticker, limit=limit)


@tool
async def get_sweep_orders(ticker: Optional[str] = None, limit: int = 25) -> list[dict]:
    """Fetch sweep orders from QuantData.us.

    Sweeps are aggressive multi-exchange fills — often signal
    institutional urgency and directional conviction.

    Args:
        ticker: Filter by ticker (optional).
        limit: Max results.
    """
    return await _data.get_sweep_orders(ticker)


@tool
async def get_wsb_mentions(ticker: str, subreddit: str = "wallstreetbets", limit: int = 25) -> list[dict]:
    """Search for ticker mentions in a subreddit (WSB, stocks, options, investing).

    Returns posts with title, score, comments, upvote ratio, and URL.

    Args:
        ticker: Stock ticker symbol.
        subreddit: Subreddit to search (default: wallstreetbets).
        limit: Max posts to return.
    """
    return await _data.get_wsb_mentions(ticker, subreddit=subreddit, limit=limit)


# ──────────────────────────────────────────────
# Phase 6: Enhanced Data Tools
# ──────────────────────────────────────────────

@tool
async def get_fear_greed_detailed() -> dict:
    """Fetch CNN Fear & Greed Index with all 7 sub-indicators.

    Sub-indicators: Market Momentum, Stock Price Strength, Stock Price Breadth,
    Put/Call Options, Market Volatility (VIX), Junk Bond Demand, Safe Haven Demand.
    """
    fg = await _data.get_fear_greed_detailed()
    return fg.model_dump(mode="json")


@tool
async def get_earnings_estimates(ticker: str, freq: str = "quarterly") -> list[dict]:
    """Fetch forward EPS estimates from Finnhub.

    Args:
        ticker: Stock ticker symbol.
        freq: 'quarterly' or 'annual'.
    """
    return await _data.get_earnings_estimates(ticker, freq)


@tool
async def get_price_target(ticker: str) -> dict:
    """Fetch analyst price target consensus (high, low, mean, median) from Finnhub.

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_price_target(ticker)


@tool
async def get_basic_fundamentals(ticker: str) -> dict:
    """Fetch 100+ fundamental metrics from Finnhub (PE, PB, ROE, margins, debt ratios).

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_basic_financials(ticker)


@tool
async def get_insider_sentiment(ticker: str) -> dict:
    """Fetch aggregated insider sentiment (MSPR — monthly purchase ratio) from Finnhub.

    Positive MSPR = net insider buying. Negative = net selling.

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_insider_sentiment(ticker)


@tool
async def get_earnings_transcript(ticker: str, quarter: Optional[int] = None, year: Optional[int] = None) -> dict:
    """Fetch earnings call transcript from Finnhub (10+ years available).

    Args:
        ticker: Stock ticker symbol.
        quarter: Quarter (1-4). Omit for latest.
        year: Year. Omit for latest.
    """
    return await _data.get_earnings_transcripts(ticker, quarter, year)


@tool
def get_multi_year_financials(ticker: str, years: int = 5) -> list[dict]:
    """Fetch multi-year XBRL financials from EDGAR 10-K filings for trend analysis.

    Args:
        ticker: Stock ticker symbol.
        years: Number of annual periods (default 5).
    """
    return _data.get_multi_year_financials(ticker, years)


@tool
async def get_dd_posts(ticker: str, limit: int = 15) -> list[dict]:
    """Fetch WSB Due Diligence (DD) tagged posts — highest quality analysis.

    Args:
        ticker: Stock ticker symbol.
        limit: Max posts to return.
    """
    return await _data.get_dd_posts(ticker, limit=limit)


@tool
async def get_corporate_actions(ticker: str) -> list[dict]:
    """Fetch corporate actions (splits, dividends, mergers, spinoffs) from Alpaca.

    Args:
        ticker: Stock ticker symbol.
    """
    return await _data.get_corporate_actions(ticker)


@tool
async def get_economic_indicator(series_id: str, limit: int = 20) -> dict:
    """Fetch FRED economic data series (GDP, CPI, unemployment, Fed rate, etc.).

    Common series: GDP, UNRATE, CPIAUCSL, FEDFUNDS, DGS10, SP500, VIXCLS.

    Args:
        series_id: FRED series ID.
        limit: Max observations.
    """
    return await _data.get_economic_series(series_id, limit=limit)


@tool
async def get_treasury_yields() -> dict:
    """Fetch Treasury yields (2Y, 10Y, 30Y), yield curve spread, and inversion status."""
    return await _data.get_treasury_yields()


@tool
def backtest_strategy(
    ticker: str,
    strategy: str = "sma_crossover",
    period: str = "2y",
) -> dict:
    """Backtest a trading strategy using VectorBT.

    Available strategies: 'sma_crossover', 'rsi', 'macd', 'compare' (runs all).

    Args:
        ticker: Stock ticker symbol.
        strategy: Strategy name.
        period: Backtest period (1y, 2y, 5y).
    """
    return _data.run_backtest(strategy, ticker, period=period)


# ──────────────────────────────────────────────
# TradingView Tools
# ──────────────────────────────────────────────

@tool
async def get_tv_technical_summary(
    ticker: str,
    exchange: str = "NASDAQ",
    interval: str = "1d",
) -> dict:
    """Get TradingView's 26-indicator technical analysis summary.

    Returns overall recommendation (STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL)
    plus individual oscillator and moving average signals.

    Args:
        ticker: Stock symbol (e.g. AAPL, TSLA).
        exchange: Exchange (NASDAQ, NYSE, AMEX).
        interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d, 1W, 1M).
    """
    return await _data.get_tv_technical_summary(ticker, exchange=exchange, interval=interval)


@tool
async def screen_stocks_tv(
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_volume: Optional[int] = None,
    min_market_cap: Optional[float] = None,
    sort_by: str = "market_cap_basic",
    limit: int = 25,
) -> list[dict]:
    """Run a TradingView stock screener scan with custom filters.

    Returns stocks with technicals, fundamentals, and performance data.
    Uses TradingView's 3000+ field screener API.

    Args:
        min_price: Minimum stock price filter.
        max_price: Maximum stock price filter.
        min_volume: Minimum daily volume filter.
        min_market_cap: Minimum market cap in dollars.
        sort_by: Sort column (default: market_cap_basic).
        limit: Max results (default 25).
    """
    return await _data.screen_stocks_tv(
        min_price=min_price, max_price=max_price,
        min_volume=min_volume, min_market_cap=min_market_cap,
        sort_by=sort_by, limit=limit,
    )


@tool
async def get_top_movers_tv(direction: str = "gainers", limit: int = 15) -> list[dict]:
    """Get top gainers, losers, or most active stocks from TradingView.

    Only includes stocks with $1B+ market cap for quality.

    Args:
        direction: One of 'gainers', 'losers', or 'active'.
        limit: Max results (default 15).
    """
    return await _data.get_top_movers_tv(direction=direction, limit=limit)


@tool
async def get_alpaca_options_snapshot(
    ticker: str,
    option_type: Optional[str] = None,
    expiration: Optional[str] = None,
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
    limit: int = 50,
) -> dict:
    """Fetch live options chain with full Greeks from Alpaca.

    Returns real-time bid/ask, last trade, and Greeks
    (delta, gamma, theta, vega, rho, IV) for each contract.

    Args:
        ticker: Underlying symbol (e.g. AAPL, SPY).
        option_type: Filter by 'call' or 'put'.
        expiration: Expiration date (YYYY-MM-DD).
        min_strike: Minimum strike price.
        max_strike: Maximum strike price.
        limit: Max contracts (default 50, max 1000).
    """
    return await _data.get_alpaca_options_snapshot(
        ticker=ticker, option_type=option_type,
        expiration=expiration, min_strike=min_strike,
        max_strike=max_strike, limit=limit,
    )


@tool
async def get_stock_snapshot(ticker: str) -> dict:
    """Fetch full real-time stock snapshot from Alpaca.

    Returns latest trade (price, size, exchange), latest quote (bid/ask),
    minute bar, daily bar, and previous daily bar — the most comprehensive
    single-ticker real-time view.

    Args:
        ticker: Stock symbol (e.g. AAPL, TSLA).
    """
    return await _data.get_stock_snapshot(ticker)


@tool
async def get_multi_snapshots(tickers: list[str]) -> dict:
    """Fetch real-time snapshots for multiple stocks in one request.

    Returns price, bid/ask, volume, VWAP, change, and change percent
    for up to 200 tickers. Perfect for watchlist monitoring.

    Args:
        tickers: List of stock symbols (e.g. ['AAPL', 'TSLA', 'NVDA']).
    """
    return await _data.get_multi_snapshots(tickers)


@tool
async def get_alpaca_news(
    symbols: Optional[list[str]] = None,
    limit: int = 20,
) -> list[dict]:
    """Fetch market news from Alpaca with optional symbol filter.

    Returns headlines, summaries, sources, and related symbols.
    Complements Finnhub news with different coverage.

    Args:
        symbols: Optional list of symbols to filter (e.g. ['AAPL', 'TSLA']).
        limit: Max articles (up to 50).
    """
    return await _data.get_alpaca_news(symbols=symbols, limit=limit)


@tool
async def get_most_actives(by: str = "volume", top: int = 20) -> list[dict]:
    """Fetch most active stocks from Alpaca screener.

    Args:
        by: Rank by 'volume' or 'trades'.
        top: Number of top stocks (max 100).
    """
    return await _data.get_most_actives(by=by, top=top)


@tool
async def get_account_info() -> dict:
    """Fetch paper trading account info from Alpaca.

    Returns buying power, portfolio value, cash, equity, margins,
    day trade count, and account status.
    """
    return await _data.get_account()


@tool
async def get_open_positions() -> list[dict]:
    """Fetch all open positions from Alpaca paper trading account.

    Returns symbol, qty, side, market value, cost basis,
    unrealized P/L, current price, and avg entry price.
    """
    return await _data.get_positions()


# ──────────────────────────────────────────────
# Technical Analysis Tools
# ──────────────────────────────────────────────

@tool
def compute_technicals(ticker: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Compute all technical indicators for a stock.

    Returns RSI, MACD, SMA/EMA, Bollinger Bands, Stochastic, ATR, ADX, OBV,
    VWAP, support/resistance levels, and an overall buy/sell/hold signal.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for lookback (default 6mo for reliable signals).
        interval: Candle interval (default 1d).
    """
    data = _data.get_stock(ticker, period=period, interval=interval)
    indicators = _ta.compute_indicators(data.history, timeframe=interval, ticker=ticker)
    return indicators.model_dump(mode="json")


@tool
def detect_divergences(ticker: str, period: str = "3mo") -> list[dict]:
    """Detect RSI and MACD divergences for a stock.

    Bullish divergence: price makes lower low, RSI makes higher low.
    Bearish divergence: price makes higher high, RSI makes lower high.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _ta.detect_divergences(data.history)


# ──────────────────────────────────────────────
# Options Analysis Tools
# ──────────────────────────────────────────────

@tool
def analyze_gex(ticker: str) -> dict:
    """Calculate Gamma Exposure (GEX) for a stock's options.

    Shows whether options dealers are long or short gamma:
    - Long gamma = price dampening (suppresses breakouts)
    - Short gamma = price amplifying (amplifies breakouts)

    Also finds the GEX flip point where dealer positioning changes.

    Args:
        ticker: Stock ticker symbol.
    """
    chain = _data.get_options(ticker)
    return _options.compute_gex(chain)


@tool
def analyze_max_pain(ticker: str) -> dict:
    """Calculate the Max Pain strike for a stock.

    Max Pain is the price where option holders lose the most money.
    Market makers are incentivized to push price toward max pain near expiry.

    Args:
        ticker: Stock ticker symbol.
    """
    chain = _data.get_options(ticker)
    return _options.compute_max_pain(chain)


@tool
def analyze_put_call_ratio(ticker: str) -> dict:
    """Calculate put/call ratio by volume and open interest.

    High ratio (>1.5) = bearish sentiment.
    Low ratio (<0.5) = bullish sentiment.

    Args:
        ticker: Stock ticker symbol.
    """
    chain = _data.get_options(ticker)
    return _options.put_call_ratio(chain)


@tool
def detect_unusual_options(ticker: str, volume_threshold: float = 3.0) -> list[dict]:
    """Detect unusual options activity for a stock.

    Flags contracts where trading volume significantly exceeds open interest.
    Volume >3x OI = someone knows something.

    Args:
        ticker: Stock ticker symbol.
        volume_threshold: Volume/OI ratio threshold (default 3.0).
    """
    chain = _data.get_options(ticker)
    return _options.detect_unusual_activity(chain, volume_threshold=volume_threshold)


@tool
def evaluate_options_strategy(
    strategy_type: str,
    legs: list[dict],
    underlying_price: float,
) -> dict:
    """Evaluate an options strategy with P/L calculation.

    Args:
        strategy_type: Strategy name (e.g. "bull_call_spread", "iron_condor").
        legs: List of option legs with keys:
              type ("call"/"put"), strike (float), premium (float),
              action ("buy"/"sell"), contracts (int, default 1).
        underlying_price: Current stock price.
    """
    return _options.evaluate_strategy(strategy_type, legs, underlying_price)


# ──────────────────────────────────────────────
# Risk Management Tools
# ──────────────────────────────────────────────

@tool
def calculate_position_size(
    account_size: float,
    entry_price: float,
    stop_price: float,
    target_price: Optional[float] = None,
    risk_pct: float = 0.01,
    win_rate: Optional[float] = None,
) -> dict:
    """Calculate optimal position size using the 1% risk rule.

    Also computes Kelly Criterion, risk/reward ratio, and expected value.

    Args:
        account_size: Total account value in dollars.
        entry_price: Planned entry price.
        stop_price: Stop-loss price.
        target_price: Take-profit price (optional).
        risk_pct: Max risk per trade as decimal (default 0.01 = 1%).
        win_rate: Historical win rate as decimal (optional, for Kelly).
    """
    pos = _risk.compute_position_size(
        account_size, entry_price, stop_price,
        target_price=target_price, risk_pct=risk_pct, win_rate=win_rate,
    )
    return pos.model_dump(mode="json")


@tool
def calculate_trailing_stop(
    entry_price: float,
    current_price: float,
    atr: float,
    multiplier: float = 2.0,
) -> dict:
    """Calculate ATR-based trailing stop.

    ATR stops adapt to volatility — wider in volatile markets, tighter in calm ones.

    Args:
        entry_price: Original entry price.
        current_price: Current market price.
        atr: Current ATR (14-period).
        multiplier: ATR multiplier for stop distance (default 2.0).
    """
    return _risk.trailing_stop(entry_price, current_price, atr, multiplier)


@tool
def score_trade_quality(
    risk_reward: Optional[float] = None,
    win_rate: Optional[float] = None,
    relative_volume: Optional[float] = None,
    rsi: Optional[float] = None,
    adx: Optional[float] = None,
    multi_tf_alignment: Optional[float] = None,
) -> dict:
    """Score a trade setup on a 0-100 scale.

    80-100 = Strong Buy, 60-79 = Buy, 40-59 = Hold, 0-39 = Sell/Reduce.

    Args:
        risk_reward: Risk/reward ratio.
        win_rate: Historical win rate (0-1).
        relative_volume: Volume relative to 20-day avg (e.g. 2.0 = 2x average).
        rsi: Current RSI value.
        adx: Current ADX value (trend strength).
        multi_tf_alignment: Multi-timeframe alignment % (0-100).
    """
    return _risk.score_trade_quality(
        risk_reward=risk_reward,
        win_rate=win_rate,
        relative_volume=relative_volume,
        rsi=rsi,
        adx=adx,
        multi_tf_alignment=multi_tf_alignment,
    )


# ──────────────────────────────────────────────
# Breakout Detection Tools
# ──────────────────────────────────────────────

@tool
def scan_breakout_precursors(ticker: str, period: str = "3mo") -> dict:
    """Scan for breakout precursor signals in a stock.

    Checks 15 signals that typically precede breakouts:
    P1-P15 covering volume, volatility, momentum, options, and structure.

    Returns active precursors and a quality score (0-100).

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis (default 3mo).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
    precursors = _breakout.scan_precursors(data.history, indicators)
    signal = _breakout.score_breakout(precursors, indicators)
    return signal.model_dump(mode="json")


@tool
def check_failed_breakout(
    ticker: str,
    breakout_level: float,
    lookback: int = 5,
) -> dict:
    """Check if a breakout has failed.

    A failed breakout occurs when price breaches resistance but cannot hold.
    Failed breakouts are valuable signals for risk management.

    Args:
        ticker: Stock ticker symbol.
        breakout_level: The resistance level that was tested.
        lookback: Number of bars to check (default 5).
    """
    data = _data.get_stock(ticker, period="1mo", interval="1d")
    result = _breakout.detect_failed_breakout(data.history, breakout_level, lookback)
    return result or {"status": "no_failed_breakout_detected"}


@tool
def full_breakout_analysis(ticker: str, period: str = "6mo") -> dict:
    """Comprehensive breakout analysis — the crown jewel.

    Combines ALL 15 precursor signals, 5-stage lifecycle classification,
    0-100 quality scoring, options-based confirmation, institutional detection,
    failed breakout check, and historical win rate into a single unified assessment.

    Returns conviction score, component breakdown, and actionable recommendation.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis (6mo+ recommended).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)

    # Try to get options data for full analysis
    options_data = None
    try:
        from app.engines.options_engine import OptionsEngine
        opts = OptionsEngine()
        gex = opts.compute_gex(ticker)
        unusual = opts.detect_unusual_activity(ticker)
        options_data = {
            "gex": gex.model_dump(mode="json") if hasattr(gex, "model_dump") else gex,
            "unusual_activity": unusual if isinstance(unusual, list) else [],
        }
    except Exception:
        pass

    return _breakout.full_breakout_analysis(data.history, indicators, options_data)


@tool
def options_breakout_confirmation(ticker: str) -> dict:
    """Options-based breakout confirmation analysis.

    Cross-references GEX dealer positioning, unusual activity, put/call ratio,
    and OI concentration to confirm or deny a breakout setup.

    Returns confirmation score (0-100), verdict, and risk flags.

    Args:
        ticker: Stock ticker symbol.
    """
    data = _data.get_stock(ticker, period="3mo", interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
    precursors = _breakout.scan_precursors(data.history, indicators)

    try:
        from app.engines.options_engine import OptionsEngine
        opts = OptionsEngine()
        gex = opts.compute_gex(ticker)
        unusual = opts.detect_unusual_activity(ticker)
        options_data = {
            "gex": gex.model_dump(mode="json") if hasattr(gex, "model_dump") else gex,
            "unusual_activity": unusual if isinstance(unusual, list) else [],
        }
        return _breakout.options_confirmation(options_data, precursors, indicators)
    except Exception as e:
        return {"error": f"Options data unavailable: {e}", "confirmation_score": 0}


@tool
def detect_institutional_tells(ticker: str, period: str = "3mo") -> dict:
    """Detect institutional accumulation/distribution from price action and flow.

    Looks for smart money footprints: OBV divergence, volume anomalies,
    narrow-range absorption days, dark pool activity, and sweep orders.

    Returns institutional score (0-100), intent classification, and signals.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")

    options_data = None
    try:
        from app.engines.options_engine import OptionsEngine
        opts = OptionsEngine()
        options_data = {
            "dark_pool": {},
            "sweep_orders": opts.detect_unusual_activity(ticker) or [],
        }
    except Exception:
        pass

    return _breakout.detect_institutional_activity(data.history, options_data)


@tool
def backtest_breakout_signals(ticker: str, period: str = "2y") -> dict:
    """Backtest historical breakout signals for a ticker.

    Identifies all historical breakouts (price breaking above 20-bar high),
    evaluates forward performance, and calculates win rates.

    Also shows volume-confirmed breakout win rate vs. unconfirmed.

    Args:
        ticker: Stock ticker symbol.
        period: Backtest period — use 1y or 2y for meaningful sample sizes.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
    return _breakout.backtest_breakouts(data.history, indicators)


# ──────────────────────────────────────────────
# Phase 7: Advanced Options Analysis Tools
# ──────────────────────────────────────────────

@tool
def compute_pl_profile(
    legs: list[dict],
    underlying_price: float,
    price_range_pct: float = 0.20,
) -> dict:
    """Compute a multi-leg options P/L profile across a price range at expiration.

    Returns a P/L curve for charting plus breakevens, max profit, max loss.

    Args:
        legs: List of option legs. Each: {'type': 'call'/'put', 'strike': float,
              'premium': float, 'action': 'buy'/'sell', 'contracts': int}.
        underlying_price: Current stock price.
        price_range_pct: Price range as fraction of underlying (default 0.20 = ±20%).
    """
    return _options.compute_pl_profile(legs, underlying_price, price_range_pct)


@tool
def probability_of_profit(
    legs: list[dict],
    underlying_price: float,
    sigma: float,
    T: float,
    r: float = 0.05,
) -> dict:
    """Monte Carlo probability of profit for any multi-leg options strategy.

    Simulates 10,000 terminal stock prices and checks how often P/L > 0.
    Returns PoP%, expected/median P/L, worst/best case.

    Args:
        legs: Option legs (same format as compute_pl_profile).
        underlying_price: Current stock price.
        sigma: Implied volatility of underlying (e.g. 0.30 for 30%).
        T: Time to expiration in years (e.g. 0.08 for 30 days).
        r: Risk-free rate (default 0.05).
    """
    return _options.probability_of_profit(legs, underlying_price, sigma, T, r)


@tool
def analyze_oi_patterns(ticker: str, expiration: Optional[str] = None) -> dict:
    """Analyze open interest patterns to detect put/call walls and strike concentration.

    Put Wall = highest put OI strike (acts as support).
    Call Wall = highest call OI strike (acts as resistance).

    Args:
        ticker: Stock ticker symbol.
        expiration: Expiration date (YYYY-MM-DD). Omit for nearest.
    """
    chain = _data.get_options(ticker, expiration=expiration)
    return _options.analyze_oi_patterns(chain)


@tool
def compute_advanced_gex(ticker: str, expiration: Optional[str] = None) -> dict:
    """Enhanced Gamma Exposure with DEX (Delta Exposure) and VEX (Vanna Exposure).

    Returns per-strike GEX/DEX/VEX arrays for charting, plus flip points and bias.
    DEX shows directional dealer delta risk.
    VEX shows how dealer delta changes with implied volatility.

    Args:
        ticker: Stock ticker symbol.
        expiration: Expiration date (YYYY-MM-DD). Omit for nearest.
    """
    chain = _data.get_options(ticker, expiration=expiration)
    return _options.compute_gex_detailed(chain)


@tool
def price_american_option(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str = "put",
) -> dict:
    """Price an American option using Barone-Adesi-Whaley analytical approximation.

    Faster than binomial trees. Shows early exercise premium vs European price.

    Args:
        S: Current stock price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate (e.g. 0.05).
        sigma: Implied volatility (e.g. 0.30).
        option_type: 'call' or 'put' (default 'put' — American puts have early exercise value).
    """
    return _options.barone_adesi_whaley(S, K, T, r, sigma, option_type)


@tool
def monte_carlo_option_price(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str = "call", n_sims: int = 10_000,
) -> dict:
    """Price a European option via Monte Carlo simulation with confidence intervals.

    Useful for complex payoffs and for validating Black-Scholes prices.
    Returns price, standard error, and 95% confidence interval.

    Args:
        S: Current stock price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate.
        sigma: Implied volatility.
        option_type: 'call' or 'put'.
        n_sims: Number of simulations (default 10,000).
    """
    return _options.monte_carlo_price(S, K, T, r, sigma, option_type, n_sims)


# ──────────────────────────────────────────────
# Phase 8: Pattern Detection & Direct Data Analysis Tools
# ──────────────────────────────────────────────

@tool
def scan_chart_patterns(ticker: str, period: str = "3mo") -> dict:
    """Scan for all candlestick and chart patterns on a stock.

    Detects 40+ patterns: doji, hammer, engulfing, head & shoulders,
    double top/bottom, triangles, wedges, flags, cup & handle, and more.
    Returns a list of detected patterns with direction and confidence.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis (default 3mo).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.scan_all_patterns(data.history)


@tool
def get_pattern_confluence(ticker: str, period: str = "3mo") -> dict:
    """Cross-reference detected patterns with technical indicators.

    Returns a conviction score (0-100) combining pattern signals
    with RSI, MACD, volume, and trend alignment.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
    indicators_dict = indicators.model_dump(mode="json")
    return _patterns.pattern_confluence(data.history, indicators_dict)


@tool
def analyze_chart_image(ticker: str, period: str = "3mo") -> dict:
    """Comprehensive direct-data chart analysis (NO Vision AI).

    Combines ta_engine, pattern_engine, and breakout_engine outputs into
    a single structured analysis. Returns trend, patterns, key levels,
    bias, indicators, and trade ideas — all from mathematical computation
    on raw OHLCV data. Faster, cheaper, and more accurate than Vision.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis (default 3mo).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
    indicators_dict = indicators.model_dump(mode="json")
    patterns = _patterns.full_scan(data.history)
    confluence = _patterns.pattern_confluence(data.history, indicators_dict)

    # Breakout analysis
    precursors = _breakout.scan_precursors(data.history, indicators)
    breakout_signal = _breakout.score_breakout(precursors, indicators)

    # Determine trend from indicators
    rsi = indicators_dict.get("rsi", 50)
    macd_hist = indicators_dict.get("macd_histogram", 0)
    sma_20 = indicators_dict.get("sma_20", 0)
    sma_50 = indicators_dict.get("sma_50", 0)
    current_price = data.history[-1]["close"] if data.history else 0

    bullish_signals = sum([
        rsi > 50 if rsi else False,
        (macd_hist or 0) > 0,
        current_price > (sma_20 or 0),
        current_price > (sma_50 or 0),
    ])
    if bullish_signals >= 3:
        trend, bias = "bullish", "bullish"
    elif bullish_signals <= 1:
        trend, bias = "bearish", "bearish"
    else:
        trend, bias = "neutral", "neutral"

    return {
        "ticker": ticker,
        "period": period,
        "method": "direct_data",
        "trend": trend,
        "trend_strength": "strong" if bullish_signals in (0, 4) else "moderate",
        "bias": bias,
        "confidence": confluence.get("conviction_score", 50),
        "indicators": indicators_dict,
        "patterns_detected": patterns.get("candlestick_patterns", []) + patterns.get("chart_patterns", []),
        "emerging_patterns": patterns.get("emerging_patterns", []),
        "key_levels": {
            "support": indicators_dict.get("support_levels", []),
            "resistance": indicators_dict.get("resistance_levels", []),
        },
        "breakout_signal": breakout_signal.model_dump(mode="json") if hasattr(breakout_signal, "model_dump") else breakout_signal,
        "pattern_count": patterns.get("pattern_count", 0),
        "overall_bias": patterns.get("overall_bias", "neutral"),
        "summary": f"{ticker} is {trend} with {patterns.get('pattern_count', 0)} patterns detected. "
                   f"RSI: {rsi}, MACD Histogram: {macd_hist}. "
                   f"Breakout score: {breakout_signal.model_dump(mode='json').get('quality_score', 'N/A') if hasattr(breakout_signal, 'model_dump') else 'N/A'}.",
    }


@tool
def narrate_chart(ticker: str, period: str = "1mo") -> dict:
    """Generate a candle-by-candle narration of recent price action (direct data).

    Fetches the last 10 OHLCV bars and sends them as structured text to
    Gemini Language AI for narrative description. No chart rendering or
    Vision AI needed — uses raw numbers for a precise narration.

    Args:
        ticker: Stock ticker symbol.
        period: Data period (default 1mo for recent candle visibility).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    bars = data.history[-10:] if len(data.history) >= 10 else data.history

    # Format OHLCV data as structured text for Language AI
    bar_descriptions = []
    for i, bar in enumerate(bars):
        o, h, l, c = bar.get("open", 0), bar.get("high", 0), bar.get("low", 0), bar.get("close", 0)
        vol = bar.get("volume", 0)
        bar_type = "bullish" if c > o else "bearish" if c < o else "doji"
        body_pct = abs(c - o) / o * 100 if o else 0
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        bar_descriptions.append({
            "bar_number": i + 1,
            "date": bar.get("timestamp", bar.get("date", f"bar_{i+1}")),
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(c, 2),
            "volume": vol,
            "type": bar_type,
            "body_size_pct": round(body_pct, 2),
            "upper_shadow": round(upper_shadow, 2),
            "lower_shadow": round(lower_shadow, 2),
            "change_pct": round((c - o) / o * 100, 2) if o else 0,
        })

    # Use Gemini Language AI (text, NOT vision) for narration
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.config import get_settings
        import json

        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.3,
            max_output_tokens=2048,
        )
        prompt = f"""Narrate the recent price action for {ticker} based on this OHLCV data.
Describe each candle's significance, body/shadow analysis, and the overall story.

Return as JSON:
{{
  "ticker": "{ticker}",
  "candle_count_narrated": {len(bar_descriptions)},
  "narration": [{{"bar_number": 1, "type": "bullish/bearish/doji", "body": "large/medium/small", "shadows": "description", "significance": "what it means"}}],
  "overall_story": "2-3 sentence narrative of the price action arc",
  "key_moment": "the most significant candle and why"
}}

OHLCV Data:
{json.dumps(bar_descriptions, indent=2, default=str)}"""

        response = llm.invoke([
            SystemMessage(content="You are an expert technical analyst. Narrate price action from OHLCV data."),
            HumanMessage(content=prompt),
        ])
        return VisionEngine._parse_json(response.content)
    except Exception as e:
        # Fallback: return raw bar data with basic narration
        return {
            "ticker": ticker,
            "candle_count_narrated": len(bar_descriptions),
            "bars": bar_descriptions,
            "overall_story": f"{ticker}: {len(bar_descriptions)} bars analyzed from OHLCV data.",
            "method": "direct_data_fallback",
            "error": str(e)[:200],
        }


@tool
def chart_health_check(ticker: str, period: str = "3mo") -> dict:
    """Comprehensive chart health report using arithmetic scoring on direct data.

    Computes a 0-100 health score from ta_engine indicators:
    trend (SMA alignment), momentum (RSI + MACD), volume (relative strength),
    volatility (BB width), and risk (ATR-based). No Vision AI needed.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
    ind = indicators.model_dump(mode="json")

    # ── Trend Score (0-100): SMA alignment + price position ──
    current_price = data.history[-1]["close"] if data.history else 0
    sma_20 = ind.get("sma_20") or 0
    sma_50 = ind.get("sma_50") or 0
    sma_200 = ind.get("sma_200") or 0
    trend_score = 0
    if current_price > sma_20: trend_score += 25
    if current_price > sma_50: trend_score += 25
    if current_price > sma_200: trend_score += 25
    if sma_20 > sma_50: trend_score += 25  # Golden alignment

    # ── Momentum Score (0-100): RSI + MACD histogram ──
    rsi = ind.get("rsi") or 50
    macd_hist = ind.get("macd_histogram") or 0
    # RSI: 50 = neutral, >70 = overbought but strong, <30 = oversold
    if 40 <= rsi <= 60:
        rsi_score = 50  # Neutral
    elif rsi > 60:
        rsi_score = min(100, 50 + (rsi - 60) * 1.25)  # Momentum strong
    else:
        rsi_score = max(0, 50 - (40 - rsi) * 1.25)  # Weakness
    macd_score = 100 if macd_hist > 0 else max(0, 50 + macd_hist * 10)
    momentum_score = int((rsi_score + macd_score) / 2)

    # ── Volume Score (0-100): relative volume ──
    volumes = [bar.get("volume", 0) for bar in data.history[-20:]]
    avg_vol = sum(volumes) / max(len(volumes), 1)
    current_vol = volumes[-1] if volumes else 0
    rel_vol = current_vol / max(avg_vol, 1)
    volume_score = min(100, int(rel_vol * 50))  # 2x avg = 100

    # ── Volatility Score (0-100): BB width normalized ──
    bb_upper = ind.get("bb_upper") or current_price
    bb_lower = ind.get("bb_lower") or current_price
    bb_width = (bb_upper - bb_lower) / max(current_price, 1) * 100
    # Normal range 3-8%, narrow = coiling, wide = volatile
    if bb_width < 3:
        volatility_score = 80  # Coiled, potential breakout
    elif bb_width < 6:
        volatility_score = 60  # Normal
    elif bb_width < 10:
        volatility_score = 40  # Elevated
    else:
        volatility_score = 20  # High volatility

    # ── Risk Score (0-100, 100 = low risk) ──
    atr = ind.get("atr") or 0
    atr_pct = (atr / max(current_price, 1)) * 100
    if atr_pct < 1.5:
        risk_score = 90  # Low risk
    elif atr_pct < 3:
        risk_score = 70  # Moderate
    elif atr_pct < 5:
        risk_score = 40  # Elevated
    else:
        risk_score = 20  # High risk

    # ── Overall ──
    overall = int((trend_score + momentum_score + volume_score + volatility_score + risk_score) / 5)
    grades = {90: "A+", 80: "A", 70: "B", 60: "C", 50: "D"}
    grade = "F"
    for threshold, g in sorted(grades.items(), reverse=True):
        if overall >= threshold:
            grade = g
            break

    # Recommendation
    if overall >= 75 and trend_score >= 75:
        recommendation = "buy"
    elif overall <= 35:
        recommendation = "sell"
    elif overall >= 50:
        recommendation = "hold"
    else:
        recommendation = "watch"

    key_risks = []
    key_opportunities = []
    if rsi > 70: key_risks.append("RSI overbought — potential pullback")
    if rsi < 30: key_opportunities.append("RSI oversold — potential bounce")
    if bb_width < 3: key_opportunities.append("Bollinger squeeze — breakout imminent")
    if atr_pct > 5: key_risks.append("High ATR — elevated volatility")
    if current_price < sma_200: key_risks.append("Below 200 SMA — long-term downtrend")
    if sma_20 > sma_50 and current_price > sma_20: key_opportunities.append("Golden SMA alignment — strong uptrend")

    return {
        "ticker": ticker,
        "method": "direct_data_arithmetic",
        "overall_health": overall,
        "grade": grade,
        "scores": {
            "trend": trend_score,
            "momentum": momentum_score,
            "volume": volume_score,
            "volatility": volatility_score,
            "risk": risk_score,
        },
        "trend_description": f"{'Bullish' if trend_score >= 75 else 'Bearish' if trend_score <= 25 else 'Neutral'} — "
                             f"price {'above' if current_price > sma_50 else 'below'} 50 SMA",
        "key_risks": key_risks or ["No significant risks detected"],
        "key_opportunities": key_opportunities or ["No immediate opportunities"],
        "recommendation": recommendation,
        "time_horizon": "swing",
        "summary": f"{ticker} health score: {overall}/100 ({grade}). "
                   f"Trend: {trend_score}, Momentum: {momentum_score}, Volume: {volume_score}. "
                   f"Recommendation: {recommendation}.",
    }


@tool
def full_scan_patterns(ticker: str, period: str = "3mo") -> dict:
    """Deep-dive pattern scan with everything: candlestick, chart, gaps, volume,
    trend lines, Fibonacci levels, and emerging patterns.

    More comprehensive than scan_chart_patterns. Use when user wants
    a complete technical pattern analysis.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis (default 3mo).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.full_scan(data.history)


@tool
def get_fibonacci_levels(ticker: str, period: str = "6mo") -> dict:
    """Calculate Fibonacci retracement and extension levels.

    Finds the significant swing high/low and computes all Fib levels
    (23.6%, 38.2%, 50%, 61.8%, 78.6%) plus extensions. Shows which
    zone the current price sits in and highlights the golden pocket.

    Args:
        ticker: Stock ticker symbol.
        period: Data period — use 6mo+ for meaningful swing detection.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.detect_fibonacci_levels(data.history)


@tool
def identify_patterns_vision(ticker: str, period: str = "3mo") -> dict:
    """Pattern identification using direct mathematical detection (NOT Vision AI).

    Uses pattern_engine to detect 40+ candlestick and chart patterns from raw
    OHLCV data. Returns patterns with forming/confirmed/completing stage,
    confidence scores, and emerging pattern progress percentages.

    This is a direct-data replacement — deterministic and free.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    scan = _patterns.full_scan(data.history)

    # Restructure to match the original vision output format
    all_patterns = []
    for p in scan.get("candlestick_patterns", []):
        if isinstance(p, dict):
            all_patterns.append({
                "name": p.get("name", "unknown"),
                "type": "candlestick",
                "direction": p.get("direction", "neutral"),
                "confidence": p.get("confidence", 0.5),
                "stage": "confirmed",
                "price_level": p.get("price_level"),
                "description": p.get("description", ""),
            })
    for p in scan.get("chart_patterns", []):
        if isinstance(p, dict):
            all_patterns.append({
                "name": p.get("name", "unknown"),
                "type": "chart_structure",
                "direction": p.get("direction", "neutral"),
                "confidence": p.get("confidence", 0.5),
                "stage": "confirmed",
                "price_level": p.get("target"),
                "description": p.get("description", ""),
            })
    for p in scan.get("emerging_patterns", []):
        if isinstance(p, dict):
            all_patterns.append({
                "name": f"{p.get('name', 'unknown')} (Forming)",
                "type": "chart_structure",
                "direction": p.get("direction", "neutral"),
                "confidence": p.get("confidence", 0.3),
                "stage": "forming",
                "price_level": p.get("watch_level"),
                "progress_pct": p.get("progress_pct", 0),
                "description": p.get("description", ""),
            })

    # Determine dominant direction
    bullish = sum(1 for p in all_patterns if p["direction"] == "bullish")
    bearish = sum(1 for p in all_patterns if p["direction"] == "bearish")
    dominant = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"

    return {
        "ticker": ticker,
        "method": "direct_data_pattern_engine",
        "patterns": all_patterns,
        "pattern_count": len(all_patterns),
        "dominant_direction": dominant,
        "actionable_patterns": [
            p["name"] for p in all_patterns
            if p.get("confidence", 0) >= 0.7 and p["stage"] == "confirmed"
        ],
    }


@tool
def compare_charts_vision(tickers: list[str], period: str = "3mo") -> dict:
    """Compare multiple stocks using direct data correlation (NOT Vision AI).

    Fetches close price arrays for up to 4 tickers and computes:
    - numpy.corrcoef correlation matrix
    - Relative strength ranking (total returns)
    - Divergence detection (correlation breakdown in recent window)
    - Lead/lag analysis via cross-correlation

    Args:
        tickers: List of ticker symbols to compare (max 4).
        period: Data period for comparison.
    """
    import numpy as np

    tickers = tickers[:4]
    price_data = {}
    returns_data = {}

    for t in tickers:
        try:
            data = _data.get_stock(t, period=period, interval="1d")
            closes = [bar["close"] for bar in data.history if bar.get("close")]
            if len(closes) >= 10:
                price_data[t] = closes
                # Calculate total return
                returns_data[t] = (closes[-1] - closes[0]) / closes[0] * 100
        except Exception:
            continue

    if len(price_data) < 2:
        return {"error": "Need at least 2 tickers with sufficient data for comparison."}

    # Align lengths (trim to shortest)
    min_len = min(len(v) for v in price_data.values())
    aligned = {t: v[-min_len:] for t, v in price_data.items()}
    ticker_list = list(aligned.keys())
    matrix = np.array([aligned[t] for t in ticker_list])

    # Correlation matrix
    corr_matrix = np.corrcoef(matrix).tolist()

    # Average pairwise correlation
    corr_values = []
    for i in range(len(ticker_list)):
        for j in range(i + 1, len(ticker_list)):
            corr_values.append(corr_matrix[i][j])
    avg_corr = sum(corr_values) / max(len(corr_values), 1)

    if avg_corr > 0.8:
        corr_label = "high"
    elif avg_corr > 0.5:
        corr_label = "moderate"
    elif avg_corr > -0.3:
        corr_label = "low"
    else:
        corr_label = "inverse"

    # Relative strength ranking
    ranked = sorted(returns_data.items(), key=lambda x: x[1], reverse=True)
    ranking = [t for t, _ in ranked]

    # Recent divergence check (last 20 bars vs full period)
    divergences = []
    if min_len >= 40:
        for i in range(len(ticker_list)):
            for j in range(i + 1, len(ticker_list)):
                full_corr = corr_matrix[i][j]
                recent = np.corrcoef(
                    matrix[i, -20:], matrix[j, -20:]
                )[0][1]
                if abs(full_corr - recent) > 0.3:
                    divergences.append(
                        f"{ticker_list[i]} vs {ticker_list[j]}: "
                        f"full-period correlation {full_corr:.2f} vs "
                        f"recent 20-bar correlation {recent:.2f} — DIVERGING"
                    )

    return {
        "method": "direct_data_numpy_correlation",
        "charts_compared": len(ticker_list),
        "tickers": ticker_list,
        "correlation": corr_label,
        "correlation_matrix": {
            f"{ticker_list[i]}_vs_{ticker_list[j]}": round(corr_matrix[i][j], 4)
            for i in range(len(ticker_list))
            for j in range(i + 1, len(ticker_list))
        },
        "avg_pairwise_correlation": round(avg_corr, 4),
        "relative_strength_ranking": ranking,
        "returns_pct": {t: round(r, 2) for t, r in returns_data.items()},
        "divergences": divergences or ["No significant divergences detected"],
        "leader": ranking[0] if ranking else "unknown",
        "summary": f"Compared {len(ticker_list)} tickers: {corr_label} correlation ({avg_corr:.2f}). "
                   f"Strongest: {ranking[0]} ({returns_data.get(ranking[0], 0):.1f}%), "
                   f"Weakest: {ranking[-1]} ({returns_data.get(ranking[-1], 0):.1f}%).",
    }


@tool
def trigger_pattern_scan(ticker: str, period: str = "3mo") -> dict:
    """Real-time pattern alert scan for a ticker.

    Scans for ALL patterns (candlestick + chart + gaps + volume + trend lines),
    compares with previous scan results (cached in Redis), and returns any
    NEW patterns detected since the last scan.

    Useful for monitoring a stock for emerging pattern setups.

    Args:
        ticker: Stock ticker symbol to scan.
        period: Data period for analysis.
    """
    import json as _json
    data = _data.get_stock(ticker, period=period, interval="1d")
    current = _patterns.full_scan(data.history)

    # Check Redis for previous scan
    prev_patterns = set()
    try:
        import redis as _redis
        from app.config import get_settings
        r = _redis.from_url(get_settings().redis_url, decode_responses=True)
        prev_raw = r.get(f"Bubby Vision:pattern_scan:{ticker}")
        if prev_raw:
            prev = _json.loads(prev_raw)
            for p in prev.get("candlestick_patterns", []) + prev.get("chart_patterns", []):
                if isinstance(p, dict):
                    prev_patterns.add(p.get("name", ""))
        # Update cache
        r.setex(f"Bubby Vision:pattern_scan:{ticker}", 600, _json.dumps(current, default=str))
    except Exception:
        pass

    # Find new patterns
    new_patterns = []
    all_p = current.get("candlestick_patterns", []) + current.get("chart_patterns", []) + \
            current.get("gap_patterns", []) + current.get("volume_patterns", []) + \
            current.get("trend_line_patterns", [])
    for p in all_p:
        if isinstance(p, dict) and p.get("name", "") not in prev_patterns:
            new_patterns.append(p)

    current["new_patterns"] = new_patterns
    current["new_pattern_count"] = len(new_patterns)
    return current


@tool
def check_pattern_outcomes(ticker: str, period: str = "6mo", lookforward: int = 20) -> dict:
    """Check outcomes of previously detected patterns.

    Evaluates whether active patterns have succeeded (hit target),
    failed (hit stop), expired, or are still active. Also returns
    pattern failure alerts.

    Args:
        ticker: Stock ticker symbol.
        period: Data period — needs enough forward data for evaluation.
        lookforward: Number of bars after detection to evaluate (default 20).
    """
    import json as _json
    data = _data.get_stock(ticker, period=period, interval="1d")

    # Get stored pattern log from Redis
    pattern_log = []
    try:
        import redis as _redis
        from app.config import get_settings
        r = _redis.from_url(get_settings().redis_url, decode_responses=True)
        log_raw = r.get(f"Bubby Vision:pattern_log:{ticker}")
        if log_raw:
            pattern_log = _json.loads(log_raw)
    except Exception:
        pass

    if not pattern_log:
        # If no stored log, scan current data and generate a log
        scan = _patterns.scan_all_patterns(data.history)
        pattern_log = [
            p for p in scan.get("candlestick_patterns", []) + scan.get("chart_patterns", [])
            if isinstance(p, dict) and (p.get("target") or p.get("stop_loss"))
        ]

    evaluated = _patterns.evaluate_pattern_outcomes(data.history, pattern_log, lookforward)

    # Categorize
    successes = [p for p in evaluated if p.get("outcome") == "success"]
    failures = [p for p in evaluated if p.get("outcome") == "failed"]
    active = [p for p in evaluated if p.get("outcome") == "active"]
    expired = [p for p in evaluated if p.get("outcome") == "expired"]

    return {
        "ticker": ticker,
        "total_evaluated": len(evaluated),
        "successes": len(successes),
        "failures": len(failures),
        "active": len(active),
        "expired": len(expired),
        "success_rate_pct": round(len(successes) / max(len(successes) + len(failures), 1) * 100, 1),
        "patterns": evaluated,
        "failure_alerts": failures,
    }


@tool
def backtest_chart_patterns(ticker: str, period: str = "2y") -> dict:
    """Historical backtest of chart patterns to measure reliability.

    Slides a detection window across the full dataset, detects all patterns
    at each position, then evaluates outcomes (target hit, stop hit, or expired).

    Returns per-pattern statistics: occurrences, win rate, avg return,
    risk/reward ratio, and a reliability score.

    Args:
        ticker: Stock ticker symbol.
        period: Backtest period — use 1y or 2y for meaningful sample sizes.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.backtest_patterns(data.history)


@tool
def get_trade_targets(ticker: str, entry: float, stop: float, period: str = "6mo") -> dict:
    """Compute multi-target take profit levels (TP1/TP2/TP3) for a trade.

    Uses Fibonacci extensions + R:R ratios for systematic profit-taking:
    - TP1 (conservative): 1:1 R:R — lock 40% of position
    - TP2 (standard): 2:1 R:R / Fib 1.618 — take 35%
    - TP3 (aggressive): 3:1 R:R / Fib 2.618 — let 25% run

    Returns targets with probability estimates based on ATR-calibrated move sizes.

    Args:
        ticker: Stock ticker symbol.
        entry: Planned entry price.
        stop: Stop loss price.
        period: Data period — 6mo recommended for ATR calibration.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")

    # Get Fibonacci levels for enhancement
    fib_levels = None
    try:
        fib_result = _patterns.detect_fibonacci_levels(data.history)
        if isinstance(fib_result, dict) and not fib_result.get("error"):
            fib_levels = fib_result
    except Exception:
        pass

    return _breakout.compute_multi_targets(
        entry=entry, stop=stop, bars=data.history, fib_levels=fib_levels,
    )


@tool
def get_anchored_vwap(ticker: str, anchor_date: Optional[str] = None, period: str = "6mo") -> dict:
    """Compute Anchored VWAP from a specific date forward.

    VWAP = cumulative(typical_price × volume) / cumulative(volume).
    Includes ±1σ and ±2σ standard-deviation bands and current price
    position relative to bands.

    Args:
        ticker: Stock ticker symbol.
        anchor_date: Date to anchor from (YYYY-MM-DD). If None, anchors from start of period.
        period: Data period to fetch.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")

    # Resolve anchor index from date
    anchor_index = 0
    if anchor_date and data.history:
        for i, bar in enumerate(data.history):
            bar_date = str(bar.timestamp)[:10] if hasattr(bar, "timestamp") else ""
            if bar_date >= anchor_date:
                anchor_index = i
                break

    return _ta.compute_anchored_vwap(data.history, anchor_index=anchor_index)


@tool
def get_market_structure(ticker: str, period: str = "3mo", lookback: int = 5) -> dict:
    """Classify market structure as Uptrend, Downtrend, or Range.

    Uses swing high/low analysis:
    - Uptrend: Higher Highs + Higher Lows
    - Downtrend: Lower Highs + Lower Lows
    - Range: No clear directional sequence

    Returns structure label, key swing levels, break-of-structure
    (BOS) invalidation price, and directional scores.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
        lookback: N-bar lookback for swing detection (default 5).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.detect_market_structure(data.history, lookback=lookback)


@tool
def get_sentiment_synthesis(ticker: str, period: str = "3mo") -> dict:
    """Synthesize all signal sources into ONE unified verdict.

    Combines:
    - Technical indicators (RSI, MACD, trend, volume)
    - Pattern detection (candlestick + chart patterns)
    - News sentiment (Finnhub + Fear & Greed + Reddit)
    - Market structure (uptrend/downtrend/range)

    Resolves conflicts between signals using weighted rules and returns
    a single STRONG_BULLISH → STRONG_BEARISH rating with confidence.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    import json

    data = _data.get_stock(ticker, period=period, interval="1d")
    bars = data.history

    # 1. Technical indicators
    indicators = _ta.compute_indicators(bars, timeframe="1d", ticker=ticker)
    ind = indicators.model_dump(mode="json")

    # 2. Pattern scan
    patterns = _patterns.scan_all_patterns(bars)
    confluence = _patterns.pattern_confluence(bars, ind)

    # 3. Market structure
    structure = _patterns.detect_market_structure(bars)

    # 4. News sentiment (best-effort)
    news_data = {}
    try:
        from app.services.data_engine import DataEngine
        _de = DataEngine()
        fg = _de.get_fear_greed()
        news_data["fear_greed"] = fg
    except Exception:
        news_data["fear_greed"] = {"value": 50, "label": "Neutral"}

    try:
        from app.services.data_engine import DataEngine
        _de = DataEngine()
        news = _de.get_company_news(ticker, days=3)
        if news:
            bull_count = sum(1 for n in news[:20] if any(
                w in (n.get("headline", "") + n.get("summary", "")).lower()
                for w in ["upgrade", "beat", "surge", "rally", "buy", "bullish"]
            ))
            bear_count = sum(1 for n in news[:20] if any(
                w in (n.get("headline", "") + n.get("summary", "")).lower()
                for w in ["downgrade", "miss", "crash", "sell", "bearish", "cut"]
            ))
            news_data["news_sentiment"] = {
                "articles_scanned": min(len(news), 20),
                "bullish_mentions": bull_count,
                "bearish_mentions": bear_count,
                "bias": "bullish" if bull_count > bear_count else "bearish" if bear_count > bull_count else "neutral",
            }
    except Exception:
        news_data["news_sentiment"] = {"bias": "neutral"}

    # Build bundle for LLM
    bundle = {
        "technical": {
            "rsi": ind.get("rsi"),
            "macd_histogram": ind.get("macd_histogram"),
            "overall_signal": ind.get("overall_signal"),
            "trend_direction": ind.get("trend_direction"),
            "volume_trend": ind.get("volume_trend"),
            "adx": ind.get("adx"),
        },
        "patterns": {
            "pattern_count": patterns.get("pattern_count", 0) if isinstance(patterns, dict) else getattr(patterns, "pattern_count", 0),
            "overall_bias": patterns.get("overall_bias", "neutral") if isinstance(patterns, dict) else getattr(patterns, "overall_bias", "neutral"),
            "bullish_count": patterns.get("bullish_count", 0) if isinstance(patterns, dict) else getattr(patterns, "bullish_count", 0),
            "bearish_count": patterns.get("bearish_count", 0) if isinstance(patterns, dict) else getattr(patterns, "bearish_count", 0),
        },
        "confluence_score": confluence.get("conviction_score", 50) if isinstance(confluence, dict) else 50,
        "news": news_data,
        "market_structure": structure,
    }

    # Invoke Gemini 3 Flash for synthesis
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.config import get_settings
        from app.agents.prompts import SENTIMENT_SYNTHESIS_PROMPT
        from app.engines.vision_engine import VisionEngine

        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.2,
            max_output_tokens=2048,
        )

        system_prompt = SENTIMENT_SYNTHESIS_PROMPT.format(ticker=ticker)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Synthesize this data for {ticker}:\n{json.dumps(bundle, indent=2, default=str)}"),
        ])
        result = VisionEngine._parse_json(response.content)
        result["method"] = "gemini_synthesis"
        result["raw_bundle"] = bundle
        return result
    except Exception as e:
        # Arithmetic fallback — no LLM needed
        tech_signal = ind.get("overall_signal", "NEUTRAL")
        pattern_bias = patterns.get("overall_bias", "neutral") if isinstance(patterns, dict) else "neutral"
        struct = structure.get("structure", "range") if isinstance(structure, dict) else "range"

        signals = [tech_signal.lower(), pattern_bias, struct if struct != "range" else "neutral"]
        bull = sum(1 for s in signals if s in ("bullish", "uptrend", "buy"))
        bear = sum(1 for s in signals if s in ("bearish", "downtrend", "sell"))

        if bull >= 2:
            unified = "BULLISH" if bull < 3 else "STRONG_BULLISH"
        elif bear >= 2:
            unified = "BEARISH" if bear < 3 else "STRONG_BEARISH"
        else:
            unified = "NEUTRAL"

        return {
            "ticker": ticker,
            "unified_signal": unified,
            "confidence": round(max(bull, bear) / 3, 2),
            "method": "arithmetic_fallback",
            "raw_bundle": bundle,
            "error": str(e)[:200],
        }


@tool
def detect_pre_candle_formations(ticker: str, period: str = "3mo") -> list[dict]:
    """Detect candlestick patterns that are exactly 1 bar from confirmation.

    These are 'setup' candles where the pattern is partially formed and a
    specific candle type on the NEXT bar would confirm it. Returns what
    pattern would form, what the setup condition is, what confirmation
    looks like, and estimated probability.

    Covers: Pre-Morning Star, Pre-Evening Star, Pre-Three White Soldiers,
    Pre-Three Black Crows, Pre-Bullish/Bearish Engulfing, Pre-Three Inside
    Up/Down, Pre-Abandoned Baby, Pre-Piercing Pattern, Pre-Dark Cloud Cover,
    Pre-Hammer Zone, Pre-Shooting Star Zone.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.detect_pre_candle_formations(data.history)


@tool
def detect_emerging_patterns(ticker: str, period: str = "3mo") -> list[dict]:
    """Detect 16+ pattern types that are currently forming but not yet confirmed.

    Returns forming versions of: Head & Shoulders, Inverse H&S, Double Top/Bottom,
    Symmetrical/Ascending/Descending Triangle, Rising/Falling Wedge, Bull/Bear Flag,
    Rectangle, Channel (Ascending/Descending/Horizontal), Broadening Formation,
    Rounded Bottom, Cup & Handle (cup phase + handle phase), Triple Top/Bottom.

    Each pattern includes: formation progress percentage, expected watch level for
    completion, invalidation price, and human-readable description.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis (needs enough bars for structure).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.detect_emerging_patterns(data.history)


@tool
def multi_timeframe_patterns(ticker: str, timeframes: str = "15m,1h,4h,1d") -> dict:
    """Cross-reference patterns across multiple timeframes.

    Runs full pattern detection on each timeframe, then identifies:
    - Pattern confluence: same pattern type at multiple timeframes
    - Bias alignment: whether all timeframes agree on direction
    - Fractal patterns: same structure at different scales
    - Dominant signal: the strongest cross-timeframe signal
    - Emerging pattern reinforcement across timeframes
    - Pre-candle formations at each timeframe

    Returns alignment_score (0-100), confluent_patterns, fractal_patterns,
    dominant_bias, and per-timeframe breakdowns.

    Args:
        ticker: Stock ticker symbol.
        timeframes: Comma-separated timeframe list (e.g. "5m,15m,1h,4h,1d,1W").
    """
    tf_list = [t.strip() for t in timeframes.split(",") if t.strip()]

    # Map timeframe strings to Finnhub/Alpaca intervals and required periods
    tf_configs = {
        "1m": ("1m", "5d"), "5m": ("5m", "1mo"),
        "15m": ("15m", "1mo"), "30m": ("30m", "3mo"),
        "1h": ("1h", "3mo"), "4h": ("4h", "6mo"),
        "1d": ("1d", "1y"), "1W": ("1wk", "2y"), "1M": ("1mo", "5y"),
    }

    bars_by_tf: dict[str, list] = {}
    for tf in tf_list:
        if tf in tf_configs:
            interval, period = tf_configs[tf]
            try:
                data = _data.get_stock(ticker, period=period, interval=interval)
                if data.history and len(data.history) >= 10:
                    bars_by_tf[tf] = data.history
            except Exception:
                continue

    return _patterns.multi_timeframe_scan(bars_by_tf)


@tool
def age_detected_patterns(ticker: str, period: str = "3mo") -> dict:
    """Apply confidence decay and freshness scoring to all detected patterns.

    Runs a full scan, then applies time-based aging to each pattern:
    - Fresh patterns get full confidence
    - Older patterns lose confidence (decay rate varies by pattern type)
    - Invalidated patterns are flagged (price broke invalidation level)
    - Confirmed patterns get boosted confidence

    Returns aged pattern list sorted by status (confirmed > fresh > active >
    aging > stale > invalidated) with staleness scores and half-life data.

    Also returns an aging_summary with counts per status category.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    scan = _patterns.full_scan(data.history)

    result = {
        "aged_patterns": scan.get("aged_patterns", []),
        "aging_summary": scan.get("aging_summary", {}),
        "total_patterns": scan.get("pattern_count", 0),
        "overall_bias": scan.get("overall_bias", "neutral"),
    }
    return result


# ── Phase 3: Growth Features ──

@tool
def get_volume_profile(ticker: str, period: str = "6mo", num_bins: int = 50) -> dict:
    """Compute volume profile — price-at-volume histogram.

    Identifies Point of Control (POC, highest volume price), Value Area
    (70% volume range), and high/low volume nodes (support/resistance magnets).

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
        num_bins: Number of price level buckets.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _ta.compute_volume_profile(data.history, num_bins=num_bins)


@tool
def get_consolidation_zones(ticker: str, period: str = "6mo", atr_multiplier: float = 0.5, min_bars: int = 8) -> dict:
    """Detect consolidation zones — tight price ranges.

    Finds periods where price stays within ATR × multiplier for min_bars+.
    Active consolidation zones often precede breakouts.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
        atr_multiplier: Range threshold as ATR fraction.
        min_bars: Minimum bars to qualify.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _ta.detect_consolidation_zones(data.history, atr_multiplier=atr_multiplier, min_bars=min_bars)


@tool
def get_liquidity_zones(ticker: str, period: str = "6mo") -> dict:
    """Detect liquidity zones — high-volume price levels.

    These are price levels where significant volume has traded, acting
    as magnets for future price action (support/resistance).

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _ta.detect_liquidity_zones(data.history)


@tool
def get_anchored_vwap(ticker: str, period: str = "6mo", anchor_index: int = 0) -> dict:
    """Compute Anchored VWAP with ±1σ / ±2σ bands from a specific bar.

    VWAP = Σ(typical_price × volume) / Σ(volume). Deviation bands highlight
    overbought/oversold relative to volume-weighted average.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
        anchor_index: Bar index to anchor VWAP from (0 = start of data).
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _ta.compute_anchored_vwap(data.history, anchor_index=anchor_index)


@tool
def get_market_structure(ticker: str, period: str = "6mo") -> dict:
    """Detect market structure: trend direction, swing highs/lows, BOS/CHoCH.

    Classifies current market regime (uptrend, downtrend, range) based on
    higher-highs/higher-lows or lower-highs/lower-lows relationships.

    Args:
        ticker: Stock ticker symbol.
        period: Data period for analysis.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _patterns.detect_market_structure(data.history)


@tool
def get_sentiment_synthesis(ticker: str) -> dict:
    """Synthesize sentiment from all available sources into a unified signal.

    Combines technical indicators, Finnhub news sentiment, Reddit/WSB social
    sentiment, Fear & Greed market sentiment, and StockTwits data. Detects
    inter-source conflicts and produces weighted overall direction.

    Args:
        ticker: Stock ticker symbol.
    """
    # Gather all sentiment sources
    fg = _data.get_fear_greed()
    news_sent = _data.get_finnhub_sentiment(ticker)
    wsb = _data.get_reddit_dd(ticker, subreddit="wallstreetbets", limit=10)
    stocktwits = _data.get_stocktwits_sentiment(ticker)

    sources = {
        "fear_greed": fg,
        "news": news_sent,
        "social_reddit": {"post_count": len(wsb) if isinstance(wsb, list) else 0},
        "stocktwits": stocktwits,
    }

    # Simple weighted synthesis
    signals = []
    if isinstance(fg, dict) and "value" in fg:
        fgi = fg["value"]
        if fgi > 60:
            signals.append(("bullish", 0.2))
        elif fgi < 40:
            signals.append(("bearish", 0.2))
        else:
            signals.append(("neutral", 0.1))

    if isinstance(news_sent, dict) and "sentiment" in news_sent:
        s = news_sent["sentiment"]
        if s > 0.1:
            signals.append(("bullish", 0.3))
        elif s < -0.1:
            signals.append(("bearish", 0.3))
        else:
            signals.append(("neutral", 0.15))

    if isinstance(stocktwits, dict) and "sentiment_ratio" in stocktwits:
        ratio = stocktwits["sentiment_ratio"]
        if ratio > 0.6:
            signals.append(("bullish", 0.25))
        elif ratio < 0.4:
            signals.append(("bearish", 0.25))
        else:
            signals.append(("neutral", 0.1))

    # Weighted vote
    bull_weight = sum(w for d, w in signals if d == "bullish")
    bear_weight = sum(w for d, w in signals if d == "bearish")
    net = bull_weight - bear_weight
    direction = "bullish" if net > 0.1 else "bearish" if net < -0.1 else "neutral"
    confidence = round(min(abs(net) / 0.5, 1.0) * 100)

    # Detect conflicts
    directions = [d for d, _ in signals]
    has_conflict = len(set(directions) - {"neutral"}) > 1

    return {
        "ticker": ticker,
        "overall_direction": direction,
        "confidence": confidence,
        "conflict_detected": has_conflict,
        "sources": sources,
        "signal_breakdown": signals,
    }


@tool
def get_correlation_matrix(tickers: str, period: str = "6mo") -> dict:
    """Compute pairwise Pearson correlation matrix across multiple tickers.

    Helps identify diversification opportunities (low/negative correlation)
    and pairs-trading candidates (high correlation).

    Args:
        tickers: Comma-separated ticker symbols (e.g. "AAPL,MSFT,GOOGL").
        period: Data period for analysis.
    """
    import numpy as np

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        return {"error": "Need at least 2 tickers (comma separated)"}

    close_arrays: dict[str, list[float]] = {}
    for t in ticker_list:
        stock = _data.get_stock(t, period=period, interval="1d")
        close_arrays[t] = [b.close for b in stock.history if b.close is not None]

    min_len = min(len(v) for v in close_arrays.values())
    if min_len < 20:
        return {"error": "Not enough data for correlation"}

    matrix_data = np.array([close_arrays[t][-min_len:] for t in ticker_list])
    corr = np.corrcoef(matrix_data)

    pairs = []
    for i in range(len(ticker_list)):
        for j in range(i + 1, len(ticker_list)):
            pairs.append({
                "pair": f"{ticker_list[i]}/{ticker_list[j]}",
                "correlation": round(float(corr[i][j]), 4),
            })
    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "tickers": ticker_list,
        "pairs": pairs,
        "data_points": min_len,
    }


@tool
def get_multi_target_tp(ticker: str, direction: str = "bullish", period: str = "6mo") -> dict:
    """Compute multi-target take-profit levels (TP1/TP2/TP3) using Fibonacci extensions.

    Provides probability-weighted price targets based on recent swing range
    with corresponding R:R ratios and stop-loss placement.

    Args:
        ticker: Stock ticker symbol.
        direction: Trade direction — "bullish" or "bearish".
        period: Data period for swing range calculation.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    bars = data.history
    if not bars or len(bars) < 20:
        return {"error": "Not enough data"}

    closes = [b.close for b in bars if b.close]
    highs = [b.high for b in bars if b.high]
    lows = [b.low for b in bars if b.low]
    current = closes[-1]
    recent_high = max(highs[-50:]) if len(highs) >= 50 else max(highs)
    recent_low = min(lows[-50:]) if len(lows) >= 50 else min(lows)
    swing = recent_high - recent_low

    fib = [0.618, 1.0, 1.618]
    sign = 1 if direction == "bullish" else -1
    stop = round(current - sign * swing * 0.382, 2)

    targets = []
    for level, f, prob in zip(["TP1", "TP2", "TP3"], fib, [75, 55, 30]):
        price = round(current + sign * swing * f, 2)
        risk = abs(current - stop)
        reward = abs(price - current)
        targets.append({
            "level": level, "price": price, "fib": f"{f:.3f}",
            "probability": prob, "rr_ratio": round(reward / risk, 2) if risk > 0 else 0,
        })

    return {
        "ticker": ticker, "current_price": current, "direction": direction,
        "swing_range": round(swing, 2), "targets": targets, "stop_loss": stop,
    }


@tool
def get_google_trends(keyword: str, timeframe: str = "today 3-m") -> dict:
    """Fetch Google Trends search interest for a stock or keyword.

    Returns interest over time, trend direction, and spike detection.
    Spikes in search interest often correlate with unusual price moves.

    Args:
        keyword: Search term (ticker symbol or company name).
        timeframe: Pytrends timeframe string.
    """
    from app.engines.trends_engine import TrendsEngine
    trends = TrendsEngine()
    if not trends.is_available:
        return {"error": "pytrends not installed. Run: pip install pytrends"}
    return trends.get_search_interest(keyword, timeframe=timeframe)


@tool
def get_stocktwits_sentiment(ticker: str) -> dict:
    """Fetch StockTwits social sentiment for a ticker.

    Returns bullish/bearish message counts, sentiment ratio, and
    trending status from the StockTwits community.

    Args:
        ticker: Stock ticker symbol.
    """
    return _data.get_stocktwits_sentiment(ticker)


@tool
def get_accuracy_dashboard(days: int = 90) -> dict:
    """Get pattern prediction accuracy dashboard.

    Shows overall win rate, per-pattern accuracy, confidence calibration,
    and daily trend for the specified lookback period.

    Args:
        days: Lookback period in days.
    """
    from app.engines.accuracy_engine import AccuracyEngine
    from app.config import get_settings
    settings = get_settings()
    accuracy = AccuracyEngine(redis_url=settings.redis_url)
    return accuracy.get_accuracy_summary(days=days)


# ──────────────────────────────────────────────
# Phase 4: Coaching, Opening Range, Ghost Charts,
#           Model Optimizer, Gamification, Psychology
# ──────────────────────────────────────────────

@tool
def get_coaching_insights(trades: list[dict]) -> dict:
    """Get AI-powered trading coaching from trade history.

    Analyzes performance stats, detects behavioral patterns, and generates
    personalized tips via Gemini 3 Flash.

    Args:
        trades: List of trade dicts with keys: ticker, action, price, quantity, timestamp, pnl, strategy.
    """
    return _coach.get_coaching_insights(trades)


@tool
def get_improvement_plan(trades: list[dict], weeks: int = 4) -> dict:
    """Week-over-week improvement plan from trade history.

    Compares weekly stats and provides trajectory + actionable suggestions.

    Args:
        trades: Full trade history.
        weeks: Number of weeks to analyze.
    """
    return _coach.get_improvement_plan(trades, weeks=weeks)


@tool
def get_psychology_report(trades: list[dict]) -> dict:
    """Full trading psychology report detecting behavioral biases.

    Detects overtrading, FOMO, revenge trading, and loss aversion
    from trade history patterns.

    Args:
        trades: Trade history.
    """
    return _coach.get_psychology_report(trades)


@tool
def capture_opening_range(ticker: str, period: str = "1d", minutes: int = 30) -> dict:
    """Capture the opening range high/low for intraday breakout tracking.

    Records the high and low of the first N minutes after market open.
    Uses 5-minute intraday bars.

    Args:
        ticker: Stock ticker.
        period: Intraday data period (default 1d).
        minutes: Opening range window in minutes (15, 30, or 60).
    """
    data = _data.get_stock(ticker, period=period, interval="5m")
    return _opening_range.capture_opening_range(ticker, data.history, minutes=minutes)


@tool
def check_or_breakout(ticker: str, minutes: int = 30) -> dict:
    """Check if a stock has broken its opening range.

    Compares current price against the cached opening range for today.

    Args:
        ticker: Stock ticker.
        minutes: Opening range window that was used.
    """
    data = _data.get_stock(ticker, period="1d", interval="1m")
    current_price = data.history[-1]["close"] if data.history else 0
    return _opening_range.check_breakout(ticker, current_price, minutes=minutes)


@tool
def find_ghost_patterns(ticker: str, period: str = "3mo", top_k: int = 5) -> dict:
    """Find historical patterns similar to current price action.

    Uses ChromaDB vector similarity to find matching historical setups
    and shows their outcomes for predictive insight.

    Args:
        ticker: Stock ticker.
        period: Data period for current pattern.
        top_k: Number of matches to return.
    """
    data = _data.get_stock(ticker, period=period, interval="1d")
    return _ghosts.find_similar_patterns(data.history, top_k=top_k)


@tool
def get_ghost_overlay(pattern_id: str, ticker: str) -> dict:
    """Get a historical price path scaled to current price for chart overlay.

    Retrieves a stored pattern and scales it to start from the current price.

    Args:
        pattern_id: ID from find_ghost_patterns results.
        ticker: Current ticker for price anchoring.
    """
    data = _data.get_stock(ticker, period="1d", interval="1m")
    current_price = data.history[-1]["close"] if data.history else 0
    return _ghosts.get_ghost_overlay(pattern_id, current_price)


@tool
def get_optimization_report() -> dict:
    """Get model optimizer report with current vs recommended thresholds.

    Shows confidence threshold analysis, bucket win rates, and improvement suggestions.
    """
    return _optimizer.get_optimization_report()


@tool
def get_streak_data() -> dict:
    """Get current and best win/loss streaks from pattern outcomes.

    Returns streak data including hot streak detection for gamification.
    """
    from app.engines.accuracy_engine import AccuracyEngine
    from app.config import get_settings
    settings = get_settings()
    accuracy = AccuracyEngine(redis_url=settings.redis_url)
    return accuracy.get_streak_data()


@tool
def get_leaderboard_stats() -> dict:
    """Get gamification leaderboard stats: win rate trends, badges, and R:R.

    Returns 7/30/90 day breakdowns, earned achievement badges, and trend direction.
    """
    from app.engines.accuracy_engine import AccuracyEngine
    from app.config import get_settings
    settings = get_settings()
    accuracy = AccuracyEngine(redis_url=settings.redis_url)
    return accuracy.get_leaderboard_stats()


# ──────────────────────────────────────────────
# Tool Collections for Agent Assignment
# ──────────────────────────────────────────────

TV_TOOLS = [
    get_tv_technical_summary,
    screen_stocks_tv,
    get_top_movers_tv,
]

ALPACA_DATA_TOOLS = [
    get_stock_snapshot,
    get_multi_snapshots,
    get_alpaca_news,
    get_most_actives,
    get_account_info,
    get_open_positions,
]

TA_TOOLS = [
    get_stock_data,
    get_stock_snapshot,
    compute_technicals,
    detect_divergences,
    get_tv_technical_summary,
    get_analyst_recommendations,
    scan_chart_patterns,
    get_pattern_confluence,
    full_scan_patterns,
    get_fibonacci_levels,
    detect_pre_candle_formations,
    detect_emerging_patterns,
    multi_timeframe_patterns,
    age_detected_patterns,
    get_anchored_vwap,
    get_volume_profile,
    get_consolidation_zones,
    get_liquidity_zones,
]

OPTIONS_TOOLS = [
    get_stock_data,
    get_options_chain,
    get_alpaca_options_snapshot,
    analyze_gex,
    compute_advanced_gex,
    analyze_max_pain,
    analyze_put_call_ratio,
    detect_unusual_options,
    evaluate_options_strategy,
    compute_pl_profile,
    probability_of_profit,
    analyze_oi_patterns,
    price_american_option,
    monte_carlo_option_price,
    get_options_flow,
    get_darkpool,
    get_sweep_orders,
]

BREAKOUT_TOOLS = [
    get_stock_data,
    compute_technicals,
    scan_breakout_precursors,
    check_failed_breakout,
    full_breakout_analysis,
    options_breakout_confirmation,
    detect_institutional_tells,
    backtest_breakout_signals,
    analyze_gex,
    detect_unusual_options,
    get_market_structure,
]

NEWS_TOOLS = [
    get_company_news,
    get_alpaca_news,
    get_fear_greed_index,
    get_fear_greed_detailed,
    get_sentiment_bundle,
    get_trending_tickers,
    get_sec_filings,
    get_financials,
    get_insider_trades,
    get_insider_transactions,
    get_insider_sentiment,
    get_earnings_calendar,
    get_earnings_estimates,
    get_price_target,
    get_basic_fundamentals,
    get_earnings_transcript,
    get_multi_year_financials,
    get_wsb_mentions,
    get_dd_posts,
    get_economic_indicator,
    get_treasury_yields,
    get_sentiment_synthesis,
    get_google_trends,
    get_stocktwits_sentiment,
    get_accuracy_dashboard,
]

PORTFOLIO_TOOLS = [
    calculate_position_size,
    calculate_trailing_stop,
    score_trade_quality,
    get_stock_data,
    get_stock_snapshot,
    compute_technicals,
    get_market_clock,
    get_account_info,
    get_open_positions,
    get_corporate_actions,
    backtest_strategy,
]

VISION_TOOLS = [
    get_stock_data,
    compute_technicals,
    scan_chart_patterns,
    get_pattern_confluence,
    full_scan_patterns,
    get_fibonacci_levels,
    detect_pre_candle_formations,
    detect_emerging_patterns,
    multi_timeframe_patterns,
    age_detected_patterns,
    analyze_chart_image,
    narrate_chart,
    chart_health_check,
    identify_patterns_vision,
    compare_charts_vision,
    trigger_pattern_scan,
    check_pattern_outcomes,
    backtest_chart_patterns,
    get_trade_targets,
    get_anchored_vwap,
    get_market_structure,
    get_sentiment_synthesis,
    get_volume_profile,
    get_consolidation_zones,
    get_liquidity_zones,
    get_google_trends,
    get_stocktwits_sentiment,
    get_accuracy_dashboard,
    get_coaching_insights,
    get_improvement_plan,
    get_psychology_report,
    capture_opening_range,
    check_or_breakout,
    find_ghost_patterns,
    get_ghost_overlay,
    get_optimization_report,
    get_streak_data,
    get_leaderboard_stats,
    get_correlation_matrix,
    get_multi_target_tp,
]

ALL_TOOLS = list({
    t.name: t
    for t in TA_TOOLS + OPTIONS_TOOLS + BREAKOUT_TOOLS + NEWS_TOOLS + PORTFOLIO_TOOLS + VISION_TOOLS + TV_TOOLS + ALPACA_DATA_TOOLS
}.values())
