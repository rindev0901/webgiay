const CACHE_NAME = 'datshoes-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/main.css',
  '/static/manifest.json'
];

// Install service worker and cache basic assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// Activate service worker and clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Network first, falling back to cache
self.addEventListener('fetch', (event) => {
  // Only cache GET requests
  if (event.request.method !== 'GET') return;

  // Skip dynamic admin, supply, cart, accounts routes to avoid caching errors
  const url = new URL(event.request.url);
  if (
    url.pathname.startsWith('/admin/') ||
    url.pathname.startsWith('/supply/') ||
    url.pathname.startsWith('/cart/') ||
    url.pathname.startsWith('/accounts/')
  ) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // If network request succeeds, clone response to cache
        if (response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // If offline, try to get from cache
        return caches.match(event.request);
      })
  );
});
