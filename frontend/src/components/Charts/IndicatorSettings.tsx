/**
 * IndicatorSettings — Popover dialog for customizing indicator parameters.
 *
 * Click an indicator label in the legend to open this dialog.
 * Allows adjusting period, color, line width, and opacity.
 */

import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export interface IndicatorConfig {
    key: string;
    label: string;
    color: string;
    lineWidth: number;
    period?: number;
    /** Min/max for period slider */
    periodRange?: [number, number];
    opacity?: number;
}

interface IndicatorSettingsProps {
    indicator: IndicatorConfig;
    position: { x: number; y: number };
    onApply: (config: IndicatorConfig) => void;
    onClose: () => void;
    onRemove: (key: string) => void;
}

const COLOR_PRESET = [
    '#42a5f5',
    '#ef5350',
    '#00c853',
    '#ffb74d',
    '#ab47bc',
    '#ff7043',
    '#26c6da',
    '#ffd54f',
    '#ce93d8',
    '#81c784',
    '#ec407a',
    '#ffffff',
];

export default function IndicatorSettings({ indicator, position, onApply, onClose, onRemove }: IndicatorSettingsProps) {
    const [config, setConfig] = useState<IndicatorConfig>({ ...indicator });
    const ref = useRef<HTMLDivElement>(null);

    // Close on outside click
    useEffect(() => {
        const handle = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) onClose();
        };
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('mousedown', handle);
        document.addEventListener('keydown', handleKey);
        return () => {
            document.removeEventListener('mousedown', handle);
            document.removeEventListener('keydown', handleKey);
        };
    }, [onClose]);

    return (
        <div className="ind-settings" ref={ref} style={{ left: position.x, top: position.y }}>
            {/* Header */}
            <div className="ind-settings-header">
                <span className="ind-settings-title">{config.label}</span>
                <button type="button" className="ind-settings-close" onClick={onClose}>
                    <X size={14} />
                </button>
            </div>

            {/* Period slider */}
            {config.period != null && config.periodRange && (
                <div className="ind-settings-row">
                    <label className="ind-settings-label">
                        Period
                        <div className="ind-settings-range-wrapper">
                            <input
                                type="range"
                                min={config.periodRange[0]}
                                max={config.periodRange[1]}
                                value={config.period}
                                onChange={(e) => setConfig((p) => ({ ...p, period: Number(e.target.value) }))}
                                className="ind-settings-range"
                            />
                            <span className="ind-settings-range-value">{config.period}</span>
                        </div>
                    </label>
                </div>
            )}

            {/* Color picker */}
            <div className="ind-settings-row">
                <span className="ind-settings-label">Color</span>
                <div className="ind-settings-colors">
                    {COLOR_PRESET.map((c) => (
                        <button
                            type="button"
                            key={c}
                            className={`ind-color-swatch ${config.color === c ? 'active' : ''}`}
                            style={{ background: c }}
                            onClick={() => setConfig((p) => ({ ...p, color: c }))}
                        />
                    ))}
                </div>
            </div>

            {/* Line width */}
            <div className="ind-settings-row">
                <span className="ind-settings-label">Width</span>
                <div className="ind-settings-widths">
                    {[1, 2, 3, 4].map((w) => (
                        <button
                            type="button"
                            key={w}
                            className={`ind-width-btn ${config.lineWidth === w ? 'active' : ''}`}
                            onClick={() => setConfig((p) => ({ ...p, lineWidth: w }))}
                        >
                            <span className="ind-width-line" style={{ height: w, background: config.color }} />
                        </button>
                    ))}
                </div>
            </div>

            {/* Actions */}
            <div className="ind-settings-actions">
                <button
                    type="button"
                    className="ind-settings-btn ind-settings-remove"
                    onClick={() => {
                        onRemove(config.key);
                        onClose();
                    }}
                >
                    Remove
                </button>
                <button
                    type="button"
                    className="ind-settings-btn ind-settings-reset"
                    onClick={() => setConfig({ ...indicator })}
                >
                    Reset
                </button>
                <button
                    type="button"
                    className="ind-settings-btn ind-settings-apply"
                    onClick={() => {
                        onApply(config);
                        onClose();
                    }}
                >
                    Apply
                </button>
            </div>
        </div>
    );
}
