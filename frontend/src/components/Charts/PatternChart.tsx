/**
 * PatternChart — Premium charting component using TradingView's lightweight-charts v5.
 *
 * Phase 1 — Core UX Parity:
 *   ● Data legend (OHLCV + indicators at cursor)
 *   ● Chart types: Candlestick, Bars, Line, Area, Heikin Ashi, Hollow Candles
 *   ● Enhanced crosshair tooltip
 *   ● Sub-panes: RSI, MACD, Stochastic
 *   ● Fullscreen, Log scale, Screenshot, Go-to-date
 *   ● Pattern markers, S/R lines, Fibonacci levels
 *
 * Phase 2 — Drawing Tools:
 *   ● Trendline, Horizontal Line, Vertical Line, Rectangle, Fibonacci
 *   ● Drawing toolbar with color picker and line width
 *   ● Undo/redo, localStorage persistence
 *   ● Right-click context menu
 *   ● Keyboard shortcuts
 */

import { useQuery } from '@tanstack/react-query';
import {
    AreaSeries,
    type BarData,
    BarSeries,
    type CandlestickData,
    CandlestickSeries,
    ColorType,
    CrosshairMode,
    createChart,
    createSeriesMarkers,
    type HistogramData,
    HistogramSeries,
    type IChartApi,
    type ISeriesApi,
    type LineData,
    LineSeries,
    LineStyle,
    type MouseEventParams,
    PriceScaleMode,
    type SeriesMarker,
    type SeriesType,
    type Time,
} from 'lightweight-charts';
import { BarChart3, Brain, Calendar, Camera, Maximize2, Minimize2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { marketApi } from '../../api/client';
import { useAIDrawings } from '../../hooks/useAIDrawings';
import { useChartAI } from '../../hooks/useChartAI';
import { useDrawingTools } from '../../hooks/useDrawingTools';
import ChartAIOverlay from './ChartAIOverlay';
import ChartAnalysisSummary from './ChartAnalysisSummary';
import ChartContextMenu from './ChartContextMenu';
import ChartLegend, { type LegendData } from './ChartLegend';
import ChartToolbar from './ChartToolbar';
import DrawingToolbar from './DrawingToolbar';
import './PatternChart.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

/* ─── Types ─── */

interface ChartDataResponse {
    ticker: string;
    candles: CandlestickData[];
    volume: HistogramData[];
    indicators: Record<string, LineData[]>;
    sub_panes: Record<string, LineData[] | HistogramData[]>;
    support: { price: number; strength: number; type: string }[];
    resistance: { price: number; strength: number; type: string }[];
    patterns: {
        candlestick: PatternEntry[];
        chart: PatternEntry[];
        gap: PatternEntry[];
        volume: PatternEntry[];
        emerging: PatternEntry[];
        trend_lines: PatternEntry[];
        pre_candle: PatternEntry[];
        aged: any[];
        aging_summary: Record<string, number>;
        summary: { total?: number; bullish?: number; bearish?: number; bias?: string };
    };
    ai_analysis?: {
        ticker: string;
        price: number;
        timestamp: number;
        sections: { title: string; icon: string; content: string; severity?: string; items?: any[] }[];
        bias: string;
        pattern_count: number;
    };
    fibonacci: Record<string, unknown>;
    [k: string]: unknown;
}

interface PatternEntry {
    name?: string;
    direction?: string;
    time?: number;
    index?: number;
    [k: string]: unknown;
}

export type ChartType = 'candlestick' | 'bars' | 'line' | 'area' | 'heikinAshi' | 'hollowCandles';

interface PatternChartProps {
    ticker: string;
    defaultPeriod?: string;
    height?: number;
    mini?: boolean;
}

/* ─── Color palette ─── */
const COLORS: Record<string, string> = {
    sma_20: '#ffb74d',
    sma_50: '#42a5f5',
    sma_200: '#ef5350',
    ema_8: '#81c784',
    ema_21: '#ce93d8',
    bb_upper: 'rgba(33,150,243,0.4)',
    bb_middle: 'rgba(33,150,243,0.6)',
    bb_lower: 'rgba(33,150,243,0.4)',
    vwap: '#ffd54f',
    rsi: '#ab47bc',
    macd_line: '#42a5f5',
    macd_signal: '#ef5350',
    stoch_k: '#29b6f6',
    stoch_d: '#ff7043',
    support: '#00c853',
    resistance: '#ff1744',
    fib: 'rgba(255,215,0,0.5)',
    // Ichimoku
    ichimoku_tenkan: '#2962ff',
    ichimoku_kijun: '#d32f2f',
    ichimoku_senkou_a: 'rgba(76,175,80,0.5)',
    ichimoku_senkou_b: 'rgba(244,67,54,0.5)',
    ichimoku_chikou: '#9c27b0',
    // Parabolic SAR
    psar: '#ffd740',
    // ATR
    atr: '#ff9100',
    // ADX
    adx: '#ffa726',
    adx_pos: '#66bb6a',
    adx_neg: '#ef5350',
    // OBV
    obv: '#42a5f5',
    // CCI
    cci: '#7e57c2',
    // Williams %R
    williams: '#26c6da',
    // MFI
    mfi: '#ec407a',
};

/* EMA Ribbon gradient colors (warm→cool) */
const RIBBON_COLORS = ['#ff1744', '#ff5252', '#ff9100', '#ffb74d', '#66bb6a', '#26c6da', '#42a5f5', '#7e57c2'];
const RIBBON_PERIODS = [8, 13, 21, 34, 55, 89, 144, 233];
const COMPARE_COLORS = ['#e040fb', '#00e5ff', '#76ff03', '#ff6e40', '#536dfe'];

const BG = '#0a0e17';
const GRID = 'rgba(255,255,255,0.04)';
const TEXT = 'rgba(255,255,255,0.5)';

/* ─── Chart type display names ─── */
const CHART_TYPE_LABELS: Record<ChartType, string> = {
    candlestick: 'Candles',
    bars: 'Bars',
    line: 'Line',
    area: 'Area',
    heikinAshi: 'Heikin Ashi',
    hollowCandles: 'Hollow',
};

/* ─── Heikin Ashi computation ─── */
function computeHeikinAshi(candles: CandlestickData[]): CandlestickData[] {
    if (!candles.length) return [];
    const result: CandlestickData[] = [];

    for (let i = 0; i < candles.length; i++) {
        const c = candles[i];
        const prev = i > 0 ? result[i - 1] : null;

        const haClose = ((c.open as number) + (c.high as number) + (c.low as number) + (c.close as number)) / 4;
        const haOpen = prev
            ? ((prev.open as number) + (prev.close as number)) / 2
            : ((c.open as number) + (c.close as number)) / 2;
        const haHigh = Math.max(c.high as number, haOpen, haClose);
        const haLow = Math.min(c.low as number, haOpen, haClose);

        result.push({
            time: c.time,
            open: haOpen,
            high: haHigh,
            low: haLow,
            close: haClose,
        });
    }
    return result;
}

/* ─── Component ─── */

export default function PatternChart({ ticker, defaultPeriod = '6mo', height = 600, mini = false }: PatternChartProps) {
    const wrapperRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<HTMLDivElement>(null);
    const rsiPaneRef = useRef<HTMLDivElement>(null);
    const macdPaneRef = useRef<HTMLDivElement>(null);
    const stochPaneRef = useRef<HTMLDivElement>(null);
    const adxPaneRef = useRef<HTMLDivElement>(null);
    const obvPaneRef = useRef<HTMLDivElement>(null);
    const cciPaneRef = useRef<HTMLDivElement>(null);
    const williamsPaneRef = useRef<HTMLDivElement>(null);
    const mfiPaneRef = useRef<HTMLDivElement>(null);
    const atrPaneRef = useRef<HTMLDivElement>(null);

    const chartApiRef = useRef<IChartApi | null>(null);
    const rsiChartRef = useRef<IChartApi | null>(null);
    const macdChartRef = useRef<IChartApi | null>(null);
    const stochChartRef = useRef<IChartApi | null>(null);
    /* Generic sub-pane chart refs */
    const genericSubPaneRefs = useRef<Map<string, IChartApi>>(new Map());

    /* Store series refs for crosshair data lookups */
    const mainSeriesRef = useRef<ISeriesApi<SeriesType, Time> | null>(null);
    const indicatorSeriesRef = useRef<Map<string, ISeriesApi<SeriesType, Time>>>(new Map());

    const [period, setPeriod] = useState(defaultPeriod);
    const [interval, setInterval] = useState('1d');
    const [chartType, setChartType] = useState<ChartType>('candlestick');
    const [activeIndicators, setActiveIndicators] = useState<Set<string>>(
        new Set(['sma_20', 'sma_50', 'bb', 'volume']),
    );
    const [activeSubPanes, setActiveSubPanes] = useState<Set<string>>(new Set(mini ? [] : ['rsi']));
    const [showPatterns, setShowPatterns] = useState(true);
    const [showFib, setShowFib] = useState(false);
    const [showSR, setShowSR] = useState(true);
    const [showEvents, setShowEvents] = useState(false);
    const [showIntelligence, setShowIntelligence] = useState(false);
    const [compareSymbols, setCompareSymbols] = useState<string[]>([]);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [logScale, setLogScale] = useState(false);
    const [legendData, setLegendData] = useState<LegendData>({ indicators: {}, valid: false });
    const [showGoToDate, setShowGoToDate] = useState(false);
    const [goToDateValue, setGoToDateValue] = useState('');
    const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
    const [showAIOverlay, setShowAIOverlay] = useState(true);
    const [showAnalysis, setShowAnalysis] = useState(false);

    /* ── Compare symbol management ── */
    const handleAddCompare = useCallback((sym: string) => {
        setCompareSymbols((prev) => {
            if (prev.includes(sym) || prev.length >= 5) return prev;
            return [...prev, sym];
        });
    }, []);

    const handleRemoveCompare = useCallback((sym: string) => {
        setCompareSymbols((prev) => prev.filter((s) => s !== sym));
    }, []);

    /* ── Drawing tools ── */
    const drawingTools = useDrawingTools(ticker);

    /* ── Data fetch ── */
    const {
        data: chartData,
        isLoading,
        isError,
    } = useQuery<ChartDataResponse>({
        queryKey: ['chartData', ticker, period, interval],
        queryFn: async () => {
            const res = await marketApi.getChartData(ticker, period, interval);
            return res.data;
        },
        staleTime: 60_000,
        enabled: !!ticker,
    });

    /* ── AI hooks — compute overlay data from chart data ── */
    const aiCandles = useMemo(() => {
        if (!chartData?.candles) return [];
        // O(1) volume index instead of O(n) .find() per candle
        const volMap = new Map<number, number>();
        if (chartData.volume) {
            for (const v of chartData.volume) volMap.set(v.time as number, v.value as number);
        }
        return chartData.candles.map((c: any) => ({
            time: c.time as number,
            open: c.open as number,
            high: c.high as number,
            low: c.low as number,
            close: c.close as number,
            volume: volMap.get(c.time as number) || 0,
        }));
    }, [chartData]);

    const aiPatterns = useMemo(() => {
        if (!chartData?.patterns) return [];
        const all = [...(chartData.patterns.candlestick || []), ...(chartData.patterns.chart || [])];
        return all.map((p: any) => ({
            pattern_name: p.name || p.pattern_name || '',
            bias: p.direction || 'neutral',
            confidence: typeof p.confidence === 'number' ? (p.confidence > 1 ? p.confidence : p.confidence * 100) : 50,
            start_idx: p.start_index ?? p.bar_index ?? 0,
            end_idx: p.end_index ?? p.bar_index ?? aiCandles.length - 1,
            target_price: p.target,
            stop_loss: p.stop_loss,
            description: p.description || '',
        }));
    }, [chartData, aiCandles.length]);

    const aiIndicators = useMemo(() => {
        if (!chartData?.indicators) return {};
        const ind: Record<string, number[]> = {};
        for (const [key, series] of Object.entries(chartData.indicators)) {
            if (Array.isArray(series)) {
                ind[key] = series.map((d: any) => d.value as number);
            }
        }
        return ind;
    }, [chartData]);

    const aiSRLevels = useMemo(() => {
        if (!chartData) return [];
        return [
            ...(chartData.support || []).map((s: any) => ({
                price: s.price,
                type: 'support' as const,
                strength: s.strength,
            })),
            ...(chartData.resistance || []).map((r: any) => ({
                price: r.price,
                type: 'resistance' as const,
                strength: r.strength,
            })),
        ];
    }, [chartData]);

    const aiFibLevels = useMemo(() => {
        if (!chartData?.fibonacci) return [];
        const fib = chartData.fibonacci as any;
        if (!fib.levels) return [];
        return (fib.levels as any[]).map((l: any) => ({ price: l.price || 0, ratio: l.ratio || 0 }));
    }, [chartData]);

    const aiOverlayData = useChartAI(aiCandles, aiPatterns, aiIndicators, aiSRLevels, aiFibLevels);
    const aiDrawings = useAIDrawings(chartData?.patterns, aiCandles[aiCandles.length - 1]?.time);

    /* ── AI drawings render effect — price lines for AI-detected features ── */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const aiPriceLinesRef = useRef<any[]>([]);

    useEffect(() => {
        const mainSeries = mainSeriesRef.current;

        // Cleanup previous AI price lines
        for (const pl of aiPriceLinesRef.current) {
            try {
                mainSeries?.removePriceLine(pl);
            } catch {
                /* noop */
            }
        }
        aiPriceLinesRef.current = [];

        if (!chartApiRef.current || !mainSeries || !chartData || mini || !showAIOverlay) return;

        // Render AI price lines (trend line levels, targets, stops)
        for (const pl of aiDrawings.priceLines) {
            const lwLineStyle =
                pl.lineStyle === 'dashed'
                    ? LineStyle.Dashed
                    : pl.lineStyle === 'dotted'
                      ? LineStyle.Dotted
                      : LineStyle.Solid;
            const created = mainSeries.createPriceLine({
                price: pl.price,
                color: pl.color,
                lineWidth: pl.lineWidth as 1 | 2 | 3 | 4,
                lineStyle: lwLineStyle,
                title: pl.title,
                axisLabelVisible: pl.axisLabelVisible,
            });
            aiPriceLinesRef.current.push(created);
        }

        // NOTE: AI markers are merged into the main chart effect's unified marker array
        // to avoid overwriting pattern/event markers.

        return () => {
            for (const pl of aiPriceLinesRef.current) {
                try {
                    mainSeriesRef.current?.removePriceLine(pl);
                } catch {
                    /* noop */
                }
            }
            aiPriceLinesRef.current = [];
        };
    }, [chartData, aiDrawings, showAIOverlay, mini]);

    /* ── Toggle helpers ── */
    const toggleIndicator = useCallback((key: string) => {
        setActiveIndicators((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    }, []);

    const toggleSubPane = useCallback((key: string) => {
        setActiveSubPanes((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    }, []);

    /* ── Fullscreen handler ── */
    const toggleFullscreen = useCallback(() => {
        if (!wrapperRef.current) return;
        if (!isFullscreen) {
            wrapperRef.current.requestFullscreen?.().catch(() => {
                /* noop */
            });
        } else {
            document.exitFullscreen?.().catch(() => {
                /* noop */
            });
        }
    }, [isFullscreen]);

    useEffect(() => {
        const handleFSChange = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', handleFSChange);
        return () => document.removeEventListener('fullscreenchange', handleFSChange);
    }, []);

    /* ── Screenshot ── */
    const takeScreenshot = useCallback(() => {
        if (!chartApiRef.current) return;
        const canvas = chartApiRef.current.takeScreenshot();
        const link = document.createElement('a');
        link.download = `${ticker}-chart-${new Date().toISOString().slice(0, 10)}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
    }, [ticker]);

    /* ── Keyboard shortcuts ── */
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Only handle when our chart wrapper is focused or document has no specific focus
            const tag = (e.target as HTMLElement)?.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

            if (e.ctrlKey || e.metaKey) {
                if (e.key === 'z') {
                    e.preventDefault();
                    drawingTools.undo();
                    return;
                }
                if (e.key === 'y') {
                    e.preventDefault();
                    drawingTools.redo();
                    return;
                }
            }

            switch (e.key.toLowerCase()) {
                case 'f':
                    toggleFullscreen();
                    break;
                case 'l':
                    setLogScale((p) => !p);
                    break;
                case 's':
                    if (!e.ctrlKey && !e.metaKey) takeScreenshot();
                    break;
                case 't':
                    drawingTools.setActiveTool('trendline');
                    break;
                case 'h':
                    drawingTools.setActiveTool('horizontalLine');
                    break;
                case 'r':
                    drawingTools.setActiveTool('rectangle');
                    break;
                case 'escape':
                    drawingTools.setActiveTool('cursor');
                    setContextMenu(null);
                    break;
                case 'delete':
                case 'backspace':
                    drawingTools.deleteSelected();
                    break;
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [drawingTools, toggleFullscreen, takeScreenshot]);

    /* ── Go to date ── */
    const handleGoToDate = useCallback(() => {
        if (!goToDateValue || !chartApiRef.current) return;
        const ts = Math.floor(new Date(goToDateValue).getTime() / 1000) as unknown as Time;
        chartApiRef.current.timeScale().scrollToPosition(-10, false);
        // Find the closest candle to the given date
        const timeScale = chartApiRef.current.timeScale();
        const coord = timeScale.timeToCoordinate(ts);
        if (coord !== null) {
            timeScale.scrollToPosition(0, false);
        }
        setShowGoToDate(false);
    }, [goToDateValue]);

    /* ── Compute candles for current chart type ── */
    const processedCandles = useMemo(() => {
        if (!chartData?.candles?.length) return [];
        if (chartType === 'heikinAshi') return computeHeikinAshi(chartData.candles);
        return chartData.candles;
    }, [chartData, chartType]);

    /* ── Build candle→index lookup for crosshair ── */
    const candleMap = useMemo(() => {
        const map = new Map<string | number, CandlestickData>();
        for (const c of processedCandles) {
            map.set(c.time as string | number, c);
        }
        return map;
    }, [processedCandles]);

    /* ── Build prevClose lookup ── */
    const prevCloseMap = useMemo(() => {
        const map = new Map<string | number, number>();
        for (let i = 1; i < processedCandles.length; i++) {
            map.set(processedCandles[i].time as string | number, processedCandles[i - 1].close as number);
        }
        return map;
    }, [processedCandles]);

    /* ── Main chart rendering ── */
    useEffect(() => {
        if (!chartRef.current || !chartData) return;

        // Destroy previous chart
        if (chartApiRef.current) {
            chartApiRef.current.remove();
            chartApiRef.current = null;
        }
        mainSeriesRef.current = null;
        indicatorSeriesRef.current.clear();

        const subPaneCount = mini ? 0 : activeSubPanes.size;
        const mainHeight = isFullscreen
            ? window.innerHeight - subPaneCount * 150 - 80
            : height - (subPaneCount > 0 ? subPaneCount * 150 : 0);

        const chart = createChart(chartRef.current, {
            width: chartRef.current.clientWidth,
            height: Math.max(mainHeight, 250),
            layout: {
                background: { type: ColorType.Solid, color: BG },
                textColor: TEXT,
                fontFamily: "'Inter', sans-serif",
            },
            grid: {
                vertLines: { color: GRID },
                horzLines: { color: GRID },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    color: 'rgba(255,255,255,0.3)',
                    style: LineStyle.Dotted,
                    labelBackgroundColor: 'rgba(42,46,57,0.9)',
                },
                horzLine: {
                    color: 'rgba(255,255,255,0.3)',
                    style: LineStyle.Dotted,
                    labelBackgroundColor: 'rgba(42,46,57,0.9)',
                },
            },
            rightPriceScale: {
                borderColor: 'rgba(255,255,255,0.1)',
                scaleMargins: { top: 0.05, bottom: activeIndicators.has('volume') ? 0.25 : 0.05 },
                mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
            },
            timeScale: {
                borderColor: 'rgba(255,255,255,0.1)',
                timeVisible: interval !== '1d' && interval !== '1wk' && interval !== '1mo',
                secondsVisible: false,
            },
        });
        chartApiRef.current = chart;

        /* ── Add main series based on chart type ── */
        let mainSeries: ISeriesApi<SeriesType, Time>;

        switch (chartType) {
            case 'bars': {
                const s = chart.addSeries(BarSeries, {
                    upColor: '#00c853',
                    downColor: '#ff1744',
                    thinBars: false,
                });
                s.setData(processedCandles as BarData[]);
                mainSeries = s as ISeriesApi<SeriesType, Time>;
                break;
            }
            case 'line': {
                const lineData: LineData[] = processedCandles.map((c) => ({
                    time: c.time,
                    value: c.close as number,
                }));
                const s = chart.addSeries(LineSeries, {
                    color: '#42a5f5',
                    lineWidth: 2,
                    crosshairMarkerVisible: true,
                    crosshairMarkerRadius: 4,
                });
                s.setData(lineData);
                mainSeries = s as ISeriesApi<SeriesType, Time>;
                break;
            }
            case 'area': {
                const areaData: LineData[] = processedCandles.map((c) => ({
                    time: c.time,
                    value: c.close as number,
                }));
                const s = chart.addSeries(AreaSeries, {
                    topColor: 'rgba(33,150,243,0.4)',
                    bottomColor: 'rgba(33,150,243,0.02)',
                    lineColor: '#42a5f5',
                    lineWidth: 2,
                    crosshairMarkerVisible: true,
                });
                s.setData(areaData);
                mainSeries = s as ISeriesApi<SeriesType, Time>;
                break;
            }
            case 'hollowCandles': {
                const s = chart.addSeries(CandlestickSeries, {
                    upColor: 'transparent',
                    downColor: '#ff1744',
                    borderUpColor: '#00c853',
                    borderDownColor: '#ff1744',
                    wickUpColor: 'rgba(0,200,83,0.6)',
                    wickDownColor: 'rgba(255,23,68,0.6)',
                });
                s.setData(processedCandles);
                mainSeries = s as ISeriesApi<SeriesType, Time>;
                break;
            }
            default: {
                const s = chart.addSeries(CandlestickSeries, {
                    upColor: '#00c853',
                    downColor: '#ff1744',
                    borderUpColor: '#00c853',
                    borderDownColor: '#ff1744',
                    wickUpColor: 'rgba(0,200,83,0.6)',
                    wickDownColor: 'rgba(255,23,68,0.6)',
                });
                s.setData(processedCandles);
                mainSeries = s as ISeriesApi<SeriesType, Time>;
                break;
            }
        }
        mainSeriesRef.current = mainSeries;

        /* ── Volume histogram ── */
        if (activeIndicators.has('volume')) {
            const volumeSeries = chart.addSeries(HistogramSeries, {
                priceFormat: { type: 'volume' },
                priceScaleId: 'volume',
            });
            volumeSeries.priceScale().applyOptions({
                scaleMargins: { top: 0.8, bottom: 0 },
            });
            volumeSeries.setData(chartData.volume);
        }

        /* ── Indicator overlays ── */
        const addOverlay = (key: string, color: string, lineWidth: number = 2, style = LineStyle.Solid) => {
            if (!activeIndicators.has(key) || !chartData.indicators[key]?.length) return null;
            const s = chart.addSeries(LineSeries, {
                color,
                lineWidth: lineWidth as 1 | 2 | 3 | 4,
                lineStyle: style,
                crosshairMarkerVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
            });
            s.setData(chartData.indicators[key]);
            indicatorSeriesRef.current.set(key, s as ISeriesApi<SeriesType, Time>);
            return s;
        };

        addOverlay('sma_20', COLORS.sma_20);
        addOverlay('sma_50', COLORS.sma_50);
        addOverlay('sma_200', COLORS.sma_200, 2, LineStyle.Dashed);
        addOverlay('ema_8', COLORS.ema_8, 1);
        addOverlay('ema_21', COLORS.ema_21, 1);
        addOverlay('vwap', COLORS.vwap, 1, LineStyle.Dotted);

        // Bollinger Bands (3 lines)
        if (activeIndicators.has('bb')) {
            const bbOpts = {
                lineWidth: 1 as const,
                crosshairMarkerVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
            };
            if (chartData.indicators.bb_upper?.length) {
                const s = chart.addSeries(LineSeries, {
                    ...bbOpts,
                    color: COLORS.bb_upper,
                    lineStyle: LineStyle.Dashed,
                });
                s.setData(chartData.indicators.bb_upper);
                indicatorSeriesRef.current.set('bb_upper', s as ISeriesApi<SeriesType, Time>);
            }
            if (chartData.indicators.bb_middle?.length) {
                const s = chart.addSeries(LineSeries, { ...bbOpts, color: COLORS.bb_middle });
                s.setData(chartData.indicators.bb_middle);
                indicatorSeriesRef.current.set('bb_middle', s as ISeriesApi<SeriesType, Time>);
            }
            if (chartData.indicators.bb_lower?.length) {
                const s = chart.addSeries(LineSeries, {
                    ...bbOpts,
                    color: COLORS.bb_lower,
                    lineStyle: LineStyle.Dashed,
                });
                s.setData(chartData.indicators.bb_lower);
                indicatorSeriesRef.current.set('bb_lower', s as ISeriesApi<SeriesType, Time>);
            }
        }

        // Ichimoku Cloud (5 lines + cloud fill)
        if (activeIndicators.has('ichimoku')) {
            const ichiOpts = {
                lineWidth: 1 as const,
                crosshairMarkerVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
            };
            addOverlay('ichimoku_tenkan', COLORS.ichimoku_tenkan, 1);
            addOverlay('ichimoku_kijun', COLORS.ichimoku_kijun, 1);
            addOverlay('ichimoku_chikou', COLORS.ichimoku_chikou, 1, LineStyle.Dotted);

            // Senkou A as area (top of cloud)
            const senkou_a = chartData.indicators.ichimoku_senkou_a;
            const senkou_b = chartData.indicators.ichimoku_senkou_b;
            if (senkou_a?.length) {
                const s = chart.addSeries(LineSeries, { ...ichiOpts, color: COLORS.ichimoku_senkou_a });
                s.setData(senkou_a);
                indicatorSeriesRef.current.set('ichimoku_senkou_a', s as ISeriesApi<SeriesType, Time>);
            }
            if (senkou_b?.length) {
                const s = chart.addSeries(LineSeries, {
                    ...ichiOpts,
                    color: COLORS.ichimoku_senkou_b,
                    lineStyle: LineStyle.Dashed,
                });
                s.setData(senkou_b);
                indicatorSeriesRef.current.set('ichimoku_senkou_b', s as ISeriesApi<SeriesType, Time>);
            }
        }

        // EMA Ribbon (8 gradient-colored EMAs)
        if (activeIndicators.has('ema_ribbon')) {
            for (let ri = 0; ri < RIBBON_PERIODS.length; ri++) {
                const key = `ema_${RIBBON_PERIODS[ri]}`;
                if (chartData.indicators[key]?.length) {
                    const s = chart.addSeries(LineSeries, {
                        color: RIBBON_COLORS[ri],
                        lineWidth: 1,
                        crosshairMarkerVisible: false,
                        priceLineVisible: false,
                        lastValueVisible: false,
                    });
                    s.setData(chartData.indicators[key]);
                    indicatorSeriesRef.current.set(key, s as ISeriesApi<SeriesType, Time>);
                }
            }
        }

        // Parabolic SAR (dots on chart)
        if (activeIndicators.has('psar') && chartData.indicators.psar?.length) {
            const s = chart.addSeries(LineSeries, {
                color: COLORS.psar,
                lineWidth: 1,
                lineStyle: LineStyle.Dotted,
                crosshairMarkerVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
                pointMarkersVisible: true,
                pointMarkersRadius: 2,
            } as any);
            s.setData(chartData.indicators.psar);
            indicatorSeriesRef.current.set('psar', s as ISeriesApi<SeriesType, Time>);
        }

        // ATR overlay
        addOverlay('atr', COLORS.atr, 1, LineStyle.Dashed);

        if (
            showSR &&
            (chartType === 'candlestick' ||
                chartType === 'heikinAshi' ||
                chartType === 'hollowCandles' ||
                chartType === 'bars')
        ) {
            for (const level of chartData.support || []) {
                mainSeries.createPriceLine({
                    price: level.price,
                    color: COLORS.support,
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: `S ${level.price.toFixed(2)} (${level.strength}×)`,
                });
            }
            for (const level of chartData.resistance || []) {
                mainSeries.createPriceLine({
                    price: level.price,
                    color: COLORS.resistance,
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: `R ${level.price.toFixed(2)} (${level.strength}×)`,
                });
            }
        }

        /* ── Fibonacci retracement levels ── */
        if (showFib && chartData.fibonacci) {
            const levels = (chartData.fibonacci as Record<string, unknown>).retracement_levels as
                | Record<string, number>
                | undefined;
            if (levels) {
                for (const [label, price] of Object.entries(levels)) {
                    if (typeof price === 'number') {
                        mainSeries.createPriceLine({
                            price,
                            color: COLORS.fib,
                            lineWidth: 1,
                            lineStyle: LineStyle.Dotted,
                            axisLabelVisible: true,
                            title: `Fib ${label}`,
                        });
                    }
                }
            }
        }

        /* ── Pattern markers (v5: createSeriesMarkers) ── */
        const allMarkers: SeriesMarker<Time>[] = [];

        if (showPatterns && chartData.patterns) {
            const addMarkers = (pats: PatternEntry[] | undefined) => {
                if (!pats) return;
                for (const p of pats) {
                    if (p.time == null) continue;
                    const dir = ((p.direction as string) || '').toLowerCase();
                    const isBullish = dir === 'bullish';
                    allMarkers.push({
                        time: p.time as unknown as Time,
                        position: isBullish ? 'belowBar' : 'aboveBar',
                        color: isBullish ? '#00c853' : '#ff1744',
                        shape: isBullish ? 'arrowUp' : 'arrowDown',
                        text: ((p.name as string) || '').slice(0, 20),
                    });
                }
            };

            addMarkers(chartData.patterns.candlestick);
            addMarkers(chartData.patterns.chart);
            addMarkers(chartData.patterns.gap);
            addMarkers(chartData.patterns.volume);

            if (chartData.patterns.emerging) {
                for (const p of chartData.patterns.emerging) {
                    if (p.time == null) continue;
                    allMarkers.push({
                        time: p.time as unknown as Time,
                        position: 'aboveBar',
                        color: '#ffd54f',
                        shape: 'circle',
                        text: `${((p.name as string) || '').slice(0, 15)} ${Math.round(((p.completion as number) || 0) * 100)}%`,
                    });
                }
            }
        }

        /* ── Event markers (earnings, dividends, splits) ── */
        if (showEvents && (chartData as any).events?.length) {
            const EVENT_STYLES: Record<string, { shape: 'arrowUp' | 'arrowDown' | 'circle'; color: string }> = {
                earnings: { shape: 'arrowUp', color: '#42a5f5' },
                dividend: { shape: 'circle', color: '#66bb6a' },
                split: { shape: 'arrowDown', color: '#ffa726' },
            };
            for (const ev of (chartData as any).events) {
                const style = EVENT_STYLES[ev.type] || EVENT_STYLES.earnings;
                allMarkers.push({
                    time: ev.time as Time,
                    position: ev.type === 'split' ? 'aboveBar' : 'belowBar',
                    shape: style.shape,
                    color: style.color,
                    text: ev.label || ev.type[0].toUpperCase(),
                    size: 1,
                });
            }
        }

        /* ── AI markers (trend line points, pre-candle setups) ── */
        if (showAIOverlay && aiDrawings.markers.length > 0) {
            for (const m of aiDrawings.markers) {
                allMarkers.push({
                    time: m.time as unknown as Time,
                    position: m.position,
                    color: m.color,
                    shape: m.shape,
                    text: m.text,
                    size: m.size,
                });
            }
        }

        /* ── Unified marker write — single call prevents overwriting ── */
        allMarkers.sort((a, b) => (a.time as number) - (b.time as number));
        if (allMarkers.length > 0) {
            createSeriesMarkers(mainSeries, allMarkers);
        }

        /* ── Crosshair move → legend data ── */
        chart.subscribeCrosshairMove((param: MouseEventParams<Time>) => {
            if (!param.time) {
                setLegendData({ indicators: {}, valid: false });
                return;
            }

            const timeKey = param.time as string | number;
            const candle = candleMap.get(timeKey);
            const indicatorValues: Record<string, number | null> = {};

            // Collect indicator values at this time
            indicatorSeriesRef.current.forEach((series, key) => {
                const data = param.seriesData.get(series);
                if (data && 'value' in data) {
                    indicatorValues[key] = (data as any).value ?? null;
                }
            });

            if (candle) {
                setLegendData({
                    open: candle.open as number,
                    high: candle.high as number,
                    low: candle.low as number,
                    close: candle.close as number,
                    volume: undefined, // volume from separate series
                    prevClose: prevCloseMap.get(timeKey),
                    indicators: indicatorValues,
                    valid: true,
                });
            } else {
                // For line/area charts, get close from the main series data
                const mainData = param.seriesData.get(mainSeriesRef.current!);
                if (mainData && 'value' in mainData) {
                    setLegendData({
                        close: (mainData as any).value,
                        prevClose: prevCloseMap.get(timeKey),
                        indicators: indicatorValues,
                        valid: true,
                    });
                }
            }
        });

        /* ── Resize observer ── */
        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                chart.applyOptions({ width: entry.contentRect.width });
            }
        });
        resizeObserver.observe(chartRef.current);

        chart.timeScale().fitContent();

        return () => {
            resizeObserver.disconnect();
            chart.remove();
            chartApiRef.current = null;
            mainSeriesRef.current = null;
            indicatorSeriesRef.current.clear();
        };
    }, [
        chartData,
        processedCandles,
        candleMap,
        prevCloseMap,
        chartType,
        activeIndicators,
        showPatterns,
        showFib,
        showSR,
        showEvents,
        showAIOverlay,
        aiDrawings,
        logScale,
        mini,
        height,
        activeSubPanes.size,
        interval,
        isFullscreen,
    ]);

    /* ── Multi-symbol compare mode (% change overlay) ── */
    const compareSeriesRef = useRef<Map<string, ISeriesApi<SeriesType, Time>>>(new Map());

    useEffect(() => {
        const chart = chartApiRef.current;
        if (!chart || !chartData || mini || compareSymbols.length === 0) {
            // Cleanup any existing compare series
            compareSeriesRef.current.forEach((s) => {
                try {
                    chart?.removeSeries(s);
                } catch {
                    /* noop */
                }
            });
            compareSeriesRef.current.clear();
            return;
        }

        // Cleanup previous compare series
        compareSeriesRef.current.forEach((s) => {
            try {
                chart.removeSeries(s);
            } catch {
                /* noop */
            }
        });
        compareSeriesRef.current.clear();

        // Fetch comparison data for each symbol
        const fetchCompare = async () => {
            const baseClose0 = chartData.candles[0]?.close as number;
            if (!baseClose0) return;

            for (let ci = 0; ci < compareSymbols.length; ci++) {
                const sym = compareSymbols[ci];
                try {
                    const resp = await fetch(
                        `/api/chart-data/${sym}?period=${chartData.period || '6mo'}&interval=${chartData.interval || '1d'}`,
                    );
                    if (!resp.ok) continue;
                    const compData = await resp.json();
                    if (!compData.candles?.length) continue;

                    const compClose0 = compData.candles[0]?.close as number;
                    if (!compClose0) continue;

                    // Normalize to % change from first bar
                    const normalizedData: LineData[] = compData.candles.map((c: CandlestickData) => ({
                        time: c.time,
                        value: ((c.close as number) / compClose0 - 1) * 100,
                    }));

                    const compSeries = chart.addSeries(LineSeries, {
                        color: COMPARE_COLORS[ci % COMPARE_COLORS.length],
                        lineWidth: 2,
                        crosshairMarkerVisible: true,
                        priceLineVisible: false,
                        lastValueVisible: true,
                        title: sym,
                        priceScaleId: 'compare',
                    });
                    compSeries.setData(normalizedData);
                    compareSeriesRef.current.set(sym, compSeries as ISeriesApi<SeriesType, Time>);
                } catch {
                    // Skip failed fetches silently
                }
            }

            // Also normalize the main series to % if comparing
            const mainNorm: LineData[] = chartData.candles.map((c: CandlestickData) => ({
                time: c.time,
                value: ((c.close as number) / baseClose0 - 1) * 100,
            }));

            const mainCompSeries = chart.addSeries(LineSeries, {
                color: '#ffffff',
                lineWidth: 2,
                crosshairMarkerVisible: true,
                priceLineVisible: false,
                lastValueVisible: true,
                title: chartData.ticker || ticker,
                priceScaleId: 'compare',
            });
            mainCompSeries.setData(mainNorm);
            compareSeriesRef.current.set('__main__', mainCompSeries as ISeriesApi<SeriesType, Time>);
        };

        fetchCompare();

        const currentCompareSeries = compareSeriesRef.current;
        return () => {
            currentCompareSeries.forEach((s) => {
                try {
                    chart.removeSeries(s);
                } catch {
                    /* noop */
                }
            });
            currentCompareSeries.clear();
        };
    }, [chartData, compareSymbols, mini, ticker]);

    /* ── Intelligence layer: GEX/OI levels on chart ── */
    useEffect(() => {
        const chart = chartApiRef.current;
        const mainSeries = mainSeriesRef.current;
        if (!chart || !mainSeries || !chartData || mini || !showIntelligence) return;

        // Fetch GEX data and add key strike price lines
        const fetchIntel = async () => {
            try {
                const resp = await fetch(`/api/options/gex-detailed/${ticker}`);
                if (!resp.ok) return;
                const gex = await resp.json();

                const lastClose = chartData.candles[chartData.candles.length - 1]?.close as number;
                if (!lastClose) return;

                // GEX Flip strike (dealer gamma flip point)
                if (gex.gex_flip_strike) {
                    mainSeries.createPriceLine({
                        price: gex.gex_flip_strike,
                        color: '#ff9100',
                        lineWidth: 2,
                        lineStyle: LineStyle.Dashed,
                        title: `GEX Flip $${gex.gex_flip_strike}`,
                        axisLabelVisible: true,
                    });
                }

                // Key GEX strike (highest absolute GEX)
                if (gex.key_strike) {
                    mainSeries.createPriceLine({
                        price: gex.key_strike,
                        color: '#e040fb',
                        lineWidth: 2,
                        lineStyle: LineStyle.Solid,
                        title: `Max GEX $${gex.key_strike}`,
                        axisLabelVisible: true,
                    });
                }

                // Top 5 high-OI strike levels (within ±10% of current price)
                if (gex.oi_by_strike) {
                    const oiEntries = Object.entries(gex.oi_by_strike) as [string, number][];
                    const nearPrice = oiEntries
                        .filter(([k]) => {
                            const strike = parseFloat(k);
                            return strike >= lastClose * 0.9 && strike <= lastClose * 1.1;
                        })
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 5);

                    for (const [strike, oi] of nearPrice) {
                        mainSeries.createPriceLine({
                            price: parseFloat(strike),
                            color: 'rgba(156, 39, 176, 0.5)',
                            lineWidth: 1,
                            lineStyle: LineStyle.Dotted,
                            title: `OI ${(oi / 1000).toFixed(0)}k`,
                            axisLabelVisible: false,
                        });
                    }
                }

                // Dealer positioning label (long/short gamma)
                if (gex.dealer_positioning) {
                    const posLabel =
                        gex.dealer_positioning === 'long_gamma'
                            ? '🟢 Dealer Long Γ (Dampening)'
                            : '🔴 Dealer Short Γ (Amplifying)';
                    mainSeries.createPriceLine({
                        price: lastClose,
                        color: gex.dealer_positioning === 'long_gamma' ? '#00c853' : '#ff1744',
                        lineWidth: 1,
                        lineStyle: LineStyle.Dotted,
                        title: posLabel,
                        axisLabelVisible: false,
                    });
                }
            } catch {
                // GEX data unavailable — silently skip
            }
        };

        fetchIntel();
    }, [chartData, showIntelligence, mini, ticker]);

    /* ── RSI sub-pane ── */
    useEffect(() => {
        if (!rsiPaneRef.current || !chartData || !activeSubPanes.has('rsi') || mini) return;

        if (rsiChartRef.current) {
            rsiChartRef.current.remove();
            rsiChartRef.current = null;
        }

        const rsiChart = createChart(rsiPaneRef.current, {
            width: rsiPaneRef.current.clientWidth,
            height: 140,
            layout: {
                background: { type: ColorType.Solid, color: BG },
                textColor: TEXT,
                fontFamily: "'Inter', sans-serif",
            },
            grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)', scaleMargins: { top: 0.05, bottom: 0.05 } },
            timeScale: { visible: false },
            crosshair: { mode: CrosshairMode.Normal },
        });
        rsiChartRef.current = rsiChart;

        const rsiSeries = rsiChart.addSeries(LineSeries, {
            color: COLORS.rsi,
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: true,
        });
        rsiSeries.setData(chartData.sub_panes.rsi as LineData[]);

        rsiSeries.createPriceLine({
            price: 70,
            color: 'rgba(255,23,68,0.4)',
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            title: '70',
            axisLabelVisible: false,
        });
        rsiSeries.createPriceLine({
            price: 30,
            color: 'rgba(0,200,83,0.4)',
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            title: '30',
            axisLabelVisible: false,
        });
        rsiSeries.createPriceLine({
            price: 50,
            color: 'rgba(255,255,255,0.1)',
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            title: '',
            axisLabelVisible: false,
        });

        const obs = new ResizeObserver((entries) => {
            for (const e of entries) rsiChart.applyOptions({ width: e.contentRect.width });
        });
        obs.observe(rsiPaneRef.current);

        if (chartApiRef.current) {
            chartApiRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (range) rsiChart.timeScale().setVisibleLogicalRange(range);
            });
        }

        return () => {
            obs.disconnect();
            rsiChart.remove();
            rsiChartRef.current = null;
        };
    }, [chartData, activeSubPanes, mini]);

    /* ── MACD sub-pane ── */
    useEffect(() => {
        if (!macdPaneRef.current || !chartData || !activeSubPanes.has('macd') || mini) return;

        if (macdChartRef.current) {
            macdChartRef.current.remove();
            macdChartRef.current = null;
        }

        const macdChart = createChart(macdPaneRef.current, {
            width: macdPaneRef.current.clientWidth,
            height: 140,
            layout: {
                background: { type: ColorType.Solid, color: BG },
                textColor: TEXT,
                fontFamily: "'Inter', sans-serif",
            },
            grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
            timeScale: { visible: false },
            crosshair: { mode: CrosshairMode.Normal },
        });
        macdChartRef.current = macdChart;

        const histSeries = macdChart.addSeries(HistogramSeries, {
            priceFormat: { type: 'price', precision: 4 },
        });
        histSeries.setData(chartData.sub_panes.macd_hist as HistogramData[]);

        const macdLine = macdChart.addSeries(LineSeries, {
            color: COLORS.macd_line,
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        macdLine.setData(chartData.sub_panes.macd_line as LineData[]);

        const sigLine = macdChart.addSeries(LineSeries, {
            color: COLORS.macd_signal,
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        sigLine.setData(chartData.sub_panes.macd_signal as LineData[]);

        macdLine.createPriceLine({
            price: 0,
            color: 'rgba(255,255,255,0.1)',
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            title: '',
            axisLabelVisible: false,
        });

        const obs = new ResizeObserver((entries) => {
            for (const e of entries) macdChart.applyOptions({ width: e.contentRect.width });
        });
        obs.observe(macdPaneRef.current);

        if (chartApiRef.current) {
            chartApiRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (range) macdChart.timeScale().setVisibleLogicalRange(range);
            });
        }

        return () => {
            obs.disconnect();
            macdChart.remove();
            macdChartRef.current = null;
        };
    }, [chartData, activeSubPanes, mini]);

    /* ── Stochastic sub-pane ── */
    useEffect(() => {
        if (!stochPaneRef.current || !chartData || !activeSubPanes.has('stoch') || mini) return;

        if (stochChartRef.current) {
            stochChartRef.current.remove();
            stochChartRef.current = null;
        }

        const stochChart = createChart(stochPaneRef.current, {
            width: stochPaneRef.current.clientWidth,
            height: 140,
            layout: {
                background: { type: ColorType.Solid, color: BG },
                textColor: TEXT,
                fontFamily: "'Inter', sans-serif",
            },
            grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)', scaleMargins: { top: 0.05, bottom: 0.05 } },
            timeScale: { visible: false },
            crosshair: { mode: CrosshairMode.Normal },
        });
        stochChartRef.current = stochChart;

        // %K line
        if (chartData.sub_panes.stoch_k) {
            const kSeries = stochChart.addSeries(LineSeries, {
                color: COLORS.stoch_k,
                lineWidth: 2,
                priceLineVisible: false,
                lastValueVisible: true,
            });
            kSeries.setData(chartData.sub_panes.stoch_k as LineData[]);
        }

        // %D line
        if (chartData.sub_panes.stoch_d) {
            const dSeries = stochChart.addSeries(LineSeries, {
                color: COLORS.stoch_d,
                lineWidth: 1,
                lineStyle: LineStyle.Dashed,
                priceLineVisible: false,
                lastValueVisible: true,
            });
            dSeries.setData(chartData.sub_panes.stoch_d as LineData[]);
        }

        // Overbought/oversold zones
        const refSeries = stochChart.addSeries(LineSeries, {
            color: 'transparent',
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
        });
        refSeries.setData([
            { time: chartData.candles[0]?.time as Time, value: 50 },
            { time: chartData.candles[chartData.candles.length - 1]?.time as Time, value: 50 },
        ]);
        refSeries.createPriceLine({
            price: 80,
            color: 'rgba(255,23,68,0.4)',
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            title: '80',
            axisLabelVisible: false,
        });
        refSeries.createPriceLine({
            price: 20,
            color: 'rgba(0,200,83,0.4)',
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            title: '20',
            axisLabelVisible: false,
        });
        refSeries.createPriceLine({
            price: 50,
            color: 'rgba(255,255,255,0.1)',
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            title: '',
            axisLabelVisible: false,
        });

        const obs = new ResizeObserver((entries) => {
            for (const e of entries) stochChart.applyOptions({ width: e.contentRect.width });
        });
        obs.observe(stochPaneRef.current);

        if (chartApiRef.current) {
            chartApiRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (range) stochChart.timeScale().setVisibleLogicalRange(range);
            });
        }

        return () => {
            obs.disconnect();
            stochChart.remove();
            stochChartRef.current = null;
        };
    }, [chartData, activeSubPanes, mini]);

    /* ── Generic sub-panes (ADX, OBV, CCI, Williams, MFI, ATR) ── */
    const GENERIC_PANE_CONFIG: {
        key: string;
        ref: React.RefObject<HTMLDivElement | null>;
        series: { dataKey: string; color: string; lineWidth?: number; style?: number }[];
        refLines?: { price: number; color: string; style?: number; title?: string }[];
    }[] = useMemo(
        () => [
            {
                key: 'adx',
                ref: adxPaneRef,
                series: [
                    { dataKey: 'adx', color: COLORS.adx, lineWidth: 2 },
                    { dataKey: 'adx_pos', color: COLORS.adx_pos },
                    { dataKey: 'adx_neg', color: COLORS.adx_neg },
                ],
                refLines: [{ price: 25, color: 'rgba(255,255,255,0.2)', style: LineStyle.Dashed, title: '25' }],
            },
            {
                key: 'obv',
                ref: obvPaneRef,
                series: [{ dataKey: 'obv', color: COLORS.obv, lineWidth: 2 }],
                refLines: [],
            },
            {
                key: 'cci',
                ref: cciPaneRef,
                series: [{ dataKey: 'cci', color: COLORS.cci, lineWidth: 2 }],
                refLines: [
                    { price: 100, color: 'rgba(255,23,68,0.4)', style: LineStyle.Dashed, title: '100' },
                    { price: -100, color: 'rgba(0,200,83,0.4)', style: LineStyle.Dashed, title: '-100' },
                    { price: 0, color: 'rgba(255,255,255,0.1)', style: LineStyle.Dotted },
                ],
            },
            {
                key: 'williams',
                ref: williamsPaneRef,
                series: [{ dataKey: 'williams', color: COLORS.williams, lineWidth: 2 }],
                refLines: [
                    { price: -20, color: 'rgba(255,23,68,0.4)', style: LineStyle.Dashed, title: '-20' },
                    { price: -80, color: 'rgba(0,200,83,0.4)', style: LineStyle.Dashed, title: '-80' },
                    { price: -50, color: 'rgba(255,255,255,0.1)', style: LineStyle.Dotted },
                ],
            },
            {
                key: 'mfi',
                ref: mfiPaneRef,
                series: [{ dataKey: 'mfi', color: COLORS.mfi, lineWidth: 2 }],
                refLines: [
                    { price: 80, color: 'rgba(255,23,68,0.4)', style: LineStyle.Dashed, title: '80' },
                    { price: 20, color: 'rgba(0,200,83,0.4)', style: LineStyle.Dashed, title: '20' },
                    { price: 50, color: 'rgba(255,255,255,0.1)', style: LineStyle.Dotted },
                ],
            },
            {
                key: 'atr',
                ref: atrPaneRef,
                series: [{ dataKey: 'atr_pane', color: COLORS.atr, lineWidth: 2 }],
                refLines: [],
            },
        ],
        [],
    );

    useEffect(() => {
        if (!chartData || mini) return;

        // Cleanup previous generic sub-pane charts
        genericSubPaneRefs.current.forEach((c) => {
            c.remove();
        });
        genericSubPaneRefs.current.clear();

        for (const pane of GENERIC_PANE_CONFIG) {
            if (!activeSubPanes.has(pane.key) || !pane.ref.current) continue;

            const paneChart = createChart(pane.ref.current, {
                width: pane.ref.current.clientWidth,
                height: 140,
                layout: {
                    background: { type: ColorType.Solid, color: BG },
                    textColor: TEXT,
                    fontFamily: "'Inter', sans-serif",
                },
                grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
                rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)', scaleMargins: { top: 0.05, bottom: 0.05 } },
                timeScale: { visible: false },
                crosshair: { mode: CrosshairMode.Normal },
            });
            genericSubPaneRefs.current.set(pane.key, paneChart);

            // Add series
            let firstSeries: ISeriesApi<SeriesType, Time> | null = null;
            for (const s of pane.series) {
                const data = chartData.sub_panes[s.dataKey];
                if (!data?.length) continue;
                const lineSeries = paneChart.addSeries(LineSeries, {
                    color: s.color,
                    lineWidth: (s.lineWidth ?? 1) as 1 | 2 | 3 | 4,
                    lineStyle: s.style ?? LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: true,
                });
                lineSeries.setData(data as LineData[]);
                if (!firstSeries) firstSeries = lineSeries as ISeriesApi<SeriesType, Time>;
            }

            // Add reference lines
            if (firstSeries && pane.refLines) {
                for (const rl of pane.refLines) {
                    firstSeries.createPriceLine({
                        price: rl.price,
                        color: rl.color,
                        lineWidth: 1,
                        lineStyle: rl.style ?? LineStyle.Dashed,
                        title: rl.title ?? '',
                        axisLabelVisible: false,
                    });
                }
            }

            // Resize observer
            const el = pane.ref.current;
            const resObs = new ResizeObserver((entries) => {
                for (const e of entries) paneChart.applyOptions({ width: e.contentRect.width });
            });
            resObs.observe(el);

            // Sync time-scale with main chart
            if (chartApiRef.current) {
                chartApiRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                    if (range) paneChart.timeScale().setVisibleLogicalRange(range);
                });
            }
        }

        const currentPaneCharts = genericSubPaneRefs.current;
        return () => {
            currentPaneCharts.forEach((c) => {
                c.remove();
            });
            currentPaneCharts.clear();
        };
    }, [chartData, activeSubPanes, mini, GENERIC_PANE_CONFIG]);

    /* ── Pattern summary badge ── */
    const summary = chartData?.patterns?.summary;
    const bias = summary?.bias || 'neutral';
    const biasEmoji = bias === 'bullish' ? '🟢' : bias === 'bearish' ? '🔴' : '⚪';

    /* ── Render ── */
    if (isError) {
        return <div className="pattern-chart-error">Failed to load chart data for {ticker}</div>;
    }

    return (
        <div className={`pattern-chart-wrapper ${isFullscreen ? 'pattern-chart-fullscreen' : ''}`} ref={wrapperRef}>
            {/* Toolbar */}
            {!mini && (
                <ChartToolbar
                    period={period}
                    setPeriod={setPeriod}
                    interval={interval}
                    setInterval={setInterval}
                    activeIndicators={activeIndicators}
                    toggleIndicator={toggleIndicator}
                    activeSubPanes={activeSubPanes}
                    toggleSubPane={toggleSubPane}
                    showPatterns={showPatterns}
                    setShowPatterns={setShowPatterns}
                    showFib={showFib}
                    setShowFib={setShowFib}
                    showSR={showSR}
                    setShowSR={setShowSR}
                    showEvents={showEvents}
                    setShowEvents={setShowEvents}
                    showIntelligence={showIntelligence}
                    setShowIntelligence={setShowIntelligence}
                    showAnalysis={showAnalysis}
                    setShowAnalysis={setShowAnalysis}
                    compareSymbols={compareSymbols}
                    onAddCompare={handleAddCompare}
                    onRemoveCompare={handleRemoveCompare}
                />
            )}

            {/* Chart controls bar (chart type, fullscreen, log, screenshot, go-to-date) */}
            {!mini && (
                <div className="chart-controls-bar">
                    {/* Chart type selector */}
                    <div className="chart-type-group">
                        <BarChart3 size={14} className="chart-ctrl-icon" />
                        {(Object.keys(CHART_TYPE_LABELS) as ChartType[]).map((ct) => (
                            <button
                                type="button"
                                key={ct}
                                className={`chart-type-btn ${chartType === ct ? 'active' : ''}`}
                                onClick={() => setChartType(ct)}
                                title={CHART_TYPE_LABELS[ct]}
                            >
                                {CHART_TYPE_LABELS[ct]}
                            </button>
                        ))}
                    </div>

                    <div className="chart-ctrl-actions">
                        {/* Go-to-date */}
                        <button
                            type="button"
                            className="chart-ctrl-btn"
                            onClick={() => setShowGoToDate(!showGoToDate)}
                            title="Go to date"
                        >
                            <Calendar size={14} />
                        </button>
                        {showGoToDate && (
                            <div className="goto-date-popover">
                                <input
                                    type="date"
                                    value={goToDateValue}
                                    onChange={(e) => setGoToDateValue(e.target.value)}
                                    className="goto-date-input"
                                />
                                <button type="button" className="goto-date-go" onClick={handleGoToDate}>
                                    Go
                                </button>
                            </div>
                        )}

                        {/* Log scale */}
                        <button
                            type="button"
                            className={`chart-ctrl-btn ${logScale ? 'active' : ''}`}
                            onClick={() => setLogScale((p) => !p)}
                            title="Log scale"
                        >
                            Log
                        </button>

                        {/* Screenshot */}
                        <button
                            type="button"
                            className="chart-ctrl-btn"
                            onClick={takeScreenshot}
                            title="Take screenshot"
                        >
                            <Camera size={14} />
                        </button>

                        {/* AI overlay toggle */}
                        <button
                            type="button"
                            className={`chart-ctrl-btn ${showAIOverlay ? 'active' : ''}`}
                            onClick={() => setShowAIOverlay((p) => !p)}
                            title="AI Insights"
                        >
                            <Brain size={14} />
                        </button>
                        {/* Fullscreen */}
                        <button
                            type="button"
                            className="chart-ctrl-btn"
                            onClick={toggleFullscreen}
                            title="Toggle fullscreen"
                        >
                            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                        </button>
                    </div>
                </div>
            )}

            {/* Pattern summary */}
            {summary && summary.total != null && summary.total > 0 && (
                <div className="pattern-summary-bar">
                    <span className="bias-badge" data-bias={bias}>
                        {biasEmoji} {bias.toUpperCase()}
                    </span>
                    <span className="pattern-counts">
                        {summary.total} patterns • {summary.bullish} bullish • {summary.bearish} bearish
                    </span>
                </div>
            )}

            {/* Loading overlay */}
            {isLoading && (
                <div className="chart-loading-overlay">
                    <div className="chart-spinner" />
                    <span>Loading chart data…</span>
                </div>
            )}

            {/* Data legend at top-left of chart + drawing toolbar */}
            <div className="chart-main-area">
                {!mini && chartData && (
                    <ChartLegend ticker={ticker} data={legendData} chartType={CHART_TYPE_LABELS[chartType]} />
                )}

                {/* AI overlay */}
                {!mini && chartData && showAIOverlay && <ChartAIOverlay data={aiOverlayData} visible={showAIOverlay} />}

                {/* AI Analysis Summary panel */}
                {!mini && chartData && (
                    <ChartAnalysisSummary
                        visible={showAnalysis}
                        onClose={() => setShowAnalysis(false)}
                        aiAnalysis={chartData.ai_analysis}
                        overlayData={aiOverlayData}
                        trendLineCount={chartData.patterns?.trend_lines?.length ?? 0}
                        emergingCount={chartData.patterns?.emerging?.length ?? 0}
                        preCandleCount={chartData.patterns?.pre_candle?.length ?? 0}
                    />
                )}

                {/* Drawing toolbar */}
                {!mini && (
                    <DrawingToolbar
                        activeTool={drawingTools.activeTool}
                        drawingColor={drawingTools.drawingColor}
                        drawingLineWidth={drawingTools.drawingLineWidth}
                        canUndo={drawingTools.canUndo}
                        canRedo={drawingTools.canRedo}
                        drawingCount={drawingTools.drawings.length}
                        onSelectTool={drawingTools.setActiveTool}
                        onColorChange={drawingTools.setDrawingColor}
                        onLineWidthChange={drawingTools.setDrawingLineWidth}
                        onUndo={drawingTools.undo}
                        onRedo={drawingTools.redo}
                        onClearAll={drawingTools.clearAll}
                        onDeleteSelected={drawingTools.deleteSelected}
                    />
                )}

                {/* Main chart */}
                <div
                    ref={chartRef}
                    role="application"
                    className={`chart-container ${drawingTools.activeTool !== 'cursor' ? 'drawing-mode' : ''}`}
                    onContextMenu={(e) => {
                        if (mini) return;
                        e.preventDefault();
                        setContextMenu({ x: e.clientX, y: e.clientY });
                    }}
                />

                {/* Context menu */}
                {contextMenu && !mini && (
                    <ChartContextMenu
                        x={contextMenu.x}
                        y={contextMenu.y}
                        onClose={() => setContextMenu(null)}
                        actions={[
                            {
                                label: 'Trend Line',
                                icon: '📈',
                                shortcut: 'T',
                                onClick: () => drawingTools.setActiveTool('trendline'),
                            },
                            {
                                label: 'Horizontal Line',
                                icon: '➖',
                                shortcut: 'H',
                                onClick: () => drawingTools.setActiveTool('horizontalLine'),
                            },
                            {
                                label: 'Rectangle',
                                icon: '⬜',
                                shortcut: 'R',
                                onClick: () => drawingTools.setActiveTool('rectangle'),
                            },
                            {
                                label: 'Fibonacci',
                                icon: '🔢',
                                onClick: () => drawingTools.setActiveTool('fibRetracement'),
                            },
                            { label: 'Measure', icon: '📏', onClick: () => drawingTools.setActiveTool('measure') },
                            { label: 'Toggle S/R', icon: '📊', divider: true, onClick: () => setShowSR((p) => !p) },
                            { label: 'Toggle Fibonacci', icon: '🎯', onClick: () => setShowFib((p) => !p) },
                            {
                                label: logScale ? 'Linear Scale' : 'Log Scale',
                                icon: '📐',
                                divider: true,
                                shortcut: 'L',
                                onClick: () => setLogScale((p) => !p),
                            },
                            { label: 'Screenshot', icon: '📸', shortcut: 'S', onClick: takeScreenshot },
                            { label: 'Fullscreen', icon: '⛶', shortcut: 'F', onClick: toggleFullscreen },
                        ]}
                    />
                )}
            </div>

            {/* Sub-panes */}
            {!mini && activeSubPanes.has('rsi') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">RSI (14)</div>
                    <div ref={rsiPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('macd') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">MACD (12, 26, 9)</div>
                    <div ref={macdPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('stoch') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">Stochastic (14, 3, 3)</div>
                    <div ref={stochPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('adx') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">ADX (14) + DI±</div>
                    <div ref={adxPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('obv') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">OBV</div>
                    <div ref={obvPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('cci') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">CCI (20)</div>
                    <div ref={cciPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('williams') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">Williams %R (14)</div>
                    <div ref={williamsPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('mfi') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">MFI (14)</div>
                    <div ref={mfiPaneRef} className="sub-pane-chart" />
                </div>
            )}
            {!mini && activeSubPanes.has('atr') && (
                <div className="sub-pane">
                    <div className="sub-pane-label">ATR (14)</div>
                    <div ref={atrPaneRef} className="sub-pane-chart" />
                </div>
            )}
        </div>
    );
}
