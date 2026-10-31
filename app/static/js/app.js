// GastroMed Pro — comportamiento de la interfaz. Sin dependencias externas.
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
    f.addEventListener("submit", function (e) { if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault(); });
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
    $$("[data-copy-prior]").forEach(function (b) {
      b.addEventListener("click", function () {
        var key = b.getAttribute("data-copy-prior");
        var ta = $('textarea[name="' + key + '"]', noteForm);
        var txt = $("[data-prior-text]", b.parentNode).textContent;
        if (!ta) return;
        ta.value = (ta.value ? ta.value + "\n" : "") + "[Tomado de la nota del " + b.getAttribute("data-prior-date") + " — revisar] " + txt;
        ta.dispatchEvent(new Event("input", { bubbles: true })); ta.focus(); grow(ta);
      });
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

  // ---- PWA: registro del service worker (solo recursos estáticos) -----------
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  }
})();
