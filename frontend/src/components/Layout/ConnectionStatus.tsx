/**
 * ConnectionStatus — WebSocket connection indicator
 *
 * Displays a small dot showing real-time WebSocket health.
 * Green: connected | Yellow: reconnecting | Red: disconnected
 */

import { useAlertStream } from '../../hooks/useWebSocket';
import './ConnectionStatus.css';

const STATUS_CONFIG = {
    connected: { label: 'Connected', className: 'status--connected' },
    reconnecting: { label: 'Reconnecting…', className: 'status--reconnecting' },
    disconnected: { label: 'Disconnected', className: 'status--disconnected' },
} as const;

export default function ConnectionStatus() {
    // Use the alert stream as the heartbeat connection
    const { status } = useAlertStream(() => {});
    const config = STATUS_CONFIG[status];

    return (
        <div className={`connection-status ${config.className}`} title={config.label}>
            <span className="status-dot" />
            <span className="status-label">{config.label}</span>
        </div>
    );
}
