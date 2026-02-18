import {
    Activity,
    Crosshair,
    LayoutDashboard,
    ListChecks,
    LogOut,
    MessageSquare,
    Search,
    Settings,
    User,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import './Sidebar.css';

const NAV_ITEMS = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/screener', icon: Search, label: 'Screener' },
    { to: '/watchlist', icon: ListChecks, label: 'Watchlist' },
    { to: '/scanner', icon: Crosshair, label: 'Pattern Scanner' },
    { to: '/flow', icon: Activity, label: 'Options Flow' },
    { to: '/chat', icon: MessageSquare, label: 'AI Chat' },
    { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
    const { user, logout } = useAuth();
    useKeyboardShortcuts();

    return (
        <aside className="sidebar">
            <div className="sidebar-brand">
                <img
                    src="/splash.png"
                    alt="Bubby Vision"
                    className="brand-icon"
                    style={{ width: 28, height: 28, borderRadius: '50%' }}
                />
                <span className="brand-text">Bubby Vision</span>
            </div>

            <nav className="sidebar-nav">
                {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
                    <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}
                    >
                        <Icon size={18} />
                        <span>{label}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="sidebar-footer">
                {user && (
                    <div className="sidebar-user">
                        <div className="sidebar-user-avatar">
                            <User size={14} />
                        </div>
                        <span className="sidebar-user-name">{user.display_name}</span>
                        <button
                            type="button"
                            className="sidebar-logout"
                            onClick={logout}
                            title="Sign out"
                            aria-label="Sign out"
                        >
                            <LogOut size={14} />
                        </button>
                    </div>
                )}
                <div className="sidebar-version">v1.0.0</div>
            </div>
        </aside>
    );
}
