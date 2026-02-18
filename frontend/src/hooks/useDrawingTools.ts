/**
 * useDrawingTools — State management for chart drawing tools.
 *
 * Manages drawing tool state: active tool, drawings array, undo/redo stack,
 * and localStorage persistence per ticker.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/* ─── Drawing types ─── */
export type DrawingToolType =
    | 'cursor'
    | 'trendline'
    | 'horizontalLine'
    | 'verticalLine'
    | 'rectangle'
    | 'fibRetracement'
    | 'text'
    | 'ray'
    | 'arrow'
    | 'measure';

export interface DrawingPoint {
    time: number; // unix timestamp
    price: number;
}

export interface Drawing {
    id: string;
    type: DrawingToolType;
    points: DrawingPoint[];
    color: string;
    lineWidth: number;
    text?: string;
    /** For horizontal line — just a price */
    price?: number;
    /** For measure tool — computed values */
    measure?: { priceDelta: number; pctDelta: number; barCount: number };
    /** Creation timestamp */
    createdAt: number;
}

interface DrawingToolsState {
    activeTool: DrawingToolType;
    drawings: Drawing[];
    selectedDrawingId: string | null;
    drawingColor: string;
    drawingLineWidth: number;
    /** Points collected so far for the current in-progress drawing */
    pendingPoints: DrawingPoint[];
}

const DEFAULT_STATE: DrawingToolsState = {
    activeTool: 'cursor',
    drawings: [],
    selectedDrawingId: null,
    drawingColor: '#42a5f5',
    drawingLineWidth: 2,
    pendingPoints: [],
};

const STORAGE_KEY = (ticker: string) => `mp_chart_drawings_${ticker}`;
const OLD_STORAGE_KEY = (ticker: string) => `bubby-chart-drawings-${ticker}`;
const MAX_DRAWINGS = 100;

function generateId(): string {
    return `d-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/** How many points each tool needs before a drawing is complete */
const TOOL_POINT_COUNT: Partial<Record<DrawingToolType, number>> = {
    trendline: 2,
    horizontalLine: 1,
    verticalLine: 1,
    rectangle: 2,
    fibRetracement: 2,
    text: 1,
    ray: 2,
    arrow: 2,
    measure: 2,
};

export function useDrawingTools(ticker: string) {
    const [state, setState] = useState<DrawingToolsState>(() => {
        // Migrate old storage key if present
        try {
            const oldKey = OLD_STORAGE_KEY(ticker);
            const oldData = localStorage.getItem(oldKey);
            if (oldData && !localStorage.getItem(STORAGE_KEY(ticker))) {
                localStorage.setItem(STORAGE_KEY(ticker), oldData);
                localStorage.removeItem(oldKey);
            }
        } catch {
            /* ignore */
        }
        // Load persisted drawings
        try {
            const saved = localStorage.getItem(STORAGE_KEY(ticker));
            if (saved) {
                const drawings = (JSON.parse(saved) as Drawing[]).slice(-MAX_DRAWINGS);
                return { ...DEFAULT_STATE, drawings };
            }
        } catch {
            /* ignore */
        }
        return DEFAULT_STATE;
    });

    const undoStackRef = useRef<Drawing[][]>([]);
    const redoStackRef = useRef<Drawing[][]>([]);
    const [undoCount, setUndoCount] = useState(0);
    const [redoCount, setRedoCount] = useState(0);

    // Persist drawings when they change (capped)
    useEffect(() => {
        try {
            const capped = state.drawings.slice(-MAX_DRAWINGS);
            localStorage.setItem(STORAGE_KEY(ticker), JSON.stringify(capped));
        } catch {
            /* ignore */
        }
    }, [state.drawings, ticker]);

    // Reload drawings when ticker changes
    useEffect(() => {
        try {
            // Migrate old key if present
            const oldKey = OLD_STORAGE_KEY(ticker);
            const oldData = localStorage.getItem(oldKey);
            if (oldData && !localStorage.getItem(STORAGE_KEY(ticker))) {
                localStorage.setItem(STORAGE_KEY(ticker), oldData);
                localStorage.removeItem(oldKey);
            }
            const saved = localStorage.getItem(STORAGE_KEY(ticker));
            const drawings = saved ? (JSON.parse(saved) as Drawing[]).slice(-MAX_DRAWINGS) : [];
            setState((prev) => ({ ...prev, drawings, pendingPoints: [], selectedDrawingId: null }));
        } catch {
            setState((prev) => ({ ...prev, drawings: [], pendingPoints: [], selectedDrawingId: null }));
        }
        undoStackRef.current = [];
        redoStackRef.current = [];
        setUndoCount(0);
        setRedoCount(0);
    }, [ticker]);

    /* ── Tool selection ── */
    const setActiveTool = useCallback((tool: DrawingToolType) => {
        setState((prev) => ({ ...prev, activeTool: tool, pendingPoints: [], selectedDrawingId: null }));
    }, []);

    const setDrawingColor = useCallback((color: string) => {
        setState((prev) => ({ ...prev, drawingColor: color }));
    }, []);

    const setDrawingLineWidth = useCallback((width: number) => {
        setState((prev) => ({ ...prev, drawingLineWidth: width }));
    }, []);

    /* ── Chart click handler — collects points and creates drawings ── */
    const addPoint = useCallback((point: DrawingPoint) => {
        setState((prev) => {
            if (prev.activeTool === 'cursor') return prev;

            const needed = TOOL_POINT_COUNT[prev.activeTool] ?? 1;
            const nextPending = [...prev.pendingPoints, point];

            if (nextPending.length >= needed) {
                // Drawing is complete — create it
                const newDrawing: Drawing = {
                    id: generateId(),
                    type: prev.activeTool,
                    points: nextPending,
                    color: prev.drawingColor,
                    lineWidth: prev.drawingLineWidth,
                    createdAt: Date.now(),
                };

                // Special cases
                if (prev.activeTool === 'horizontalLine') {
                    newDrawing.price = point.price;
                }
                if (prev.activeTool === 'measure' && nextPending.length === 2) {
                    const [p1, p2] = nextPending;
                    newDrawing.measure = {
                        priceDelta: p2.price - p1.price,
                        pctDelta: ((p2.price - p1.price) / p1.price) * 100,
                        barCount: Math.abs(p2.time - p1.time) / 86400, // approximate days
                    };
                }

                // Save undo state
                undoStackRef.current.push([...prev.drawings]);
                redoStackRef.current = [];
                setUndoCount(undoStackRef.current.length);
                setRedoCount(0);

                return {
                    ...prev,
                    drawings: [...prev.drawings, newDrawing],
                    pendingPoints: [],
                    // Reset to cursor after single-point tools
                    activeTool: needed === 1 ? 'cursor' : prev.activeTool,
                };
            }

            return { ...prev, pendingPoints: nextPending };
        });
    }, []);

    /* ── Selection ── */
    const selectDrawing = useCallback((id: string | null) => {
        setState((prev) => ({ ...prev, selectedDrawingId: id }));
    }, []);

    /* ── Delete selected ── */
    const deleteSelected = useCallback(() => {
        setState((prev) => {
            if (!prev.selectedDrawingId) return prev;
            undoStackRef.current.push([...prev.drawings]);
            redoStackRef.current = [];
            setUndoCount(undoStackRef.current.length);
            setRedoCount(0);
            return {
                ...prev,
                drawings: prev.drawings.filter((d) => d.id !== prev.selectedDrawingId),
                selectedDrawingId: null,
            };
        });
    }, []);

    /* ── Clear all ── */
    const clearAll = useCallback(() => {
        setState((prev) => {
            if (prev.drawings.length === 0) return prev;
            undoStackRef.current.push([...prev.drawings]);
            redoStackRef.current = [];
            setUndoCount(undoStackRef.current.length);
            setRedoCount(0);
            return { ...prev, drawings: [], selectedDrawingId: null };
        });
    }, []);

    /* ── Undo ── */
    const undo = useCallback(() => {
        setState((prev) => {
            if (undoStackRef.current.length === 0) return prev;
            redoStackRef.current.push([...prev.drawings]);
            const restored = undoStackRef.current.pop()!;
            setUndoCount(undoStackRef.current.length);
            setRedoCount(redoStackRef.current.length);
            return { ...prev, drawings: restored, selectedDrawingId: null };
        });
    }, []);

    /* ── Redo ── */
    const redo = useCallback(() => {
        setState((prev) => {
            if (redoStackRef.current.length === 0) return prev;
            undoStackRef.current.push([...prev.drawings]);
            const restored = redoStackRef.current.pop()!;
            setUndoCount(undoStackRef.current.length);
            setRedoCount(redoStackRef.current.length);
            return { ...prev, drawings: restored, selectedDrawingId: null };
        });
    }, []);

    /* ── Import drawing — accept a pre-built Drawing (e.g. from AI) ── */
    const importDrawing = useCallback((drawing: Drawing) => {
        setState((prev) => {
            undoStackRef.current.push([...prev.drawings]);
            redoStackRef.current = [];
            setUndoCount(undoStackRef.current.length);
            setRedoCount(0);
            return { ...prev, drawings: [...prev.drawings, drawing] };
        });
    }, []);

    /* ── Import multiple drawings at once ── */
    const importDrawings = useCallback((drawings: Drawing[]) => {
        if (drawings.length === 0) return;
        setState((prev) => {
            undoStackRef.current.push([...prev.drawings]);
            redoStackRef.current = [];
            setUndoCount(undoStackRef.current.length);
            setRedoCount(0);
            return { ...prev, drawings: [...prev.drawings, ...drawings] };
        });
    }, []);

    return {
        activeTool: state.activeTool,
        drawings: state.drawings,
        selectedDrawingId: state.selectedDrawingId,
        drawingColor: state.drawingColor,
        drawingLineWidth: state.drawingLineWidth,
        pendingPoints: state.pendingPoints,
        canUndo: undoCount > 0,
        canRedo: redoCount > 0,
        setActiveTool,
        setDrawingColor,
        setDrawingLineWidth,
        addPoint,
        selectDrawing,
        deleteSelected,
        clearAll,
        undo,
        redo,
        importDrawing,
        importDrawings,
    };
}
