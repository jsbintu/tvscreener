/**
 * usePanelState — Persist panel open/closed states to localStorage.
 *
 * All panel states are stored in a single JSON object under `mp_panel_states`.
 * Provides a drop-in replacement for `useState<boolean>(defaultOpen)`.
 */
import { useCallback, useState } from 'react';

const STORAGE_KEY = 'mp_panel_states';

/** Read the full panel-state map from localStorage */
function readMap(): Record<string, boolean> {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch {
        return {};
    }
}

/** Write the full panel-state map to localStorage */
function writeMap(map: Record<string, boolean>) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
    } catch {
        /* quota exceeded — ignore */
    }
}

/**
 * Hook that persists a panel's open/closed state to localStorage.
 *
 * @param panelId  Unique string identifier for this panel (e.g. "sd-technicals")
 * @param defaultOpen  Initial state if no persisted value exists
 * @returns  [isOpen, toggle] — current state and a toggle function
 */
export function usePanelState(panelId: string, defaultOpen = true): [boolean, () => void] {
    const [open, setOpen] = useState<boolean>(() => {
        const map = readMap();
        return panelId in map ? map[panelId] : defaultOpen;
    });

    const toggle = useCallback(() => {
        setOpen((prev) => {
            const next = !prev;
            const map = readMap();
            map[panelId] = next;
            writeMap(map);
            return next;
        });
    }, [panelId]);

    return [open, toggle];
}
