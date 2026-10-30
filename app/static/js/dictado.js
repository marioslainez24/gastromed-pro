/* GastroMed Pro · Dictado por voz con el reconocimiento integrado del navegador (Chrome/Edge).
   Gratuito. El audio lo procesa el servicio de voz del navegador (Google o Microsoft); por eso se activa
   solo con aviso de privacidad en Ajustes. El texto se inserta en el campo y el médico lo revisa. */
(function () {
  "use strict";
  var cfg = document.getElementById("dictado-cfg");
  if (!cfg) return;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var note = document.querySelector(".dictation-note");
  if (!SR) {
    if (note) { note.hidden = false; note.textContent = "El dictado por voz requiere Google Chrome o Microsoft Edge."; }
    return;
  }
  if (!window.isSecureContext) {
    if (note) { note.hidden = false; note.textContent = "Para dictar desde el celular, abra el programa con la dirección https:// que muestra la ventana de GastroMed Pro."; }
    return;
  }
  if (note) note.hidden = false;
  var lang = cfg.getAttribute("data-lang") || "es-MX";
  var COMMANDS = [
    [/\s*\bpunto y aparte\b\s*/gi, ".\n"], [/\s*\bnueva l[ií]nea\b\s*/gi, "\n"], [/\s*\bpunto y coma\b/gi, ";"],
    [/\s*\bdos puntos\b/gi, ":"], [/\s*\bpunto\b/gi, "."], [/\s*\bcoma\b/gi, ","],
    [/\s*\babrir par[eé]ntesis\b\s*/gi, " ("], [/\s*\bcerrar par[eé]ntesis\b/gi, ")"], [/\s*\bguion\b\s*/gi, " - "]
  ];
  function clean(t) {
    COMMANDS.forEach(function (c) { t = t.replace(c[0], c[1]); });
    return t.replace(/([.:;\n]\s*)([a-záéíóúñ])/g, function (m, a, b) { return a + b.toUpperCase(); });
  }
  var active = null, rec = null;
  function stop() { if (rec) { try { rec.stop(); } catch (e) {} } }
  function insert(ta, text) {
    var start = ta.selectionStart, end = ta.selectionEnd, before = ta.value.slice(0, start);
    if (before && !/[\s(]$/.test(before) && !/^[.,;:)\n]/.test(text)) text = " " + text;
    if (!before.trim() || /[.\n]\s*$/.test(before)) text = text.replace(/^(\s*)([a-záéíóúñ])/, function (m, a, b) { return a + b.toUpperCase(); });
    ta.value = before + text + ta.value.slice(end);
    var pos = start + text.length; ta.setSelectionRange(pos, pos);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }
  function start(ta, btn) {
    if (active) { stop(); return; }
    rec = new SR(); rec.lang = lang; rec.continuous = true; rec.interimResults = true;
    var live = document.createElement("span"); live.className = "dictation-live small muted"; live.setAttribute("aria-live", "polite");
    btn.after(live);
    active = { ta: ta, btn: btn };
    btn.classList.add("is-on"); btn.setAttribute("aria-pressed", "true"); btn.title = "Detener dictado"; btn.textContent = "⏹ Detener";
    rec.onresult = function (ev) {
      var interim = "";
      for (var i = ev.resultIndex; i < ev.results.length; i++) {
        var r = ev.results[i];
        if (r.isFinal) insert(ta, clean(r[0].transcript.trim())); else interim += r[0].transcript;
      }
      live.textContent = interim;
    };
    rec.onerror = function (ev) {
      var msg = { "not-allowed": "Permita el uso del micrófono en el navegador.", "no-speech": "No se detectó voz.",
                  "network": "Sin conexión a internet: el dictado del navegador la necesita.", "audio-capture": "No se encontró micrófono." }[ev.error];
      if (msg) live.textContent = msg;
    };
    rec.onend = function () {
      btn.classList.remove("is-on"); btn.setAttribute("aria-pressed", "false"); btn.title = "Dictar en este campo"; btn.textContent = "🎤 Dictar";
      setTimeout(function () { live.remove(); }, 2500); active = null; rec = null;
    };
    ta.focus(); rec.start();
  }
  document.querySelectorAll("form textarea").forEach(function (ta) {
    if (ta.readOnly || ta.disabled) return;
    var b = document.createElement("button");
    b.type = "button"; b.className = "mic-btn"; b.title = "Dictar en este campo"; b.setAttribute("aria-label", "Dictar en este campo");
    b.setAttribute("aria-pressed", "false"); b.textContent = "🎤 Dictar";
    b.addEventListener("click", function () { if (active && active.ta !== ta) { stop(); return; } start(ta, b); });
    ta.after(b);
  });
})();
