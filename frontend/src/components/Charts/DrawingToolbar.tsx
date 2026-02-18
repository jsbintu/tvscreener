/**
 * DrawingToolbar — Floating sidebar with drawing tool icons, color picker, and controls.
 */

import {
    ArrowDownUp,
    ArrowUpRight,
    BarChart2,
    Minus,
    MousePointer2,
    MoveUpRight,
    Palette,
    Redo2,
    Ruler,
    Square,
    Trash2,
    TrendingUp,
    Type,
    Undo2,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import type { DrawingToolType } from '../../hooks/useDrawingTools';
import './DrawingToolbar.css';

interface DrawingToolbarProps {
    activeTool: DrawingToolType;
    drawingColor: string;
    drawingLineWidth: number;
    canUndo: boolean;
    canRedo: boolean;
    drawingCount: number;
    onSelectTool: (tool: DrawingToolType) => void;
    onColorChange: (color: string) => void;
    onLineWidthChange: (w: number) => void;
    onUndo: () => void;
    onRedo: () => void;
    onClearAll: () => void;
    onDeleteSelected: () => void;
}

const TOOLS: { type: DrawingToolType; icon: React.ReactNode; label: string }[] = [
    { type: 'cursor', icon: <MousePointer2 size={16} />, label: 'Select' },
    { type: 'trendline', icon: <TrendingUp size={16} />, label: 'Trend Line' },
    { type: 'horizontalLine', icon: <Minus size={16} />, label: 'Horizontal Line' },
    { type: 'verticalLine', icon: <ArrowDownUp size={16} />, label: 'Vertical Line' },
    { type: 'ray', icon: <MoveUpRight size={16} />, label: 'Ray' },
    { type: 'rectangle', icon: <Square size={16} />, label: 'Rectangle' },
    { type: 'fibRetracement', icon: <BarChart2 size={16} />, label: 'Fibonacci' },
    { type: 'arrow', icon: <ArrowUpRight size={16} />, label: 'Arrow' },
    { type: 'text', icon: <Type size={16} />, label: 'Text' },
    { type: 'measure', icon: <Ruler size={16} />, label: 'Measure' },
];

const COLOR_PALETTE = [
    '#42a5f5',
    '#ef5350',
    '#00c853',
    '#ffd54f',
    '#ab47bc',
    '#ff7043',
    '#26c6da',
    '#ec407a',
    '#9ccc65',
    '#ffffff',
];

const LINE_WIDTHS = [1, 2, 3, 4];

export default function DrawingToolbar({
    activeTool,
    drawingColor,
    drawingLineWidth,
    canUndo,
    canRedo,
    drawingCount,
    onSelectTool,
    onColorChange,
    onLineWidthChange,
    onUndo,
    onRedo,
    onClearAll,
    onDeleteSelected,
}: DrawingToolbarProps) {
    const [showColorPicker, setShowColorPicker] = useState(false);
    const [showWidthPicker, setShowWidthPicker] = useState(false);

    const handleToolClick = useCallback(
        (tool: DrawingToolType) => {
            onSelectTool(tool);
            setShowColorPicker(false);
            setShowWidthPicker(false);
        },
        [onSelectTool],
    );

    return (
        <div className="drawing-toolbar">
            {/* Drawing tools */}
            <div className="dt-tools">
                {TOOLS.map((t) => (
                    <button
                        type="button"
                        key={t.type}
                        className={`dt-tool-btn ${activeTool === t.type ? 'active' : ''}`}
                        onClick={() => handleToolClick(t.type)}
                        title={t.label}
                    >
                        {t.icon}
                    </button>
                ))}
            </div>

            <div className="dt-divider" />

            {/* Color picker */}
            <div className="dt-color-section">
                <button
                    type="button"
                    className="dt-tool-btn dt-color-btn"
                    onClick={() => {
                        setShowColorPicker((p) => !p);
                        setShowWidthPicker(false);
                    }}
                    title="Drawing color"
                >
                    <Palette size={14} />
                    <span className="dt-color-swatch" style={{ background: drawingColor }} />
                </button>
                {showColorPicker && (
                    <div className="dt-color-popover">
                        {COLOR_PALETTE.map((c) => (
                            <button
                                type="button"
                                key={c}
                                className={`dt-color-opt ${drawingColor === c ? 'active' : ''}`}
                                style={{ background: c }}
                                onClick={() => {
                                    onColorChange(c);
                                    setShowColorPicker(false);
                                }}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Line width picker */}
            <div className="dt-width-section">
                <button
                    type="button"
                    className="dt-tool-btn"
                    onClick={() => {
                        setShowWidthPicker((p) => !p);
                        setShowColorPicker(false);
                    }}
                    title="Line width"
                >
                    <span
                        className="dt-width-preview"
                        style={{
                            height: drawingLineWidth,
                            background: drawingColor,
                        }}
                    />
                </button>
                {showWidthPicker && (
                    <div className="dt-width-popover">
                        {LINE_WIDTHS.map((w) => (
                            <button
                                type="button"
                                key={w}
                                className={`dt-width-opt ${drawingLineWidth === w ? 'active' : ''}`}
                                onClick={() => {
                                    onLineWidthChange(w);
                                    setShowWidthPicker(false);
                                }}
                            >
                                <span className="dt-width-line" style={{ height: w, background: drawingColor }} />
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="dt-divider" />

            {/* Undo / Redo */}
            <button
                type="button"
                className={`dt-tool-btn ${!canUndo ? 'disabled' : ''}`}
                onClick={onUndo}
                disabled={!canUndo}
                title="Undo (Ctrl+Z)"
            >
                <Undo2 size={14} />
            </button>
            <button
                type="button"
                className={`dt-tool-btn ${!canRedo ? 'disabled' : ''}`}
                onClick={onRedo}
                disabled={!canRedo}
                title="Redo (Ctrl+Y)"
            >
                <Redo2 size={14} />
            </button>

            <div className="dt-divider" />

            {/* Delete / Clear */}
            <button
                type="button"
                className="dt-tool-btn dt-delete-btn"
                onClick={onDeleteSelected}
                title="Delete selected"
            >
                <Trash2 size={14} />
            </button>
            {drawingCount > 0 && (
                <button
                    type="button"
                    className="dt-tool-btn dt-clear-btn"
                    onClick={onClearAll}
                    title="Clear all drawings"
                >
                    Clear
                </button>
            )}
        </div>
    );
}
