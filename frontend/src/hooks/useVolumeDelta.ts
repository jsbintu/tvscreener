/**
 * VolumeDelta — Sub-pane showing buy vs sell volume per bar.
 *
 * When we don't have trade-level data, estimates buy/sell volume
 * using a close-position-in-range heuristic:
 *   buyRatio = (close - low) / (high - low)
 *   buyVol = volume * buyRatio
 *   sellVol = volume * (1 - buyRatio)
 *   delta = buyVol - sellVol
 */
import { useMemo } from 'react';

export interface VolumeDeltaBar {
    time: number;
    delta: number; // positive = net buying, negative = net selling
    buyVolume: number;
    sellVolume: number;
    totalVolume: number;
    cumDelta: number; // cumulative delta from start
}

interface CandleInput {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export function useVolumeDelta(candles: CandleInput[]): VolumeDeltaBar[] {
    return useMemo(() => {
        if (!candles.length) return [];

        let cumDelta = 0;
        return candles.map((c) => {
            const vol = c.volume || 0;
            const range = c.high - c.low;
            const buyRatio = range > 0 ? (c.close - c.low) / range : 0.5;
            const buyVolume = vol * buyRatio;
            const sellVolume = vol * (1 - buyRatio);
            const delta = buyVolume - sellVolume;
            cumDelta += delta;

            return {
                time: c.time,
                delta,
                buyVolume,
                sellVolume,
                totalVolume: vol,
                cumDelta,
            };
        });
    }, [candles]);
}
