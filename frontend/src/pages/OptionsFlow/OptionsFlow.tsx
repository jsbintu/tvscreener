/**
 * OptionsFlow v2 — Full tabbed interface with all data
 *
 * Tabs:
 * 1. Live Flow (QuantData combined)
 * 2. Unusual Activity
 * 3. Sweeps
 * 4. Dark Flow
 * 5. Insider Flow (OptionStrats)
 * 6. Congressional Trades
 * 7. OptionStrats (iframe)
 * 8. Options Calculator
 *
 * Panels: Net Drift, Gainers/Losers, Volatility Skew
 */

import { useQuery } from '@tanstack/react-query';
import {
    Activity,
    Calculator,
    ExternalLink,
    Eye,
    Landmark,
    Moon,
    TrendingDown,
    TrendingUp,
    Users,
    Zap,
} from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { marketApi } from '../../api/client';
import OptionStratsEmbed from '../../components/Embeds/OptionStratsEmbed';
import { formatCompact, formatCurrency, formatDate, formatPercent, priceColorClass, timeAgo } from '../../utils/format';
import './OptionsFlow.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

type TabKey = 'flow' | 'unusual' | 'sweeps' | 'dark' | 'insider' | 'congress' | 'iframe' | 'calculator';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'flow', label: 'Live Flow', icon: <Activity size={14} /> },
    { key: 'unusual', label: 'Unusual', icon: <Eye size={14} /> },
    { key: 'sweeps', label: 'Sweeps', icon: <Zap size={14} /> },
    { key: 'dark', label: 'Dark Flow', icon: <Moon size={14} /> },
    { key: 'insider', label: 'Insider', icon: <Users size={14} /> },
    { key: 'congress', label: 'Congressional', icon: <Landmark size={14} /> },
    { key: 'iframe', label: 'OptionStrats', icon: <ExternalLink size={14} /> },
    { key: 'calculator', label: 'Calculator', icon: <Calculator size={14} /> },
];

function FlowTable({ data }: { data: any[] }) {
    if (!data.length) {
        return (
            <div className="empty-state">
                <Activity size={32} />
                <span>No data available</span>
            </div>
        );
    }
    return (
        <div className="flow-table-wrap">
            <table className="data-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Type</th>
                        <th>Strike</th>
                        <th>Expiry</th>
                        <th>Premium</th>
                        <th>Volume</th>
                        <th>OI</th>
                        <th>Side</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {data.slice(0, 50).map((e: any, i: number) => (
                        <tr key={i}>
                            <td className="flow-ticker">{e.ticker || e.symbol || '—'}</td>
                            <td>
                                <span
                                    className={`badge ${
                                        (e.type || e.option_type || '').toLowerCase().includes('call')
                                            ? 'badge-green'
                                            : 'badge-red'
                                    }`}
                                >
                                    {e.type || e.option_type || '—'}
                                </span>
                            </td>
                            <td>{e.strike ? formatCurrency(e.strike) : '—'}</td>
                            <td>{e.expiry || e.expiration || e.exp || '—'}</td>
                            <td>{formatCurrency(e.premium || e.total_premium || e.notional || null)}</td>
                            <td>{formatCompact(e.volume)}</td>
                            <td>{formatCompact(e.open_interest || e.oi)}</td>
                            <td>
                                <span
                                    className={`badge ${
                                        (e.side || e.trade_type || '').toLowerCase().includes('buy') ||
                                        (e.side || '').toLowerCase() === 'bid'
                                            ? 'badge-green'
                                            : 'badge-red'
                                    }`}
                                >
                                    {e.side || e.trade_type || '—'}
                                </span>
                            </td>
                            <td className="flow-time">
                                {e.timestamp || e.datetime ? timeAgo(e.timestamp || e.datetime) : '—'}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function CongressTable({ data }: { data: any[] }) {
    if (!data.length) {
        return (
            <div className="empty-state">
                <Landmark size={32} />
                <span>No congressional trades</span>
            </div>
        );
    }
    return (
        <div className="flow-table-wrap">
            <table className="data-table">
                <thead>
                    <tr>
                        <th>Rep</th>
                        <th>Ticker</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {data.slice(0, 30).map((t: any, i: number) => (
                        <tr key={i}>
                            <td>{t.representative || t.name || '—'}</td>
                            <td className="flow-ticker">{t.ticker || t.symbol || '—'}</td>
                            <td>
                                <span
                                    className={`badge ${
                                        (t.type || t.transaction || '').toLowerCase().includes('purchase')
                                            ? 'badge-green'
                                            : 'badge-red'
                                    }`}
                                >
                                    {t.type || t.transaction || '—'}
                                </span>
                            </td>
                            <td>{t.amount || t.range || '—'}</td>
                            <td>{formatDate(t.date || t.transaction_date || '')}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default function OptionsFlow() {
    const navigate = useNavigate();
    const [tab, setTab] = useState<TabKey>('flow');

    // ── TanStack Query helpers ──
    const exArr = (res: any) => {
        const d = res?.data;
        return Array.isArray(d) ? d : d?.data || d?.results || [];
    };

    const { data: flowRaw, isLoading: loading } = useQuery({
        queryKey: ['optflow', 'flow'],
        queryFn: () => marketApi.getOptionsFlow(),
    });
    const flow = exArr(flowRaw);

    const { data: unusualRaw } = useQuery({
        queryKey: ['optflow', 'unusual'],
        queryFn: () => marketApi.getUnusualActivity(),
    });
    const unusual = exArr(unusualRaw);

    const { data: sweepsRaw } = useQuery({ queryKey: ['optflow', 'sweeps'], queryFn: () => marketApi.getSweeps() });
    const sweeps = exArr(sweepsRaw);

    const { data: darkRaw } = useQuery({ queryKey: ['optflow', 'dark'], queryFn: () => marketApi.getDarkFlow() });
    const dark = exArr(darkRaw);

    const { data: insiderRaw } = useQuery({
        queryKey: ['optflow', 'insider'],
        queryFn: () => marketApi.getInsiderFlow(),
    });
    const insider = exArr(insiderRaw);

    const { data: congressRaw } = useQuery({
        queryKey: ['optflow', 'congress'],
        queryFn: () => marketApi.getCongressionalFlow(),
    });
    const congress = exArr(congressRaw);

    const { data: driftRaw } = useQuery({ queryKey: ['optflow', 'netDrift'], queryFn: () => marketApi.getNetDrift() });
    const netDrift = exArr(driftRaw).slice(0, 10);

    const { data: glRaw } = useQuery({
        queryKey: ['optflow', 'gainersLosers'],
        queryFn: () => marketApi.getGainersLosers(),
    });
    const gainersLosers = exArr(glRaw).slice(0, 10);

    const tabCounts: Record<TabKey, number> = {
        flow: flow.length,
        unusual: unusual.length,
        sweeps: sweeps.length,
        dark: dark.length,
        insider: insider.length,
        congress: congress.length,
        iframe: 0,
        calculator: 0,
    };

    const tabBadgeColors: Record<TabKey, string> = {
        flow: 'blue',
        unusual: 'amber',
        sweeps: 'red',
        dark: 'purple',
        insider: 'green',
        congress: 'amber',
        iframe: 'blue',
        calculator: 'purple',
    };

    const [pricerInputs, setPricerInputs] = useState({
        S: 100,
        K: 100,
        T: 0.25,
        sigma: 0.3,
        r: 0.05,
        option_type: 'call',
        model: 'black_scholes',
    });
    const [pricerResult, setPricerResult] = useState<any>(null);
    const [pricerLoading, setPricerLoading] = useState(false);
    const [strategyEval, setStrategyEval] = useState<any>(null);
    const [plAtDate, setPlAtDate] = useState<any>(null);
    const [profitableRange, setProfitableRange] = useState<any>(null);

    const runPricer = async () => {
        setPricerLoading(true);
        setStrategyEval(null);
        setPlAtDate(null);
        setProfitableRange(null);
        try {
            const res = await marketApi.priceOption(pricerInputs);
            setPricerResult(res.data);
            // Also do a quick strategy evaluation for this single leg
            const leg = {
                type: pricerInputs.option_type,
                strike: pricerInputs.K,
                premium: res.data?.price ?? 0,
                action: 'buy',
                contracts: 1,
            };
            try {
                const evalRes = await marketApi.evaluateStrategy(
                    `long_${pricerInputs.option_type}`,
                    [leg],
                    pricerInputs.S,
                );
                setStrategyEval(evalRes.data);
            } catch {
                // Strategy eval is optional
            }
            // P/L at 30 days from now
            try {
                const plRes = await marketApi.computePlAtDate([leg], pricerInputs.S, 30, pricerInputs.r);
                setPlAtDate(plRes.data);
            } catch {
                // optional
            }
            // Profitable price range
            try {
                const prRes = await marketApi.computeProfitableRange([leg], pricerInputs.S);
                setProfitableRange(prRes.data);
            } catch {
                // optional
            }
        } catch {
            setPricerResult({ error: 'Pricing failed' });
        } finally {
            setPricerLoading(false);
        }
    };

    const renderTabContent = () => {
        if (tab === 'iframe') {
            return <OptionStratsEmbed ticker="SPY" strategy="flow" height={600} />;
        }
        if (tab === 'congress') {
            return <CongressTable data={congress} />;
        }
        if (tab === 'calculator') {
            return (
                <div className="calc-container">
                    <div className="calc-form">
                        <h3 className="calc-title">
                            <Calculator size={16} /> Option Pricer
                        </h3>
                        <div className="calc-inputs">
                            {(['S', 'K', 'T', 'sigma', 'r'] as const).map((field) => (
                                <div key={field} className="calc-field">
                                    <label>
                                        {field === 'S'
                                            ? 'Stock Price'
                                            : field === 'K'
                                              ? 'Strike'
                                              : field === 'T'
                                                ? 'Time (yrs)'
                                                : field === 'sigma'
                                                  ? 'IV (σ)'
                                                  : 'Rate (r)'}
                                        <input
                                            type="number"
                                            step="any"
                                            value={(pricerInputs as any)[field]}
                                            onChange={(e) =>
                                                setPricerInputs((prev) => ({
                                                    ...prev,
                                                    [field]: parseFloat(e.target.value) || 0,
                                                }))
                                            }
                                        />
                                    </label>
                                </div>
                            ))}
                            <div className="calc-field">
                                <label>
                                    Type
                                    <select
                                        value={pricerInputs.option_type}
                                        onChange={(e) =>
                                            setPricerInputs((prev) => ({ ...prev, option_type: e.target.value }))
                                        }
                                    >
                                        <option value="call">Call</option>
                                        <option value="put">Put</option>
                                    </select>
                                </label>
                            </div>
                            <div className="calc-field">
                                <label>
                                    Model
                                    <select
                                        value={pricerInputs.model}
                                        onChange={(e) =>
                                            setPricerInputs((prev) => ({ ...prev, model: e.target.value }))
                                        }
                                    >
                                        <option value="black_scholes">Black-Scholes</option>
                                        <option value="monte_carlo">Monte Carlo</option>
                                        <option value="binomial">Binomial Tree</option>
                                        <option value="baw">Barone-Adesi-Whaley</option>
                                    </select>
                                </label>
                            </div>
                        </div>
                        <button type="button" className="btn btn-primary" onClick={runPricer} disabled={pricerLoading}>
                            {pricerLoading ? 'Computing…' : 'Price Option'}
                        </button>
                    </div>
                    {pricerResult && !pricerResult.error && (
                        <div className="calc-results">
                            <div className="calc-price-card">
                                <div className="calc-price-label">Option Price</div>
                                <div className="calc-price-value">${pricerResult.price?.toFixed(4) ?? '—'}</div>
                                <div className="calc-model-tag">{pricerResult.model || pricerInputs.model}</div>
                            </div>
                            {pricerResult.greeks && (
                                <div className="calc-greeks">
                                    {['delta', 'gamma', 'theta', 'vega', 'rho'].map((g) => (
                                        <div key={g} className="greek-card">
                                            <div className="greek-label">{g}</div>
                                            <div className="greek-value">
                                                {pricerResult.greeks[g]?.toFixed(4) ?? '—'}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {/* Strategy Evaluation (Phase 7b audit) */}
                            {strategyEval && (
                                <div className="calc-greeks" style={{ marginTop: 12 }}>
                                    <div className="greek-card">
                                        <div className="greek-label">Max Profit</div>
                                        <div className="greek-value" style={{ color: 'var(--accent-green)' }}>
                                            {strategyEval.max_profit === 'unlimited'
                                                ? '∞'
                                                : formatCurrency(strategyEval.max_profit)}
                                        </div>
                                    </div>
                                    <div className="greek-card">
                                        <div className="greek-label">Max Loss</div>
                                        <div className="greek-value" style={{ color: 'var(--accent-red)' }}>
                                            {formatCurrency(strategyEval.max_loss)}
                                        </div>
                                    </div>
                                    <div className="greek-card">
                                        <div className="greek-label">Breakevens</div>
                                        <div className="greek-value">
                                            {(strategyEval.breakevens ?? [])
                                                .map((b: number) => formatCurrency(b))
                                                .join(', ') || '—'}
                                        </div>
                                    </div>
                                    <div className="greek-card">
                                        <div className="greek-label">R/R Ratio</div>
                                        <div className="greek-value">{strategyEval.risk_reward_ratio ?? '—'}</div>
                                    </div>
                                    <div className="greek-card">
                                        <div className="greek-label">PoP</div>
                                        <div className="greek-value">
                                            {strategyEval.probability_of_profit != null
                                                ? `${strategyEval.probability_of_profit}%`
                                                : '—'}
                                        </div>
                                    </div>
                                </div>
                            )}
                            {/* P/L at Date (30d) */}
                            {plAtDate && (
                                <div className="calc-greeks" style={{ marginTop: 12 }}>
                                    <div className="greek-card">
                                        <div className="greek-label">P/L (30d)</div>
                                        <div
                                            className="greek-value"
                                            style={{
                                                color:
                                                    (plAtDate.total_pl ?? 0) >= 0
                                                        ? 'var(--accent-green)'
                                                        : 'var(--accent-red)',
                                            }}
                                        >
                                            {formatCurrency(plAtDate.total_pl)}
                                        </div>
                                    </div>
                                    {plAtDate.estimated_value != null && (
                                        <div className="greek-card">
                                            <div className="greek-label">Est. Value</div>
                                            <div className="greek-value">
                                                {formatCurrency(plAtDate.estimated_value)}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                            {/* Profitable Price Range */}
                            {profitableRange && (
                                <div className="calc-greeks" style={{ marginTop: 12 }}>
                                    <div className="greek-card">
                                        <div className="greek-label">Profit Zone</div>
                                        <div className="greek-value" style={{ color: 'var(--accent-green)' }}>
                                            {formatCurrency(profitableRange.min_price)} –{' '}
                                            {profitableRange.max_price === 'unlimited'
                                                ? '∞'
                                                : formatCurrency(profitableRange.max_price)}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                    {pricerResult?.error && (
                        <div className="text-muted" style={{ marginTop: 16 }}>
                            {pricerResult.error}
                        </div>
                    )}
                </div>
            );
        }
        const dataMap: Record<string, any[]> = {
            flow,
            unusual,
            sweeps,
            dark,
            insider,
        };
        return <FlowTable data={dataMap[tab] || []} />;
    };

    return (
        <div className="page-container">
            <h1 className="page-title">
                <Activity size={28} /> Options Flow
            </h1>

            {/* ── Tabs ── */}
            <div className="flow-tabs">
                {TABS.map((t) => (
                    <button
                        type="button"
                        key={t.key}
                        className={`flow-tab ${tab === t.key ? 'flow-tab--active' : ''}`}
                        onClick={() => setTab(t.key)}
                    >
                        {t.icon}
                        {t.label}
                        {tabCounts[t.key] > 0 && (
                            <span className={`badge badge-${tabBadgeColors[t.key]}`}>{tabCounts[t.key]}</span>
                        )}
                    </button>
                ))}
            </div>

            {/* ── Tab Content ── */}
            <div className="card flow-content">
                {loading && tab !== 'iframe' ? (
                    <div className="skeleton" style={{ height: 400 }} />
                ) : (
                    renderTabContent()
                )}
            </div>

            {/* ── Bottom Panels ── */}
            <div className="grid-2 flow-panels">
                {/* Net Drift */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <TrendingUp size={14} /> Net Drift
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ height: 120 }} />
                    ) : netDrift.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Drift</th>
                                    <th>Volume</th>
                                </tr>
                            </thead>
                            <tbody>
                                {netDrift.map((d: any, i: number) => {
                                    const drift = d.net_drift ?? d.drift ?? d.value ?? 0;
                                    return (
                                        <tr
                                            key={i}
                                            onClick={() => navigate(`/stock/${d.ticker || d.symbol}`)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <td className="flow-ticker">{d.ticker || d.symbol || '—'}</td>
                                            <td className={priceColorClass(drift)}>{formatPercent(drift)}</td>
                                            <td>{formatCompact(d.volume)}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">No drift data</div>
                    )}
                </div>

                {/* Gainers/Losers */}
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">
                            <TrendingDown size={14} /> Options Gainers / Losers
                        </span>
                    </div>
                    {loading ? (
                        <div className="skeleton" style={{ height: 120 }} />
                    ) : gainersLosers.length > 0 ? (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th>Type</th>
                                    <th>Change</th>
                                    <th>Premium</th>
                                </tr>
                            </thead>
                            <tbody>
                                {gainersLosers.map((g: any, i: number) => {
                                    const chg = g.change_percent ?? g.change ?? g.perf ?? 0;
                                    return (
                                        <tr
                                            key={i}
                                            onClick={() => navigate(`/stock/${g.ticker || g.symbol}`)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <td className="flow-ticker">{g.ticker || g.symbol || '—'}</td>
                                            <td>
                                                <span
                                                    className={`badge ${
                                                        (g.type || g.direction || '').toLowerCase().includes('bull')
                                                            ? 'badge-green'
                                                            : 'badge-red'
                                                    }`}
                                                >
                                                    {g.type || g.direction || '—'}
                                                </span>
                                            </td>
                                            <td className={priceColorClass(chg)}>{formatPercent(chg)}</td>
                                            <td>{formatCompact(g.premium || g.total_premium || g.notional)}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    ) : (
                        <div className="empty-state">No gainers/losers</div>
                    )}
                </div>
            </div>
        </div>
    );
}
