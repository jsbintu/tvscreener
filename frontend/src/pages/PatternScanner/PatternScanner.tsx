/**
 * PatternScanner — Real-time multi-ticker pattern scanning dashboard
 *
 * Features:
 *   1. Watchlist manager: Add/remove tickers for automated pattern scanning
 *   2. Live scan results: View detected patterns per ticker
 *   3. Quick-scan: Trigger on-demand pattern scan for any ticker
 *   4. Emerging patterns: See patterns that are still forming
 *   5. WebSocket alerts: Pattern detections arrive in real-time
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    ArrowDownCircle,
    ArrowUpCircle,
    Crosshair,
    Eye,
    Loader2,
    Minus,
    Plus,
    RefreshCw,
    Trash2,
    Zap,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { marketApi } from '../../api/client';
import PatternChart from '../../components/Charts/PatternChart';
import SkeletonLoader from '../../components/Data/SkeletonLoader';
import { useAlertStream } from '../../hooks/useWebSocket';
import './PatternScanner.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface LiveAlert {
    id: number;
    ticker: string;
    pattern: string;
    direction: string;
    confidence: number;
    timestamp: Date;
}

let alertCounter = 0;

export default function PatternScanner() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [tickerInput, setTickerInput] = useState('');
    const [scanningTicker, setScanningTicker] = useState<string | null>(null);
    const [quickScanResult, setQuickScanResult] = useState<any>(null);
    const [liveAlerts, setLiveAlerts] = useState<LiveAlert[]>([]);

    // ── Fetch current watchlist ──
    const { data: wlRaw, isLoading } = useQuery({
        queryKey: ['patternWatchlist'],
        queryFn: () => marketApi.getPatternWatchlist(),
        refetchInterval: 30_000,
    });
    const watchlist: string[] = wlRaw?.data?.watchlist ?? [];
    const scanResults: Record<string, any> = wlRaw?.data?.results ?? {};

    // ── Mutations ──
    const addMutation = useMutation({
        mutationFn: (tickers: string[]) => marketApi.managePatternWatchlist(tickers, 'add'),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patternWatchlist'] }),
    });

    const removeMutation = useMutation({
        mutationFn: (tickers: string[]) => marketApi.managePatternWatchlist(tickers, 'remove'),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patternWatchlist'] }),
    });

    // ── Live WebSocket alerts ──
    useAlertStream(
        useCallback((alert: any) => {
            if (alert.alert_type === 'pattern_detected') {
                setLiveAlerts((prev) =>
                    [
                        {
                            id: ++alertCounter,
                            ticker: alert.ticker || '???',
                            pattern: alert.pattern || 'Unknown',
                            direction: alert.direction || 'neutral',
                            confidence: alert.confidence || 0,
                            timestamp: new Date(),
                        },
                        ...prev,
                    ].slice(0, 100),
                );
            }
        }, []),
    );

    // ── Handlers ──
    const handleAddTicker = (e: React.FormEvent) => {
        e.preventDefault();
        const ticker = tickerInput.trim().toUpperCase();
        if (ticker && !watchlist.includes(ticker)) {
            addMutation.mutate([ticker]);
            setTickerInput('');
        }
    };

    const handleRemoveTicker = (ticker: string) => {
        removeMutation.mutate([ticker]);
    };

    const handleQuickScan = async (ticker: string) => {
        setScanningTicker(ticker);
        setQuickScanResult(null);
        try {
            const res = await marketApi.triggerPatternScan(ticker);
            setQuickScanResult({ ticker, ...res.data });
        } catch {
            setQuickScanResult({ ticker, error: 'Scan failed' });
        } finally {
            setScanningTicker(null);
        }
    };

    // ── Helpers ──
    const dirIcon = (dir: string) => {
        if (dir === 'bullish') return <ArrowUpCircle size={14} className="dir-bull" />;
        if (dir === 'bearish') return <ArrowDownCircle size={14} className="dir-bear" />;
        return <Minus size={14} className="dir-neutral" />;
    };

    const patternCount = (result: any) => {
        if (!result?.last_scan) return 0;
        const s = result.last_scan;
        return (
            (s.candlestick_patterns?.length || 0) +
            (s.chart_patterns?.length || 0) +
            (s.gap_patterns?.length || 0) +
            (s.volume_patterns?.length || 0)
        );
    };

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">
                    <Crosshair size={22} />
                    Pattern Scanner
                </h1>
                <p className="page-subtitle">
                    Real-time multi-ticker pattern detection — 40+ candlestick & chart patterns
                </p>
            </div>

            <div className="scanner-layout">
                {/* ── Left: Watchlist Manager ── */}
                <div className="scanner-watchlist card">
                    <div className="scanner-card-header">
                        <h3>
                            <Eye size={16} /> Scan Watchlist
                        </h3>
                        <span className="badge">{watchlist.length}</span>
                    </div>

                    <form className="scanner-add-form" onSubmit={handleAddTicker}>
                        <input
                            type="text"
                            className="scanner-ticker-input"
                            placeholder="Add ticker (e.g. AAPL)"
                            value={tickerInput}
                            onChange={(e) => setTickerInput(e.target.value)}
                            maxLength={10}
                        />
                        <button
                            type="submit"
                            className="btn btn--primary btn--sm"
                            disabled={!tickerInput.trim() || addMutation.isPending}
                        >
                            <Plus size={14} /> Add
                        </button>
                    </form>

                    {isLoading ? (
                        <SkeletonLoader lines={5} />
                    ) : watchlist.length === 0 ? (
                        <div className="scanner-empty">Add tickers above to start scanning for patterns</div>
                    ) : (
                        <div className="scanner-ticker-list">
                            {watchlist.map((ticker) => {
                                const result = scanResults[ticker];
                                const count = patternCount(result);
                                const bias = result?.last_scan?.overall_bias;
                                return (
                                    <div key={ticker} className="scanner-ticker-row">
                                        <button
                                            type="button"
                                            className="scanner-ticker-name"
                                            onClick={() => navigate(`/stock/${ticker}`)}
                                        >
                                            {ticker}
                                        </button>
                                        <div className="scanner-ticker-meta">
                                            {count > 0 && (
                                                <span
                                                    className={`scanner-pattern-count ${bias === 'bullish' ? 'bullish' : bias === 'bearish' ? 'bearish' : ''}`}
                                                >
                                                    {count} pattern{count !== 1 ? 's' : ''}
                                                </span>
                                            )}
                                            <button
                                                type="button"
                                                className="scanner-action-btn"
                                                title={`Quick scan ${ticker}`}
                                                onClick={() => handleQuickScan(ticker)}
                                                disabled={scanningTicker === ticker}
                                            >
                                                {scanningTicker === ticker ? (
                                                    <Loader2 size={14} className="spin" />
                                                ) : (
                                                    <Zap size={14} />
                                                )}
                                            </button>
                                            <button
                                                type="button"
                                                className="scanner-action-btn scanner-action-btn--danger"
                                                title={`Remove ${ticker}`}
                                                onClick={() => handleRemoveTicker(ticker)}
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* ── Right: Results ── */}
                <div className="scanner-results">
                    {/* Live Alerts */}
                    <div className="card">
                        <div className="scanner-card-header">
                            <h3>
                                <Zap size={16} /> Live Pattern Alerts
                            </h3>
                            {liveAlerts.length > 0 && (
                                <button type="button" className="notif-clear-btn" onClick={() => setLiveAlerts([])}>
                                    Clear
                                </button>
                            )}
                        </div>
                        {liveAlerts.length === 0 ? (
                            <div className="scanner-empty">
                                Waiting for pattern detections… Scans run every 5 minutes during market hours.
                            </div>
                        ) : (
                            <div className="scanner-alert-list">
                                {liveAlerts.map((alert) => (
                                    <button
                                        type="button"
                                        key={alert.id}
                                        className="scanner-alert-row"
                                        onClick={() => navigate(`/stock/${alert.ticker}`)}
                                    >
                                        {dirIcon(alert.direction)}
                                        <span className="scanner-alert-ticker">{alert.ticker}</span>
                                        <span className="scanner-alert-pattern">{alert.pattern}</span>
                                        <span className="scanner-alert-conf">
                                            {Math.round(alert.confidence * 100)}%
                                        </span>
                                        <span className="scanner-alert-time">
                                            {alert.timestamp.toLocaleTimeString()}
                                        </span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Quick Scan Results */}
                    {quickScanResult && (
                        <div className="card">
                            <div className="scanner-card-header">
                                <h3>
                                    <RefreshCw size={16} />
                                    Quick Scan — {quickScanResult.ticker}
                                </h3>
                                <span className={`scanner-bias-badge ${quickScanResult.overall_bias || ''}`}>
                                    {quickScanResult.overall_bias || 'neutral'}
                                </span>
                            </div>
                            {quickScanResult.error ? (
                                <div className="scanner-empty">{quickScanResult.error}</div>
                            ) : (
                                <div className="scanner-scan-grid">
                                    {/* Candlestick Patterns */}
                                    {quickScanResult.candlestick_patterns?.length > 0 && (
                                        <div className="scanner-section">
                                            <h4 className="scanner-section-title">Candlestick Patterns</h4>
                                            <div className="scanner-chips">
                                                {quickScanResult.candlestick_patterns.map((p: any, i: number) => (
                                                    <span key={i} className={`pattern-chip ${p.direction || ''}`}>
                                                        {dirIcon(p.direction)} {p.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {/* Chart Patterns */}
                                    {quickScanResult.chart_patterns?.length > 0 && (
                                        <div className="scanner-section">
                                            <h4 className="scanner-section-title">Chart Patterns</h4>
                                            <div className="scanner-chips">
                                                {quickScanResult.chart_patterns.map((p: any, i: number) => (
                                                    <span key={i} className={`pattern-chip ${p.direction || ''}`}>
                                                        {dirIcon(p.direction)} {p.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {/* Gap Patterns */}
                                    {quickScanResult.gap_patterns?.length > 0 && (
                                        <div className="scanner-section">
                                            <h4 className="scanner-section-title">Gap Patterns</h4>
                                            <div className="scanner-chips">
                                                {quickScanResult.gap_patterns.map((p: any, i: number) => (
                                                    <span key={i} className={`pattern-chip ${p.direction || ''}`}>
                                                        {dirIcon(p.direction)} {p.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {/* Volume Patterns */}
                                    {quickScanResult.volume_patterns?.length > 0 && (
                                        <div className="scanner-section">
                                            <h4 className="scanner-section-title">Volume Patterns</h4>
                                            <div className="scanner-chips">
                                                {quickScanResult.volume_patterns.map((p: any, i: number) => (
                                                    <span key={i} className={`pattern-chip ${p.direction || ''}`}>
                                                        {dirIcon(p.direction)} {p.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {/* Emerging Patterns */}
                                    {quickScanResult.emerging_patterns?.length > 0 && (
                                        <div className="scanner-section scanner-section--emerging">
                                            <h4 className="scanner-section-title">🔮 Emerging (Forming)</h4>
                                            <div className="scanner-chips">
                                                {quickScanResult.emerging_patterns.map((p: any, i: number) => (
                                                    <span key={i} className="pattern-chip emerging">
                                                        {p.name} — {Math.round((p.completion || 0) * 100)}% formed
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {/* Fibonacci */}
                                    {quickScanResult.fibonacci && (
                                        <div className="scanner-section">
                                            <h4 className="scanner-section-title">Fibonacci Levels</h4>
                                            <div className="scanner-fib-grid">
                                                {Object.entries(quickScanResult.fibonacci.retracement_levels || {}).map(
                                                    ([k, v]) => (
                                                        <div key={k} className="scanner-fib-row">
                                                            <span className="scanner-fib-label">{k}</span>
                                                            <span className="scanner-fib-value">
                                                                ${(v as number).toFixed(2)}
                                                            </span>
                                                        </div>
                                                    ),
                                                )}
                                            </div>
                                        </div>
                                    )}
                                    {/* Summary */}
                                    <div className="scanner-section">
                                        <h4 className="scanner-section-title">Summary</h4>
                                        <div className="scanner-summary-row">
                                            <span>
                                                Total: <strong>{quickScanResult.pattern_count ?? 0}</strong>
                                            </span>
                                            <span className="price-up">
                                                Bullish: <strong>{quickScanResult.bullish_count ?? 0}</strong>
                                            </span>
                                            <span className="price-down">
                                                Bearish: <strong>{quickScanResult.bearish_count ?? 0}</strong>
                                            </span>
                                            <span>
                                                New: <strong>{quickScanResult.new_pattern_count ?? 0}</strong>
                                            </span>
                                        </div>
                                    </div>
                                    {/* Mini PatternChart for quick scan */}
                                    <div className="scanner-mini-chart">
                                        <PatternChart ticker={quickScanResult.ticker} height={320} mini />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Watchlist Scan Status */}
                    {watchlist.length > 0 && (
                        <div className="card">
                            <div className="scanner-card-header">
                                <h3>
                                    <Crosshair size={16} /> Watchlist Scan Status
                                </h3>
                            </div>
                            <div className="scanner-status-table">
                                <div className="scanner-status-header">
                                    <span>Ticker</span>
                                    <span>Patterns</span>
                                    <span>Bias</span>
                                    <span>Alerts</span>
                                </div>
                                {watchlist.map((ticker) => {
                                    const result = scanResults[ticker];
                                    const scan = result?.last_scan;
                                    const alerts = result?.recent_alerts || [];
                                    const count = patternCount(result);
                                    return (
                                        <button
                                            type="button"
                                            key={ticker}
                                            className="scanner-status-row"
                                            onClick={() => navigate(`/stock/${ticker}`)}
                                        >
                                            <span className="scanner-status-ticker">{ticker}</span>
                                            <span className={`scanner-status-count ${count > 0 ? 'has-patterns' : ''}`}>
                                                {scan ? count : '—'}
                                            </span>
                                            <span className={`scanner-status-bias ${scan?.overall_bias || ''}`}>
                                                {scan?.overall_bias || '—'}
                                            </span>
                                            <span className="scanner-status-alerts">
                                                {alerts.length > 0 ? `${alerts.length} recent` : '—'}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
