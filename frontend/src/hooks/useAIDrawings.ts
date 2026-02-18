/**
 * useAIDrawings — Converts AI-detected patterns into drawable chart primitives.
 *
 * Takes chart data (with patterns, trend lines, emerging patterns) and produces
 * structured drawing instructions for the lightweight-charts library.
 *
 * AI drawings are visually distinct from user drawings (dashed, labeled, colored by bias).
 * Each drawing is tagged with source: 'ai' for identification.
 */
import { useMemo } from 'react';
import type { Drawing } from './useDrawingTools';

/* ─── Types ─── */

/** A price line to overlay on the main series */
export interface AIPriceLine {
    price: number;
    color: string;
    lineWidth: number;
    lineStyle: 'solid' | 'dashed' | 'dotted';
    title: string;
    axisLabelVisible: boolean;
    source: 'ai';
}

/** A series marker (arrow/circle) for pattern events */
export interface AIMarker {
    time: number;
    position: 'aboveBar' | 'belowBar';
    color: string;
    shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
    text: string;
    size: number;
    source: 'ai';
}

/** A trend line segment to draw between two points */
export interface AITrendLine {
    name: string;
    direction: 'bullish' | 'bearish' | 'neutral';
    confidence: number;
    description: string;
    color: string;
    lineWidth: number;
    lineStyle: 'solid' | 'dashed';
    source: 'ai';
}

/** Emerging pattern with progress indicator */
export interface AIEmergingPattern {
    name: string;
    direction: string;
    progress: number; // 0-100
    description: string;
    time: number;
    color: string;
    source: 'ai';
}

/** Pre-candle setup (1 bar from confirmation) */
export interface AIPreCandleSetup {
    name: string;
    confirmationNeeded: string;
    probability: number; // 0-100
    time: number;
    source: 'ai';
}

/** Full AI drawing output */
export interface AIDrawingsData {
    priceLines: AIPriceLine[];
    markers: AIMarker[];
    trendLines: AITrendLine[];
    emergingPatterns: AIEmergingPattern[];
    preCandleSetups: AIPreCandleSetup[];
    /** Drawings that can be persisted via useDrawingTools.importDrawing() */
    persistableDrawings: Drawing[];
    analysisTimestamp: number;
}

/* ─── Pattern entry shape from backend ─── */
interface PatternItem {
    name?: string;
    pattern_name?: string;
    direction?: string;
    confidence?: number;
    bar_index?: number;
    time?: number;
    description?: string;
    entry_trigger?: number;
    target?: number;
    stop_loss?: number;
    formation_progress?: number;
    progress?: number;
    completion?: number;
    confirmation_needed?: string;
    probability?: number;
}

/** Fibonacci level from backend */
interface FibLevel {
    ratio: number;
    price: number;
    label?: string;
}

/** Support/Resistance level from confluence */
interface SRLevel {
    price: number;
    type: 'support' | 'resistance';
    strength?: number;
    sources?: string[];
}

/** Channel boundary */
interface ChannelBoundary {
    upper: number;
    lower: number;
    mid?: number;
    type?: string;
}

/** Trade target (TP1/TP2/TP3) */
interface TradeTarget {
    price: number;
    rr_ratio: string;
    pct_from_entry: number;
    probability_pct: number;
    position_pct: number;
    label: string;
}

/** Comprehensive analysis data from backend */
export interface ComprehensiveData {
    fibLevels?: FibLevel[];
    supportResistance?: SRLevel[];
    channels?: ChannelBoundary[];
    tradeTargets?: {
        entry?: number;
        stop?: number;
        tp1?: TradeTarget;
        tp2?: TradeTarget;
        tp3?: TradeTarget;
    };
}

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ChartPatterns {
    candlestick?: PatternItem[];
    chart?: PatternItem[];
    gap?: PatternItem[];
    volume?: PatternItem[];
    emerging?: PatternItem[];
    trend_lines?: PatternItem[];
    pre_candle?: PatternItem[];
    aged?: any[];
    aging_summary?: Record<string, number>;
    summary?: { total?: number; bullish?: number; bearish?: number; bias?: string };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/* ─── Color mapping ─── */
const DIRECTION_COLORS: Record<string, string> = {
    bullish: '#00c853',
    bearish: '#ff1744',
    neutral: '#78909c',
};

const AI_TRENDLINE_COLORS: Record<string, string> = {
    bullish: 'rgba(0, 200, 83, 0.7)',
    bearish: 'rgba(255, 23, 68, 0.7)',
    neutral: 'rgba(120, 144, 156, 0.5)',
};

const FIB_COLORS: Record<number, string> = {
    0.236: '#8e24aa',
    0.382: '#5c6bc0',
    0.5: '#26a69a',
    0.618: '#ffa726',
    0.786: '#ef5350',
    1.0: '#ab47bc',
    1.618: '#42a5f5',
    2.618: '#66bb6a',
};

const TP_COLORS = {
    tp1: '#4fc3f7',
    tp2: '#81c784',
    tp3: '#ffb74d',
    entry: '#e0e0e0',
    stop: '#ef5350',
};

/**
 * useAIDrawings — converts pattern engine output into chart-drawable primitives.
 */
export function useAIDrawings(
    patterns: ChartPatterns | undefined,
    lastBarTime: number | undefined,
    comprehensiveData?: ComprehensiveData,
): AIDrawingsData {
    return useMemo(() => {
        const priceLines: AIPriceLine[] = [];
        const markers: AIMarker[] = [];
        const trendLines: AITrendLine[] = [];
        const emergingPatterns: AIEmergingPattern[] = [];
        const preCandleSetups: AIPreCandleSetup[] = [];

        if (!patterns) {
            return {
                priceLines,
                markers,
                trendLines,
                emergingPatterns,
                preCandleSetups,
                persistableDrawings: [],
                analysisTimestamp: 0,
            };
        }

        const persistableDrawings: Drawing[] = [];

        // ── Trend lines → AIPriceLine + AITrendLine ──
        if (patterns.trend_lines) {
            for (const tl of patterns.trend_lines) {
                const name = tl.name || tl.pattern_name || 'Trend Line';
                const dir = (tl.direction || 'neutral') as 'bullish' | 'bearish' | 'neutral';
                const conf = Math.round((tl.confidence || 0.5) * 100);

                trendLines.push({
                    name,
                    direction: dir,
                    confidence: conf,
                    description: tl.description || '',
                    color: AI_TRENDLINE_COLORS[dir] || AI_TRENDLINE_COLORS.neutral,
                    lineWidth: 2,
                    lineStyle: 'dashed',
                    source: 'ai',
                });

                // If entry_trigger available, draw as price line
                if (tl.entry_trigger) {
                    priceLines.push({
                        price: tl.entry_trigger,
                        color: AI_TRENDLINE_COLORS[dir] || AI_TRENDLINE_COLORS.neutral,
                        lineWidth: 2,
                        lineStyle: 'dashed',
                        title: `AI: ${name} (${conf}%)`,
                        axisLabelVisible: true,
                        source: 'ai',
                    });
                }

                // Stop loss line
                if (tl.stop_loss) {
                    priceLines.push({
                        price: tl.stop_loss,
                        color: 'rgba(255, 23, 68, 0.4)',
                        lineWidth: 1,
                        lineStyle: 'dotted',
                        title: `AI SL: $${tl.stop_loss.toFixed(2)}`,
                        axisLabelVisible: false,
                        source: 'ai',
                    });
                }

                // Add marker at trend line detection point
                if (tl.time) {
                    markers.push({
                        time: tl.time,
                        position: dir === 'bullish' ? 'belowBar' : 'aboveBar',
                        color: DIRECTION_COLORS[dir] || DIRECTION_COLORS.neutral,
                        shape: 'square',
                        text: `📈 ${name.slice(0, 18)}`,
                        size: 1,
                        source: 'ai',
                    });
                }

                // Persistable: entry trigger as horizontal line
                if (tl.entry_trigger) {
                    const tlId = `ai-tl-${tl.time || 0}-${tl.entry_trigger.toFixed(2)}`;
                    persistableDrawings.push({
                        id: tlId,
                        type: 'horizontalLine',
                        points: [{ time: tl.time || 0, price: tl.entry_trigger }],
                        price: tl.entry_trigger,
                        color: AI_TRENDLINE_COLORS[dir] || AI_TRENDLINE_COLORS.neutral,
                        lineWidth: 2,
                        text: `AI: ${name} (${conf}%)`,
                        createdAt: tl.time || 0,
                    });
                }

                // Persistable: stop loss as horizontal line
                if (tl.stop_loss) {
                    const slId = `ai-sl-${tl.time || 0}-${tl.stop_loss.toFixed(2)}`;
                    persistableDrawings.push({
                        id: slId,
                        type: 'horizontalLine',
                        points: [{ time: tl.time || 0, price: tl.stop_loss }],
                        price: tl.stop_loss,
                        color: 'rgba(255, 23, 68, 0.6)',
                        lineWidth: 1,
                        text: `AI SL: $${tl.stop_loss.toFixed(2)}`,
                        createdAt: tl.time || 0,
                    });
                }
            }
        }

        // ── Chart pattern targets → price lines ──
        if (patterns.chart) {
            for (const cp of patterns.chart) {
                if (cp.target) {
                    priceLines.push({
                        price: cp.target,
                        color: DIRECTION_COLORS[cp.direction || 'neutral'],
                        lineWidth: 1,
                        lineStyle: 'dashed',
                        title: `AI Target: $${cp.target.toFixed(2)}`,
                        axisLabelVisible: true,
                        source: 'ai',
                    });
                }
                if (cp.stop_loss) {
                    priceLines.push({
                        price: cp.stop_loss,
                        color: 'rgba(255, 23, 68, 0.4)',
                        lineWidth: 1,
                        lineStyle: 'dotted',
                        title: `AI SL: $${cp.stop_loss.toFixed(2)}`,
                        axisLabelVisible: false,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Candlestick pattern markers ──
        const CANDLE_EMOJIS: Record<string, string> = {
            Hammer: '🔨',
            'Inverted Hammer': '🔨',
            'Hanging Man': '🕯️',
            'Shooting Star': '⭐',
            Doji: '✚',
            'Dragonfly Doji': '🐉',
            'Gravestone Doji': '🪦',
            'Bullish Engulfing': '🐂',
            'Bearish Engulfing': '🐻',
            'Morning Star': '🌅',
            'Evening Star': '🌆',
            'Bullish Harami': '🟢',
            'Bearish Harami': '🔴',
            'Three White Soldiers': '⬆️',
            'Three Black Crows': '⬇️',
            'Piercing Pattern': '📌',
            'Dark Cloud Cover': '☁️',
            'Spinning Top': '🔄',
        };

        if (patterns.candlestick) {
            for (const cs of patterns.candlestick) {
                const name = cs.name || cs.pattern_name || 'Candle';
                const dir = (cs.direction || 'neutral') as string;
                const emoji = CANDLE_EMOJIS[name] || (dir === 'bullish' ? '🟢' : dir === 'bearish' ? '🔴' : '⚪');

                if (cs.time) {
                    markers.push({
                        time: cs.time,
                        position: dir === 'bullish' ? 'belowBar' : 'aboveBar',
                        color: DIRECTION_COLORS[dir] || DIRECTION_COLORS.neutral,
                        shape: dir === 'bullish' ? 'arrowUp' : dir === 'bearish' ? 'arrowDown' : 'circle',
                        text: `${emoji} ${name.slice(0, 16)}`,
                        size: 1,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Aged pattern opacity decay ──
        // Apply opacity reduction to price lines from aged patterns
        if (patterns.aged) {
            for (const aged of patterns.aged) {
                const staleness = aged.staleness ?? 0;
                const status = aged.status ?? 'active';

                // Skip invalidated patterns entirely
                if (status === 'invalidated') continue;

                // Calculate opacity: fresh=1.0, stale=0.2
                const opacity = Math.max(0.2, 1.0 - staleness / 120);
                const name = aged.name || 'Pattern';
                const dir = aged.direction || 'neutral';

                // Draw entry trigger with aged opacity
                if (aged.entry_trigger && typeof aged.entry_trigger === 'number') {
                    const baseColor = DIRECTION_COLORS[dir] || DIRECTION_COLORS.neutral;
                    priceLines.push({
                        price: aged.entry_trigger,
                        color: baseColor.replace(')', `, ${opacity})`).replace('rgb(', 'rgba(').replace('#', '#'),
                        lineWidth: staleness < 30 ? 2 : 1,
                        lineStyle: staleness < 50 ? 'dashed' : 'dotted',
                        title: `AI: ${name} [${status}] — $${aged.entry_trigger.toFixed(2)}`,
                        axisLabelVisible: staleness < 50,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Emerging patterns → AIEmergingPattern ──
        if (patterns.emerging) {
            for (const ep of patterns.emerging) {
                const name = ep.name || ep.pattern_name || 'Unknown';
                const dir = ep.direction || 'neutral';
                let progress = ep.formation_progress ?? ep.progress ?? ep.completion ?? 0;
                if (typeof progress === 'number' && progress <= 1) {
                    progress = Math.round(progress * 100);
                }

                emergingPatterns.push({
                    name,
                    direction: dir,
                    progress: progress as number,
                    description: ep.description || '',
                    time: ep.time || 0,
                    color: DIRECTION_COLORS[dir] || DIRECTION_COLORS.neutral,
                    source: 'ai',
                });
            }
        }

        // ── Pre-candle setups → AIPreCandleSetup ──
        if (patterns.pre_candle) {
            for (const pc of patterns.pre_candle) {
                const name = pc.name || pc.pattern_name || 'Setup';
                let prob = pc.probability || 0;
                if (typeof prob === 'number' && prob <= 1) {
                    prob = Math.round(prob * 100);
                }

                preCandleSetups.push({
                    name,
                    confirmationNeeded: pc.confirmation_needed || 'Unknown',
                    probability: prob as number,
                    time: pc.time || 0,
                    source: 'ai',
                });

                // Add marker for pre-candle setup
                if (pc.time) {
                    markers.push({
                        time: pc.time,
                        position: 'aboveBar',
                        color: '#ffd54f',
                        shape: 'circle',
                        text: `⏭️ ${name.slice(0, 12)}`,
                        size: 1,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Gap patterns → price lines (gap fill targets) + markers ──
        if (patterns.gap) {
            for (const g of patterns.gap) {
                const name = g.name || g.pattern_name || 'Gap';
                const dir = (g.direction || 'neutral') as string;

                // Marker for gap detection
                if (g.time) {
                    markers.push({
                        time: g.time,
                        position: dir === 'bullish' ? 'belowBar' : 'aboveBar',
                        color: '#b388ff',
                        shape: 'square',
                        text: `⚡ ${name.slice(0, 14)}`,
                        size: 1,
                        source: 'ai',
                    });
                }

                // Gap fill target as price line
                if (g.target) {
                    priceLines.push({
                        price: g.target,
                        color: 'rgba(179, 136, 255, 0.5)',
                        lineWidth: 1,
                        lineStyle: 'dotted',
                        title: `AI Gap Fill: $${g.target.toFixed(2)}`,
                        axisLabelVisible: false,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Volume patterns → markers for spikes/divergences ──
        if (patterns.volume) {
            for (const vp of patterns.volume) {
                const name = vp.name || vp.pattern_name || 'Volume';
                const dir = (vp.direction || 'neutral') as string;

                if (vp.time) {
                    markers.push({
                        time: vp.time,
                        position: 'belowBar',
                        color: dir === 'bullish' ? '#69f0ae' : dir === 'bearish' ? '#ff8a80' : '#90a4ae',
                        shape: 'circle',
                        text: `📊 ${name.slice(0, 14)}`,
                        size: 1,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Fibonacci level lines ──
        if (comprehensiveData?.fibLevels) {
            for (const fib of comprehensiveData.fibLevels) {
                const color = FIB_COLORS[fib.ratio] || '#9e9e9e';
                const label = fib.label || `Fib ${(fib.ratio * 100).toFixed(1)}%`;
                priceLines.push({
                    price: fib.price,
                    color,
                    lineWidth: 1,
                    lineStyle: 'dotted',
                    title: `AI: ${label} — $${fib.price.toFixed(2)}`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
        }

        // ── Support/Resistance confluence lines ──
        if (comprehensiveData?.supportResistance) {
            for (const sr of comprehensiveData.supportResistance) {
                const isSup = sr.type === 'support';
                const strength = sr.strength || 1;
                priceLines.push({
                    price: sr.price,
                    color: isSup ? 'rgba(0, 200, 83, 0.5)' : 'rgba(255, 23, 68, 0.5)',
                    lineWidth: Math.min(3, Math.max(1, strength)),
                    lineStyle: strength >= 3 ? 'solid' : 'dashed',
                    title: `AI ${isSup ? 'S' : 'R'}: $${sr.price.toFixed(2)}`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
        }

        // ── Channel boundary lines ──
        if (comprehensiveData?.channels) {
            for (const ch of comprehensiveData.channels) {
                priceLines.push({
                    price: ch.upper,
                    color: 'rgba(255, 167, 38, 0.6)',
                    lineWidth: 2,
                    lineStyle: 'dashed',
                    title: `AI Channel Top: $${ch.upper.toFixed(2)}`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
                priceLines.push({
                    price: ch.lower,
                    color: 'rgba(255, 167, 38, 0.6)',
                    lineWidth: 2,
                    lineStyle: 'dashed',
                    title: `AI Channel Bot: $${ch.lower.toFixed(2)}`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
                if (ch.mid) {
                    priceLines.push({
                        price: ch.mid,
                        color: 'rgba(255, 167, 38, 0.3)',
                        lineWidth: 1,
                        lineStyle: 'dotted',
                        title: `AI Channel Mid: $${ch.mid.toFixed(2)}`,
                        axisLabelVisible: false,
                        source: 'ai',
                    });
                }
            }
        }

        // ── Trade targets (TP1/TP2/TP3) ──
        if (comprehensiveData?.tradeTargets) {
            const tt = comprehensiveData.tradeTargets;
            if (tt.entry) {
                priceLines.push({
                    price: tt.entry,
                    color: TP_COLORS.entry,
                    lineWidth: 2,
                    lineStyle: 'solid',
                    title: `Entry: $${tt.entry.toFixed(2)}`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
            if (tt.stop) {
                priceLines.push({
                    price: tt.stop,
                    color: TP_COLORS.stop,
                    lineWidth: 2,
                    lineStyle: 'solid',
                    title: `Stop: $${tt.stop.toFixed(2)}`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
            if (tt.tp1) {
                priceLines.push({
                    price: tt.tp1.price,
                    color: TP_COLORS.tp1,
                    lineWidth: 2,
                    lineStyle: 'dashed',
                    title: `TP1 (${tt.tp1.rr_ratio}) $${tt.tp1.price.toFixed(2)} — ${tt.tp1.probability_pct}%`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
            if (tt.tp2) {
                priceLines.push({
                    price: tt.tp2.price,
                    color: TP_COLORS.tp2,
                    lineWidth: 2,
                    lineStyle: 'dashed',
                    title: `TP2 (${tt.tp2.rr_ratio}) $${tt.tp2.price.toFixed(2)} — ${tt.tp2.probability_pct}%`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
            if (tt.tp3) {
                priceLines.push({
                    price: tt.tp3.price,
                    color: TP_COLORS.tp3,
                    lineWidth: 2,
                    lineStyle: 'dashed',
                    title: `TP3 (${tt.tp3.rr_ratio}) $${tt.tp3.price.toFixed(2)} — ${tt.tp3.probability_pct}%`,
                    axisLabelVisible: true,
                    source: 'ai',
                });
            }
        }

        return {
            priceLines,
            markers,
            trendLines,
            emergingPatterns,
            preCandleSetups,
            persistableDrawings,
            analysisTimestamp: lastBarTime || 0,
        };
    }, [patterns, lastBarTime, comprehensiveData]);
}
