/**
 * WebSocket hooks — JWT-authenticated with auto-reconnect
 *
 * Passes stored JWT token as `?token=` query param.
 * Reconnects with exponential backoff (1s → 30s max, 5 attempts).
 */

import { useEffect, useRef, useState } from 'react';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

interface PriceData {
    ticker: string;
    price: number | null;
    bid: number | null;
    ask: number | null;
    volume: number | null;
    timestamp: string | null;
}

type ConnectionState = 'disconnected' | 'connected' | 'reconnecting';

// ── Helpers ──

function getAuthParam(): string {
    const token = localStorage.getItem('mp_access_token');
    if (token) return `token=${encodeURIComponent(token)}`;
    const key = localStorage.getItem('mp_api_key') || import.meta.env.VITE_API_KEY;
    if (key) return `api_key=${encodeURIComponent(key)}`;
    return '';
}

const RETRY_MAX_ATTEMPTS = 5;
const RETRY_INITIAL_MS = 1000;
const RETRY_MAX_MS = 30000;

function retryDelay(attempt: number): number {
    return Math.min(RETRY_INITIAL_MS * 2 ** attempt, RETRY_MAX_MS);
}

// ── useLivePrice ──

export function useLivePrice(ticker: string | null) {
    const [price, setPrice] = useState<PriceData | null>(null);
    const [lastUpdate, setLastUpdate] = useState<number | null>(null);
    const [status, setStatus] = useState<ConnectionState>('disconnected');
    const wsRef = useRef<WebSocket | null>(null);
    const attemptRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const activeRef = useRef(true);

    useEffect(() => {
        if (!ticker) return;

        activeRef.current = true;
        attemptRef.current = 0;
        queueMicrotask(() => setPrice(null));

        function connect() {
            if (!ticker || !activeRef.current) return;

            const auth = getAuthParam();
            const url = `${WS_BASE}/ws/stream/${ticker}${auth ? `?${auth}` : ''}`;
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setStatus('connected');
                attemptRef.current = 0;
            };

            ws.onclose = () => {
                if (!activeRef.current) {
                    setStatus('disconnected');
                    return;
                }
                if (attemptRef.current < RETRY_MAX_ATTEMPTS) {
                    setStatus('reconnecting');
                    const delay = retryDelay(attemptRef.current);
                    attemptRef.current++;
                    timerRef.current = setTimeout(connect, delay);
                } else {
                    setStatus('disconnected');
                }
            };

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'price') {
                        setPrice(msg.data);
                        setLastUpdate(Date.now());
                    }
                } catch {
                    /* ignore malformed */
                }
            };
        }

        connect();

        return () => {
            activeRef.current = false;
            if (timerRef.current) clearTimeout(timerRef.current);
            wsRef.current?.close();
            setStatus('disconnected');
        };
    }, [ticker]);

    return { price, status, connected: status === 'connected', lastUpdate };
}

// ── useAlertStream ──

export function useAlertStream(onAlert: (data: Record<string, unknown>) => void) {
    const [status, setStatus] = useState<ConnectionState>('disconnected');
    const wsRef = useRef<WebSocket | null>(null);
    const attemptRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const activeRef = useRef(true);
    const onAlertRef = useRef(onAlert);

    // Keep callback ref in sync inside an effect
    useEffect(() => {
        onAlertRef.current = onAlert;
    }, [onAlert]);

    useEffect(() => {
        activeRef.current = true;
        attemptRef.current = 0;

        function connect() {
            if (!activeRef.current) return;

            const auth = getAuthParam();
            const url = `${WS_BASE}/ws/alerts${auth ? `?${auth}` : ''}`;
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setStatus('connected');
                attemptRef.current = 0;
            };

            ws.onclose = () => {
                if (!activeRef.current) {
                    setStatus('disconnected');
                    return;
                }
                if (attemptRef.current < RETRY_MAX_ATTEMPTS) {
                    setStatus('reconnecting');
                    const delay = retryDelay(attemptRef.current);
                    attemptRef.current++;
                    timerRef.current = setTimeout(connect, delay);
                } else {
                    setStatus('disconnected');
                }
            };

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'alert') {
                        onAlertRef.current(msg.data);
                    }
                } catch {
                    /* ignore */
                }
            };
        }

        connect();

        return () => {
            activeRef.current = false;
            if (timerRef.current) clearTimeout(timerRef.current);
            wsRef.current?.close();
            setStatus('disconnected');
        };
    }, []);

    return { status, connected: status === 'connected' };
}

// ── useOrderStream (Questrade Plus) ──

interface OrderEvent {
    type: 'order' | 'execution' | 'order_snapshot' | 'info' | 'error' | 'heartbeat';
    data: Record<string, unknown>;
}

export function useOrderStream(onOrder: (event: OrderEvent) => void) {
    const [status, setStatus] = useState<ConnectionState>('disconnected');
    const wsRef = useRef<WebSocket | null>(null);
    const attemptRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const activeRef = useRef(true);
    const onOrderRef = useRef(onOrder);

    useEffect(() => {
        onOrderRef.current = onOrder;
    }, [onOrder]);

    useEffect(() => {
        activeRef.current = true;
        attemptRef.current = 0;

        function connect() {
            if (!activeRef.current) return;

            const auth = getAuthParam();
            const url = `${WS_BASE}/ws/orders${auth ? `?${auth}` : ''}`;
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setStatus('connected');
                attemptRef.current = 0;
            };

            ws.onclose = () => {
                if (!activeRef.current) {
                    setStatus('disconnected');
                    return;
                }
                if (attemptRef.current < RETRY_MAX_ATTEMPTS) {
                    setStatus('reconnecting');
                    const delay = retryDelay(attemptRef.current);
                    attemptRef.current++;
                    timerRef.current = setTimeout(connect, delay);
                } else {
                    setStatus('disconnected');
                }
            };

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data) as OrderEvent;
                    if (msg.type !== 'heartbeat') {
                        onOrderRef.current(msg);
                    }
                } catch {
                    /* ignore */
                }
            };
        }

        connect();

        return () => {
            activeRef.current = false;
            if (timerRef.current) clearTimeout(timerRef.current);
            wsRef.current?.close();
            setStatus('disconnected');
        };
    }, []);

    return { status, connected: status === 'connected' };
}
