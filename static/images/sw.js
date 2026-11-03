
const CACHE_NAME = "phone-recovery-v1";

// Install service worker
self.addEventListener("install", (event) => {
    self.skipWaiting();
});

// Activate service worker
self.addEventListener("activate", (event) => {
    event.waitUntil(
        self.clients.claim()
    );
});

// Cache only static files, never private pages or case records
self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);

    if (
        request.method === "GET" &&
        url.origin === self.location.origin &&
        url.pathname.startsWith("/static/")
    ) {
        event.respondWith(
            caches.open(CACHE_NAME).then(async (cache) => {
                const cached = await cache.match(request);

                if (cached) {
                    return cached;
                }

                const response = await fetch(request);

                if (response.ok) {
                    cache.put(request, response.clone());
                }

                return response;
            })
        );
    }
});
