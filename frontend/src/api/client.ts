/**
 * Bubby Vision — API Client
 *
 * Full coverage of all backend routes across:
 *   routes.py       — data_router, chat_router, links_router, options_live_router,
 *                     alpaca_data_router, extended_data_router
 *   routes_market.py — market_router (sentiment, flow, TV, OptionStrats, QuantData)
 *   routes_watchlist.py — watchlist_router
 */

import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_V1 = `${API_BASE}/v1/api`;

const client = axios.create({
    baseURL: API_V1,
    timeout: 30000,
    headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor: prefer JWT, fall back to API key ──
client.interceptors.request.use((config) => {
    config.headers = config.headers || {};

    // JWT token takes priority
    const token = typeof localStorage !== 'undefined' && localStorage.getItem('mp_access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }

    // API key as fallback
    const apiKey =
        import.meta.env.VITE_API_KEY ||
        (typeof localStorage !== 'undefined' && localStorage.getItem('mp_api_key')) ||
        '';
    if (apiKey) {
        config.headers['X-API-Key'] = apiKey;
    }

    return config;
});

// ── Response interceptor: 401 silent refresh / 429 / 5xx ──
let isRefreshing = false;
let refreshQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

function processQueue(error: unknown, token: string | null) {
    refreshQueue.forEach(({ resolve, reject }) => {
        if (error) reject(error);
        else if (token) resolve(token);
    });
    refreshQueue = [];
}

client.interceptors.response.use(
    (res) => res,
    async (err: AxiosError) => {
        const status = err.response?.status;
        const originalRequest = err.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // Silent token refresh on 401
        if (status === 401 && !originalRequest._retry) {
            const refreshToken = localStorage.getItem('mp_refresh_token');

            if (refreshToken) {
                if (isRefreshing) {
                    // Queue requests while refresh is in progress
                    return new Promise((resolve, reject) => {
                        refreshQueue.push({
                            resolve: (token: string) => {
                                originalRequest.headers.Authorization = `Bearer ${token}`;
                                resolve(client(originalRequest));
                            },
                            reject,
                        });
                    });
                }

                originalRequest._retry = true;
                isRefreshing = true;

                try {
                    const res = await axios.post(`${API_V1}/auth/refresh`, {
                        refresh_token: refreshToken,
                    });
                    const newAccess = res.data.access_token;
                    const newRefresh = res.data.refresh_token;

                    localStorage.setItem('mp_access_token', newAccess);
                    localStorage.setItem('mp_refresh_token', newRefresh);

                    processQueue(null, newAccess);
                    originalRequest.headers.Authorization = `Bearer ${newAccess}`;
                    return client(originalRequest);
                } catch (refreshErr) {
                    processQueue(refreshErr, null);
                    localStorage.removeItem('mp_access_token');
                    localStorage.removeItem('mp_refresh_token');
                    window.location.href = '/login';
                    return Promise.reject(refreshErr);
                } finally {
                    isRefreshing = false;
                }
            } else {
                // No refresh token — redirect to login
                localStorage.removeItem('mp_access_token');
                window.location.href = '/login';
            }
        } else if (status === 429) {
            const retryAfter = err.response?.headers?.['retry-after'];
            console.warn(`[API] Rate limited${retryAfter ? ` — retry after ${retryAfter}s` : ''}`);
        } else if (status && status >= 500) {
            console.error(
                `[API] Server error ${status}: ${(err.response?.data as { detail?: string })?.detail || err.message}`,
            );
        }
        return Promise.reject(err);
    },
);

// ────────────────────────────────────────────────
// Stock & Core Data  (data_router — routes.py)
// ────────────────────────────────────────────────
export const stockApi = {
    // Core data
    getStock: (ticker: string, period = '1mo', interval = '1d') =>
        client.get(`/stock/${ticker}`, { params: { period, interval } }),
    getOptions: (ticker: string, expiration?: string) => client.get(`/options/${ticker}`, { params: { expiration } }),
    getNews: (ticker: string, limit = 20) => client.get(`/news/${ticker}`, { params: { limit } }),

    // Extended data (extended_data_router — routes.py)
    getFinancials: (ticker: string) => client.get(`/financials/${ticker}`),
    getEarningsCalendar: (days = 7) => client.get('/earnings-calendar', { params: { days } }),
    getAnalyst: (ticker: string) => client.get(`/analyst/${ticker}`),
    getInsiderTransactions: (ticker: string) => client.get(`/insider/${ticker}`),
    getDarkpool: (ticker: string, limit = 25) => client.get(`/darkpool/${ticker}`, { params: { limit } }),

    // Live options (options_live_router — routes.py)
    getLiveOptions: (
        ticker: string,
        opts?: {
            option_type?: string;
            expiration?: string;
            min_strike?: number;
            max_strike?: number;
            limit?: number;
        },
    ) => client.get(`/options/${ticker}/live`, { params: opts }),

    // External links (links_router — routes.py)
    getExternalLinks: (category?: string) => client.get('/links', { params: { category } }),
    getTickerLinks: (ticker: string) => client.get(`/links/ticker/${ticker}`),
};

// ────────────────────────────────────────────────
// Alpaca Market Data  (alpaca_data_router — routes.py)
// ────────────────────────────────────────────────
export const alpacaApi = {
    getSnapshot: (ticker: string) => client.get(`/snapshot/${ticker}`),
    getBatchSnapshots: (symbols: string) => client.get('/snapshots', { params: { symbols } }),
    getMarketNews: (symbols?: string, limit = 20) => client.get('/news/market', { params: { symbols, limit } }),
    getMostActive: (by = 'volume', top = 20) => client.get('/most-actives', { params: { by, top } }),
    getAccount: () => client.get('/account'),
    getPositions: () => client.get('/positions'),
};

// ────────────────────────────────────────────────
// Market Data  (market_router — routes_market.py)
// ────────────────────────────────────────────────
export const marketApi = {
    // Sentiment
    getSentiment: (ticker: string) => client.get(`/sentiment/${ticker}`),
    getFearGreed: () => client.get('/sentiment/fear-greed'),

    // SEC Filings
    getFilings: (ticker: string, form_type?: string, limit = 10) =>
        client.get(`/filings/${ticker}`, { params: { form_type, limit } }),

    // Options Chain (real exchange data)
    getOptionsChain: (ticker: string, expiration?: string) =>
        client.get(`/options/${ticker}`, { params: { expiration } }),
    getOptionsChainLive: (
        ticker: string,
        params?: {
            option_type?: string;
            expiration?: string;
            min_strike?: number;
            max_strike?: number;
            limit?: number;
        },
    ) => client.get(`/options/${ticker}/live`, { params }),

    // Options Flow (QuantData)
    getOptionsFlow: (ticker?: string, min_premium = 100000) =>
        client.get('/options-flow', { params: { ticker, min_premium } }),
    getUnusualActivity: (ticker?: string) => client.get('/unusual-activity', { params: { ticker } }),
    getSweeps: (ticker?: string) => client.get('/sweeps', { params: { ticker } }),
    getCombinedFlow: (ticker?: string, min_premium = 50000) =>
        client.get('/combined-flow', { params: { ticker, min_premium } }),

    // OptionStrats
    getIV: (ticker: string) => client.get(`/optionstrats/iv/${ticker}`),
    getOptionStratsUrls: (ticker: string, strategy?: string) =>
        client.get(`/optionstrats/urls/${ticker}`, { params: { strategy } }),
    getInsiderFlow: (limit = 25) => client.get('/optionstrats/insider-flow', { params: { limit } }),
    getStrategyCatalog: () => client.get('/optionstrats/strategy-catalog'),
    getCongressionalFlow: (limit = 25) => client.get('/congress', { params: { limit } }),

    // Combined News
    getCombinedNews: (ticker?: string, limit = 50) => client.get('/news', { params: { ticker, limit } }),
    getQuantDataNews: (ticker?: string, topic?: string, limit = 50) =>
        client.get('/news/quantdata', { params: { ticker, topic, limit } }),

    // QuantData Intelligence
    getNetDrift: (ticker?: string, date?: string) => client.get('/net-drift', { params: { ticker, date } }),
    getNetFlow: (ticker?: string, limit = 50) => client.get('/net-flow', { params: { ticker, limit } }),
    getDarkFlow: (ticker?: string, limit = 25) => client.get('/dark-flow', { params: { ticker, limit } }),
    getExposure: (ticker: string, exposure_type = 'gex', expiration?: string) =>
        client.get(`/exposure/${ticker}`, { params: { exposure_type, expiration } }),
    getHeatMap: (ticker: string, metric = 'gex', expiration?: string) =>
        client.get(`/heatmap/${ticker}`, { params: { metric, expiration } }),
    getVolatilityDrift: (ticker: string, date?: string) => client.get(`/vol-drift/${ticker}`, { params: { date } }),
    getVolatilitySkew: (ticker: string, expiration?: string) =>
        client.get(`/vol-skew/${ticker}`, { params: { expiration } }),
    getGainersLosers: (direction = 'bullish', limit = 25) =>
        client.get('/gainers-losers', { params: { direction, limit } }),

    // Market Clock & Trending
    getMarketClock: () => client.get('/market-clock'),
    getTrending: () => client.get('/trending'),
    getWsb: (ticker: string, subreddit = 'wallstreetbets', limit = 25) =>
        client.get(`/wsb/${ticker}`, { params: { subreddit, limit } }),

    // TradingView
    getTechnical: (ticker: string, exchange = 'NASDAQ', interval = '1d') =>
        client.get(`/tv/technical/${ticker}`, { params: { exchange, interval } }),
    getScreener: (params?: {
        market?: string;
        min_price?: number;
        max_price?: number;
        min_volume?: number;
        min_change?: number;
        max_change?: number;
    }) => client.get('/tv/screener', { params }),
    getMovers: (direction = 'gainers', limit = 15) => client.get('/tv/movers', { params: { direction, limit } }),
    getTvSnapshot: (ticker: string) => client.get(`/tv/snapshot/${ticker}`),
    getRealtimeQuote: (ticker: string) => client.get(`/tv/quote/${ticker}`),
    getBatchQuotes: (tickers: string) => client.get('/tv/batch-quotes', { params: { tickers } }),
    getTvFinancials: (ticker: string) => client.get(`/tv/financials/${ticker}`),
    getEarningsCalendar: (limit = 50, upcoming_only = true) =>
        client.get('/tv/earnings-calendar', { params: { limit, upcoming_only } }),
    getShortInterest: (limit = 25) => client.get('/tv/short-interest', { params: { limit } }),
    getSectorPerformance: (top_per_sector = 5) => client.get('/tv/sector-performance', { params: { top_per_sector } }),

    // Breakout Analysis (Phase 10)
    getBreakoutFull: (ticker: string, period = '6mo') => client.get(`/breakout/full/${ticker}`, { params: { period } }),
    getBreakoutOptionsConfirm: (ticker: string) => client.get(`/breakout/options-confirm/${ticker}`),
    getBreakoutInstitutional: (ticker: string, period = '3mo') =>
        client.get(`/breakout/institutional/${ticker}`, { params: { period } }),
    getBreakoutBacktest: (ticker: string, period = '2y') =>
        client.get(`/breakout/backtest/${ticker}`, { params: { period } }),

    // Phase 6: Enhanced Data
    getFearGreedDetailed: () => client.get('/fear-greed/detailed'),
    getEarningsEstimates: (ticker: string, freq = 'quarterly') =>
        client.get(`/earnings/estimates/${ticker}`, { params: { freq } }),
    getPriceTarget: (ticker: string) => client.get(`/price-target/${ticker}`),
    getBasicFundamentals: (ticker: string) => client.get(`/fundamentals/${ticker}`),
    getInsiderSentiment: (ticker: string) => client.get(`/insider-sentiment/${ticker}`),
    getCorporateActions: (ticker: string) => client.get(`/corporate-actions/${ticker}`),

    // Phase 6: Economic Data (FRED)
    getEconomicDashboard: () => client.get('/economic/dashboard'),
    getTreasuryYields: () => client.get('/treasury-yields'),

    // Phase 8: Pattern Detection
    getPatterns: (ticker: string, period = '3mo') => client.get(`/patterns/${ticker}`, { params: { period } }),
    getPatternConfluence: (ticker: string, period = '3mo') =>
        client.get(`/patterns/confluence/${ticker}`, { params: { period } }),
    getFullPatternScan: (ticker: string, period = '3mo') =>
        client.get(`/patterns/full/${ticker}`, { params: { period } }),
    getFibonacci: (ticker: string, period = '6mo') =>
        client.get(`/patterns/fibonacci/${ticker}`, { params: { period } }),

    // Phase 7: Advanced Options
    getOiPatterns: (ticker: string, expiration?: string) =>
        client.get(`/options/oi-patterns/${ticker}`, { params: { expiration } }),
    getGexDetailed: (ticker: string, expiration?: string) =>
        client.get(`/options/gex-detailed/${ticker}`, { params: { expiration } }),

    // Phase 7b: Advanced Options Analytics (audit — previously orphaned)
    getMaxPain: (ticker: string, expiration?: string) =>
        client.get(`/options/max-pain/${ticker}`, { params: { expiration } }),
    getPCR: (ticker: string, expiration?: string) => client.get(`/options/pcr/${ticker}`, { params: { expiration } }),
    getIVAnalysis: (ticker: string, expiration?: string) =>
        client.get(`/options/iv-analysis/${ticker}`, { params: { expiration } }),
    getUnusualInternal: (ticker: string, expiration?: string, threshold = 3.0) =>
        client.get(`/options/unusual/${ticker}`, { params: { expiration, threshold } }),
    getSmartMoney: (ticker: string, expiration?: string) =>
        client.get(`/options/smart-money/${ticker}`, { params: { expiration } }),
    evaluateStrategy: (strategyType: string, legs: object[], underlyingPrice: number) =>
        client.post('/options/evaluate-strategy', legs, {
            params: { strategy_type: strategyType, underlying_price: underlyingPrice },
        }),
    computePlAtDate: (legs: object[], underlyingPrice: number, targetDays: number, r = 0.05) =>
        client.post('/options/pl-at-date', legs, {
            params: { underlying_price: underlyingPrice, target_days: targetDays, r },
        }),
    computeProfitableRange: (legs: object[], underlyingPrice: number) =>
        client.post('/options/profitable-range', legs, {
            params: { underlying_price: underlyingPrice },
        }),

    // Higher-Order Greeks (2nd/3rd order: charm, vanna, vomma, veta, color, speed, ultima, zomma)
    getHigherGreeks: (ticker: string, expiryDays = 30, optionType = 'call', r = 0.05) =>
        client.get(`/options/higher-greeks/${ticker}`, {
            params: { expiry_days: expiryDays, option_type: optionType, r },
        }),

    // Merton model pricing (dividend-adjusted BSM)
    priceMerton: (params: {
        S: number;
        K: number;
        T: number;
        r?: number;
        sigma?: number;
        q?: number;
        option_type?: string;
    }) => client.post('/options/price-merton', params),

    // Phase 8: Direct Data Chart Analysis
    getChartHealth: (ticker: string, period = '3mo') => client.get(`/vision/health/${ticker}`, { params: { period } }),

    // TA Engine — full indicator set
    getIndicators: (ticker: string, period = '6mo', interval = '1d') =>
        client.get(`/ta/indicators/${ticker}`, { params: { period, interval } }),

    // ── Phase 12: Remaining Routes ──

    // Earnings & Financials deep-dive
    getEarningsTranscript: (ticker: string, quarter?: number, year?: number) =>
        client.get(`/earnings/transcript/${ticker}`, { params: { quarter, year } }),
    getMultiYearFinancials: (ticker: string, years = 5) =>
        client.get(`/financials/${ticker}/multi-year`, { params: { years } }),
    getQuarterlyFinancials: (ticker: string, quarters = 8) =>
        client.get(`/financials/${ticker}/quarterly`, { params: { quarters } }),
    getWsbDD: (ticker: string, limit = 15) => client.get(`/wsb/dd/${ticker}`, { params: { limit } }),

    // Generic FRED series
    getEconomicSeries: (seriesId: string, limit = 100) => client.get(`/economic/${seriesId}`, { params: { limit } }),

    // Options Calculator
    computePlProfile: (legs: object[], underlyingPrice: number, priceRangePct = 0.2) =>
        client.post('/options/pl-profile', legs, {
            params: { underlying_price: underlyingPrice, price_range_pct: priceRangePct },
        }),
    computePoP: (legs: object[], underlyingPrice: number, sigma: number, T: number, r = 0.05) =>
        client.post('/options/probability-of-profit', legs, {
            params: { underlying_price: underlyingPrice, sigma, T, r },
        }),
    priceOption: (params: {
        S: number;
        K: number;
        T: number;
        sigma: number;
        r?: number;
        option_type?: string;
        model?: string;
        american?: boolean;
    }) => client.post('/options/price', null, { params }),

    // Direct Data Analysis (analyze / compare / narrate — no Vision AI)
    analyzeChart: (ticker: string, context = '') =>
        client.post('/vision/analyze', null, { params: { ticker, context } }),
    compareCharts: (tickers: string[], period = '3mo') =>
        client.post('/vision/compare', tickers, { params: { period } }),
    narrateChart: (ticker: string, period = '1mo') => client.get(`/vision/narrate/${ticker}`, { params: { period } }),

    // Comprehensive Analysis (AI Data Pipeline)
    getComprehensiveAnalysis: (ticker: string, period = '3mo', interval = '1d') =>
        client.get(`/analysis/comprehensive/${ticker}`, { params: { period, interval } }),
    getTradeTargets: (ticker: string, entry: number, stop: number, period = '6mo') =>
        client.get(`/analysis/targets/${ticker}`, { params: { entry, stop, period } }),

    // Pattern Alerts & Backtest
    triggerPatternScan: (ticker: string, period = '3mo') =>
        client.get(`/patterns/scan/${ticker}`, { params: { period } }),
    getPatternOutcomes: (ticker: string, period = '6mo', lookforward = 20) =>
        client.get(`/patterns/outcomes/${ticker}`, { params: { period, lookforward } }),
    backtestPatterns: (ticker: string, period = '2y') =>
        client.get(`/patterns/backtest/${ticker}`, { params: { period } }),
    managePatternWatchlist: (tickers: string[], action = 'add') =>
        client.post('/patterns/watchlist', tickers, { params: { action } }),
    getPatternAlerts: (ticker: string, limit = 20) => client.get(`/patterns/alerts/${ticker}`, { params: { limit } }),
    getPatternWatchlist: () => client.get('/patterns/watchlist'),
    getChartData: (ticker: string, period = '6mo', interval = '1d') =>
        client.get(`/chart-data/${ticker}`, { params: { period, interval } }),

    // ── Phase 2: Briefing, Journal, Synthesis ──
    getLatestBriefing: () => client.get('/briefing/latest'),
    getLatestJournal: () => client.get('/journal/latest'),
    getJournalByDate: (date: string) => client.get(`/journal/${date}`),
    getAnchoredVwap: (ticker: string, anchorDate?: string, period = '6mo') =>
        client.get(`/analysis/anchored-vwap/${ticker}`, { params: { anchor_date: anchorDate, period } }),
    getMarketStructure: (ticker: string, period = '3mo', lookback = 5) =>
        client.get(`/analysis/market-structure/${ticker}`, { params: { period, lookback } }),
    getSentimentSynthesis: (ticker: string, period = '3mo') =>
        client.get(`/analysis/sentiment/${ticker}`, { params: { period } }),

    // ── Questrade Plus Features ──

    // Options P&L Calculator (PnLCalculator engine)
    calculateOptionsPnl: (
        legs: Array<{
            option_type: string;
            strike: number;
            premium: number;
            quantity: number;
            expiration?: string;
            delta?: number;
            gamma?: number;
            theta?: number;
            vega?: number;
            iv?: number;
        }>,
        underlyingPrice: number,
        strategyName = 'Custom Strategy',
        priceRangePct = 0.3,
    ) =>
        client.post('/options/pnl', {
            legs,
            underlying_price: underlyingPrice,
            strategy_name: strategyName,
            price_range_pct: priceRangePct,
        }),

    // Portfolio Rebalancer
    rebalancePortfolio: (
        targetAllocations?: Array<{
            ticker: string;
            target_pct: number;
            sector?: string;
        }>,
    ) =>
        client.post('/portfolio/rebalance', {
            target_allocations: targetAllocations ?? null,
        }),

    // Market Heatmap (sector-level performance)
    getMarketHeatmap: (tickers?: string) => client.get('/heatmap', { params: { tickers } }),

    // Account Activities & Executions
    getAccountActivities: (startTime?: string, endTime?: string) =>
        client.get('/account/activities', { params: { start_time: startTime, end_time: endTime } }),
    getAccountExecutions: (startTime?: string, endTime?: string) =>
        client.get('/account/executions', { params: { start_time: startTime, end_time: endTime } }),

    // Order Notification Streaming Port
    getOrderNotificationPort: () => client.get('/account/notification-port'),

    // ── Questrade Plus Phase 2 — Data Intelligence ──

    // Enriched Quote (L1 + fundamentals + derived metrics)
    getEnrichedQuote: (ticker: string) => client.get(`/quote/enriched/${ticker}`),

    // Dividend Calendar for all holdings
    getDividendCalendar: () => client.get('/account/dividends'),

    // Portfolio Performance (unrealized + realized P&L, dividends, commissions)
    getPortfolioPerformance: () => client.get('/account/performance'),

    // Currency Exposure (CAD vs USD breakdown)
    getCurrencyExposure: () => client.get('/account/currency-exposure'),

    // Market Status (exchange open/closed/pre/post)
    getMarketStatus: () => client.get('/markets/status'),

    // Order Impact Preview (what-if cost/commission)
    previewOrderImpact: (ticker: string, quantity: number, action = 'Buy', orderType = 'Market', limitPrice?: number) =>
        client.post('/order/impact', {
            ticker,
            quantity,
            action,
            order_type: orderType,
            limit_price: limitPrice ?? null,
        }),
};

// ────────────────────────────────────────────────
// Watchlist & Alerts  (watchlist_router — routes_watchlist.py)
// ────────────────────────────────────────────────
export const watchlistApi = {
    getWatchlist: (user_id = 'default') => client.get('/watchlist', { params: { user_id } }),
    addTicker: (ticker: string, user_id = 'default') => client.post('/watchlist', { ticker }, { params: { user_id } }),
    removeTicker: (ticker: string, user_id = 'default') =>
        client.delete(`/watchlist/${ticker}`, { params: { user_id } }),
    getAlerts: (user_id = 'default') => client.get('/alerts', { params: { user_id } }),
    createAlert: (data: { ticker: string; threshold: number; direction: string }, user_id = 'default') =>
        client.post('/alerts', data, { params: { user_id } }),
    deleteAlert: (alert_id: string, user_id = 'default') =>
        client.delete(`/alerts/${alert_id}`, { params: { user_id } }),
};

// ────────────────────────────────────────────────
// Chat / AI Agent  (chat_router — routes.py)
// ────────────────────────────────────────────────
export const chatApi = {
    send: (message: string, conversation_id?: string, preferred_agent?: string) =>
        client.post('/chat', { message, conversation_id, preferred_agent }),
    dashboard: (ticker: string, conversation_id?: string) =>
        client.post('/chat', {
            message: `Generate a comprehensive Decision Dashboard for ${ticker}. Use ALL available tools.`,
            conversation_id,
            preferred_agent: 'sentiment',
        }),
};

// ────────────────────────────────────────────────
// Analysis & Growth Features  (market_router — routes_market.py, Phase 3)
// ────────────────────────────────────────────────
export const analysisApi = {
    // Volume Profile — price-at-volume histogram with POC and value area
    getVolumeProfile: (ticker: string, period = '6mo', numBins = 50) =>
        client.get(`/market/analysis/volume-profile/${ticker}`, { params: { period, num_bins: numBins } }),

    // Consolidation Zones — tight price ranges preceding breakouts
    getConsolidationZones: (ticker: string, period = '6mo', atrMultiplier = 0.5, minBars = 8) =>
        client.get(`/market/analysis/consolidation/${ticker}`, {
            params: { period, atr_multiplier: atrMultiplier, min_bars: minBars },
        }),

    // Liquidity Zones — high-volume price nodes
    getLiquidityZones: (ticker: string, period = '6mo') =>
        client.get(`/market/analysis/liquidity/${ticker}`, { params: { period } }),

    // Google Trends — search interest spikes
    getGoogleTrends: (keyword: string, timeframe = 'today 3-m') =>
        client.get(`/market/analysis/google-trends/${keyword}`, { params: { timeframe } }),

    // StockTwits — social sentiment
    getStockTwits: (ticker: string) => client.get(`/market/analysis/stocktwits/${ticker}`),

    // Accuracy Dashboard — pattern prediction tracking
    getAccuracyDashboard: (days = 90) => client.get('/market/accuracy/dashboard', { params: { days } }),
    getPatternAccuracy: (name: string, days = 90) =>
        client.get(`/market/accuracy/pattern/${name}`, { params: { days } }),
    getConfidenceCalibration: (days = 90) => client.get('/market/accuracy/calibration', { params: { days } }),

    // Alert History & Chains
    getAlertHistory: (limit = 50) => client.get('/market/alerts/history', { params: { limit } }),
    getActiveChains: () => client.get('/market/alerts/chains'),
    getTickerChains: (ticker: string) => client.get(`/market/alerts/chains/${ticker}`),

    // Walk-Forward Backtesting
    walkForwardBacktest: (ticker: string, strategy = 'sma_crossover', inSamplePct = 0.7, period = '5y') =>
        client.get(`/market/backtest/walk-forward/${ticker}`, {
            params: { strategy, in_sample_pct: inSamplePct, period },
        }),

    // Monte Carlo Backtesting
    monteCarloBacktest: (ticker: string, strategy = 'sma_crossover', nSimulations = 1000, period = '2y') =>
        client.get(`/market/backtest/monte-carlo/${ticker}`, {
            params: { strategy, n_simulations: nSimulations, period },
        }),

    // ── Phase 4: Coaching, Opening Range, Ghost Charts, Optimizer, Gamification ──

    // AI Trading Coach
    getCoachingInsights: (trades: Record<string, unknown>[]) => client.post('/market/coaching/insights', trades),
    getImprovementPlan: (trades: Record<string, unknown>[], weeks = 4) =>
        client.post('/market/coaching/improvement-plan', trades, { params: { weeks } }),
    getPsychologyReport: (trades: Record<string, unknown>[]) => client.post('/market/coaching/psychology', trades),

    // Opening Range Tracker
    captureOpeningRange: (ticker: string, minutes = 30) =>
        client.get(`/market/opening-range/${ticker}`, { params: { minutes } }),
    checkORBreakout: (ticker: string, minutes = 30) =>
        client.get(`/market/opening-range/${ticker}/breakout`, { params: { minutes } }),

    // Ghost Charts (historical pattern overlays)
    findGhostPatterns: (ticker: string, period = '3mo', topK = 5) =>
        client.get(`/market/ghost-charts/${ticker}`, { params: { period, top_k: topK } }),
    getGhostOverlay: (patternId: string, ticker: string) =>
        client.get(`/market/ghost-charts/overlay/${patternId}`, { params: { ticker } }),

    // Model Optimizer
    getOptimizationReport: () => client.get('/market/optimizer/report'),

    // Gamification
    getStreakData: () => client.get('/market/gamification/streaks'),
    getLeaderboardStats: () => client.get('/market/gamification/leaderboard'),

    // ── Tier 2: Advanced Analytics ──

    // Anchored VWAP
    getAnchoredVwap: (ticker: string, anchorIndex = 0, period = '6mo') =>
        client.get(`/market/analysis/avwap/${ticker}`, { params: { anchor_index: anchorIndex, period } }),

    // Market Structure
    getMarketStructure: (ticker: string, period = '6mo') =>
        client.get(`/market/analysis/market-structure/${ticker}`, { params: { period } }),

    // Correlation Matrix
    getCorrelationMatrix: (tickers: string[], period = '6mo') =>
        client.post('/market/analysis/correlation', { tickers, period }),

    // Multi-Target TP
    getMultiTargetTP: (ticker: string, direction = 'bullish', period = '6mo') =>
        client.get(`/market/analysis/multi-target/${ticker}`, { params: { direction, period } }),

    // Sentiment Synthesis (unified TA + news + social)
    getSentimentSynthesis: (ticker: string, period = '3mo') =>
        client.get(`/market/analysis/sentiment/${ticker}`, { params: { period } }),

    // Social Volume Spikes
    getSocialVolume: (ticker: string) => client.get(`/market/analysis/social-volume/${ticker}`),

    // Pattern Accuracy (QuestDB)
    getPatternAccuracyQDB: (pattern?: string, ticker?: string) =>
        client.get('/market/analysis/pattern-accuracy', { params: { pattern, ticker } }),
    getRecentOutcomes: (limit = 50) => client.get('/market/analysis/pattern-outcomes/recent', { params: { limit } }),

    // Position Risk Overlay
    getPositionRisk: (positions: Record<string, unknown>[], accountSize = 100000) =>
        client.post('/market/account/positions/risk', positions, { params: { account_size: accountSize } }),

    // Exit Analysis
    getExitAnalysis: (ticker: string, period = '1mo') =>
        client.get(`/market/analysis/exit-analysis/${ticker}`, { params: { period } }),

    // ── OpenBB Enhanced Data (Phase 9) ──

    // Institutional ownership (13F holders from SEC filings)
    getInstitutionalOwnership: (ticker: string, limit = 20) =>
        client.get(`/market/institutional/${ticker}`, { params: { limit } }),

    // Upcoming US economic events
    getEconomicCalendar: (daysAhead = 7) =>
        client.get('/market/economic-calendar', { params: { days_ahead: daysAhead } }),

    // Historical dividend payments
    getDividendHistory: (ticker: string, limit = 20) =>
        client.get(`/market/dividends/${ticker}`, { params: { limit } }),

    // ETF underlying holdings
    getETFHoldings: (ticker: string, limit = 25) => client.get(`/market/etf-holdings/${ticker}`, { params: { limit } }),

    // Forward revenue/EPS consensus estimates
    getAnalystEstimates: (ticker: string) => client.get(`/market/analyst-estimates/${ticker}`),

    // OpenBB SDK health check
    getOpenBBHealth: () => client.get('/market/openbb-health'),

    // ── OpenBB News Wire (Bloomberg-grade) ──

    // Global market news — macro, geopolitical, central bank, earnings
    getWorldNews: (limit = 50, topic?: string) => client.get('/market/news/world', { params: { limit, topic } }),

    // Company-specific news aggregated from multiple OpenBB providers
    getCompanyNewsOpenBB: (ticker: string, limit = 30) =>
        client.get(`/market/news/company/${ticker}`, { params: { limit } }),
};

// ────────────────────────────────────────────────
// Chat History Persistence  (chat_history_router — routes_chat_history.py)
// ────────────────────────────────────────────────
export const conversationApi = {
    list: (user_id = 'default') => client.get('/conversations', { params: { user_id } }),
    getMessages: (conv_id: string, user_id = 'default') =>
        client.get(`/conversations/${conv_id}/messages`, { params: { user_id } }),
    saveMessage: (
        conv_id: string,
        message: { role: string; content: string; agent?: string; tools?: string[]; timestamp?: string },
        user_id = 'default',
    ) => client.post(`/conversations/${conv_id}/messages`, message, { params: { user_id } }),
    saveConversation: (
        conv_id: string,
        title: string,
        messages: { role: string; content: string; agent?: string; tools?: string[]; timestamp?: string }[],
        user_id = 'default',
    ) => client.put(`/conversations/${conv_id}`, { title, messages }, { params: { user_id } }),
    delete: (conv_id: string, user_id = 'default') =>
        client.delete(`/conversations/${conv_id}`, { params: { user_id } }),
};

// ────────────────────────────────────────────────
// User Preferences  (preferences_router — routes_preferences.py)
// ────────────────────────────────────────────────
export const preferencesApi = {
    get: (user_id = 'default') => client.get('/preferences', { params: { user_id } }),
    update: (preferences: Record<string, unknown>, user_id = 'default') =>
        client.put('/preferences', { preferences }, { params: { user_id } }),
    set: (key: string, value: unknown, user_id = 'default') =>
        client.patch(`/preferences/${key}`, { value }, { params: { user_id } }),
    reset: (user_id = 'default') => client.delete('/preferences', { params: { user_id } }),
};

// ────────────────────────────────────────────────
// Screener Filter Presets  (presets_router — routes_presets.py)
// ────────────────────────────────────────────────
export const presetsApi = {
    list: (user_id = 'default') => client.get('/presets/screener', { params: { user_id } }),
    create: (name: string, filters: Record<string, unknown>, user_id = 'default') =>
        client.post('/presets/screener', { name, filters }, { params: { user_id } }),
    delete: (preset_id: string, user_id = 'default') =>
        client.delete(`/presets/screener/${preset_id}`, { params: { user_id } }),
};

// ────────────────────────────────────────────────
// Health  (health_router — routes.py, unversioned)
// ────────────────────────────────────────────────
export const healthApi = {
    check: () => axios.get(`${API_BASE}/health`),
};

// ────────────────────────────────────────────────
// Auth  (auth_router — backend/app/auth/routes.py)
// ────────────────────────────────────────────────
export const authApi = {
    login: (email: string, password: string) => client.post('/auth/login', { email, password }),
    register: (email: string, password: string, display_name: string) =>
        client.post('/auth/register', { email, password, display_name }),
    refresh: (refresh_token: string) => client.post('/auth/refresh', { refresh_token }),
    me: () => client.get('/auth/me'),
    updateProfile: (display_name: string) => client.patch('/auth/profile', { display_name }),
    changePassword: (current_password: string, new_password: string) =>
        client.put('/auth/password', { current_password, new_password }),
};

export default client;
