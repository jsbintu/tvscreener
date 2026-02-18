import { useQuery } from '@tanstack/react-query';
import { Bell, BellRing, Download, ListChecks, Plus, Trash2 } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { watchlistApi } from '../../api/client';
import SkeletonLoader from '../../components/Data/SkeletonLoader';
import { useAlertStream } from '../../hooks/useWebSocket';
import { exportToCSV } from '../../utils/export';
import './Watchlist.css';

interface WatchItem {
    ticker: string;
    added_at?: string;
}

interface AlertItem {
    id?: string;
    ticker: string;
    threshold: number;
    direction: string;
    triggered?: boolean;
}

export default function Watchlist() {
    const navigate = useNavigate();
    const [newTicker, setNewTicker] = useState('');
    const [alertTicker, setAlertTicker] = useState('');
    const [alertThreshold, setAlertThreshold] = useState('');
    const [alertDir, setAlertDir] = useState('above');
    const [liveAlerts, setLiveAlerts] = useState<Record<string, unknown>[]>([]);

    const onAlert = useCallback((data: Record<string, unknown>) => {
        setLiveAlerts((prev) => [data, ...prev].slice(0, 10));
    }, []);
    useAlertStream(onAlert);

    // TanStack Query — watchlist + alerts
    const { data: itemsRaw, isLoading: wlLoading } = useQuery({
        queryKey: ['watchlist', 'items'],
        queryFn: async () => {
            const r = await watchlistApi.getWatchlist();
            const d = r.data;
            return Array.isArray(d) ? d : d?.data || [];
        },
    });
    const [items, setItems] = useState<WatchItem[]>([]);
    // Sync query data into local state for optimistic mutations
    if (itemsRaw && items.length === 0 && itemsRaw.length > 0) {
        setItems(itemsRaw);
    }

    const { data: alertsRaw, isLoading: alLoading } = useQuery({
        queryKey: ['watchlist', 'alerts'],
        queryFn: async () => {
            const r = await watchlistApi.getAlerts();
            const d = r.data;
            return Array.isArray(d) ? d : d?.data || [];
        },
    });
    const [alerts, setAlerts] = useState<AlertItem[]>([]);
    if (alertsRaw && alerts.length === 0 && alertsRaw.length > 0) {
        setAlerts(alertsRaw);
    }

    const loading = wlLoading || alLoading;

    const addTicker = async () => {
        const t = newTicker.trim().toUpperCase();
        if (!t) return;
        try {
            await watchlistApi.addTicker(t);
            setItems((prev) => [...prev, { ticker: t }]);
            setNewTicker('');
        } catch {
            /* ignore */
        }
    };

    const removeTicker = async (ticker: string) => {
        try {
            await watchlistApi.removeTicker(ticker);
            setItems((prev) => prev.filter((i) => i.ticker !== ticker));
        } catch {
            /* ignore */
        }
    };

    const createAlert = async () => {
        const t = alertTicker.trim().toUpperCase();
        const th = parseFloat(alertThreshold);
        if (!t || Number.isNaN(th)) return;
        try {
            await watchlistApi.createAlert({ ticker: t, threshold: th, direction: alertDir });
            setAlerts((prev) => [...prev, { ticker: t, threshold: th, direction: alertDir }]);
            setAlertTicker('');
            setAlertThreshold('');
        } catch {
            /* ignore */
        }
    };

    return (
        <div className="page-container">
            <h1 className="page-title">
                <ListChecks size={28} />
                Watchlist & Alerts
            </h1>

            <div className="watchlist-layout">
                {/* Watchlist */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">Tracked Tickers</span>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() =>
                                    exportToCSV(
                                        items.map((item) => ({
                                            ticker: typeof item === 'string' ? item : item.ticker,
                                            added_at: typeof item === 'string' ? '' : item.added_at || '',
                                        })),
                                        [
                                            { key: 'ticker', label: 'Ticker' },
                                            { key: 'added_at', label: 'Added At' },
                                        ],
                                        `watchlist_${new Date().toISOString().slice(0, 10)}`,
                                    )
                                }
                                disabled={items.length === 0}
                                title="Export watchlist as CSV"
                            >
                                <Download size={14} />
                            </button>
                            <span className="badge badge-blue">{items.length}</span>
                        </div>
                    </div>

                    <div className="wl-add-row">
                        <input
                            className="input"
                            placeholder="Add ticker (e.g. AAPL)"
                            value={newTicker}
                            onChange={(e) => setNewTicker(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && addTicker()}
                            maxLength={10}
                        />
                        <button type="button" className="btn btn-primary" onClick={addTicker}>
                            <Plus size={16} /> Add
                        </button>
                    </div>

                    {loading ? (
                        <SkeletonLoader variant="lines" lines={3} />
                    ) : items.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th style={{ textAlign: 'right' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item, i) => {
                                    const ticker = typeof item === 'string' ? item : item.ticker;
                                    return (
                                        <tr key={i}>
                                            <td>
                                                <button
                                                    type="button"
                                                    className="wl-ticker"
                                                    onClick={() => navigate(`/stock/${ticker}`)}
                                                >
                                                    {ticker}
                                                </button>
                                            </td>
                                            <td style={{ textAlign: 'right' }}>
                                                <button
                                                    type="button"
                                                    className="btn btn-danger btn-sm"
                                                    onClick={() => removeTicker(ticker)}
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">
                            <ListChecks size={32} />
                            <span>No tickers tracked yet</span>
                        </div>
                    )}
                </div>

                {/* Alerts */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <Bell size={14} /> Price Alerts
                        </span>
                        <span className="badge badge-amber">{alerts.length}</span>
                    </div>

                    <div className="alert-form">
                        <input
                            className="input"
                            placeholder="Ticker"
                            value={alertTicker}
                            onChange={(e) => setAlertTicker(e.target.value)}
                            maxLength={10}
                        />
                        <input
                            className="input"
                            type="number"
                            placeholder="Price"
                            value={alertThreshold}
                            onChange={(e) => setAlertThreshold(e.target.value)}
                        />
                        <select className="input" value={alertDir} onChange={(e) => setAlertDir(e.target.value)}>
                            <option value="above">Above</option>
                            <option value="below">Below</option>
                        </select>
                        <button type="button" className="btn btn-primary" onClick={createAlert}>
                            <Plus size={16} /> Alert
                        </button>
                    </div>

                    {alerts.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Direction</th>
                                    <th>Threshold</th>
                                </tr>
                            </thead>
                            <tbody>
                                {alerts.map((a, i) => (
                                    <tr key={i}>
                                        <td className="wl-ticker">{a.ticker}</td>
                                        <td>{a.direction}</td>
                                        <td>${a.threshold.toFixed(2)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">
                            <Bell size={32} />
                            <span>No alerts configured</span>
                        </div>
                    )}

                    {/* Live Alerts */}
                    {liveAlerts.length > 0 && (
                        <div className="live-alerts">
                            <div className="card-title" style={{ marginBottom: 8 }}>
                                <BellRing size={14} /> Live Notifications
                            </div>
                            {liveAlerts.map((a, i) => (
                                <div key={i} className="live-alert-item">
                                    {JSON.stringify(a)}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
