// Service worker de GastroMed Pro.
// Política: SOLO se guardan en caché recursos estáticos (estilos, scripts, íconos).
// Ninguna página, expediente, PDF ni respuesta de datos se almacena en el dispositivo.
const CACHE = "gm-static-v1";
const STATIC = ["/static/css/app.css", "/static/js/app.js", "/static/js/theme.js", "/static/icons/icon.svg",
                "/static/icons/sprite.svg", "/static/icons/icon-192.png", "/static/offline.html"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((r) => r || fetch(e.request)));
    return;
  }
  if (e.request.mode === "navigate") {
    // Red siempre; si no hay conexión se muestra un aviso sin datos clínicos.
    e.respondWith(fetch(e.request).catch(() => caches.match("/static/offline.html")));
  }
});
