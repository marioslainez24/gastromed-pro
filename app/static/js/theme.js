// Aplica el tema elegido antes de pintar la página (solo preferencia visual; no guarda datos clínicos).
(function () {
  try {
    var t = localStorage.getItem("gm-tema");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* almacenamiento no disponible: se usa el tema del sistema */ }
})();
