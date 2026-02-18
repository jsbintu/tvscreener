/**
 * Dashboard v3 — 9 panels + live WebSocket prices, alert toasts, auto-refresh
 *
 * Panels:
 * 1. Market Status + Clock
 * 2. Fear & Greed gauge
 * 3. Watchlist mini-cards (LIVE prices via WebSocket)
 * 4. Top Movers (gainers/losers/active)
 * 5. Trending (WSB)
 * 6. Sector Performance heatmap
 * 7. Earnings Calendar
 * 8. Short Squeeze Scanner
 * 9. Combined News Feed
 *
 * Live Features:
 * - WebSocket price streaming on watchlist tickers
 * - Real-time alert toast notifications
 * - 60s auto-refresh with last-updated timestamp
 */

import { useQuery } from '@tanstack/react-query';
import {
    Activity,
    AlertTriangle,
    BarChart3,
    Bell,
    BookOpen,
    Briefcase,
    Calendar,
    Clock,
    DollarSign,
    ExternalLink,
    Gauge,
    Globe,
    Newspaper,
    Radio,
    RefreshCw,
    TrendingDown,
    TrendingUp,
    Wallet,
    Wifi,
    X,
    Zap,
} from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { healthApi, marketApi, watchlistApi } from '../../api/client';
import Sparkline from '../../components/Charts/Sparkline';
import PriceTag from '../../components/Data/PriceTag';
import SkeletonLoader from '../../components/Data/SkeletonLoader';
import { useAlertStream, useLivePrice } from '../../hooks/useWebSocket';
import { formatCompact, formatCurrency, formatDate, formatPercent, priceColorClass, timeAgo } from '../../utils/format';
import './Dashboard.css';
import {
    CoachingPanel,
    GamificationPanel,
    GhostChartPanel,
    OpeningRangePanel,
    OptimizerPanel,
} from '../../components/Phase4';
import '../../components/Phase4/Phase4.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface AlertToast {
    id: number;
    message: string;
    ticker?: string;
    type: string;
    timestamp: Date;
}

/** Individual watchlist ticker with live WS price */
function LiveTickerTag({ ticker, onClick }: { ticker: string; onClick: () => void }) {
    const { price, connected } = useLivePrice(ticker);
    return (
        <button type="button" className="ticker-tag ticker-tag--live" onClick={onClick}>
            <span className="ticker-tag-symbol">{ticker}</span>
            {connected && price?.price != null && (
                <span className="ticker-tag-price">{formatCurrency(price.price)}</span>
            )}
            {connected && <span className="live-dot" title="Live" />}
        </button>
    );
}

export default function Dashboard() {
    const navigate = useNavigate();

    // ── TanStack Query helpers ──
    const extractData = (res: any) => res?.data ?? null;
    const extractArr = (res: any) => {
        const d = extractData(res);
        return Array.isArray(d) ? d : d?.data || d?.results || [];
    };

    const REFETCH = 60_000; // 60s auto-refresh

    // ── Queries ──
    const { data: fearGreedRaw } = useQuery({
        queryKey: ['dashboard', 'fearGreed'],
        queryFn: () => marketApi.getFearGreed(),
        refetchInterval: REFETCH,
    });
    const fearGreed = extractData(fearGreedRaw);

    const { data: moversRaw } = useQuery({
        queryKey: ['dashboard', 'movers'],
        queryFn: () => marketApi.getMovers(),
        refetchInterval: REFETCH,
    });
    const movers = extractArr(moversRaw).slice(0, 8);

    const { data: trendingRaw } = useQuery({
        queryKey: ['dashboard', 'trending'],
        queryFn: () => marketApi.getTrending(),
        refetchInterval: REFETCH,
    });
    const trending = extractArr(trendingRaw).slice(0, 8);

    const { data: healthRaw } = useQuery({
        queryKey: ['dashboard', 'health'],
        queryFn: () => healthApi.check(),
        refetchInterval: REFETCH,
    });
    const marketStatus = extractData(healthRaw)?.status === 'ok' ? 'Online' : healthRaw ? 'Degraded' : 'Loading...';

    const { data: watchlistRaw } = useQuery({
        queryKey: ['dashboard', 'watchlist'],
        queryFn: () => watchlistApi.getWatchlist(),
        refetchInterval: REFETCH,
    });
    const watchlist: string[] = (() => {
        const wl = extractData(watchlistRaw);
        return Array.isArray(wl) ? wl.map((w: any) => (typeof w === 'string' ? w : w.ticker || '')) : [];
    })();

    const { data: clockRaw } = useQuery({
        queryKey: ['dashboard', 'clock'],
        queryFn: () => marketApi.getMarketClock(),
        refetchInterval: REFETCH,
    });
    const marketClock = extractData(clockRaw);

    const { data: sectorsRaw } = useQuery({
        queryKey: ['dashboard', 'sectors'],
        queryFn: () => marketApi.getSectorPerformance(),
        refetchInterval: REFETCH,
    });
    const sectors = extractArr(sectorsRaw).slice(0, 12);

    const { data: earningsRaw } = useQuery({
        queryKey: ['dashboard', 'earnings'],
        queryFn: () => marketApi.getEarningsCalendar(20),
        refetchInterval: REFETCH,
    });
    const earnings = extractArr(earningsRaw).slice(0, 10);

    const { data: shortRaw } = useQuery({
        queryKey: ['dashboard', 'shortInterest'],
        queryFn: () => marketApi.getShortInterest(15),
        refetchInterval: REFETCH,
    });
    const shortInterest = extractArr(shortRaw).slice(0, 10);

    const { data: newsRaw } = useQuery({
        queryKey: ['dashboard', 'news'],
        queryFn: () => marketApi.getCombinedNews(undefined, 12),
        refetchInterval: REFETCH,
    });
    const newsFeed = extractArr(newsRaw).slice(0, 10);

    const { data: econRaw } = useQuery({
        queryKey: ['dashboard', 'economic'],
        queryFn: () => marketApi.getEconomicDashboard(),
        refetchInterval: REFETCH,
    });
    const economicData = extractData(econRaw);

    const { data: yieldRaw } = useQuery({
        queryKey: ['dashboard', 'yields'],
        queryFn: () => marketApi.getTreasuryYields(),
        refetchInterval: REFETCH,
    });
    const treasuryYields = extractData(yieldRaw);

    const { data: fgdRaw, dataUpdatedAt } = useQuery({
        queryKey: ['dashboard', 'fgDetailed'],
        queryFn: () => marketApi.getFearGreedDetailed(),
        refetchInterval: REFETCH,
    });
    const fgDetailed = extractData(fgdRaw);

    // ── Questrade Plus Queries ──
    const { data: perfRaw } = useQuery({
        queryKey: ['dashboard', 'performance'],
        queryFn: () => marketApi.getPortfolioPerformance(),
        refetchInterval: REFETCH,
    });
    const performance = extractData(perfRaw);

    const { data: divRaw } = useQuery({
        queryKey: ['dashboard', 'dividends'],
        queryFn: () => marketApi.getDividendCalendar(),
        refetchInterval: REFETCH * 5,
    });
    const dividends = extractData(divRaw);

    const { data: currRaw } = useQuery({
        queryKey: ['dashboard', 'currency'],
        queryFn: () => marketApi.getCurrencyExposure(),
        refetchInterval: REFETCH,
    });
    const currencyExposure = extractData(currRaw);

    const { data: mktStatusRaw } = useQuery({
        queryKey: ['dashboard', 'mktStatus'],
        queryFn: () => marketApi.getMarketStatus(),
        refetchInterval: REFETCH,
    });
    const mktStatus = extractData(mktStatusRaw);

    // ── Pre/Post-Market Workflow ──
    const { data: briefRaw } = useQuery({
        queryKey: ['dashboard', 'briefing'],
        queryFn: () => marketApi.getLatestBriefing(),
        refetchInterval: REFETCH * 5,
    });
    const briefing = extractData(briefRaw);

    const { data: journalRaw } = useQuery({
        queryKey: ['dashboard', 'journal'],
        queryFn: () => marketApi.getLatestJournal(),
        refetchInterval: REFETCH * 5,
    });
    const journal = extractData(journalRaw);

    const loading = !fearGreedRaw && !moversRaw;
    const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt) : null;

    // ── Alert toasts (WS — not query-managed) ──
    const [alerts, setAlerts] = useState<AlertToast[]>([]);
    const alertIdRef = useRef(0);

    // Alert stream via WebSocket
    const handleAlert = useCallback((data: Record<string, unknown>) => {
        const id = ++alertIdRef.current;
        const toast: AlertToast = {
            id,
            message: (data.message as string) || (data.alert as string) || JSON.stringify(data),
            ticker: data.ticker as string | undefined,
            type: (data.type as string) || 'alert',
            timestamp: new Date(),
        };
        setAlerts((prev) => [toast, ...prev].slice(0, 5));
        // Auto-dismiss after 8s
        setTimeout(() => {
            setAlerts((prev) => prev.filter((a) => a.id !== id));
        }, 8000);
    }, []);
    const { connected: alertsConnected } = useAlertStream(handleAlert);

    const fgValue = fearGreed?.value as number | undefined;
    const fgLabel = fearGreed?.label as string | undefined;

    const getFgColor = (val: number) => {
        if (val <= 25) return 'var(--accent-red)';
        if (val <= 45) return 'var(--accent-amber)';
        if (val <= 55) return 'var(--text-secondary)';
        return 'var(--accent-green)';
    };

    const dismissAlert = (id: number) => {
        setAlerts((prev) => prev.filter((a) => a.id !== id));
    };

    return (
        <div className="page-container">
            <div className="dashboard-header">
                <h1 className="page-title">
                    <Gauge size={28} /> Dashboard
                </h1>
                <div className="dashboard-meta">
                    {alertsConnected && (
                        <span className="ws-status" title="Alert stream connected">
                            <Wifi size={12} /> Live
                        </span>
                    )}
                    {lastUpdated && (
                        <span className="last-updated">
                            <RefreshCw size={11} />
                            {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    )}
                </div>
            </div>

            {/* Alert Toast Stack */}
            {alerts.length > 0 && (
                <div className="alert-toast-stack">
                    {alerts.map((a) => (
                        <div key={a.id} className="alert-toast">
                            <Bell size={14} />
                            <div className="alert-toast-body">
                                {a.ticker && <strong>{a.ticker}</strong>}
                                <span>{a.message}</span>
                            </div>
                            <button type="button" className="alert-toast-close" onClick={() => dismissAlert(a.id)}>
                                <X size={12} />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Row 1: Status + F&G + Watchlist ── */}
            <div className="grid-3 dashboard-top">
                {/* 1. Market Status + Clock */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Clock size={14} /> Market Status
                        </span>
                        <span className={`status-dot ${marketStatus === 'Online' ? 'online' : 'degraded'}`} />
                    </div>
                    <div className="status-value">{marketStatus}</div>
                    {marketClock && (
                        <div className="clock-details">
                            {marketClock.is_open != null && (
                                <div className="clock-row">
                                    <span>Market</span>
                                    <span className={`badge badge-${marketClock.is_open ? 'green' : 'red'}`}>
                                        {marketClock.is_open ? 'OPEN' : 'CLOSED'}
                                    </span>
                                </div>
                            )}
                            {marketClock.next_open && (
                                <div className="clock-row">
                                    <span>Next Open</span>
                                    <span className="clock-time">{formatDate(marketClock.next_open)}</span>
                                </div>
                            )}
                            {marketClock.next_close && (
                                <div className="clock-row">
                                    <span>Next Close</span>
                                    <span className="clock-time">{formatDate(marketClock.next_close)}</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* 2. Fear & Greed */}
                <div className="card fg-card">
                    <div className="card-header">
                        <span className="card-title">Fear & Greed</span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 60 }} />
                    ) : fgValue != null ? (
                        <div className="fg-display">
                            <div className="fg-value" style={{ color: getFgColor(fgValue) }}>
                                {fgValue}
                            </div>
                            <div className="fg-label">{fgLabel || 'Neutral'}</div>
                            <div className="fg-bar-track">
                                <div
                                    className="fg-bar-fill"
                                    style={{
                                        width: `${fgValue}%`,
                                        background: getFgColor(fgValue),
                                    }}
                                />
                            </div>
                        </div>
                    ) : (
                        <div className="text-muted">Unavailable</div>
                    )}
                </div>

                {/* 3. Watchlist — LIVE prices */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">Watchlist</span>
                        <span className="badge badge-blue">{watchlist.length}</span>
                    </div>
                    {watchlist.length > 0 ? (
                        <div className="watchlist-tags">
                            {watchlist.slice(0, 10).map((t) => (
                                <LiveTickerTag key={t} ticker={t} onClick={() => navigate(`/stock/${t}`)} />
                            ))}
                        </div>
                    ) : (
                        <div className="text-muted">No tickers tracked</div>
                    )}
                </div>
            </div>

            {/* ── Row 2: Top Movers ── */}
            <div className="card movers-card">
                <div className="card-header">
                    <span className="card-title">
                        <TrendingUp size={16} /> Top Movers
                    </span>
                </div>
                {loading ? (
                    <SkeletonLoader variant="card" height="200px" />
                ) : movers.length > 0 ? (
                    <div className="grid-4 movers-grid">
                        {movers.map((m: any, i: number) => {
                            const symbol = m.ticker || m.symbol || m.name || `#${i}`;
                            const chg = m.change_percent ?? m.perf ?? m.change ?? 0;
                            const px = m.close ?? m.price ?? 0;
                            return (
                                <button
                                    type="button"
                                    key={i}
                                    className="mover-card"
                                    onClick={() => navigate(`/stock/${symbol}`)}
                                >
                                    <div className="mover-ticker">{symbol}</div>
                                    <div className="mover-price">
                                        <PriceTag price={px} change={chg} size="sm" showFlash={false} />
                                    </div>
                                    <Sparkline
                                        data={[
                                            px * (1 - (Math.abs(chg) / 100) * 1.2),
                                            px * (1 - (Math.abs(chg) / 100) * 0.7),
                                            px * (1 - (Math.abs(chg) / 100) * 0.4),
                                            px * (1 - (chg / 100) * 0.1),
                                            px,
                                        ]}
                                        color="auto"
                                        width={70}
                                        height={20}
                                    />
                                    <div className={`mover-change ${priceColorClass(chg)}`}>
                                        {chg > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                        {formatPercent(chg)}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                ) : (
                    <div className="empty-state">
                        <TrendingUp size={32} />
                        <span>No mover data available</span>
                    </div>
                )}
            </div>

            {/* ── Row 3: Two-column — Trending + Sector Performance ── */}
            <div className="grid-2 dashboard-mid">
                {/* 5. Trending (WSB) */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Newspaper size={16} /> WSB Trending
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : trending.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Mentions</th>
                                    <th>Sentiment</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trending.map((t: any, i: number) => (
                                    <tr
                                        key={i}
                                        onClick={() => navigate(`/stock/${t.ticker || t.symbol}`)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <td>{t.ticker || t.symbol || ''}</td>
                                        <td>{t.mentions || t.count || 0}</td>
                                        <td>
                                            <span
                                                className={`badge ${
                                                    t.sentiment === 'bullish'
                                                        ? 'badge-green'
                                                        : t.sentiment === 'bearish'
                                                          ? 'badge-red'
                                                          : 'badge-amber'
                                                }`}
                                            >
                                                {t.sentiment || 'neutral'}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">
                            <Newspaper size={32} />
                            <span>No trending data</span>
                        </div>
                    )}
                </div>

                {/* 6. Sector Performance Heatmap */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <BarChart3 size={16} /> Sector Performance
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : sectors.length > 0 ? (
                        <div className="sector-grid">
                            {sectors.map((s: any, i: number) => {
                                const chg = s.change ?? s.change_percent ?? s.perf ?? 0;
                                return (
                                    <div key={i} className={`sector-tile ${priceColorClass(chg)}`}>
                                        <div className="sector-name">{s.sector || s.name || s.description || ''}</div>
                                        <div className="sector-change">{formatPercent(chg)}</div>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <BarChart3 size={32} />
                            <span>No sector data</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Row 4: Two-column — Earnings + Short Squeeze ── */}
            <div className="grid-2 dashboard-mid">
                {/* 7. Earnings Calendar */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Calendar size={16} /> Earnings Calendar
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : earnings.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Date</th>
                                    <th>Time</th>
                                    <th>EPS Est</th>
                                </tr>
                            </thead>
                            <tbody>
                                {earnings.map((e: any, i: number) => (
                                    <tr
                                        key={i}
                                        onClick={() => navigate(`/stock/${e.ticker || e.symbol}`)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <td>
                                            <strong>{e.ticker || e.symbol || ''}</strong>
                                        </td>
                                        <td>{formatDate(e.date || e.earnings_date || '')}</td>
                                        <td>
                                            <span className="badge badge-blue">{e.time || e.when || '—'}</span>
                                        </td>
                                        <td>
                                            {e.eps_estimate != null ? `$${Number(e.eps_estimate).toFixed(2)}` : '—'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">
                            <Calendar size={32} />
                            <span>No earnings data</span>
                        </div>
                    )}
                </div>

                {/* 8. Short Squeeze Scanner */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Zap size={16} /> Short Squeeze Scanner
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : shortInterest.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Short %</th>
                                    <th>Float</th>
                                    <th>Volume</th>
                                </tr>
                            </thead>
                            <tbody>
                                {shortInterest.map((s: any, i: number) => (
                                    <tr
                                        key={i}
                                        onClick={() => navigate(`/stock/${s.ticker || s.symbol}`)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <td>
                                            <strong>{s.ticker || s.symbol || ''}</strong>
                                        </td>
                                        <td className="price-down">
                                            {s.short_percent != null
                                                ? `${Number(s.short_percent).toFixed(1)}%`
                                                : s.short_interest
                                                  ? formatCompact(s.short_interest)
                                                  : '—'}
                                        </td>
                                        <td>{formatCompact(s.float_shares || s.float)}</td>
                                        <td>{formatCompact(s.volume)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">
                            <Zap size={32} />
                            <span>No short squeeze data</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Row 5: Combined News Feed ── */}
            <div className="card news-feed-card">
                <div className="card-header">
                    <span className="card-title">
                        <Newspaper size={16} /> Market News
                    </span>
                </div>
                {loading ? (
                    <div className="skeleton" style={{ width: '100%', height: 200 }} />
                ) : newsFeed.length > 0 ? (
                    <div className="news-list">
                        {newsFeed.map((n: any, i: number) => (
                            <a
                                key={i}
                                className="news-item"
                                href={n.url || '#'}
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                <div className="news-headline">{n.headline || n.title || ''}</div>
                                <div className="news-meta">
                                    <span>{n.source || ''}</span>
                                    <span>{timeAgo(n.datetime || n.date || n.published_at || '')}</span>
                                    <ExternalLink size={12} />
                                </div>
                            </a>
                        ))}
                    </div>
                ) : (
                    <div className="empty-state">
                        <Newspaper size={32} />
                        <span>No news available</span>
                    </div>
                )}
            </div>

            {/* ── Row 6: Two-column — Economic Pulse + Detailed F&G ── */}
            <div className="grid-2 dashboard-mid">
                {/* 10. Economic Pulse */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <DollarSign size={16} /> Economic Pulse
                        </span>
                        {treasuryYields?.inverted && (
                            <span className="badge badge-red" title="Yield curve is inverted — recession signal">
                                <AlertTriangle size={10} /> Inverted
                            </span>
                        )}
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : economicData ? (
                        <div className="econ-grid">
                            {[
                                { label: 'GDP', key: 'gdp', fmt: (v: number) => `${v?.toFixed(1)}%` },
                                { label: 'CPI', key: 'cpi', fmt: (v: number) => `${v?.toFixed(1)}%` },
                                { label: 'Unemployment', key: 'unemployment', fmt: (v: number) => `${v?.toFixed(1)}%` },
                                { label: 'Fed Rate', key: 'fed_rate', fmt: (v: number) => `${v?.toFixed(2)}%` },
                            ].map((item) => {
                                const val = economicData[item.key]?.value ?? economicData[item.key] ?? null;
                                return (
                                    <div key={item.key} className="econ-card">
                                        <div className="econ-label">{item.label}</div>
                                        <div className="econ-value">{val != null ? item.fmt(val) : '—'}</div>
                                    </div>
                                );
                            })}
                            {treasuryYields && (
                                <>
                                    <div className="econ-card">
                                        <div className="econ-label">2Y Yield</div>
                                        <div className="econ-value">
                                            {(treasuryYields.us_2y ?? treasuryYields['2y'])?.toFixed(2) ?? '—'}%
                                        </div>
                                    </div>
                                    <div className="econ-card">
                                        <div className="econ-label">10Y Yield</div>
                                        <div className="econ-value">
                                            {(treasuryYields.us_10y ?? treasuryYields['10y'])?.toFixed(2) ?? '—'}%
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <DollarSign size={32} />
                            <span>Economic data unavailable</span>
                        </div>
                    )}
                </div>

                {/* 11. Detailed Fear & Greed */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Activity size={16} /> Fear & Greed Breakdown
                        </span>
                        {fgDetailed?.value != null && (
                            <span
                                className={`badge badge-${fgDetailed.value >= 55 ? 'green' : fgDetailed.value <= 45 ? 'red' : 'amber'}`}
                            >
                                {fgDetailed.value}
                            </span>
                        )}
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : fgDetailed?.sub_indicators && Array.isArray(fgDetailed.sub_indicators) ? (
                        <div className="fg-detailed-grid">
                            {fgDetailed.sub_indicators.map((sub: any, i: number) => (
                                <div key={i} className="fg-sub-row">
                                    <div className="fg-sub-label">
                                        {sub.name || sub.indicator || `Indicator ${i + 1}`}
                                    </div>
                                    <div className="fg-sub-bar-track">
                                        <div
                                            className="fg-sub-bar-fill"
                                            style={{
                                                width: `${Math.min(100, Math.max(0, sub.value ?? 50))}%`,
                                                background: getFgColor(sub.value ?? 50),
                                            }}
                                        />
                                    </div>
                                    <div className="fg-sub-value" style={{ color: getFgColor(sub.value ?? 50) }}>
                                        {sub.value ?? '—'}
                                    </div>
                                    <div className="fg-sub-classification">{sub.classification || sub.label || ''}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Activity size={32} />
                            <span>No detailed F&G data</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Row 7: Questrade Portfolio Intelligence ── */}
            <div className="grid-2 dashboard-mid">
                {/* 12. Portfolio Performance */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Wallet size={16} /> Portfolio P&L
                        </span>
                        {performance?.summary?.net_performance != null && (
                            <span
                                className={`badge badge-${performance.summary.net_performance >= 0 ? 'green' : 'red'}`}
                            >
                                {performance.summary.net_performance >= 0 ? '+' : ''}
                                {formatCurrency(performance.summary.net_performance)}
                            </span>
                        )}
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : performance?.summary ? (
                        <div className="econ-grid">
                            {[
                                { label: 'Unrealized', key: 'total_unrealized_pnl', color: true },
                                { label: 'Realized', key: 'total_realized_pnl', color: true },
                                { label: 'Dividends', key: 'total_dividends' },
                                { label: 'Commissions', key: 'total_commissions' },
                                { label: 'Fees', key: 'total_fees' },
                                { label: 'Net P&L', key: 'net_performance', color: true },
                            ].map((item) => {
                                const val: number = performance.summary[item.key] ?? 0;
                                return (
                                    <div key={item.key} className="econ-card">
                                        <div className="econ-label">{item.label}</div>
                                        <div
                                            className="econ-value"
                                            style={
                                                item.color
                                                    ? { color: val >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }
                                                    : undefined
                                            }
                                        >
                                            {val >= 0 ? '+' : ''}
                                            {formatCurrency(val)}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Wallet size={32} />
                            <span>Connect Questrade for P&L data</span>
                        </div>
                    )}
                </div>

                {/* 13. Dividend Calendar */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Calendar size={16} /> Dividend Calendar
                        </span>
                        {dividends?.total_projected_monthly_income != null && (
                            <span className="badge badge-green">
                                {formatCurrency(dividends.total_projected_monthly_income)}/mo
                            </span>
                        )}
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 120 }} />
                    ) : dividends?.holdings_with_dividends?.length > 0 ? (
                        <div className="compact-list">
                            {dividends.holdings_with_dividends.slice(0, 6).map((d: any) => (
                                <div key={d.ticker} className="compact-row">
                                    <span className="ticker-cell">{d.ticker}</span>
                                    <span className="yield-cell" style={{ color: 'var(--accent-green)' }}>
                                        {d.yield_pct?.toFixed(2) ?? '—'}%
                                    </span>
                                    <span className="date-cell">{d.ex_date ? formatDate(d.ex_date) : '—'}</span>
                                    <span className="income-cell">
                                        {formatCurrency(d.projected_quarterly_income)}/qtr
                                    </span>
                                </div>
                            ))}
                            {dividends.total_holdings > 6 && (
                                <div className="compact-row" style={{ opacity: 0.6, justifyContent: 'center' }}>
                                    +{dividends.total_holdings - 6} more holdings
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Calendar size={32} />
                            <span>No dividend holdings</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Row 8: Currency Exposure + Exchange Status ── */}
            <div className="grid-2 dashboard-mid">
                {/* 14. Currency Exposure */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Globe size={16} /> Currency Exposure
                        </span>
                        {currencyExposure?.total_portfolio_value != null && (
                            <span className="badge badge-amber">
                                {formatCurrency(currencyExposure.total_portfolio_value)}
                            </span>
                        )}
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 100 }} />
                    ) : currencyExposure?.currencies ? (
                        <div className="econ-grid">
                            {Object.entries(currencyExposure.currencies).map(([curr, info]: [string, any]) => (
                                <div key={curr} className="econ-card">
                                    <div className="econ-label">{curr}</div>
                                    <div className="econ-value">{formatCurrency(info.total_market_value)}</div>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                        {info.allocation_pct?.toFixed(1)}% · {info.position_count} positions
                                    </div>
                                </div>
                            ))}
                            {currencyExposure.cash_balances &&
                                Object.entries(currencyExposure.cash_balances).map(([curr, bal]: [string, any]) => (
                                    <div key={`cash-${curr}`} className="econ-card">
                                        <div className="econ-label">{curr} Cash</div>
                                        <div className="econ-value">{formatCurrency(bal.cash)}</div>
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                            BP: {formatCurrency(bal.buying_power)}
                                        </div>
                                    </div>
                                ))}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Globe size={32} />
                            <span>Currency data unavailable</span>
                        </div>
                    )}
                </div>

                {/* 15. Exchange Status */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Radio size={16} /> Exchange Status
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ width: '100%', height: 100 }} />
                    ) : mktStatus?.markets?.length > 0 ? (
                        <div className="compact-list">
                            {mktStatus.markets.map((m: any) => (
                                <div key={m.name} className="compact-row">
                                    <span className="ticker-cell">{m.name}</span>
                                    <span
                                        className={`badge badge-${m.status === 'open' ? 'green' : m.status === 'pre_market' ? 'amber' : m.status === 'after_hours' ? 'amber' : 'red'}`}
                                    >
                                        {m.status === 'open'
                                            ? 'OPEN'
                                            : m.status === 'pre_market'
                                              ? 'PRE'
                                              : m.status === 'after_hours'
                                                ? 'AH'
                                                : 'CLOSED'}
                                    </span>
                                    <span className="date-cell" style={{ fontSize: '0.7rem' }}>
                                        {m.start_time && m.end_time
                                            ? `${new Date(m.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} — ${new Date(m.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                                            : '—'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Radio size={32} />
                            <span>Exchange data unavailable</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Row 9: Morning Brief + Trading Journal ── */}
            <div className="grid-2 dashboard-mid">
                {/* Morning Briefing */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Briefcase size={16} /> Morning Briefing
                        </span>
                        {briefing?.date && <span className="badge badge-blue">{briefing.date}</span>}
                    </div>
                    {briefing ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {briefing.summary && (
                                <div className="text-muted" style={{ fontSize: '0.82rem', lineHeight: 1.5 }}>
                                    {briefing.summary}
                                </div>
                            )}
                            {briefing.watchlist_alerts &&
                                Array.isArray(briefing.watchlist_alerts) &&
                                briefing.watchlist_alerts.length > 0 && (
                                    <div className="compact-list" style={{ maxHeight: 180, overflow: 'auto' }}>
                                        {briefing.watchlist_alerts.slice(0, 6).map((alert: any, i: number) => (
                                            <div key={i} className="compact-row">
                                                <span className="ticker-cell">
                                                    {alert.ticker || alert.symbol || '—'}
                                                </span>
                                                <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                                                    {alert.message || alert.reason || JSON.stringify(alert)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Briefcase size={32} />
                            <span>No morning briefing yet</span>
                        </div>
                    )}
                </div>

                {/* Trading Journal */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <BookOpen size={16} /> Trading Journal
                        </span>
                        {journal?.date && <span className="badge badge-amber">{journal.date}</span>}
                    </div>
                    {journal ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {journal.narrative && (
                                <div className="text-muted" style={{ fontSize: '0.82rem', lineHeight: 1.5 }}>
                                    {journal.narrative}
                                </div>
                            )}
                            <div className="econ-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                                <div className="econ-card">
                                    <div className="econ-label">Trades</div>
                                    <div className="econ-value">{journal.total_trades ?? '—'}</div>
                                </div>
                                <div className="econ-card">
                                    <div className="econ-label">Win Rate</div>
                                    <div
                                        className={`econ-value ${(journal.win_rate || 0) > 0.5 ? 'price-up' : 'price-down'}`}
                                    >
                                        {journal.win_rate != null ? `${(journal.win_rate * 100).toFixed(0)}%` : '—'}
                                    </div>
                                </div>
                                <div className="econ-card">
                                    <div className="econ-label">P&L</div>
                                    <div className={`econ-value ${(journal.pnl || 0) > 0 ? 'price-up' : 'price-down'}`}>
                                        {journal.pnl != null ? formatCurrency(journal.pnl) : '—'}
                                    </div>
                                </div>
                                <div className="econ-card">
                                    <div className="econ-label">Best Trade</div>
                                    <div className="econ-value price-up">{journal.best_trade || '—'}</div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="empty-state">
                            <BookOpen size={32} />
                            <span>No journal entry today</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Row 10: Phase 4 — Coaching + Gamification ── */}
            <div className="grid-2 dashboard-mid">
                <CoachingPanel />
                <GamificationPanel />
            </div>

            {/* ── Row 10: Phase 4 — Opening Range + Optimizer ── */}
            <div className="grid-2 dashboard-mid">
                <OpeningRangePanel ticker="SPY" />
                <OptimizerPanel />
            </div>

            {/* ── Row 11: Phase 4 — Ghost Charts ── */}
            <GhostChartPanel ticker="SPY" />
        </div>
    );
}
