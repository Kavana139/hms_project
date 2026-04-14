// MediCore HMS — Service Worker
// Placeholder for PWA offline support

self.addEventListener('install', function(event) {
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', function(event) {
    // Pass-through: no offline caching in this version
    event.respondWith(fetch(event.request));
});
