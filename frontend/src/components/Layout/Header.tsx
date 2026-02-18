import { Bell, Menu, Search } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAlertStream } from '../../hooks/useWebSocket';
import { timeAgo } from '../../utils/format';
import ConnectionStatus from './ConnectionStatus';
import './Header.css';
import './NotificationPanel.css';

/* ─── Types ─── */

interface Notification {
    id: number;
    ticker?: string;
    message: string;
    type: 'alert' | 'info';
    timestamp: Date;
    read: boolean;
}

let notifCounter = 0;

/* ─── Component ─── */

export default function Header() {
    const [query, setQuery] = useState('');
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [panelOpen, setPanelOpen] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    // ── WebSocket alert stream → notifications ──
    useAlertStream(
        useCallback(
            (alert: {
                ticker?: string;
                message?: string;
                alert_type?: string;
                pattern?: string;
                direction?: string;
                confidence?: number;
            }) => {
                let message = alert.message || `Alert for ${alert.ticker || 'unknown'}`;
                if (alert.alert_type === 'pattern_detected' && alert.pattern) {
                    const dir = alert.direction === 'bullish' ? '🟢' : alert.direction === 'bearish' ? '🔴' : '⚪';
                    const conf = alert.confidence ? ` (${Math.round(alert.confidence * 100)}%)` : '';
                    message = `${dir} ${alert.pattern}${conf}`;
                }
                const notif: Notification = {
                    id: ++notifCounter,
                    ticker: alert.ticker,
                    message,
                    type: 'alert',
                    timestamp: new Date(),
                    read: false,
                };
                setNotifications((prev) => [notif, ...prev].slice(0, 50));
            },
            [],
        ),
    );

    // ── Click outside → close panel ──
    useEffect(() => {
        if (!panelOpen) return;
        const handler = (e: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
                setPanelOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [panelOpen]);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        const ticker = query.trim().toUpperCase();
        if (ticker) {
            navigate(`/stock/${ticker}`);
            setQuery('');
        }
    };

    const unreadCount = notifications.filter((n) => !n.read).length;

    const togglePanel = () => {
        setPanelOpen((prev) => !prev);
        // Mark all as read when opening
        if (!panelOpen) {
            setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        }
    };

    const clearAll = () => {
        setNotifications([]);
        setPanelOpen(false);
    };

    const handleNotifClick = (notif: Notification) => {
        if (notif.ticker) {
            navigate(`/stock/${notif.ticker}`);
            setPanelOpen(false);
        }
    };

    const toggleSidebar = () => {
        const open = document.body.getAttribute('data-sidebar-open') === 'true';
        document.body.setAttribute('data-sidebar-open', String(!open));
    };

    return (
        <header className="app-header">
            <button
                type="button"
                className="header-icon-btn header-hamburger"
                title="Toggle menu"
                onClick={toggleSidebar}
            >
                <Menu size={20} />
            </button>
            <form className="header-search" onSubmit={handleSearch}>
                <Search size={16} className="search-icon" />
                <input
                    className="search-input"
                    type="text"
                    placeholder="Search ticker (e.g. AAPL)..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    maxLength={10}
                />
            </form>

            <div className="header-actions">
                <ConnectionStatus />
                <div className="notification-wrapper" ref={panelRef}>
                    <button type="button" className="header-icon-btn" title="Notifications" onClick={togglePanel}>
                        <Bell size={18} />
                        {unreadCount > 0 && (
                            <span className="notification-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
                        )}
                    </button>

                    {panelOpen && (
                        <div className="notification-panel">
                            <div className="notif-header">
                                <h4>Notifications</h4>
                                {notifications.length > 0 && (
                                    <button type="button" className="notif-clear-btn" onClick={clearAll}>
                                        Clear all
                                    </button>
                                )}
                            </div>
                            <div className="notif-list">
                                {notifications.length === 0 ? (
                                    <div className="notif-empty">No notifications yet</div>
                                ) : (
                                    notifications.map((notif) => (
                                        <button
                                            type="button"
                                            key={notif.id}
                                            className="notif-item"
                                            onClick={() => handleNotifClick(notif)}
                                        >
                                            <span className={`notif-dot notif-dot--${notif.type}`} />
                                            <div className="notif-content">
                                                <p className="notif-message">
                                                    {notif.ticker && (
                                                        <span className="notif-ticker">{notif.ticker} </span>
                                                    )}
                                                    {notif.message}
                                                </p>
                                                <span className="notif-time">
                                                    {timeAgo(notif.timestamp.toISOString())}
                                                </span>
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
}
