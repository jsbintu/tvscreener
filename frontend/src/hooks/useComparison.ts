/**
 * useComparison — Hook for ticker comparison overlay on the chart.
 *
 * Allows overlaying SPY / QQQ / sector ETFs on the same chart,
 * normalized to percentage change from the visible start point.
 */

import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import { stockApi } from '../api/client';

export interface ComparisonSeries {
    ticker: string;
    color: string;
    visible: boolean;
}

interface ComparisonDataPoint {
    time: number;
    value: number; // percentage change from first visible bar
}

const PRESET_TICKERS: ComparisonSeries[] = [
    { ticker: 'SPY', color: '#42a5f5', visible: false },
    { ticker: 'QQQ', color: '#ab47bc', visible: false },
    { ticker: 'IWM', color: '#ffb74d', visible: false },
    { ticker: 'DIA', color: '#26c6da', visible: false },
];

export function useComparison(mainTicker: string, period: string, interval: string) {
    const [series, setSeries] = useState<ComparisonSeries[]>(() =>
        PRESET_TICKERS.filter((t) => t.ticker !== mainTicker.toUpperCase()),
    );

    const activeTickers = useMemo(() => series.filter((s) => s.visible).map((s) => s.ticker), [series]);

    // Fetch comparison data for active tickers
    const { data: comparisonData } = useQuery({
        queryKey: ['comparison', activeTickers, period, interval],
        queryFn: async () => {
            if (!activeTickers.length) return {};
            const results: Record<string, ComparisonDataPoint[]> = {};
            await Promise.all(
                activeTickers.map(async (ticker) => {
                    try {
                        const resp = await stockApi.getStock(ticker, period, interval);
                        // resp.data.candles or resp.data.chart
                        const candles = resp?.data?.candles || resp?.data?.chart || [];
                        if (candles.length) {
                            const firstClose = candles[0].close;
                            results[ticker] = candles.map((c: { time: number; close: number }) => ({
                                time: c.time,
                                value: ((c.close - firstClose) / firstClose) * 100,
                            }));
                        }
                    } catch {
                        // Silently skip failed tickers
                    }
                }),
            );
            return results;
        },
        enabled: activeTickers.length > 0,
        staleTime: 60_000,
    });

    const toggleComparison = useCallback((ticker: string) => {
        setSeries((prev) => prev.map((s) => (s.ticker === ticker ? { ...s, visible: !s.visible } : s)));
    }, []);

    const addCustomTicker = useCallback((ticker: string, color: string) => {
        const upper = ticker.toUpperCase();
        setSeries((prev) => {
            if (prev.some((s) => s.ticker === upper)) {
                return prev.map((s) => (s.ticker === upper ? { ...s, visible: true } : s));
            }
            return [...prev, { ticker: upper, color, visible: true }];
        });
    }, []);

    return {
        series,
        comparisonData: comparisonData || {},
        toggleComparison,
        addCustomTicker,
        activeTickers,
    };
}
