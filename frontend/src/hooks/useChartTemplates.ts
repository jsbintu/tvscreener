/**
 * useChartTemplates — Save/load chart configurations as named templates.
 *
 * Manages preset and custom templates with indicator settings,
 * chart type, period, interval, and sub-pane configuration.
 * Persisted to localStorage.
 */
import { useCallback, useState } from 'react';

export interface ChartTemplate {
    id: string;
    name: string;
    icon: string;
    isPreset: boolean;
    config: {
        chartType: string;
        period: string;
        interval: string;
        activeIndicators: string[];
        activeSubPanes: string[];
        showPatterns: boolean;
        showFib: boolean;
        showSR: boolean;
        showAIOverlay: boolean;
    };
}

const PRESET_TEMPLATES: ChartTemplate[] = [
    {
        id: 'scalper',
        name: 'Scalper',
        icon: '⚡',
        isPreset: true,
        config: {
            chartType: 'candlestick',
            period: '1d',
            interval: '1m',
            activeIndicators: ['ema_8', 'ema_21', 'vwap', 'bb', 'volume'],
            activeSubPanes: ['rsi', 'macd'],
            showPatterns: false,
            showFib: false,
            showSR: true,
            showAIOverlay: true,
        },
    },
    {
        id: 'daytrader',
        name: 'Day Trader',
        icon: '📊',
        isPreset: true,
        config: {
            chartType: 'candlestick',
            period: '5d',
            interval: '5m',
            activeIndicators: ['ema_9', 'ema_21', 'vwap', 'bb', 'volume'],
            activeSubPanes: ['rsi', 'macd', 'stoch'],
            showPatterns: true,
            showFib: false,
            showSR: true,
            showAIOverlay: true,
        },
    },
    {
        id: 'swing',
        name: 'Swing Trader',
        icon: '🌊',
        isPreset: true,
        config: {
            chartType: 'candlestick',
            period: '3mo',
            interval: '1d',
            activeIndicators: ['sma_20', 'sma_50', 'sma_200', 'bb', 'volume'],
            activeSubPanes: ['rsi', 'macd', 'stoch'],
            showPatterns: true,
            showFib: true,
            showSR: true,
            showAIOverlay: true,
        },
    },
    {
        id: 'investor',
        name: 'Long-Term',
        icon: '📈',
        isPreset: true,
        config: {
            chartType: 'line',
            period: '5y',
            interval: '1wk',
            activeIndicators: ['sma_50', 'sma_200', 'volume'],
            activeSubPanes: ['rsi'],
            showPatterns: true,
            showFib: false,
            showSR: true,
            showAIOverlay: true,
        },
    },
    {
        id: 'clean',
        name: 'Clean View',
        icon: '🔍',
        isPreset: true,
        config: {
            chartType: 'candlestick',
            period: '6mo',
            interval: '1d',
            activeIndicators: ['volume'],
            activeSubPanes: [],
            showPatterns: false,
            showFib: false,
            showSR: false,
            showAIOverlay: false,
        },
    },
    {
        id: 'ichimoku',
        name: 'Ichimoku',
        icon: '☁️',
        isPreset: true,
        config: {
            chartType: 'candlestick',
            period: '6mo',
            interval: '1d',
            activeIndicators: ['ichimoku', 'volume'],
            activeSubPanes: ['rsi'],
            showPatterns: false,
            showFib: false,
            showSR: false,
            showAIOverlay: true,
        },
    },
];

const STORAGE_KEY = 'mp_chart_templates';
const OLD_STORAGE_KEY = 'bubby-chart-templates';

function loadCustomTemplates(): ChartTemplate[] {
    try {
        // Migrate old key if present
        const oldData = localStorage.getItem(OLD_STORAGE_KEY);
        if (oldData && !localStorage.getItem(STORAGE_KEY)) {
            localStorage.setItem(STORAGE_KEY, oldData);
            localStorage.removeItem(OLD_STORAGE_KEY);
        }
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved) : [];
    } catch {
        return [];
    }
}

function saveCustomTemplates(templates: ChartTemplate[]) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
    } catch {
        /* ignore */
    }
}

export function useChartTemplates() {
    const [customTemplates, setCustomTemplates] = useState<ChartTemplate[]>(loadCustomTemplates);

    const allTemplates = [...PRESET_TEMPLATES, ...customTemplates];

    const saveTemplate = useCallback((name: string, config: ChartTemplate['config']) => {
        const template: ChartTemplate = {
            id: `custom-${Date.now()}`,
            name,
            icon: '💾',
            isPreset: false,
            config,
        };
        setCustomTemplates((prev) => {
            const next = [...prev, template];
            saveCustomTemplates(next);
            return next;
        });
    }, []);

    const deleteTemplate = useCallback((id: string) => {
        setCustomTemplates((prev) => {
            const next = prev.filter((t) => t.id !== id);
            saveCustomTemplates(next);
            return next;
        });
    }, []);

    return {
        templates: allTemplates,
        saveTemplate,
        deleteTemplate,
    };
}
