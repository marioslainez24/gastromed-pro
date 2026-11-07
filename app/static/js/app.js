// NeuroMed Pro — comportamiento de la interfaz. Sin dependencias externas.
// Regla: no se guarda información clínica en el navegador (ni localStorage ni caché).
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var csrf = function () { var i = $('input[name="csrf_token"]'); return i ? i.value : ""; };

  // ---- Tema claro/oscuro ---------------------------------------------------
  $$("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var root = document.documentElement;
      var cur = root.getAttribute("data-theme") ||
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = cur === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("gm-tema", next); } catch (e) {}
    });
  });

  // ---- Atajo "/" para la búsqueda global -----------------------------------
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (e.key === "/" && !e.ctrlKey && !e.metaKey && tag !== "input" && tag !== "textarea" && tag !== "select") {
      var s = $("#buscar-global");
      if (s) { e.preventDefault(); s.focus(); s.select(); }
    }
  });

  // ---- Autocompletar pacientes ---------------------------------------------
  function autocomplete(input, list, url, onPick) {
    var timer = null, items = [], idx = -1, ctrl = null;
    function close() { list.hidden = true; list.innerHTML = ""; idx = -1; input.setAttribute("aria-expanded", "false"); }
    function render() {
      list.innerHTML = "";
      if (!items.length) {
        var li = document.createElement("li"); li.className = "muted small"; li.style.padding = ".5rem";
        li.textContent = "Sin coincidencias"; list.appendChild(li);
      }
      items.forEach(function (it, i) {
        var li = document.createElement("li");
        var el = document.createElement(onPick ? "button" : "a");
        if (onPick) { el.type = "button"; } else { el.href = it.url; }
        el.setAttribute("role", "option");
        el.setAttribute("aria-selected", i === idx ? "true" : "false");
        var b = document.createElement("b"); b.textContent = it.nombre;
        var sm = document.createElement("span"); sm.className = "small muted";
        sm.textContent = " · " + it.mrn + (it.documento ? " · " + it.documento : "");
        el.appendChild(b); el.appendChild(sm);
        el.addEventListener("mousedown", function (ev) { ev.preventDefault(); pick(i); });
        li.appendChild(el); list.appendChild(li);
      });
      list.hidden = false; input.setAttribute("aria-expanded", "true");
    }
    function pick(i) {
      var it = items[i]; if (!it) return;
      if (onPick) { onPick(it); close(); } else { window.location.href = it.url; }
    }
    input.addEventListener("input", function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(function () {
        if (ctrl) ctrl.abort();
        ctrl = new AbortController();
        fetch(url + "&q=" + encodeURIComponent(q), { headers: { Accept: "application/json" }, credentials: "same-origin", signal: ctrl.signal })
          .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
          .then(function (d) { items = d.resultados || []; idx = -1; render(); })
          .catch(function () {});
      }, 200);
    });
    input.addEventListener("keydown", function (e) {
      if (list.hidden) return;
      if (e.key === "ArrowDown") { e.preventDefault(); idx = Math.min(idx + 1, items.length - 1); render(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); idx = Math.max(idx - 1, 0); render(); }
      else if (e.key === "Enter" && idx >= 0) { e.preventDefault(); pick(idx); }
      else if (e.key === "Escape") { close(); }
    });
    input.addEventListener("blur", function () { setTimeout(close, 150); });
  }
  $$("form[data-autocomplete]").forEach(function (f) {
    autocomplete($('input[name="q"]', f), $(".suggest", f), f.getAttribute("data-autocomplete"));
  });
  $$("[data-picker]").forEach(function (box) {
    var input = $('input[type="search"]', box), hidden = $('input[name="patient_id"]', box);
    autocomplete(input, $(".suggest", box), box.getAttribute("data-picker"), function (it) {
      hidden.value = it.id; input.value = it.nombre + " · " + it.mrn; input.setAttribute("data-picked", "1");
    });
    input.addEventListener("input", function () { hidden.value = ""; });
  });

  // ---- Aviso de cambios sin guardar ----------------------------------------
  var dirty = false;
  $$("form[data-dirty-guard]").forEach(function (f) {
    f.addEventListener("input", function () { dirty = true; });
    f.addEventListener("submit", function () { dirty = false; });
  });
  window.addEventListener("beforeunload", function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  // ---- Confirmaciones y utilidades -----------------------------------------
  $$("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
      else if (f.hasAttribute("data-discard")) dirty = false;     // descartar: no preguntar por cambios sin guardar
    });
  });
  $$("[data-autosubmit]").forEach(function (s) { s.addEventListener("change", function () { s.form.submit(); }); });
  $$("[data-back]").forEach(function (a) {
    a.addEventListener("click", function (e) { if (history.length > 1) { e.preventDefault(); history.back(); } });
  });
  var typeSel = $("select[data-durations]");
  if (typeSel) {
    typeSel.addEventListener("change", function () {
      var d = JSON.parse(typeSel.getAttribute("data-durations"));
      var dur = $('input[name="duration"]'); if (dur && d[typeSel.value]) dur.value = d[typeSel.value];
    });
  }
  function grow(t) { t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight + 2, 700) + "px"; }
  $$("textarea[data-grow]").forEach(function (t) { grow(t); t.addEventListener("input", function () { grow(t); }); });

  // ---- Nota clínica: autoguardado en el servidor ----------------------------
  var noteForm = $("form[data-autosave]");
  if (noteForm) {
    var state = $("[data-save-state]"), versionInput = $("[data-version]", noteForm), saving = false, pending = false, conflict = false, t2 = null;
    var bmiOut = $("[data-bmi]");
    function setState(msg, isErr) { state.textContent = msg; state.classList.toggle("is-error", !!isErr); }
    function payload() {
      var data = {};
      new FormData(noteForm).forEach(function (v, k) { if (k !== "csrf_token" && k !== "then") data[k] = v; });
      return data;
    }
    function save() {
      if (conflict) return;
      if (saving) { pending = true; return; }
      saving = true; setState("Guardando…");
      fetch(noteForm.getAttribute("data-autosave"), {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf() },
        body: JSON.stringify(payload())
      }).then(function (r) {
        return r.json().then(function (d) { return { status: r.status, d: d }; }, function () { return { status: r.status, d: {} }; });
      }).then(function (res) {
        if (res.status === 200) {
          versionInput.value = res.d.version; dirty = false;
          var now = new Date(); setState("Guardado automáticamente " + now.toLocaleTimeString("es-HN", { hour: "2-digit", minute: "2-digit" }));
          if (bmiOut) bmiOut.textContent = res.d.imc ? String(res.d.imc) : "—";
        } else if (res.status === 409) {
          conflict = true; setState("CONFLICTO: la nota se modificó en otra ventana o dispositivo. Copie su texto y recargue la página.", true);
        } else if (res.status === 422) {
          var errs = res.d.campos ? Object.keys(res.d.campos).map(function (k) { return res.d.campos[k]; }).join(" ") : "";
          setState("No guardado: " + errs, true);
        } else if (res.status === 401) {
          setState("Su sesión expiró. Copie su texto, inicie sesión y vuelva a pegarlo.", true);
        } else {
          setState("No se pudo guardar (error " + res.status + "). Se reintentará.", true);
        }
      }).catch(function () {
        setState("Sin conexión: los cambios aún no están guardados en el servidor.", true);
      }).then(function () {
        saving = false; if (pending) { pending = false; save(); }
      });
    }
    noteForm.addEventListener("input", function () {
      setState("Cambios sin guardar…"); clearTimeout(t2); t2 = setTimeout(save, 2500);
    });
    // BMI inmediato (visual); el valor oficial lo calcula el servidor.
    function liveBmi() {
      var w = parseFloat((($('input[name="v_peso_kg"]') || {}).value || "").replace(",", "."));
      var h = parseFloat((($('input[name="v_talla_cm"]') || {}).value || "").replace(",", "."));
      if (bmiOut) bmiOut.textContent = (w > 0 && h > 0) ? (Math.round(w / Math.pow(h / 100, 2) * 10) / 10).toString() : "—";
    }
    $$('input[name="v_peso_kg"], input[name="v_talla_cm"]').forEach(function (i) { i.addEventListener("input", liveBmi); });
    $$("input[data-range]").forEach(function (i) {
      i.addEventListener("change", function () {
        var p = i.getAttribute("data-range").split("-"), v = parseFloat(i.value.replace(",", "."));
        var bad = i.value !== "" && (isNaN(v) || v < parseFloat(p[0]) || v > parseFloat(p[1]));
        i.setAttribute("aria-invalid", bad ? "true" : "false");
      });
    });
    // Copiar información de la nota previa con su fecha, para revisión explícita.
    function copyPrior(b, focus) {
      var key = b.getAttribute("data-copy-prior");
      var ta = $('textarea[name="' + key + '"]', noteForm);
      var txt = $("[data-prior-text]", b.closest(".prior-item")).textContent;
      if (!ta || b.disabled) return;
      ta.value = (ta.value.trim() ? ta.value.replace(/\s+$/, "") + "\n" : "") + "[Tomado de la nota del " + b.getAttribute("data-prior-date") + " — revisar] " + txt;
      ta.dispatchEvent(new Event("input", { bubbles: true })); grow(ta); if (focus) ta.focus();
      b.disabled = true; b.textContent = "✓ Copiado";
    }
    $$("[data-copy-prior]").forEach(function (b) { b.addEventListener("click", function () { copyPrior(b, true); }); });
    var cpAll = $("[data-copy-prior-all]");
    if (cpAll) cpAll.addEventListener("click", function () {
      $$("[data-copy-prior]").forEach(function (b) { copyPrior(b, false); });
      cpAll.disabled = true; cpAll.textContent = "✓ Todo copiado: revise y actualice";
    });
  }

  // ---- Receta: agregar/quitar medicamentos ----------------------------------
  var rxBox = $("#rx-items");
  if (rxBox) {
    function renumber() {
      $$("[data-rx-item]", rxBox).forEach(function (fs, i) {
        $("[data-rx-num]", fs).textContent = i + 1;
        $$("input", fs).forEach(function (inp) { inp.name = inp.name.replace(/^item-\d+-/, "item-" + i + "-"); });
      });
    }
    $("[data-rx-add]").addEventListener("click", function () {
      var items = $$("[data-rx-item]", rxBox);
      if (items.length >= 15) { window.alert("Máximo 15 medicamentos por receta."); return; }
      var clone = items[items.length - 1].cloneNode(true);
      $$("input", clone).forEach(function (i) { i.value = i.name.indexOf("-route") > -1 ? "oral" : ""; });
      rxBox.appendChild(clone); renumber(); $("input", clone).focus();
    });
    rxBox.addEventListener("click", function (e) {
      if (!e.target.matches("[data-rx-remove]")) return;
      var items = $$("[data-rx-item]", rxBox);
      if (items.length === 1) { $$("input", items[0]).forEach(function (i) { i.value = ""; }); return; }
      e.target.closest("[data-rx-item]").remove(); renumber();
    });
  }

  // ---- Laboratorio: mostrar todas las pruebas del catálogo ------------------
  $$("[data-show-all-labs]").forEach(function (b) {
    b.addEventListener("click", function () {
      $$("tr.hidden-row").forEach(function (r) { r.classList.remove("hidden-row"); }); b.remove();
    });
  });

  // ---- Frases predefinidas: botón «Frases» bajo cada campo ------------------
  var frData = $("#frases-data");
  if (frData) {
    var phrases = []; try { phrases = JSON.parse(frData.getAttribute("data-frases") || "[]"); } catch (e) {}
    var adminUrl = frData.getAttribute("data-admin");
    var openMenu = null;
    function closeMenu() { if (openMenu) { openMenu.remove(); openMenu = null; } }
    document.addEventListener("click", function (e) { if (openMenu && !openMenu.contains(e.target) && !e.target.matches(".phr-btn")) closeMenu(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenu(); });
    function insertText(ta, text) {
      var s = ta.selectionStart, en = ta.selectionEnd, before = ta.value.slice(0, s), after = ta.value.slice(en);
      if (document.activeElement !== ta && !ta.value.slice(0, s).length && ta.value.length) { before = ta.value; after = ""; s = en = ta.value.length; }
      var sep = before && !/\s$/.test(before) ? (/[.:]$/.test(before) ? " " : "\n") : "";
      ta.value = before + sep + text + after;
      var pos = (before + sep + text).length; ta.focus(); ta.setSelectionRange(pos, pos);
      ta.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
    }
    $$("textarea[data-phrase-field]").forEach(function (ta) {
      var f = ta.getAttribute("data-phrase-field");
      var mine = phrases.filter(function (p) { return p.f === f || p.f === "*"; });
      var wrap = document.createElement("div"); wrap.className = "phr-wrap";
      var btn = document.createElement("button"); btn.type = "button"; btn.className = "link-btn small phr-btn";
      btn.textContent = mine.length ? "Frases (" + mine.length + ") ▾" : "＋ Frases";
      wrap.appendChild(btn);
      ta.insertAdjacentElement("afterend", wrap);
      var lastPos = null;
      ta.addEventListener("blur", function () { lastPos = [ta.selectionStart, ta.selectionEnd]; });
      btn.addEventListener("click", function () {
        if (openMenu) { closeMenu(); return; }
        if (!mine.length) { window.open(adminUrl, "_blank", "noopener"); return; }
        var menu = document.createElement("div"); menu.className = "phr-menu"; menu.setAttribute("role", "menu");
        mine.forEach(function (p) {
          var b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "menuitem");
          var t = document.createElement("b"); t.textContent = p.t; var sm = document.createElement("small"); sm.textContent = p.b;
          b.appendChild(t); b.appendChild(sm);
          b.addEventListener("click", function () {
            if (lastPos) ta.setSelectionRange(lastPos[0], lastPos[1]);
            insertText(ta, p.b); closeMenu();
          });
          menu.appendChild(b);
        });
        var a = document.createElement("a"); a.href = adminUrl; a.target = "_blank"; a.rel = "noopener"; a.className = "small"; a.textContent = "Administrar frases…";
        a.style.display = "block"; a.style.padding = ".4rem .55rem"; menu.appendChild(a);
        wrap.appendChild(menu); openMenu = menu;
        var first = menu.querySelector("button"); if (first) first.focus();
      });
    });
  }

  // ---- Plantillas de nota: llenan los campos vacíos -------------------------
  var tplBar = $("[data-note-tpls]");
  if (tplBar) {
    var tpls = []; try { tpls = JSON.parse(tplBar.getAttribute("data-note-tpls") || "[]"); } catch (e) {}
    var tsel = $("[data-tpl-select]", tplBar), tmsg = $("[data-tpl-msg]", tplBar);
    if (!tpls.length) { tplBar.hidden = true; }
    tpls.forEach(function (t, i) { var o = document.createElement("option"); o.value = i; o.textContent = t.name; tsel.appendChild(o); });
    $("[data-tpl-apply]", tplBar).addEventListener("click", function () {
      var t = tpls[tsel.value]; if (!t) return;
      var filled = 0, kept = 0;
      Object.keys(t.fields).forEach(function (k) {
        var ta = document.querySelector("textarea[name='" + k + "']");
        if (!ta) return;
        if (ta.value.trim()) { kept++; return; }
        ta.value = t.fields[k]; ta.dispatchEvent(new Event("input", { bubbles: true })); filled++;
      });
      dirty = true;
      tmsg.textContent = "Plantilla «" + t.name + "» aplicada: " + filled + " campo(s) llenados" + (kept ? ", " + kept + " ya tenían texto y se conservaron." : ".") + " Revise el texto.";
    });
  }

  // ---- Endoscopia: desplegable de diagnósticos frecuentes para la conclusión -
  var dxPanel = $("[data-dx-panel]");
  if (dxPanel) {
    var dxs = []; try { dxs = JSON.parse(dxPanel.getAttribute("data-dx") || "[]"); } catch (e) {}
    var dxOpen = $("[data-dx-open]"), dxList = $("[data-dx-list]", dxPanel), dxSearch = $("[data-dx-search]", dxPanel), dxCode = $("[data-dx-code]", dxPanel);
    var dxTa = document.getElementById(dxOpen.getAttribute("data-dx-open"));
    try { var pref = localStorage.getItem("gm-dx-code"); if (pref !== null) dxCode.checked = pref === "1"; } catch (e) {}
    dxCode.addEventListener("change", function () { try { localStorage.setItem("gm-dx-code", dxCode.checked ? "1" : "0"); } catch (e) {} });
    function dxNorm(x) { return x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
    function dxRender() {
      var q = dxNorm(dxSearch.value.trim()), grp = null;
      dxList.textContent = "";
      dxs.forEach(function (d) {
        if (q && dxNorm(d.t + " " + d.g + " " + (d.c || "")).indexOf(q) < 0) return;
        if (d.g !== grp) { grp = d.g; var h = document.createElement("h4"); h.className = "dx-grp"; h.textContent = grp; dxList.appendChild(h); }
        var b = document.createElement("button"); b.type = "button"; b.className = "dx-item"; b.setAttribute("role", "option");
        var t = document.createElement("span"); t.textContent = d.t; b.appendChild(t);
        if (d.c) { var c = document.createElement("span"); c.className = "dx-code mono"; c.textContent = d.c + (d.a ? "*" : ""); b.appendChild(c); }
        b.addEventListener("click", function () {
          var line = d.t + (dxCode.checked && d.c ? " (CIE-10 " + d.c + (d.a ? "*" : "") + ")" : "");
          var v = dxTa.value.replace(/\s+$/, "");
          dxTa.value = (v ? v + "\n" : "") + line;
          dxTa.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
          b.classList.add("is-added"); setTimeout(function () { b.classList.remove("is-added"); }, 900);
        });
        dxList.appendChild(b);
      });
      if (!dxList.children.length) { var p = document.createElement("p"); p.className = "small muted"; p.textContent = "Sin resultados. Escriba el diagnóstico directamente en la conclusión o guárdelo como frase."; dxList.appendChild(p); }
    }
    function dxToggle(show) { dxPanel.hidden = !show; dxOpen.setAttribute("aria-expanded", show ? "true" : "false"); if (show) { dxRender(); dxSearch.focus(); } }
    dxOpen.addEventListener("click", function () { dxToggle(dxPanel.hidden); });
    $("[data-dx-close]", dxPanel).addEventListener("click", function () { dxToggle(false); });
    dxSearch.addEventListener("input", dxRender);
    dxSearch.addEventListener("keydown", function (e) { if (e.key === "Enter") e.preventDefault(); if (e.key === "Escape") dxToggle(false); });
  }

  // ---- Asistente de historia de la enfermedad actual ------------------------
  var hx = $("[data-hea-assist]");
  if (hx) {
    var hxForm = document.getElementById("hea-form"), hxActions = $("[data-hea-actions]", hx), hxMsg = $("[data-hea-msg]", hx);
    var hxTarget = document.querySelector("textarea[name='" + hx.getAttribute("data-target") + "']");
    function hxShow(code) {
      $$("[data-hea-group]", hx).forEach(function (gp) { gp.hidden = gp.getAttribute("data-hea-group") !== code; });
      hxActions.hidden = !code;
    }
    $$("[data-hea-motivo]", hx).forEach(function (r) { r.addEventListener("change", function () { hxShow(r.value); }); });
    // Un clic sobre una opción ya elegida la desmarca
    $$("input[data-toggle-radio]", hx).forEach(function (r) {
      r.addEventListener("mousedown", function () { r.setAttribute("data-was", r.checked ? "1" : ""); });
      r.addEventListener("click", function () { if (r.getAttribute("data-was") === "1") { r.checked = false; r.setAttribute("data-was", ""); } });
    });
    $("[data-hea-clear]", hx).addEventListener("click", function () {
      var code = (hx.querySelector("[data-hea-motivo]:checked") || {}).value;
      var gp = code && hx.querySelector("[data-hea-group='" + code + "']");
      if (!gp) return;
      $$("input", gp).forEach(function (i) { if (i.type === "checkbox" || (i.type === "radio" && i.name.slice(-11) !== "-hea_unidad")) i.checked = false; else if (i.type !== "radio") i.value = ""; });
    });
    $("[data-hea-write]", hx).addEventListener("click", function () {
      var fd = new FormData(hxForm), tok = csrf();
      fd.append("csrf_token", tok);
      hxMsg.textContent = "Redactando…"; hxMsg.classList.remove("is-error");
      fetch(hx.getAttribute("data-url"), { method: "POST", body: fd, credentials: "same-origin",
                                           headers: { "X-Requested-With": "fetch", "X-CSRF-Token": tok, Accept: "application/json" } })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) { hxMsg.textContent = res.d.error || res.d.detalle || "No se pudo redactar."; hxMsg.classList.add("is-error"); return; }
          var v = hxTarget.value.replace(/\s+$/, "");
          hxTarget.value = (v ? v + "\n\n" : "") + res.d.texto;
          hxTarget.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
          hxTarget.scrollIntoView({ block: "center", behavior: "smooth" });
          hxMsg.textContent = "Listo: se agregó a la historia. Revíselo y corrija o dicte lo que falte.";
        })
        .catch(function () { hxMsg.textContent = "Sin conexión con el programa."; hxMsg.classList.add("is-error"); });
    });
  }

  // ---- Exploración física con clics -----------------------------------------
  var ex = $("[data-exam-assist]");
  if (ex) {
    var exForm = document.getElementById("exam-form"), exMsg = $("[data-exam-msg]", ex);
    $$("[data-exam-sys]", ex).forEach(function (sys) {
      var more = $("[data-exam-more]", sys), box = $("[data-exam-findings]", sys), nor = $("[data-exam-normal]", sys);
      more.addEventListener("click", function () { box.hidden = !box.hidden; more.setAttribute("aria-expanded", box.hidden ? "false" : "true"); });
      // Al marcar un hallazgo se quita «Normal» (y se ofrece «Resto sin alteraciones»)
      $$("[data-exam-finding]", sys).forEach(function (f) {
        f.addEventListener("change", function () { if ((f.checked || (f.value && f.type !== "checkbox" && f.type !== "radio")) && nor.checked) nor.checked = false; });
      });
    });
    function exWrite() {
      var fd = new FormData(exForm), tok = csrf();
      fd.append("csrf_token", tok);
      exMsg.textContent = "Redactando…"; exMsg.classList.remove("is-error");
      return fetch(ex.getAttribute("data-url"), { method: "POST", body: fd, credentials: "same-origin",
                                                  headers: { "X-Requested-With": "fetch", "X-CSRF-Token": tok, Accept: "application/json" } })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) { exMsg.textContent = res.d.error || res.d.detalle || "No se pudo redactar."; exMsg.classList.add("is-error"); return; }
          var first = null;
          Object.keys(res.d.campos).forEach(function (k) {
            var ta = document.querySelector("textarea[name='" + k + "']"); if (!ta) return;
            var v = ta.value.replace(/\s+$/, "");
            ta.value = (v ? v + (k === "narrativa" ? "\n\n" : "\n") : "") + res.d.campos[k];
            ta.dispatchEvent(new Event("input", { bubbles: true })); if (!first) first = ta;
          });
          dirty = true;
          if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
          exMsg.textContent = "Listo: se agregó a la exploración. Revíselo y corrija lo que haga falta.";
        })
        .catch(function () { exMsg.textContent = "Sin conexión con el programa."; exMsg.classList.add("is-error"); });
    }
    $("[data-exam-write]", ex).addEventListener("click", exWrite);
    $("[data-exam-allnormal]", ex).addEventListener("click", function () {
      ["general", "cardiopulmonar", "mental", "pares", "motor", "reflejos", "sensibilidad", "coordinacion"].forEach(function (k) {
        var sys = ex.querySelector("[data-exam-sys='" + k + "']"); if (!sys) return;
        if (!$$("[data-exam-finding]", sys).some(function (f) { return f.checked || ((f.type === "text" || f.inputMode) && f.type !== "checkbox" && f.type !== "radio" && f.value); }))
          $("[data-exam-normal]", sys).checked = true;
      });
      exWrite();
    });
    $("[data-exam-clear]", ex).addEventListener("click", function () {
      $$("input", ex).forEach(function (i) { if (i.type === "checkbox" || i.type === "radio") i.checked = false; else i.value = ""; });
      exMsg.textContent = "";
    });
  }

  // ---- Endoscopia: hallazgos con clics y sugerencias de diagnóstico ----------
  var efRoot = $("[data-efind-url]");
  if (efRoot) {
    var efUrl = efRoot.getAttribute("data-efind-url"), sugBox = $("[data-dx-suggest]"), concl = document.getElementById("conclusion");
    function addSuggestion(d) {
      if (!sugBox || !concl) return;
      var label = d.t + (d.c ? " (CIE-10 " + d.c + (d.a ? "*" : "") + ")" : "");
      if (concl.value.indexOf(d.t) >= 0) return;
      if ($$("button", sugBox).some(function (b) { return b.getAttribute("data-t") === d.t; })) return;
      var b = document.createElement("button"); b.type = "button"; b.className = "hea-chip dx-sug"; b.setAttribute("data-t", d.t);
      b.textContent = "＋ " + label;
      b.addEventListener("click", function () {
        var codeOn = $("[data-dx-code]"); codeOn = codeOn ? codeOn.checked : true;
        var line = d.t + (codeOn && d.c ? " (CIE-10 " + d.c + (d.a ? "*" : "") + ")" : "");
        var v = concl.value.replace(/\s+$/, "");
        concl.value = (v ? v + "\n" : "") + line; concl.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
        b.remove(); if (!$$("button", sugBox).length) sugBox.hidden = true;
      });
      sugBox.appendChild(b); sugBox.hidden = false;
    }
    $$("[data-efind]").forEach(function (box) {
      var sec = box.getAttribute("data-efind"), ta = document.getElementById("nar-" + sec);
      $$("[data-efind-pick]", box).forEach(function (r) {
        r.addEventListener("change", function () { $$("[data-efind-params]", box).forEach(function (g) { g.hidden = g.getAttribute("data-efind-params") !== r.value; }); });
      });
      $$("[data-efind-add]", box).forEach(function (btn) {
        var fk = btn.getAttribute("data-efind-add"), grp = btn.closest("[data-efind-params]"), msg = $("[data-efind-msg]", grp);
        btn.addEventListener("click", function () {
          var fd = new FormData(), tok = csrf(), pre = "ef-" + sec + "-" + fk + "-";
          fd.append("csrf_token", tok); fd.append("section", sec); fd.append("finding", fk);
          $$("input", grp).forEach(function (i) {
            if (!i.name || i.name.indexOf(pre) !== 0) return;
            if ((i.type === "checkbox" || i.type === "radio") && !i.checked) return;
            if (i.type !== "checkbox" && i.type !== "radio" && !i.value) return;
            fd.append(i.name, i.value);
          });
          msg.textContent = "…"; msg.classList.remove("is-error");
          fetch(efUrl, { method: "POST", body: fd, credentials: "same-origin", headers: { "X-Requested-With": "fetch", "X-CSRF-Token": tok, Accept: "application/json" } })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
              if (!res.ok) { msg.textContent = res.d.error || res.d.detalle || "No se pudo agregar."; msg.classList.add("is-error"); return; }
              var normalBtn = document.querySelector("[data-fill-normal='nar-" + sec + "']");
              var normalTxt = normalBtn ? (normalBtn.getAttribute("data-normal") || "").trim() : "";
              var v = ta.value.replace(/\s+$/, ""), replaced = false;
              if (normalTxt && v === normalTxt) { v = ""; replaced = true; }
              ta.value = (v ? v + " " : "") + res.d.texto; ta.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
              (res.d.dx || []).forEach(addSuggestion);
              $$("input", grp).forEach(function (i) { if (i.type === "checkbox" || i.type === "radio") i.checked = false; else i.value = ""; });
              msg.textContent = replaced ? "Agregado (se reemplazó el texto normal de este segmento)." : "Agregado. Puede agregar otro.";
            })
            .catch(function () { msg.textContent = "Sin conexión con el programa."; msg.classList.add("is-error"); });
        });
      });
    });
  }

  // ---- Endoscopia: recomendaciones sugeridas según la conclusión ------------
  var recBox = $("[data-rec-suggest]");
  if (recBox) {
    var recs = {}; try { recs = JSON.parse(recBox.getAttribute("data-recs") || "{}"); } catch (e) {}
    var cTa = document.getElementById("conclusion"), rTa = document.getElementById("recommendations");
    function recSync() {
      $$("button", recBox).forEach(function (b) { b.remove(); });
      Object.keys(recs).forEach(function (dx) {
        if (cTa.value.indexOf(dx) < 0 || rTa.value.indexOf(recs[dx]) >= 0) return;
        var b = document.createElement("button"); b.type = "button"; b.className = "hea-chip dx-sug"; b.title = recs[dx];
        b.textContent = "＋ " + dx;
        b.addEventListener("click", function () {
          var v = rTa.value.replace(/\s+$/, ""); rTa.value = (v ? v + "\n" : "") + recs[dx];
          rTa.dispatchEvent(new Event("input", { bubbles: true })); dirty = true; recSync();
        });
        recBox.appendChild(b);
      });
      recBox.hidden = !$$("button", recBox).length;
    }
    if (cTa && rTa) { cTa.addEventListener("input", recSync); rTa.addEventListener("input", recSync); recSync(); }
  }
  var recSel = $("[data-rec-select]");
  if (recSel) recSel.addEventListener("change", function () {
    var o = recSel.options[recSel.selectedIndex]; $("[data-rec-text]").value = o ? (o.getAttribute("data-rec") || "") : "";
  });

  // ---- Antecedentes con clics (se guardan en el expediente) -----------------
  $$("[data-ant]").forEach(function (box) {
    var url = box.getAttribute("data-url"), msg = $("[data-ant-msg]", box);
    var target = box.getAttribute("data-target") ? document.getElementById(box.getAttribute("data-target")) : null;
    var lastGen = target ? target.value : "";
    function setText(t) {
      if (!target) return;
      if (!target.value.trim() || target.value === lastGen) {
        target.value = t; lastGen = t; target.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
        return true;
      }
      return false;
    }
    function send(data, btn) {
      var fd = new FormData(), tok = csrf();
      fd.append("csrf_token", tok);
      Object.keys(data).forEach(function (k) { [].concat(data[k]).forEach(function (v) { fd.append(k, v); }); });
      msg.textContent = "Guardando…"; msg.classList.remove("is-error");
      fetch(url, { method: "POST", body: fd, credentials: "same-origin", headers: { "X-Requested-With": "fetch", "X-CSRF-Token": tok, Accept: "application/json" } })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) { msg.textContent = res.d.error || res.d.detalle || "No se pudo guardar."; msg.classList.add("is-error"); return; }
          if (btn) { btn.classList.add("is-on"); if (btn.textContent.indexOf("✓") !== 0) btn.textContent = "✓ " + btn.textContent; }
          if (data.habit) $$("[data-ant-habit='" + data.habit + "']", box).forEach(function (b) { if (b !== btn) { b.classList.remove("is-on"); b.textContent = b.getAttribute("data-value"); } });
          var updated = setText(res.d.texto);
          msg.textContent = (res.d.agregado ? "Guardado en el expediente: " : "Ya estaba registrado: ") + res.d.descripcion +
            (target && !updated ? ". Usted editó el campo: pulse «Actualizar» para traer la lista completa." : ".");
          if (!target) { setTimeout(function () { dirty = false; location.hash = "antecedentes"; location.reload(); }, 600); }
        })
        .catch(function () { msg.textContent = "Sin conexión con el programa."; msg.classList.add("is-error"); });
    }
    $$("[data-ant-add]", box).forEach(function (b) {
      b.addEventListener("click", function () { send({ category: b.getAttribute("data-category"), item: b.getAttribute("data-item") }, b); });
    });
    $$("[data-ant-habit]", box).forEach(function (b) {
      b.addEventListener("click", function () {
        var det = $("[data-ant-detail]", box);
        send({ category: "habito", habit: b.getAttribute("data-ant-habit"), value: b.getAttribute("data-value"), detail: det.value }, b);
        det.value = "";
      });
    });
    var famBtn = $("[data-ant-fam-add]", box);
    if (famBtn) famBtn.addEventListener("click", function () {
      var it = box.querySelector("[data-ant-fam]:checked");
      if (!it) { msg.textContent = "Elija el antecedente familiar."; msg.classList.add("is-error"); return; }
      send({ category: "familiar", item: it.value, relative: $$("[data-ant-rel]:checked", box).map(function (c) { return c.value; }) });
      it.checked = false; $$("[data-ant-rel]", box).forEach(function (c) { c.checked = false; });
    });
    $("[data-ant-other-add]", box).addEventListener("click", function () {
      var o = $("[data-ant-other]", box), w = $("[data-ant-when]", box);
      send({ category: $("[data-ant-other-cat]", box).value, item: "__otro__", other: o.value, when_text: w.value });
      o.value = ""; w.value = "";
    });
    var ref = $("[data-ant-refresh]", box);
    if (ref) ref.addEventListener("click", function () {
      fetch(box.getAttribute("data-text-url"), { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); }).then(function (d) {
          if (target.value.trim() && target.value !== lastGen && !window.confirm("¿Reemplazar el texto del campo «Antecedentes» por la lista del expediente?")) return;
          target.value = d.texto; lastGen = d.texto; target.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
          msg.textContent = "Antecedentes actualizados desde el expediente.";
        });
    });
  });

  // ---- Solicitud de laboratorio: perfiles, buscador y contador ---------------
  var sheet = $("[data-lab-sheet]");
  if (sheet) {
    var tests = $$("[data-test]", sheet), profs = $$("[data-profile]", sheet), count = $("[data-lab-count]", sheet);
    tests.forEach(function (t) { t.setAttribute("data-user", t.checked ? "1" : ""); t.addEventListener("change", function () { t.setAttribute("data-user", t.checked ? "1" : ""); syncLab(); }); });
    function syncLab() {
      var cov = {};
      profs.forEach(function (p) { if (p.checked) (p.getAttribute("data-components") || "").split(" ").forEach(function (k) { if (k) cov[k] = 1; }); });
      var n = 0;
      tests.forEach(function (t) {
        var lab = t.closest("label");
        if (cov[t.value]) { t.checked = true; t.disabled = true; lab.classList.add("in-profile"); }
        else { if (t.disabled) { t.disabled = false; t.checked = !!t.getAttribute("data-user"); } lab.classList.remove("in-profile"); if (t.checked) n++; }
      });
      profs.forEach(function (p) { if (p.checked) n++; });
      count.textContent = n;
    }
    profs.forEach(function (p) { p.addEventListener("change", function () { syncLab(); dirty = true; }); });
    syncLab();
    var search = $("[data-lab-search]", sheet);
    function norm(x) { return x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
    search.addEventListener("input", function () {
      var q = norm(search.value.trim());
      $$("[data-lab-item]", sheet).forEach(function (it) { it.hidden = q && norm(it.textContent).indexOf(q) < 0; });
      $$("[data-lab-sec]", sheet).forEach(function (sec) { sec.hidden = !$$("[data-lab-item]", sec).some(function (i) { return !i.hidden; }); });
    });
    search.addEventListener("keydown", function (e) { if (e.key === "Enter") e.preventDefault(); });
  }

  // ---- Endoscopia: botón «Normal» por segmento y «Todo normal» --------------
  function fillNormal(btn, ask) {
    var ta = document.getElementById(btn.getAttribute("data-fill-normal"));
    if (!ta) return false;
    var txt = btn.getAttribute("data-normal") || "";
    if (ta.value.trim()) {
      if (!ask || ta.value.trim() === txt.trim()) return false;
      if (!window.confirm("Este campo ya tiene texto. ¿Reemplazarlo por la descripción normal?")) return false;
    }
    ta.value = txt; ta.dispatchEvent(new Event("input", { bubbles: true })); dirty = true;
    return true;
  }
  var zsel = $("select[name='zline']");
  function zlineExtras() { $$("[data-zline-extra]").forEach(function (el) { el.hidden = !(zsel && zsel.value === "no_coincide"); }); }
  if (zsel) { zsel.addEventListener("change", zlineExtras); zlineExtras(); }
  $$("[data-fill-normal]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (fillNormal(b, true) && b.getAttribute("data-fill-normal") === "nar-ueg" && zsel && !zsel.value) { zsel.value = "coincide"; zlineExtras(); }
    });
  });
  $$("[data-fill-all-normal]").forEach(function (b) {
    b.addEventListener("click", function () {
      var n = 0, kept = 0;
      $$("[data-fill-normal]").forEach(function (x) {
        var ta = document.getElementById(x.getAttribute("data-fill-normal"));
        if (ta && ta.value.trim()) { kept++; } else if (fillNormal(x, false)) { n++; }
      });
      if (zsel && !zsel.value) { zsel.value = "coincide"; zlineExtras(); }
      b.textContent = kept ? "✓ Listo (" + kept + " campo(s) con texto se conservaron)" : "✓ Listo: revise el texto";
    });
  });

  // ---- Filas repetibles (hallazgos, frascos, prótesis) -----------------------
  $$("[data-row-add]").forEach(function (btn) {
    var box = document.getElementById(btn.getAttribute("data-row-add"));
    var prefix = box.getAttribute("data-rows");
    function renumber() {
      $$("[data-row]", box).forEach(function (row, i) {
        $$("input, select, textarea", row).forEach(function (el) {
          el.name = el.name.replace(new RegExp("^" + prefix + "-\\d+-"), prefix + "-" + i + "-");
        });
      });
    }
    btn.addEventListener("click", function () {
      var rows = $$("[data-row]", box), clone;
      if (rows.length >= 40) return;
      if (rows.length) { clone = rows[rows.length - 1].cloneNode(true); }
      else { clone = document.getElementById("tpl-" + box.id).content.firstElementChild.cloneNode(true); }
      $$("input, textarea", clone).forEach(function (el) { el.value = ""; });
      $$("select", clone).forEach(function (el) { el.selectedIndex = 0; });
      box.appendChild(clone); renumber();
      var n = $("input[name$='-number']", clone); if (n) n.value = rows.length + 1;
      dirty = true;
    });
    box.addEventListener("click", function (e) {
      if (!e.target.matches("[data-row-remove]")) return;
      var rows = $$("[data-row]", box);
      var row = e.target.closest("[data-row]");
      if (rows.length === 1 && prefix !== "stent") { $$("input, textarea", row).forEach(function (el) { el.value = ""; }); $$("select", row).forEach(function (el) { el.selectedIndex = 0; }); }
      else { row.remove(); renumber(); }
      dirty = true;
    });
  });

  // ---- Subir archivo al elegirlo -------------------------------------------
  $$("[data-autosubmit-file]").forEach(function (inp) { inp.addEventListener("change", function () { if (inp.files.length) inp.form.submit(); }); });

  // ---- Endoscopia: subir imágenes una por una (evita el límite de tamaño por envío y no pierde el informe)
  $$("[data-img-upload]").forEach(function (inp) {
    var form = inp.form, status = $("[data-img-status]");
    function say(msg, err) { if (status) { status.textContent = msg; status.classList.toggle("is-error", !!err); status.classList.remove("muted"); } }
    inp.addEventListener("change", function () {
      var files = Array.prototype.slice.call(inp.files || []);
      if (!files.length) return;
      var csrfTok = $("input[name=csrf_token]", form).value, patient = $("input[name=confirm_patient]", form).value;
      var ok = 0, errors = [];
      var proc = $("#proc-form");
      // 1) Guardar primero lo escrito en el informe para no perderlo al recargar
      var saveFirst = (proc && dirty) ? fetch(proc.action, { method: "POST", body: (function () { var fd = new FormData(proc); fd.set("then", "guardar"); return fd; })(),
                                                             credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error("No se pudo guardar el informe (error " + r.status + ")."); dirty = false; })
                                         : Promise.resolve();
      say("Guardando el informe…");
      saveFirst.then(function () {
        // 2) Subir cada imagen por separado
        return files.reduce(function (chain, f, i) {
          return chain.then(function () {
            say("Subiendo imagen " + (i + 1) + " de " + files.length + "…");
            var fd = new FormData();
            fd.append("csrf_token", csrfTok); fd.append("confirm_patient", patient); fd.append("imagen", f, f.name);
            return fetch(form.action, { method: "POST", body: fd, credentials: "same-origin",
                                        headers: { "X-Requested-With": "fetch", "X-CSRF-Token": csrfTok } })
              .then(function (r) {
                if (r.status === 413) { errors.push(f.name + ": supera el tamaño permitido (20 MB)."); return; }
                return r.json().then(function (d) {
                  if (d.agregadas) ok += d.agregadas;
                  (d.errores || []).forEach(function (e) { errors.push(e); });
                }, function () { errors.push(f.name + ": error " + r.status + " del servidor."); });
              })
              .catch(function () { errors.push(f.name + ": sin conexión con el programa."); });
          });
        }, Promise.resolve());
      }).then(function () {
        if (errors.length) {
          say(ok + " de " + files.length + " imagen(es) subidas. No se subieron: " + errors.join(" · "), true);
          if (ok) { var b = document.createElement("button"); b.type = "button"; b.className = "btn btn-sm"; b.textContent = "Ver las imágenes subidas";
                    b.addEventListener("click", function () { dirty = false; location.hash = "imagenes"; location.reload(); }); status.appendChild(document.createTextNode(" ")); status.appendChild(b); }
        } else {
          say(ok + " imagen(es) subidas. Actualizando…"); dirty = false; location.hash = "imagenes"; location.reload();
        }
      }).catch(function (e) { say(e.message, true); });
      inp.value = "";
    });
  });

  // ---- Anotaciones sobre imágenes (marcas numeradas; el original no se modifica)
  $$("[data-img-card]").forEach(function (card) {
    var area = $("[data-annot-area]", card), svg = $("[data-annot-svg]", card), input = $("[data-annot-input]", card);
    if (!area || !input) return;
    var marks = [];
    try { marks = JSON.parse(input.value || "[]"); } catch (e) { marks = []; }
    var NS = "http://www.w3.org/2000/svg";
    function draw() {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      marks.forEach(function (m, i) {
        var c = document.createElementNS(NS, "circle"); c.setAttribute("cx", m.x * 100); c.setAttribute("cy", m.y * 100); c.setAttribute("r", 3.2);
        c.setAttribute("class", "annot-dot"); svg.appendChild(c);
        var t = document.createElementNS(NS, "text"); t.setAttribute("x", m.x * 100); t.setAttribute("y", m.y * 100 + 1.4);
        t.setAttribute("class", "annot-num"); t.setAttribute("text-anchor", "middle"); t.textContent = String(i + 1); svg.appendChild(t);
      });
      input.value = JSON.stringify(marks);
    }
    draw();
    if (area.hasAttribute("data-annot-edit")) {
      area.addEventListener("click", function (e) {
        if (marks.length >= 12) return;
        var r = area.getBoundingClientRect();
        var text = window.prompt("Texto de la marca " + (marks.length + 1) + " (opcional):", "") ;
        if (text === null) return;
        marks.push({ x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height, text: text.slice(0, 60) });
        draw(); dirty = true;
      });
      var clr = $("[data-annot-clear]", card);
      if (clr) clr.addEventListener("click", function () { marks = []; draw(); dirty = true; });
    }
  });

  // ---- Esquema anatómico del informe (v0.19.0): clic en el dibujo = marca numerada --------
  var anat = $("[data-anat]");
  if (anat) {
    var anatBox = anat.closest(".anat-box"), anatList = $("[data-anat-list]", anatBox), anatTpl = $("[data-anat-tpl]", anatBox);
    var anatMarks = $(".anat-marks", anat), NS = "http://www.w3.org/2000/svg", anatSeq = $$("[data-anat-row]", anatList).length;
    var anatColor = {};
    $$(".anat-colors span", anatBox).forEach(function (sp) { anatColor[sp.getAttribute("data-k")] = sp.getAttribute("data-c"); });
    function anatDraw() {
      while (anatMarks.firstChild) anatMarks.removeChild(anatMarks.firstChild);
      $$("[data-anat-row]", anatList).forEach(function (row, i) {
        var x = parseFloat(row.getAttribute("data-x")), y = parseFloat(row.getAttribute("data-y"));
        var kind = $("[data-anat-kindsel]", row).value;
        var g = document.createElementNS(NS, "g"); g.setAttribute("class", "anat-mark");
        var c = document.createElementNS(NS, "circle");
        c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", 8); c.setAttribute("fill", anatColor[kind] || "#6d4c41");
        var t = document.createElementNS(NS, "text");
        t.setAttribute("x", x); t.setAttribute("y", y + 3.5); t.setAttribute("text-anchor", "middle"); t.textContent = i + 1;
        g.appendChild(c); g.appendChild(t); anatMarks.appendChild(g);
      });
    }
    function anatChanged(el) { el.dispatchEvent(new Event("input", { bubbles: true })); }
    anat.addEventListener("click", function (e) {
      var reg = e.target.closest("[data-seg]");
      if (!reg) return;
      var pt = anat.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      var p = pt.matrixTransform(anat.getScreenCTM().inverse());
      var kindIn = $('input[name="anat-kind"]:checked');
      var row = anatTpl.content.firstElementChild.cloneNode(true), n = anatSeq++;
      row.setAttribute("data-x", p.x.toFixed(1)); row.setAttribute("data-y", p.y.toFixed(1));
      $$("[data-f]", row).forEach(function (inp) { inp.name = "mark-" + n + "-" + inp.getAttribute("data-f"); });
      $('[data-f="x"]', row).value = p.x.toFixed(1); $('[data-f="y"]', row).value = p.y.toFixed(1);
      $('[data-f="seg"]', row).value = reg.getAttribute("data-seg");
      $(".anat-seg", row).textContent = reg.getAttribute("data-seg");
      $('[data-f="kind"]', row).value = kindIn ? kindIn.value : "lesion";
      anatList.appendChild(row); anatDraw(); anatChanged($('[data-f="x"]', row));
      $('[data-f="label"]', row).focus();
    });
    anatList.addEventListener("click", function (e) {
      if (!e.target.matches("[data-anat-del]")) return;
      var row = e.target.closest("[data-anat-row]"), prev = row.previousElementSibling || anatList;
      row.remove(); anatDraw(); anatChanged(prev);
    });
    anatList.addEventListener("change", function (e) { if (e.target.matches("[data-anat-kindsel]")) anatDraw(); });
  }

  // ---- PWA: registro del service worker (solo recursos estáticos) -----------
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  }
  // ---- Visor de imágenes en grande (v0.22): estudios agrupados del expediente ----
  (function () {
    var links = $$("a[data-gal]");
    if (!links.length) return;
    var ov = document.createElement("div");
    ov.className = "gal-overlay"; ov.hidden = true;
    ov.setAttribute("role", "dialog"); ov.setAttribute("aria-modal", "true"); ov.setAttribute("aria-label", "Imágenes del estudio");
    ov.innerHTML = '<div class="gal-top"><span class="gal-cap"></span><span><a class="gal-dl" href="#">Descargar</a> ' +
      '<button type="button" class="gal-btn gal-close" aria-label="Cerrar">✕</button></span></div>' +
      '<div class="gal-stage"><button type="button" class="gal-btn gal-prev" aria-label="Anterior">‹</button><img alt="">' +
      '<button type="button" class="gal-btn gal-next" aria-label="Siguiente">›</button></div><div class="gal-bottom"></div>';
    document.body.appendChild(ov);
    var img = $(".gal-stage img", ov), cap = $(".gal-cap", ov), strip = $(".gal-bottom", ov), dl = $(".gal-dl", ov);
    var items = [], cur = 0, last = null;
    function show(i) {
      cur = (i + items.length) % items.length;
      var a = items[cur];
      img.src = a.getAttribute("href"); img.alt = a.getAttribute("data-cap") || "";
      cap.textContent = (a.getAttribute("data-cap") || "") + "  ·  " + (cur + 1) + " de " + items.length;
      dl.href = a.getAttribute("href") + (a.getAttribute("href").indexOf("?") < 0 ? "?" : "&") + "descargar=1";
      $$("img", strip).forEach(function (t, k) { t.classList.toggle("on", k === cur); if (k === cur && t.scrollIntoView) t.scrollIntoView({block: "nearest", inline: "center"}); });
      var multi = items.length > 1;
      $(".gal-prev", ov).hidden = !multi; $(".gal-next", ov).hidden = !multi; strip.hidden = !multi;
    }
    function open(key, start) {
      items = links.filter(function (a) { return a.getAttribute("data-gal") === key; });
      if (!items.length) return;
      strip.innerHTML = "";
      items.forEach(function (a, k) {
        var t = document.createElement("img"); t.src = a.getAttribute("href"); t.alt = "Imagen " + (k + 1);
        t.addEventListener("click", function () { show(k); }); strip.appendChild(t);
      });
      last = document.activeElement;
      ov.hidden = false; document.body.style.overflow = "hidden";
      show(start || 0);
      $(".gal-close", ov).focus();
    }
    function close() { ov.hidden = true; img.removeAttribute("src"); document.body.style.overflow = ""; if (last && last.focus) last.focus(); }
    links.forEach(function (a) {
      a.addEventListener("click", function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey) return;
        e.preventDefault();
        var key = a.getAttribute("data-gal");
        open(key, links.filter(function (x) { return x.getAttribute("data-gal") === key; }).indexOf(a));
      });
    });
    $$("[data-gal-open]").forEach(function (b) { b.addEventListener("click", function () { open(b.getAttribute("data-gal-open"), 0); }); });
    $(".gal-close", ov).addEventListener("click", close);
    $(".gal-prev", ov).addEventListener("click", function () { show(cur - 1); });
    $(".gal-next", ov).addEventListener("click", function () { show(cur + 1); });
    ov.addEventListener("click", function (e) { if (e.target === ov || e.target.classList.contains("gal-stage")) close(); });
    document.addEventListener("keydown", function (e) {
      if (ov.hidden) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") show(cur - 1);
      else if (e.key === "ArrowRight") show(cur + 1);
    });
    var x0 = null;
    img.addEventListener("touchstart", function (e) { x0 = e.touches.length === 1 ? e.touches[0].clientX : null; }, {passive: true});
    img.addEventListener("touchend", function (e) {
      if (x0 === null || !e.changedTouches.length) return;
      var dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1));
    });
  })();
  // ---- Tipo de atención (v0.22): sala y cama solo si es de sala o emergencia ----
  $$("[data-care]").forEach(function (box) {
    var sel = $("[data-care-select]", box);
    if (!sel) return;
    var upd = function () {
      var on = sel.value === "sala" || sel.value === "emergencia";
      $$("[data-care-sala]", box).forEach(function (el) { el.hidden = !on; });
    };
    sel.addEventListener("change", upd); upd();
  });
  // Servicio (v0.28): «Otro» muestra el cuadro para escribirlo
  $$("[data-service-select]").forEach(function (sel) {
    var other = $("[data-service-other]");
    var upd = function () { if (other) { other.hidden = sel.value !== "otro"; if (sel.value !== "otro") { var i = $("input", other); if (i) i.value = ""; } } };
    sel.addEventListener("change", upd);
  });
  // ---- Botón «Copiar» de un texto fijo (v0.24: código de equipo) ----
  $$("[data-copy-text]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = b.getAttribute("data-copy-text"), old = b.textContent;
      var done = function () { b.textContent = "Copiado ✓"; setTimeout(function () { b.textContent = old; }, 1800); };
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(t).then(done, function () {}); }
      else { var ta = document.createElement("textarea"); ta.value = t; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done(); } catch (e) {} document.body.removeChild(ta); }
    });
  });
  // ---- Plantillas de hallazgos por patología (v0.26): menú en cada segmento ----
  (function () {
    var holder = $("#plantillas-data");
    if (!holder) return;
    var data = {};
    try { data = JSON.parse(holder.getAttribute("data-tpl") || "{}"); } catch (e) { return; }
    $$("select[data-tpl-target]").forEach(function (sel) {
      sel.addEventListener("change", function () {
        var t = data[sel.value], ta = document.getElementById(sel.getAttribute("data-tpl-target"));
        sel.value = "";
        if (!t || !ta) return;
        var cur = ta.value.trim();
        var nb = document.querySelector("[data-fill-normal='" + ta.id + "']");
        var normal = nb ? (nb.getAttribute("data-normal") || "").trim() : "";
        // campo vacío o con el texto normal → se reemplaza; si ya tiene otro texto → se agrega debajo
        ta.value = (!cur || cur === normal) ? t.b : ta.value.replace(/\s+$/, "") + "\n" + t.b;
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        if (t.c) {
          var cc = document.getElementById("conclusion");
          if (cc) {
            var cnb = document.querySelector("[data-fill-normal='conclusion']");
            var cn = cnb ? (cnb.getAttribute("data-normal") || "").trim() : "";
            var cv = cc.value.trim();
            var add = t.c.split("\n").filter(function (l) { return l.trim() && cv.indexOf(l.trim()) < 0; });
            if (add.length) {
              cc.value = (!cv || cv === cn) ? add.join("\n") : cc.value.replace(/\s+$/, "") + "\n" + add.join("\n");
              cc.dispatchEvent(new Event("input", { bubbles: true }));
            }
          }
        }
        dirty = true;
        ta.focus();
      });
    });
  })();
  // ---- Mover logos (v0.28): ▲ ▼ ◀ ▶ de 2 mm, con indicación de cuánto se movió ----
  (function () {
    var btns = $$("[data-nudge]");
    if (!btns.length) return;
    function label(k) {
      var el = $("[data-nudge-label='" + k + "']");
      if (!el) return;
      var dy = parseFloat($("#dy-" + k).value || "0"), dx = parseFloat($("#dx-" + k).value || "0"), parts = [];
      if (dy) parts.push(Math.abs(dy) + " mm " + (dy < 0 ? "arriba" : "abajo"));
      if (dx) parts.push(Math.abs(dx) + " mm a la " + (dx < 0 ? "izquierda" : "derecha"));
      el.textContent = parts.length ? parts.join(" · ") : "sin mover";
    }
    btns.forEach(function (b) {
      var k = b.getAttribute("data-nudge").replace(/^d[xy]-/, "");
      label(k);
      b.addEventListener("click", function () {
        var inp = document.getElementById(b.getAttribute("data-nudge"));
        var v = Math.max(-20, Math.min(20, (parseFloat(inp.value || "0") || 0) + parseFloat(b.getAttribute("data-step"))));
        inp.value = String(v); label(k);
      });
    });
  })();
})();
