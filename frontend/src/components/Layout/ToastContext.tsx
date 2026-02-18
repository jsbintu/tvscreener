/**
 * ToastContext — notification system
 *
 * Provides useToast() hook with toast.success(), toast.error(), toast.info().
 * Auto-dismisses after 5s, glassmorphic styling, slide-in animation.
 */

import { AlertCircle, CheckCircle, Info, X } from 'lucide-react';
import { createContext, type ReactNode, useCallback, useContext, useRef, useState } from 'react';

type ToastType = 'success' | 'error' | 'info';

interface Toast {
    id: string;
    type: ToastType;
    message: string;
}

interface ToastActions {
    success: (message: string) => void;
    error: (message: string) => void;
    info: (message: string) => void;
    dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastActions | null>(null);

const TOAST_DURATION = 5000;
const TOAST_ICONS = {
    success: CheckCircle,
    error: AlertCircle,
    info: Info,
};

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

    const dismiss = useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        const timer = timers.current.get(id);
        if (timer) {
            clearTimeout(timer);
            timers.current.delete(id);
        }
    }, []);

    const addToast = useCallback(
        (type: ToastType, message: string) => {
            const id = `toast-${++toastCounter}`;
            setToasts((prev) => [...prev, { id, type, message }]);

            const timer = setTimeout(() => dismiss(id), TOAST_DURATION);
            timers.current.set(id, timer);
        },
        [dismiss],
    );

    const actions: ToastActions = {
        success: (msg) => addToast('success', msg),
        error: (msg) => addToast('error', msg),
        info: (msg) => addToast('info', msg),
        dismiss,
    };

    return (
        <ToastContext.Provider value={actions}>
            {children}
            <output className="toast-container" aria-live="polite">
                {toasts.map((t) => {
                    const Icon = TOAST_ICONS[t.type];
                    return (
                        <div key={t.id} className={`toast toast--${t.type}`}>
                            <Icon size={16} className="toast-icon" />
                            <span className="toast-message">{t.message}</span>
                            <button
                                type="button"
                                className="toast-close"
                                onClick={() => dismiss(t.id)}
                                aria-label="Dismiss"
                            >
                                <X size={14} />
                            </button>
                        </div>
                    );
                })}
            </output>
        </ToastContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastActions {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
    return ctx;
}
