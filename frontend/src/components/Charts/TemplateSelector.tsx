/**
 * TemplateSelector — Dropdown for selecting chart configuration templates.
 *
 * Shows preset templates (Scalper, Swing, etc.) and user-saved templates.
 * Click to apply. Options to save current config and delete custom templates.
 */

import { BookmarkPlus, ChevronDown, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ChartTemplate } from '../../hooks/useChartTemplates';

interface TemplateSelectorProps {
    templates: ChartTemplate[];
    onApply: (config: ChartTemplate['config']) => void;
    onSave: (name: string, config: ChartTemplate['config']) => void;
    onDelete: (id: string) => void;
    currentConfig: ChartTemplate['config'];
}

export default function TemplateSelector({
    templates,
    onApply,
    onSave,
    onDelete,
    currentConfig,
}: TemplateSelectorProps) {
    const [open, setOpen] = useState(false);
    const [showSave, setShowSave] = useState(false);
    const [saveName, setSaveName] = useState('');
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handle = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
                setShowSave(false);
            }
        };
        document.addEventListener('mousedown', handle);
        return () => document.removeEventListener('mousedown', handle);
    }, []);

    const handleSave = () => {
        if (saveName.trim()) {
            onSave(saveName.trim(), currentConfig);
            setSaveName('');
            setShowSave(false);
        }
    };

    return (
        <div className="template-selector" ref={ref}>
            <button
                type="button"
                className="chart-ctrl-btn template-trigger"
                onClick={() => setOpen((o) => !o)}
                title="Chart Templates"
            >
                🎛️ <ChevronDown size={10} />
            </button>

            {open && (
                <div className="template-dropdown">
                    <div className="template-header">Templates</div>

                    {templates.map((t) => (
                        <div key={t.id} className="template-item">
                            <button
                                type="button"
                                className="template-item-btn"
                                onClick={() => {
                                    onApply(t.config);
                                    setOpen(false);
                                }}
                            >
                                <span className="template-icon">{t.icon}</span>
                                <span className="template-name">{t.name}</span>
                            </button>
                            {!t.isPreset && (
                                <button
                                    type="button"
                                    className="template-delete"
                                    onClick={() => onDelete(t.id)}
                                    title="Delete template"
                                >
                                    <Trash2 size={12} />
                                </button>
                            )}
                        </div>
                    ))}

                    <div className="template-divider" />

                    {showSave ? (
                        <div className="template-save-row">
                            <input
                                className="template-save-input"
                                placeholder="Template name…"
                                value={saveName}
                                onChange={(e) => setSaveName(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                            />
                            <button type="button" className="template-save-btn" onClick={handleSave}>
                                Save
                            </button>
                        </div>
                    ) : (
                        <button
                            type="button"
                            className="template-item-btn template-add"
                            onClick={() => setShowSave(true)}
                        >
                            <BookmarkPlus size={14} />
                            <span>Save Current</span>
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}
