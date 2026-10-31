// Service worker de GastroMed Pro.
// Política: SOLO se guardan recursos estáticos (estilos, scripts, íconos) y SOLO para usarlos sin conexión.
// Ninguna página, expediente, PDF ni respuesta de datos se almacena en el dispositivo.
// v0.10.2: el nombre de la caché lleva la versión del programa y los archivos se piden SIEMPRE primero a la PC
// (antes se servía para siempre la copia de la primera instalación y las funciones nuevas no aparecían).
const VERSION = "__GM_VERSION__";
const CACHE = "gm-static-" + VERSION;
const OFFLINE = "/static/offline.html";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add(OFFLINE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {
    // Primero la red (siempre la versión actual); la copia guardada solo si la PC no responde.
    e.respondWith(fetch(e.request).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request)));
    return;
  }
  if (e.request.mode === "navigate") {
    // Red siempre; si no hay conexión se muestra un aviso sin datos clínicos.
    e.respondWith(fetch(e.request).catch(() => caches.match(OFFLINE)));
  }
});
