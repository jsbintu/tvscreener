// ── MarketPilot Service Worker ──
// Caches static assets for offline access, uses network-first for API calls.

const CACHE_NAME = 'marketpilot-v1';
const STATIC_ASSETS = [
    '/',
    '/manifest.json',
];

// Install: pre-cache core shell
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// Fetch: network-first for API, cache-first for assets
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Network-first for API calls and WebSocket
    if (url.pathname.startsWith('/v1/api') || url.pathname.startsWith('/ws')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // Cache successful API responses for offline fallback
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
                    }
                    return response;
                })
                .catch(() => caches.match(request))
        );
        return;
    }

    // Cache-first for static assets (JS, CSS, images, fonts)
    event.respondWith(
        caches.match(request).then((cached) => {
            if (cached) return cached;

            return fetch(request).then((response) => {
                // Only cache same-origin successful responses
                if (response.ok && url.origin === self.location.origin) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
                }
                return response;
            });
        })
    );
});
