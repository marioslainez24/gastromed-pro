// NeuroMed Pro — captura de imágenes desde capturadora de video (UVC) o señal de prueba.
// Reglas: confirmar paciente antes de encender la cámara; detener la cámara al salir; nada se guarda en el navegador.
(function () {
  "use strict";
  var root = document.querySelector("[data-capture]");
  if (!root) return;
  var $ = function (s) { return root.querySelector(s); };
  var video = $("[data-video]"), canvasTest = $("[data-test-canvas]"), status = $("[data-status]");
  var devSel = $("[data-device]"), resSel = $("[data-resolution]"), startBtn = $("[data-start]"), stopBtn = $("[data-stop]");
  var shotBtn = $("[data-shot]"), confirm = $("[data-confirm-patient]"), thumbs = $("[data-thumbs]"), countEl = $("[data-count]");
  var stream = null, testTimer = null, count = 0, busy = false;

  function setStatus(t, err) { status.textContent = t; status.classList.toggle("warn-text", !!err); }

  function stopAll() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    if (testTimer) { cancelAnimationFrame(testTimer); testTimer = null; }
    video.srcObject = null; video.hidden = false; canvasTest.hidden = true;
    shotBtn.disabled = true; stopBtn.disabled = true;
  }
  window.addEventListener("pagehide", stopAll);
  window.addEventListener("beforeunload", stopAll);
  document.addEventListener("visibilitychange", function () { if (document.hidden && stream) { stopAll(); setStatus("Cámara detenida al salir de la página."); } });

  confirm.addEventListener("change", function () {
    var ok = confirm.checked;
    [devSel, resSel, startBtn].forEach(function (el) { el.disabled = !ok; });
    if (!ok) { stopAll(); setStatus("Confirme el paciente para habilitar la cámara."); return; }
    setStatus("Elija el dispositivo y pulse «Iniciar video».");
    listDevices();
  });

  function listDevices() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
      setStatus("Este navegador no permite usar cámaras aquí. Use Chrome o Edge en esta PC (http://localhost). Puede practicar con la señal de prueba.", true);
      return;
    }
    navigator.mediaDevices.enumerateDevices().then(function (devs) {
      var cams = devs.filter(function (d) { return d.kind === "videoinput"; });
      while (devSel.options.length > 1) devSel.remove(1);
      cams.forEach(function (d, i) {
        var o = document.createElement("option"); o.value = d.deviceId; o.textContent = d.label || ("Cámara / capturadora " + (i + 1));
        devSel.appendChild(o);
      });
      if (!cams.length) setStatus("No se detectó ninguna capturadora. Puede usar la señal de prueba.");
    }).catch(function () {});
  }

  function startTest() {
    var ctx = canvasTest.getContext("2d"), t0 = performance.now();
    video.hidden = true; canvasTest.hidden = false;
    (function draw(now) {
      var t = (now - t0) / 1000, w = canvasTest.width, h = canvasTest.height;
      var g = ctx.createRadialGradient(w / 2, h / 2, 40, w / 2, h / 2, w / 1.6);
      g.addColorStop(0, "#f2b8a0"); g.addColorStop(0.55, "#c86b5a"); g.addColorStop(1, "#3a1410");
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = "rgba(255,230,220,.35)"; ctx.lineWidth = 6;
      for (var i = 0; i < 5; i++) { ctx.beginPath(); ctx.ellipse(w / 2 + Math.sin(t + i) * 30, h / 2, 120 + i * 90, 70 + i * 55, 0, 0, Math.PI * 2); ctx.stroke(); }
      ctx.fillStyle = "rgba(0,0,0,.6)"; ctx.fillRect(0, h - 48, w, 48);
      ctx.fillStyle = "#fff"; ctx.font = "26px sans-serif";
      ctx.fillText("SEÑAL DE PRUEBA · " + new Date().toLocaleTimeString("es-HN"), 24, h - 16);
      testTimer = requestAnimationFrame(draw);
    })(t0);
    shotBtn.disabled = false; stopBtn.disabled = false;
    setStatus("Señal de prueba activa. Las capturas se guardan como imágenes reales del procedimiento: elimínelas del informe si solo está practicando.");
  }

  startBtn.addEventListener("click", function () {
    if (!confirm.checked) return;
    stopAll();
    if (!devSel.value) { startTest(); return; }
    var wh = resSel.value.split("x");
    navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: devSel.value }, width: { ideal: +wh[0] }, height: { ideal: +wh[1] } }, audio: false })
      .then(function (s) {
        stream = s; video.srcObject = s; video.play();
        var st = s.getVideoTracks()[0].getSettings();
        setStatus("Video activo: " + (st.width || "?") + " × " + (st.height || "?") + ". Pulse «Capturar» o la barra espaciadora.");
        shotBtn.disabled = false; stopBtn.disabled = false;
      })
      .catch(function (e) {
        setStatus("No se pudo abrir la capturadora (" + (e.name || "error") + "). Revise que esté conectada, que otra aplicación no la esté usando y que dio permiso al navegador.", true);
      });
  });
  stopBtn.addEventListener("click", function () { stopAll(); setStatus("Cámara detenida."); });

  function grab() {
    if (shotBtn.disabled || busy) return;
    var src = canvasTest.hidden ? video : canvasTest;
    var w = canvasTest.hidden ? video.videoWidth : canvasTest.width, h = canvasTest.hidden ? video.videoHeight : canvasTest.height;
    if (!w || !h) return;
    var c = document.createElement("canvas"); c.width = w; c.height = h;
    c.getContext("2d").drawImage(src, 0, 0, w, h);
    busy = true;
    c.toBlob(function (blob) {
      var fd = new FormData();
      fd.append("csrf_token", root.getAttribute("data-csrf"));
      fd.append("confirm_patient", root.getAttribute("data-patient"));
      fd.append("source", "captura");
      fd.append("imagen", blob, "captura.jpg");
      fetch(root.getAttribute("data-upload"), { method: "POST", body: fd, credentials: "same-origin",
                                                headers: { "X-Requested-With": "fetch", "X-CSRF-Token": root.getAttribute("data-csrf") } })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error((res.d.errores || []).join(" ") || "error");
          count += 1; countEl.textContent = count + " imagen(es) capturadas y guardadas";
          var im = document.createElement("img"); im.src = c.toDataURL("image/jpeg", 0.5); im.alt = "Captura " + count; thumbs.prepend(im);
        })
        .catch(function (e) { setStatus("No se guardó la imagen: " + e.message, true); })
        .then(function () { busy = false; });
    }, "image/jpeg", 0.92);
  }
  shotBtn.addEventListener("click", grab);
  document.addEventListener("keydown", function (e) {
    if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "SELECT") { e.preventDefault(); grab(); }
  });
})();
