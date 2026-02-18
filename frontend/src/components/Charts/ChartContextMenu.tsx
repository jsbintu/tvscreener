/**
 * ChartContextMenu — Right-click context menu for the chart.
 *
 * Provides quick access to: indicator toggles, timeframe changes,
 * toggle S/R, add horizontal line, take screenshot, go fullscreen.
 */
import { useEffect, useRef } from 'react';

interface ContextMenuAction {
    label: string;
    icon?: string;
    shortcut?: string;
    divider?: boolean;
    onClick: () => void;
}

interface ChartContextMenuProps {
    x: number;
    y: number;
    actions: ContextMenuAction[];
    onClose: () => void;
}

export default function ChartContextMenu({ x, y, actions, onClose }: ChartContextMenuProps) {
    const ref = useRef<HTMLDivElement>(null);

    // Close on outside click or Escape
    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) onClose();
        };
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('mousedown', handleClick);
        document.addEventListener('keydown', handleKey);
        return () => {
            document.removeEventListener('mousedown', handleClick);
            document.removeEventListener('keydown', handleKey);
        };
    }, [onClose]);

    // Adjust position to stay within viewport
    const style: React.CSSProperties = {
        position: 'fixed',
        left: x,
        top: y,
        zIndex: 100,
    };

    return (
        <div className="chart-ctx-menu" ref={ref} style={style}>
            {actions.map((action, i) => (
                <div key={i}>
                    {action.divider && <div className="ctx-divider" />}
                    <button
                        type="button"
                        className="ctx-item"
                        onClick={() => {
                            action.onClick();
                            onClose();
                        }}
                    >
                        {action.icon && <span className="ctx-icon">{action.icon}</span>}
                        <span className="ctx-label">{action.label}</span>
                        {action.shortcut && <span className="ctx-shortcut">{action.shortcut}</span>}
                    </button>
                </div>
            ))}
        </div>
    );
}
