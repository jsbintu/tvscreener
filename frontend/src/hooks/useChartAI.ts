/**
 * useChartAI — AI-powered chart overlay data hook.
 *
 * Derives AI annotations from pattern data:
 *   - Pattern Annotations (boxes with confidence + target + stop-loss)
 *   - Confluence Zones (multi-signal convergence areas)
 *   - Prediction Zones (forward range based on pattern targets)
 *   - Chart Health Score (0-100 composite score)
 *
 * This hook is pure computation — no canvas drawing.
 * It takes chart data + pattern data as input and returns structured overlay data.
 */
import { useMemo } from 'react';

/* ─── Types ─── */
export interface PatternAnnotation {
    id: string;
    name: string;
    bias: 'bullish' | 'bearish' | 'neutral';
    confidence: number; // 0-100
    startTime: number; // unix timestamp
    endTime: number; // unix timestamp
    startPrice: number;
    endPrice: number;
    target?: number;
    stopLoss?: number;
    description: string;
}

export interface ConfluenceZone {
    id: string;
    priceLevel: number;
    strength: number; // 0-100 (how many signals converge)
    signals: string[]; // ["SMA 200", "Support", "Fib 0.618"]
    bias: 'support' | 'resistance';
}

export interface PredictionZone {
    startTime: number;
    bias: 'bullish' | 'bearish' | 'neutral';
    upperBound: number;
    lowerBound: number;
    midline: number;
    confidence: number; // 0-100
}

export interface ChartHealthScore {
    overall: number; // 0-100
    trendScore: number; // 0-100
    momentumScore: number; // 0-100
    volatilityScore: number; // 0-100
    volumeScore: number; // 0-100
    label: string; // "Strong", "Neutral", "Weak"
    color: string; // gradient color
}

export interface AIOverlayData {
    annotations: PatternAnnotation[];
    confluenceZones: ConfluenceZone[];
    predictionZone: PredictionZone | null;
    healthScore: ChartHealthScore;
}

/* ─── Interfaces for input data ─── */
interface PatternEntry {
    pattern_name?: string;
    bias?: string;
    confidence?: number;
    start_idx?: number;
    end_idx?: number;
    target_price?: number;
    stop_loss?: number;
    description?: string;
}

interface CandleEntry {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

interface IndicatorData {
    sma_20?: number[];
    sma_50?: number[];
    sma_200?: number[];
    rsi?: number[];
    bb_upper?: number[];
    bb_lower?: number[];
    [key: string]: number[] | undefined;
}

interface SRLevel {
    price: number;
    type: 'support' | 'resistance';
    strength?: number;
}

interface FibLevel {
    price: number;
    ratio: number;
}

/* ─── Helper functions ─── */
function computeConfluenceZones(
    candles: CandleEntry[],
    indicators: IndicatorData,
    srLevels: SRLevel[],
    fibLevels: FibLevel[],
): ConfluenceZone[] {
    if (!candles.length) return [];

    const lastCandle = candles[candles.length - 1];
    const priceRange = lastCandle.close * 0.03; // 3% tolerance
    const zones: Map<number, { signals: string[]; bias: 'support' | 'resistance' }> = new Map();

    const addSignal = (price: number, signal: string, bias: 'support' | 'resistance') => {
        // Find existing zone within tolerance
        for (const [key, zone] of zones) {
            if (Math.abs(key - price) < priceRange * 0.5) {
                zone.signals.push(signal);
                return;
            }
        }
        zones.set(price, { signals: [signal], bias });
    };

    // S/R levels
    for (const sr of srLevels) {
        addSignal(sr.price, `${sr.type === 'support' ? 'Support' : 'Resistance'}`, sr.type);
    }

    // Fibonacci levels
    for (const fib of fibLevels) {
        const bias = fib.price < lastCandle.close ? 'support' : 'resistance';
        addSignal(fib.price, `Fib ${fib.ratio}`, bias);
    }

    // Moving averages at last candle
    const lastIdx = candles.length - 1;
    if (indicators.sma_20?.[lastIdx]) {
        const bias = indicators.sma_20[lastIdx] < lastCandle.close ? 'support' : 'resistance';
        addSignal(indicators.sma_20[lastIdx], 'SMA 20', bias);
    }
    if (indicators.sma_50?.[lastIdx]) {
        const bias = indicators.sma_50[lastIdx] < lastCandle.close ? 'support' : 'resistance';
        addSignal(indicators.sma_50[lastIdx], 'SMA 50', bias);
    }
    if (indicators.sma_200?.[lastIdx]) {
        const bias = indicators.sma_200[lastIdx] < lastCandle.close ? 'support' : 'resistance';
        addSignal(indicators.sma_200[lastIdx], 'SMA 200', bias);
    }
    if (indicators.bb_upper?.[lastIdx]) {
        addSignal(indicators.bb_upper[lastIdx], 'BB Upper', 'resistance');
    }
    if (indicators.bb_lower?.[lastIdx]) {
        addSignal(indicators.bb_lower[lastIdx], 'BB Lower', 'support');
    }

    // Filter to zones with 2+ signals
    return Array.from(zones.entries())
        .filter(([, z]) => z.signals.length >= 2)
        .map(([price, z], idx) => ({
            id: `cz-${idx}`,
            priceLevel: price,
            strength: Math.min(100, z.signals.length * 25),
            signals: z.signals,
            bias: z.bias,
        }))
        .sort((a, b) => b.strength - a.strength);
}

function computeHealthScore(candles: CandleEntry[], indicators: IndicatorData): ChartHealthScore {
    if (candles.length < 20) {
        return {
            overall: 50,
            trendScore: 50,
            momentumScore: 50,
            volatilityScore: 50,
            volumeScore: 50,
            label: 'N/A',
            color: '#78909c',
        };
    }

    const last = candles[candles.length - 1];
    const lastIdx = candles.length - 1;

    // Trend score: price vs moving averages
    let trendScore = 50;
    if (indicators.sma_20?.[lastIdx] && indicators.sma_50?.[lastIdx]) {
        const aboveSma20 = last.close > indicators.sma_20[lastIdx];
        const aboveSma50 = last.close > indicators.sma_50[lastIdx];
        const sma20AboveSma50 = indicators.sma_20[lastIdx] > indicators.sma_50[lastIdx];
        trendScore = (aboveSma20 ? 25 : 0) + (aboveSma50 ? 25 : 0) + (sma20AboveSma50 ? 25 : 0);
        // 200 SMA bonus
        if (indicators.sma_200?.[lastIdx] && last.close > indicators.sma_200[lastIdx]) trendScore += 25;
    }

    // Momentum score: RSI
    let momentumScore = 50;
    if (indicators.rsi?.[lastIdx]) {
        const rsi = indicators.rsi[lastIdx];
        momentumScore = rsi > 70 ? 85 : rsi > 50 ? 65 : rsi > 30 ? 35 : 15;
    }

    // Volatility score: ATR vs price (lower is healthier for trend)
    let volatilityScore = 50;
    if (candles.length >= 14) {
        const recent14 = candles.slice(-14);
        const avgRange = recent14.reduce((sum, c) => sum + (c.high - c.low), 0) / 14;
        const avgRangePct = (avgRange / last.close) * 100;
        volatilityScore = avgRangePct < 1 ? 80 : avgRangePct < 2 ? 65 : avgRangePct < 4 ? 45 : 25;
    }

    // Volume score: recent vs average
    let volumeScore = 50;
    if (candles.length >= 20) {
        const recent5Vol = candles.slice(-5).reduce((s, c) => s + (c.volume || 0), 0) / 5;
        const avg20Vol = candles.slice(-20).reduce((s, c) => s + (c.volume || 0), 0) / 20;
        if (avg20Vol > 0) {
            const ratio = recent5Vol / avg20Vol;
            volumeScore = ratio > 1.5 ? 85 : ratio > 1 ? 65 : ratio > 0.5 ? 40 : 20;
        }
    }

    const overall = Math.round((trendScore + momentumScore + volatilityScore + volumeScore) / 4);
    const label = overall >= 75 ? 'Strong' : overall >= 55 ? 'Healthy' : overall >= 40 ? 'Neutral' : 'Weak';
    const color = overall >= 75 ? '#00c853' : overall >= 55 ? '#42a5f5' : overall >= 40 ? '#ffd54f' : '#ef5350';

    return { overall, trendScore, momentumScore, volatilityScore, volumeScore, label, color };
}

function computePredictionZone(
    candles: CandleEntry[],
    patterns: PatternEntry[],
    indicators: IndicatorData,
): PredictionZone | null {
    if (!candles.length) return null;

    const last = candles[candles.length - 1];
    const lastIdx = candles.length - 1;

    // Use pattern targets if available
    const bullishPatterns = patterns.filter((p) => p.bias === 'bullish' && p.target_price);
    const bearishPatterns = patterns.filter((p) => p.bias === 'bearish' && p.target_price);

    let bias: 'bullish' | 'bearish' | 'neutral' = 'neutral';
    let upper = last.close * 1.05;
    let lower = last.close * 0.95;

    if (bullishPatterns.length > bearishPatterns.length) {
        bias = 'bullish';
        const avgTarget = bullishPatterns.reduce((s, p) => s + (p.target_price || 0), 0) / bullishPatterns.length;
        upper = avgTarget;
        lower = bullishPatterns.reduce((s, p) => s + (p.stop_loss || last.close * 0.97), 0) / bullishPatterns.length;
    } else if (bearishPatterns.length > bullishPatterns.length) {
        bias = 'bearish';
        const avgTarget = bearishPatterns.reduce((s, p) => s + (p.target_price || 0), 0) / bearishPatterns.length;
        lower = avgTarget;
        upper = bearishPatterns.reduce((s, p) => s + (p.stop_loss || last.close * 1.03), 0) / bearishPatterns.length;
    } else if (indicators.bb_upper?.[lastIdx] && indicators.bb_lower?.[lastIdx]) {
        // Fallback to Bollinger Band range
        upper = indicators.bb_upper[lastIdx];
        lower = indicators.bb_lower[lastIdx];
    }

    const confidence =
        patterns.length > 0 ? Math.round(patterns.reduce((s, p) => s + (p.confidence || 50), 0) / patterns.length) : 40;

    return {
        startTime: last.time,
        bias,
        upperBound: upper,
        lowerBound: lower,
        midline: (upper + lower) / 2,
        confidence,
    };
}

/* ─── Main hook ─── */
export function useChartAI(
    candles: CandleEntry[],
    patterns: PatternEntry[],
    indicators: IndicatorData,
    srLevels: SRLevel[],
    fibLevels: FibLevel[],
): AIOverlayData {
    return useMemo(() => {
        // Pattern annotations
        const annotations: PatternAnnotation[] = patterns
            .filter((p) => p.pattern_name && p.start_idx != null && p.end_idx != null)
            .map((p, i) => {
                const startCandle = candles[p.start_idx!] || candles[0];
                const endCandle = candles[p.end_idx!] || candles[candles.length - 1];
                const sliceCandles = candles.slice(p.start_idx!, (p.end_idx || 0) + 1);
                const highInRange =
                    sliceCandles.length > 0 ? Math.max(...sliceCandles.map((c) => c.high)) : endCandle.high;
                const lowInRange =
                    sliceCandles.length > 0 ? Math.min(...sliceCandles.map((c) => c.low)) : endCandle.low;

                return {
                    id: `pa-${i}`,
                    name: p.pattern_name!,
                    bias: (p.bias || 'neutral') as 'bullish' | 'bearish' | 'neutral',
                    confidence: p.confidence || 50,
                    startTime: startCandle.time,
                    endTime: endCandle.time,
                    startPrice: lowInRange,
                    endPrice: highInRange,
                    target: p.target_price,
                    stopLoss: p.stop_loss,
                    description: p.description || p.pattern_name || '',
                };
            });

        // Confluence zones
        const confluenceZones = computeConfluenceZones(candles, indicators, srLevels, fibLevels);

        // Prediction zone
        const predictionZone = computePredictionZone(candles, patterns, indicators);

        // Health score
        const healthScore = computeHealthScore(candles, indicators);

        return { annotations, confluenceZones, predictionZone, healthScore };
    }, [candles, patterns, indicators, srLevels, fibLevels]);
}
