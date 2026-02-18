/**
 * ChartToolbar — Controls for the PatternChart component.
 *
 * Timeframe selector, indicator toggles, sub-pane toggles,
 * pattern overlay, Fibonacci, and S/R toggles.
 */

interface ChartToolbarProps {
    period: string;
    setPeriod: (p: string) => void;
    interval: string;
    setInterval: (i: string) => void;
    activeIndicators: Set<string>;
    toggleIndicator: (key: string) => void;
    activeSubPanes: Set<string>;
    toggleSubPane: (key: string) => void;
    showPatterns: boolean;
    setShowPatterns: (v: boolean) => void;
    showFib: boolean;
    setShowFib: (v: boolean) => void;
    showSR: boolean;
    setShowSR: (v: boolean) => void;
    showEvents: boolean;
    setShowEvents: (v: boolean) => void;
    showIntelligence: boolean;
    setShowIntelligence: (v: boolean) => void;
    showAnalysis: boolean;
    setShowAnalysis: (v: boolean) => void;
    compareSymbols: string[];
    onAddCompare: (sym: string) => void;
    onRemoveCompare: (sym: string) => void;
}

const PERIODS = [
    { label: '1M', value: '1mo' },
    { label: '3M', value: '3mo' },
    { label: '6M', value: '6mo' },
    { label: '1Y', value: '1y' },
    { label: '2Y', value: '2y' },
    { label: '5Y', value: '5y' },
];

const INTERVALS = [
    { label: '5m', value: '5m' },
    { label: '15m', value: '15m' },
    { label: '1H', value: '1h' },
    { label: '1D', value: '1d' },
    { label: '1W', value: '1wk' },
];

const OVERLAY_INDICATORS = [
    { key: 'sma_20', label: 'SMA 20', color: '#ffb74d' },
    { key: 'sma_50', label: 'SMA 50', color: '#42a5f5' },
    { key: 'sma_200', label: 'SMA 200', color: '#ef5350' },
    { key: 'ema_8', label: 'EMA 8', color: '#81c784' },
    { key: 'ema_21', label: 'EMA 21', color: '#ce93d8' },
    { key: 'bb', label: 'Bollinger', color: '#2196f3' },
    { key: 'vwap', label: 'VWAP', color: '#ffd54f' },
    { key: 'ichimoku', label: 'Ichimoku', color: '#26c6da' },
    { key: 'ema_ribbon', label: 'MA Ribbon', color: '#ab47bc' },
    { key: 'psar', label: 'PSAR', color: '#ffd740' },
    { key: 'atr', label: 'ATR', color: '#ff9100' },
    { key: 'volume', label: 'Volume', color: '#78909c' },
];

const SUB_PANES = [
    { key: 'rsi', label: 'RSI' },
    { key: 'macd', label: 'MACD' },
    { key: 'stoch', label: 'Stoch' },
    { key: 'adx', label: 'ADX' },
    { key: 'obv', label: 'OBV' },
    { key: 'cci', label: 'CCI' },
    { key: 'williams', label: 'W%R' },
    { key: 'mfi', label: 'MFI' },
    { key: 'atr', label: 'ATR' },
];

export default function ChartToolbar({
    period,
    setPeriod,
    interval,
    setInterval,
    activeIndicators,
    toggleIndicator,
    activeSubPanes,
    toggleSubPane,
    showPatterns,
    setShowPatterns,
    showFib,
    setShowFib,
    showSR,
    setShowSR,
    showEvents,
    setShowEvents,
    showIntelligence,
    setShowIntelligence,
    showAnalysis,
    setShowAnalysis,
    compareSymbols,
    onAddCompare,
    onRemoveCompare,
}: ChartToolbarProps) {
    return (
        <div className="chart-toolbar">
            {/* Timeframe row */}
            <div className="toolbar-row">
                <div className="toolbar-group">
                    <span className="toolbar-label">Period</span>
                    <div className="toolbar-pills">
                        {PERIODS.map((p) => (
                            <button
                                type="button"
                                key={p.value}
                                className={`pill ${period === p.value ? 'pill--active' : ''}`}
                                onClick={() => setPeriod(p.value)}
                            >
                                {p.label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="toolbar-group">
                    <span className="toolbar-label">Interval</span>
                    <div className="toolbar-pills">
                        {INTERVALS.map((i) => (
                            <button
                                type="button"
                                key={i.value}
                                className={`pill ${interval === i.value ? 'pill--active' : ''}`}
                                onClick={() => setInterval(i.value)}
                            >
                                {i.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Indicators row */}
            <div className="toolbar-row">
                <div className="toolbar-group">
                    <span className="toolbar-label">Overlays</span>
                    <div className="toolbar-pills">
                        {OVERLAY_INDICATORS.map((ind) => (
                            <button
                                type="button"
                                key={ind.key}
                                className={`pill pill--indicator ${activeIndicators.has(ind.key) ? 'pill--active' : ''}`}
                                onClick={() => toggleIndicator(ind.key)}
                                style={
                                    activeIndicators.has(ind.key) ? { borderColor: ind.color, color: ind.color } : {}
                                }
                            >
                                <span className="indicator-dot" style={{ background: ind.color }} />
                                {ind.label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="toolbar-group">
                    <span className="toolbar-label">Panes</span>
                    <div className="toolbar-pills">
                        {SUB_PANES.map((sp) => (
                            <button
                                type="button"
                                key={sp.key}
                                className={`pill ${activeSubPanes.has(sp.key) ? 'pill--active' : ''}`}
                                onClick={() => toggleSubPane(sp.key)}
                            >
                                {sp.label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="toolbar-group">
                    <span className="toolbar-label">Layers</span>
                    <div className="toolbar-pills">
                        <button
                            type="button"
                            className={`pill ${showPatterns ? 'pill--active' : ''}`}
                            onClick={() => setShowPatterns(!showPatterns)}
                        >
                            📐 Patterns
                        </button>
                        <button
                            type="button"
                            className={`pill ${showFib ? 'pill--active' : ''}`}
                            onClick={() => setShowFib(!showFib)}
                        >
                            📏 Fibonacci
                        </button>
                        <button
                            type="button"
                            className={`pill ${showSR ? 'pill--active' : ''}`}
                            onClick={() => setShowSR(!showSR)}
                        >
                            ⎯ S/R Levels
                        </button>
                        <button
                            type="button"
                            className={`pill ${showEvents ? 'pill--active' : ''}`}
                            onClick={() => setShowEvents(!showEvents)}
                        >
                            📅 Events
                        </button>
                        <button
                            type="button"
                            className={`pill ${showIntelligence ? 'pill--active' : ''}`}
                            onClick={() => setShowIntelligence(!showIntelligence)}
                        >
                            🧠 Intel
                        </button>
                        <button
                            type="button"
                            className={`pill ${showAnalysis ? 'pill--active' : ''}`}
                            onClick={() => setShowAnalysis(!showAnalysis)}
                        >
                            📋 Analysis
                        </button>
                    </div>
                </div>

                {/* Compare */}
                <div className="toolbar-group">
                    <span className="toolbar-label">Compare</span>
                    <div className="toolbar-pills">
                        {compareSymbols.map((sym) => (
                            <button
                                type="button"
                                key={sym}
                                className="pill pill--active pill--compare"
                                onClick={() => onRemoveCompare(sym)}
                                title={`Remove ${sym}`}
                            >
                                {sym} ×
                            </button>
                        ))}
                        <input
                            className="compare-input"
                            placeholder="+ Add"
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    const val = (e.target as HTMLInputElement).value.trim().toUpperCase();
                                    if (val) {
                                        onAddCompare(val);
                                        (e.target as HTMLInputElement).value = '';
                                    }
                                }
                            }}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
