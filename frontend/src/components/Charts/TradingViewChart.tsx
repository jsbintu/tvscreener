/**
 * TradingViewChart — Embeds the official TradingView Advanced Charts Widget
 *
 * Gives users the EXACT TradingView experience: 100+ indicators, drawing tools,
 * timeframes from 1m to 1M, volume profile, chart replay, compare mode.
 */

import { memo, useEffect, useRef } from 'react';

interface TradingViewChartProps {
    ticker: string;
    exchange?: string;
    height?: number | string;
    interval?: string;
    theme?: 'dark' | 'light';
}

function TradingViewChartInner({
    ticker,
    exchange = 'NASDAQ',
    height = 500,
    interval = 'D',
    theme = 'dark',
}: TradingViewChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const scriptRef = useRef<HTMLScriptElement | null>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        // Clean up previous widget
        const container = containerRef.current;
        container.innerHTML = '';

        // Create widget container div
        const widgetDiv = document.createElement('div');
        widgetDiv.className = 'tradingview-widget-container__widget';
        widgetDiv.style.height = typeof height === 'number' ? `${height}px` : height;
        widgetDiv.style.width = '100%';
        container.appendChild(widgetDiv);

        // Load widget script
        const script = document.createElement('script');
        script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
        script.type = 'text/javascript';
        script.async = true;
        script.innerHTML = JSON.stringify({
            symbol: `${exchange}:${ticker}`,
            interval: interval,
            timezone: 'America/New_York',
            theme: theme,
            style: '1', // Candlestick
            locale: 'en',
            allow_symbol_change: true,
            calendar: true,
            support_host: 'https://www.tradingview.com',
            toolbar_bg: '#0d1117',
            hide_side_toolbar: false,
            withdateranges: true,
            studies: ['RSI@tv-basicstudies', 'MACD@tv-basicstudies'],
            enable_publishing: false,
            hide_top_toolbar: false,
            save_image: true,
            width: '100%',
            height: typeof height === 'number' ? height : 500,
            backgroundColor: 'rgba(13, 17, 23, 1)',
            gridColor: 'rgba(48, 54, 61, 0.3)',
        });

        container.appendChild(script);
        scriptRef.current = script;

        return () => {
            container.innerHTML = '';
        };
    }, [ticker, exchange, interval, height, theme]);

    return (
        <div
            ref={containerRef}
            className="tradingview-widget-container"
            style={{
                width: '100%',
                height: typeof height === 'number' ? `${height}px` : height,
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
            }}
        />
    );
}

const TradingViewChart = memo(TradingViewChartInner);
export default TradingViewChart;
