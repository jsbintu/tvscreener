/**
 * Settings Page — user profile and preferences
 */

import { AlertCircle, Bell, CheckCircle, Lock, LogOut, Moon, Sun, Table, Trash2, User } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { authApi, preferencesApi } from '../../api/client';
import { useToast } from '../../components/Layout/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../hooks/useTheme';
import './Settings.css';

export default function Settings() {
    const { user, logout } = useAuth();
    const toast = useToast();
    const { theme, toggleTheme } = useTheme();

    // Profile
    const [displayName, setDisplayName] = useState(user?.display_name || '');
    const [profileSaving, setProfileSaving] = useState(false);

    // Password
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [passwordSaving, setPasswordSaving] = useState(false);

    // Preferences
    const [notifySound, setNotifySound] = useState(() => {
        return localStorage.getItem('mp_notify_sound') !== 'false';
    });
    const [compactMode, setCompactMode] = useState(() => {
        return localStorage.getItem('mp_compact_mode') === 'true';
    });

    // Delete confirmation
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // Hydrate preferences from API on mount (overrides localStorage)
    useEffect(() => {
        preferencesApi
            .get()
            .then((res) => {
                const prefs = res.data?.preferences;
                if (prefs) {
                    if (typeof prefs.notify_sound === 'boolean') {
                        setNotifySound(prefs.notify_sound);
                        try {
                            localStorage.setItem('mp_notify_sound', String(prefs.notify_sound));
                        } catch {
                            /* ignore */
                        }
                    }
                    if (typeof prefs.compact_mode === 'boolean') {
                        setCompactMode(prefs.compact_mode);
                        try {
                            localStorage.setItem('mp_compact_mode', String(prefs.compact_mode));
                        } catch {
                            /* ignore */
                        }
                        document.documentElement.classList.toggle('compact-mode', prefs.compact_mode);
                    }
                }
            })
            .catch(() => {
                /* API unavailable — localStorage stands */
            });
    }, []);

    async function handleProfileSave(e: FormEvent) {
        e.preventDefault();
        setProfileSaving(true);
        try {
            await authApi.updateProfile(displayName);
            toast.success('Profile updated');
        } catch {
            toast.error('Failed to update profile');
        } finally {
            setProfileSaving(false);
        }
    }

    async function handlePasswordChange(e: FormEvent) {
        e.preventDefault();
        if (newPassword !== confirmPassword) {
            toast.error('Passwords do not match');
            return;
        }
        if (newPassword.length < 8) {
            toast.error('Password must be at least 8 characters');
            return;
        }
        setPasswordSaving(true);
        try {
            await authApi.changePassword(currentPassword, newPassword);
            toast.success('Password changed');
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch {
            toast.error('Failed to change password');
        } finally {
            setPasswordSaving(false);
        }
    }

    function handleNotifyToggle() {
        const next = !notifySound;
        setNotifySound(next);
        try {
            localStorage.setItem('mp_notify_sound', String(next));
        } catch {
            /* ignore */
        }
        // Persist to API (fire-and-forget)
        preferencesApi.set('notify_sound', next).catch(() => {
            /* API down */
        });
        toast.info(next ? 'Notification sounds enabled' : 'Notification sounds disabled');
    }

    function handleCompactToggle() {
        const next = !compactMode;
        setCompactMode(next);
        try {
            localStorage.setItem('mp_compact_mode', String(next));
        } catch {
            /* ignore */
        }
        // Persist to API (fire-and-forget)
        preferencesApi.set('compact_mode', next).catch(() => {
            /* API down */
        });
        document.documentElement.classList.toggle('compact-mode', next);
        toast.info(next ? 'Compact mode enabled' : 'Compact mode disabled');
    }

    function handleDeleteAccount() {
        // Reset server-side preferences
        preferencesApi.reset().catch(() => {
            /* ignore */
        });
        // Selectively clear only MarketPilot preference keys,
        // preserving auth tokens and third-party state
        const keysToRemove: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('mp_') || key.startsWith('marketpilot_') || key.startsWith('bubby-'))) {
                keysToRemove.push(key);
            }
        }
        keysToRemove.forEach((k) => {
            localStorage.removeItem(k);
        });
        logout();
        toast.info('Account deleted');
    }

    return (
        <div className="settings-page page-container">
            <h1 className="page-title">Settings</h1>

            {/* ── Profile ── */}
            <section className="settings-card">
                <div className="settings-card-header">
                    <User size={18} />
                    <h2>Profile</h2>
                </div>
                <form onSubmit={handleProfileSave} className="settings-form">
                    <div className="settings-field">
                        <label htmlFor="settings-email">Email</label>
                        <input id="settings-email" type="email" className="input" value={user?.email || ''} disabled />
                    </div>
                    <div className="settings-field">
                        <label htmlFor="settings-name">Display Name</label>
                        <input
                            id="settings-name"
                            type="text"
                            className="input"
                            value={displayName}
                            onChange={(e) => setDisplayName(e.target.value)}
                            required
                        />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={profileSaving}>
                        <CheckCircle size={14} />
                        {profileSaving ? 'Saving…' : 'Save Profile'}
                    </button>
                </form>
            </section>

            {/* ── Password ── */}
            <section className="settings-card">
                <div className="settings-card-header">
                    <Lock size={18} />
                    <h2>Change Password</h2>
                </div>
                <form onSubmit={handlePasswordChange} className="settings-form">
                    <div className="settings-field">
                        <label htmlFor="settings-current-pw">Current Password</label>
                        <input
                            id="settings-current-pw"
                            type="password"
                            className="input"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            required
                        />
                    </div>
                    <div className="settings-field">
                        <label htmlFor="settings-new-pw">New Password</label>
                        <input
                            id="settings-new-pw"
                            type="password"
                            className="input"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            required
                            minLength={8}
                        />
                    </div>
                    <div className="settings-field">
                        <label htmlFor="settings-confirm-pw">Confirm New Password</label>
                        <input
                            id="settings-confirm-pw"
                            type="password"
                            className="input"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                            minLength={8}
                        />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={passwordSaving}>
                        <Lock size={14} />
                        {passwordSaving ? 'Changing…' : 'Change Password'}
                    </button>
                </form>
            </section>

            {/* ── Preferences ── */}
            <section className="settings-card">
                <div className="settings-card-header">
                    <Bell size={18} />
                    <h2>Preferences</h2>
                </div>
                <div className="settings-toggles">
                    <div className="settings-toggle-row">
                        <div>
                            <span className="toggle-label">
                                {theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />} Appearance
                            </span>
                            <span className="toggle-desc">{theme === 'dark' ? 'Dark mode' : 'Light mode'}</span>
                        </div>
                        <button
                            type="button"
                            className={`toggle-switch ${theme === 'light' ? 'toggle-on' : ''}`}
                            onClick={toggleTheme}
                            role="switch"
                            aria-checked={theme === 'light'}
                        >
                            <span className="toggle-thumb" />
                        </button>
                    </div>
                    <div className="settings-toggle-row">
                        <div>
                            <span className="toggle-label">Notification Sounds</span>
                            <span className="toggle-desc">Play sounds for alerts and notifications</span>
                        </div>
                        <button
                            type="button"
                            className={`toggle-switch ${notifySound ? 'toggle-on' : ''}`}
                            onClick={handleNotifyToggle}
                            role="switch"
                            aria-checked={notifySound}
                        >
                            <span className="toggle-thumb" />
                        </button>
                    </div>
                    <div className="settings-toggle-row">
                        <div>
                            <span className="toggle-label">Compact Tables</span>
                            <span className="toggle-desc">Reduce row height in data tables</span>
                        </div>
                        <button
                            type="button"
                            className={`toggle-switch ${compactMode ? 'toggle-on' : ''}`}
                            onClick={handleCompactToggle}
                            role="switch"
                            aria-checked={compactMode}
                        >
                            <span className="toggle-thumb" />
                        </button>
                    </div>
                </div>
            </section>

            {/* ── Keyboard Shortcuts ── */}
            <section className="settings-card">
                <div className="settings-card-header">
                    <Table size={18} />
                    <h2>Keyboard Shortcuts</h2>
                </div>
                <div className="shortcuts-grid">
                    <div className="shortcut-row">
                        <kbd>/</kbd>
                        <span>Focus search</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>Esc</kbd>
                        <span>Blur / close</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>g</kbd> <kbd>d</kbd>
                        <span>Dashboard</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>g</kbd> <kbd>s</kbd>
                        <span>Screener</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>g</kbd> <kbd>w</kbd>
                        <span>Watchlist</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>g</kbd> <kbd>c</kbd>
                        <span>Chat</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>g</kbd> <kbd>f</kbd>
                        <span>Options Flow</span>
                    </div>
                    <div className="shortcut-row">
                        <kbd>g</kbd> <kbd>x</kbd>
                        <span>Settings</span>
                    </div>
                </div>
            </section>

            {/* ── Danger Zone ── */}
            <section className="settings-card settings-card--danger">
                <div className="settings-card-header">
                    <AlertCircle size={18} />
                    <h2>Danger Zone</h2>
                </div>
                <div className="settings-danger-actions">
                    <button type="button" className="btn btn-outline" onClick={logout}>
                        <LogOut size={14} />
                        Sign Out
                    </button>
                    {!showDeleteConfirm ? (
                        <button type="button" className="btn btn-danger" onClick={() => setShowDeleteConfirm(true)}>
                            <Trash2 size={14} />
                            Delete Account
                        </button>
                    ) : (
                        <div className="delete-confirm">
                            <p>Are you sure? This action cannot be undone.</p>
                            <div className="delete-confirm-actions">
                                <button type="button" className="btn btn-danger" onClick={handleDeleteAccount}>
                                    Yes, delete my account
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-outline"
                                    onClick={() => setShowDeleteConfirm(false)}
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
}
