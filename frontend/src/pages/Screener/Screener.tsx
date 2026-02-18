/**
 * Screener v2 — Full-featured stock screener with filter controls
 * wired to the TV screener backend endpoint's query params
 */

import { useQuery } from '@tanstack/react-query';
import {
    Bookmark,
    Download,
    Filter,
    Loader2,
    Search,
    SlidersHorizontal,
    Trash2,
    TrendingDown,
    TrendingUp,
    Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { marketApi, presetsApi } from '../../api/client';
import SkeletonLoader from '../../components/Data/SkeletonLoader';
import { exportToCSV } from '../../utils/export';
import { formatCompact, formatCurrency, formatPercent, priceColorClass } from '../../utils/format';
import './Screener.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Filters {
    market: string;
    minPrice: string;
    maxPrice: string;
    minVolume: string;
    minChange: string;
    maxChange: string;
}

const DEFAULT_FILTERS: Filters = {
    market: 'america',
    minPrice: '',
    maxPrice: '',
    minVolume: '',
    minChange: '',
    maxChange: '',
};

function SortIcon({ col, sortKey, sortDir }: { col: string; sortKey: string; sortDir: 'asc' | 'desc' }) {
    if (sortKey !== col) return null;
    return sortDir === 'desc' ? <TrendingDown size={12} /> : <TrendingUp size={12} />;
}

export default function Screener() {
    const navigate = useNavigate();
    const [search, setSearch] = useState('');
    const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
    const [showFilters, setShowFilters] = useState(false);
    const [sortKey, setSortKey] = useState<string>('change_percent');
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
    const [breakoutScores, setBreakoutScores] = useState<Record<string, any>>({});
    const [scanning, setScanning] = useState(false);

    // ── Filter Presets ──
    interface Preset {
        id: string;
        name: string;
        filters: Filters;
        created_at: number;
    }
    const [presets, setPresets] = useState<Preset[]>([]);
    const [presetName, setPresetName] = useState('');
    const [savingPreset, setSavingPreset] = useState(false);

    // Load presets from API on mount
    useEffect(() => {
        presetsApi
            .list()
            .then((res) => {
                const items = (res.data?.presets || []).map((p: any) => ({
                    id: p.id,
                    name: p.name,
                    filters: p.filters || {},
                    created_at: p.created_at || 0,
                }));
                setPresets(items);
            })
            .catch(() => {
                /* API unavailable */
            });
    }, []);

    const savePreset = async () => {
        const name = presetName.trim();
        if (!name) return;
        setSavingPreset(true);
        try {
            const res = await presetsApi.create(name, filters as unknown as Record<string, unknown>);
            const created = res.data;
            setPresets((prev) => [
                { id: created.id, name: created.name, filters: created.filters, created_at: created.created_at },
                ...prev,
            ]);
            setPresetName('');
        } catch {
            /* ignore */
        }
        setSavingPreset(false);
    };

    const loadPreset = (preset: Preset) => {
        setFilters({ ...DEFAULT_FILTERS, ...preset.filters });
    };

    const deletePreset = async (id: string) => {
        try {
            await presetsApi.delete(id);
            setPresets((prev) => prev.filter((p) => p.id !== id));
        } catch {
            /* ignore */
        }
    };

    // TanStack Query — screener data
    const buildParams = () => {
        const params: Record<string, any> = {};
        if (filters.market) params.market = filters.market;
        if (filters.minPrice) params.min_price = Number(filters.minPrice);
        if (filters.maxPrice) params.max_price = Number(filters.maxPrice);
        if (filters.minVolume) params.min_volume = Number(filters.minVolume);
        if (filters.minChange) params.min_change = Number(filters.minChange);
        if (filters.maxChange) params.max_change = Number(filters.maxChange);
        return params;
    };

    const { data: screenerRaw, isLoading: loading } = useQuery({
        queryKey: ['screener', filters],
        queryFn: async () => {
            const res = await marketApi.getScreener(buildParams());
            const d = res.data;
            return Array.isArray(d) ? d : d?.data || d?.results || [];
        },
    });
    const rows: any[] = screenerRaw ?? [];

    const filtered = rows.filter((r: any) => {
        const sym = (r.ticker || r.symbol || r.name || '').toLowerCase();
        return sym.includes(search.toLowerCase());
    });

    const sorted = [...filtered].sort((a: any, b: any) => {
        if (sortKey === '_conviction') {
            const aConv = breakoutScores[a.ticker || a.symbol || a.name]?.conviction_score ?? -1;
            const bConv = breakoutScores[b.ticker || b.symbol || b.name]?.conviction_score ?? -1;
            return sortDir === 'desc' ? bConv - aConv : aConv - bConv;
        }
        const aVal = a[sortKey] ?? 0;
        const bVal = b[sortKey] ?? 0;
        return sortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });

    const handleSort = (key: string) => {
        if (sortKey === key) {
            setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
        } else {
            setSortKey(key);
            setSortDir('desc');
        }
    };

    const updateFilter = (key: keyof Filters, val: string) => {
        setFilters((f) => ({ ...f, [key]: val }));
    };

    /** Batch-scan top screener results for breakout conviction */
    const scanBreakouts = async () => {
        if (scanning || sorted.length === 0) return;
        setScanning(true);
        const top = sorted.slice(0, 20);
        const results = await Promise.allSettled(
            top.map((r: any) => {
                const sym = r.ticker || r.symbol || r.name || '';
                return marketApi.getBreakoutFull(sym).then((res) => ({
                    ticker: sym,
                    data: res.data,
                }));
            }),
        );
        const scores: Record<string, any> = { ...breakoutScores };
        results.forEach((r) => {
            if (r.status === 'fulfilled' && r.value?.data) {
                scores[r.value.ticker] = r.value.data;
            }
        });
        setBreakoutScores(scores);
        setScanning(false);
    };

    return (
        <div className="page-container">
            <h1 className="page-title">
                <Filter size={28} /> Stock Screener
            </h1>

            {/* Toolbar */}
            <div className="screener-toolbar">
                <div className="screener-search">
                    <Search size={16} />
                    <input
                        className="input"
                        type="text"
                        placeholder="Filter by ticker..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <div className="screener-toolbar-right">
                    <button
                        type="button"
                        className={`btn btn-ghost ${scanning ? 'btn-ghost--active' : ''}`}
                        onClick={scanBreakouts}
                        disabled={scanning || sorted.length === 0}
                        title="Scan top 20 results for breakout conviction"
                    >
                        {scanning ? <Loader2 size={14} className="spin-icon" /> : <Zap size={14} />}
                        {scanning ? 'Scanning...' : 'Breakout Scan'}
                    </button>
                    <button
                        type="button"
                        className={`btn btn-ghost ${showFilters ? 'btn-ghost--active' : ''}`}
                        onClick={() => setShowFilters((s) => !s)}
                    >
                        <SlidersHorizontal size={14} /> Filters
                    </button>
                    <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() =>
                            exportToCSV(
                                sorted.slice(0, 100).map((r: any) => ({
                                    ticker: r.ticker || r.symbol || r.name || '',
                                    price: r.close ?? r.price ?? 0,
                                    change_pct: r.change_percent ?? r.perf ?? r.change ?? 0,
                                    volume: r.volume ?? 0,
                                    market_cap: r.market_cap ?? 0,
                                    sector: r.sector || '',
                                })),
                                [
                                    { key: 'ticker', label: 'Ticker' },
                                    { key: 'price', label: 'Price' },
                                    { key: 'change_pct', label: 'Change %' },
                                    { key: 'volume', label: 'Volume' },
                                    { key: 'market_cap', label: 'Market Cap' },
                                    { key: 'sector', label: 'Sector' },
                                ],
                                `screener_${new Date().toISOString().slice(0, 10)}`,
                            )
                        }
                        disabled={sorted.length === 0}
                        title="Export results as CSV"
                    >
                        <Download size={14} /> Export
                    </button>
                    <span className="badge badge-blue">{sorted.length} results</span>
                </div>
            </div>

            {/* Filter Panel */}
            {showFilters && (
                <div className="card screener-filters">
                    <div className="filter-grid">
                        <div className="filter-group">
                            <label className="filter-label">
                                Market
                                <select
                                    className="input filter-select"
                                    value={filters.market}
                                    onChange={(e) => updateFilter('market', e.target.value)}
                                >
                                    <option value="america">America</option>
                                    <option value="japan">Japan</option>
                                    <option value="india">India</option>
                                    <option value="uk">UK</option>
                                    <option value="germany">Germany</option>
                                    <option value="canada">Canada</option>
                                </select>
                            </label>
                        </div>
                        <div className="filter-group">
                            <label className="filter-label">
                                Min Price
                                <input
                                    className="input"
                                    type="number"
                                    placeholder="e.g. 5"
                                    value={filters.minPrice}
                                    onChange={(e) => updateFilter('minPrice', e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="filter-group">
                            <label className="filter-label">
                                Max Price
                                <input
                                    className="input"
                                    type="number"
                                    placeholder="e.g. 500"
                                    value={filters.maxPrice}
                                    onChange={(e) => updateFilter('maxPrice', e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="filter-group">
                            <label className="filter-label">
                                Min Volume
                                <input
                                    className="input"
                                    type="number"
                                    placeholder="e.g. 1000000"
                                    value={filters.minVolume}
                                    onChange={(e) => updateFilter('minVolume', e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="filter-group">
                            <label className="filter-label">
                                Min Change %
                                <input
                                    className="input"
                                    type="number"
                                    step="0.5"
                                    placeholder="e.g. -5"
                                    value={filters.minChange}
                                    onChange={(e) => updateFilter('minChange', e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="filter-group">
                            <label className="filter-label">
                                Max Change %
                                <input
                                    className="input"
                                    type="number"
                                    step="0.5"
                                    placeholder="e.g. 10"
                                    value={filters.maxChange}
                                    onChange={(e) => updateFilter('maxChange', e.target.value)}
                                />
                            </label>
                        </div>
                    </div>
                    <div className="screener-preset-row">
                        <button type="button" className="btn btn-ghost" onClick={() => setFilters(DEFAULT_FILTERS)}>
                            Reset Filters
                        </button>
                        <div className="preset-save-group">
                            <input
                                className="input preset-name-input"
                                type="text"
                                placeholder="Preset name…"
                                value={presetName}
                                onChange={(e) => setPresetName(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') savePreset();
                                }}
                            />
                            <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={savePreset}
                                disabled={!presetName.trim() || savingPreset}
                            >
                                <Bookmark size={12} /> Save
                            </button>
                        </div>
                    </div>
                    {presets.length > 0 && (
                        <div className="preset-chips">
                            {presets.map((p) => (
                                <div key={p.id} className="preset-chip">
                                    <button type="button" className="preset-chip-label" onClick={() => loadPreset(p)}>
                                        <Bookmark size={10} /> {p.name}
                                    </button>
                                    <button
                                        type="button"
                                        className="preset-chip-delete"
                                        onClick={() => deletePreset(p.id)}
                                        title="Delete preset"
                                    >
                                        <Trash2 size={10} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Results Table */}
            <div className="card">
                {loading ? (
                    <SkeletonLoader variant="lines" lines={8} />
                ) : sorted.length > 0 ? (
                    <div className="screener-table-wrap">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th onClick={() => handleSort('ticker')} className="sortable">
                                        Ticker <SortIcon col="ticker" sortKey={sortKey} sortDir={sortDir} />
                                    </th>
                                    <th onClick={() => handleSort('close')} className="sortable">
                                        Price <SortIcon col="close" sortKey={sortKey} sortDir={sortDir} />
                                    </th>
                                    <th onClick={() => handleSort('change_percent')} className="sortable">
                                        Change <SortIcon col="change_percent" sortKey={sortKey} sortDir={sortDir} />
                                    </th>
                                    <th onClick={() => handleSort('volume')} className="sortable">
                                        Volume <SortIcon col="volume" sortKey={sortKey} sortDir={sortDir} />
                                    </th>
                                    <th onClick={() => handleSort('market_cap')} className="sortable">
                                        Mkt Cap <SortIcon col="market_cap" sortKey={sortKey} sortDir={sortDir} />
                                    </th>
                                    <th>Sector</th>
                                    {Object.keys(breakoutScores).length > 0 && (
                                        <th onClick={() => handleSort('_conviction')} className="sortable">
                                            Conviction{' '}
                                            <SortIcon col="_conviction" sortKey={sortKey} sortDir={sortDir} />
                                        </th>
                                    )}
                                </tr>
                            </thead>
                            <tbody>
                                {sorted.slice(0, 100).map((r: any, i: number) => {
                                    const sym = r.ticker || r.symbol || r.name || '';
                                    const chg = r.change_percent ?? r.perf ?? r.change ?? 0;
                                    const px = r.close ?? r.price ?? 0;
                                    return (
                                        <tr
                                            key={i}
                                            onClick={() => navigate(`/stock/${sym}`)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <td className="screener-ticker">{sym}</td>
                                            <td>{formatCurrency(px)}</td>
                                            <td className={priceColorClass(chg)}>{formatPercent(chg)}</td>
                                            <td>{formatCompact(r.volume)}</td>
                                            <td>{formatCompact(r.market_cap)}</td>
                                            <td className="screener-sector">{r.sector || '—'}</td>
                                            {Object.keys(breakoutScores).length > 0 && (
                                                <td>
                                                    {breakoutScores[sym] ? (
                                                        <span
                                                            className={`conviction-badge conviction-${
                                                                breakoutScores[sym].conviction_score >= 75
                                                                    ? 'high'
                                                                    : breakoutScores[sym].conviction_score >= 50
                                                                      ? 'mid'
                                                                      : 'low'
                                                            }`}
                                                        >
                                                            {breakoutScores[sym].conviction_score}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted" style={{ fontSize: 12 }}>
                                                            —
                                                        </span>
                                                    )}
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="empty-state">
                        <Search size={32} />
                        <span>No screener data available</span>
                    </div>
                )}
            </div>
        </div>
    );
}
