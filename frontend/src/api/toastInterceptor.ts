/**
 * Toast Interceptor — fires toast notifications on API errors
 *
 * Attaches a response error interceptor that shows user-friendly
 * toast messages for common HTTP error codes.
 * Skips 401 (handled by silent refresh in client.ts).
 */

import type { AxiosError, AxiosInstance } from 'axios';

interface ToastActions {
    error: (message: string) => void;
}

const STATUS_MESSAGES: Record<number, string> = {
    400: 'Bad request — please check your input',
    403: "You don't have permission to do that",
    404: 'Resource not found',
    409: 'Conflict — this resource already exists',
    422: 'Validation error — please check your input',
    429: 'Too many requests — please slow down',
    500: 'Server error — please try again later',
    502: 'Service temporarily unavailable',
    503: 'Service is under maintenance',
};

let interceptorId: number | null = null;

export function installToastInterceptor(client: AxiosInstance, toast: ToastActions) {
    // Remove previous interceptor if re-installing
    if (interceptorId !== null) {
        client.interceptors.response.eject(interceptorId);
    }

    interceptorId = client.interceptors.response.use(
        (res) => res,
        (err: AxiosError) => {
            const status = err.response?.status;

            // Skip 401 — handled by silent refresh in client.ts
            if (status === 401) {
                return Promise.reject(err);
            }

            if (status) {
                // Try to extract detail message from response
                const detail = (err.response?.data as { detail?: string })?.detail;
                const fallback = STATUS_MESSAGES[status] || `Request failed (${status})`;
                toast.error(detail || fallback);
            } else if (err.code === 'ERR_NETWORK') {
                toast.error('Network error — check your connection');
            } else if (err.code === 'ECONNABORTED') {
                toast.error('Request timed out — please try again');
            }

            return Promise.reject(err);
        },
    );
}
