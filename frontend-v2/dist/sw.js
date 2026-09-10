// Swiggy MCP PWA Service Worker
const CACHE_NAME = 'swiggy-mcp-cache-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;
  
  // Exclude API, WebSocket and dynamic proxy endpoints from caching
  const url = new URL(event.request.url);
  if (
    url.pathname.startsWith('/api') ||
    url.pathname.startsWith('/chat') ||
    url.pathname.startsWith('/auth') ||
    url.pathname.startsWith('/mcp') ||
    url.pathname.startsWith('/orders') ||
    url.pathname.startsWith('/cart') ||
    url.pathname.startsWith('/addresses')
  ) {
    return;
  }

  // Network-first strategy, falling back to cache
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200 && response.type === 'basic') {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
