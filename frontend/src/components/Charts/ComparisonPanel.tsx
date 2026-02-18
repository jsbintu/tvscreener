/**
 * ComparisonPanel — Mini-panel for toggling comparison tickers.
 *
 * Rendered in the chart controls area, shows small toggle pills
 * for SPY, QQQ, IWM, DIA with colored indicators.
 */
import type { ComparisonSeries } from '../../hooks/useComparison';

interface ComparisonPanelProps {
    series: ComparisonSeries[];
    onToggle: (ticker: string) => void;
}

export default function ComparisonPanel({ series, onToggle }: ComparisonPanelProps) {
    return (
        <div className="comparison-panel">
            <span className="comparison-label">Compare</span>
            <div className="comparison-pills">
                {series.map((s) => (
                    <button
                        type="button"
                        key={s.ticker}
                        className={`comparison-pill ${s.visible ? 'active' : ''}`}
                        onClick={() => onToggle(s.ticker)}
                        style={s.visible ? { borderColor: s.color, color: s.color } : {}}
                    >
                        <span className="comparison-dot" style={{ background: s.color }} />
                        {s.ticker}
                    </button>
                ))}
            </div>
        </div>
    );
}
