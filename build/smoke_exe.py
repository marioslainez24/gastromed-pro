"""Prueba de humo del ejecutable ya construido (se corre en Windows real dentro de GitHub Actions).

  python build/smoke_exe.py dist/GastroMedPro.exe

Arranca el .exe con una carpeta de datos temporal y recorre el flujo principal:
configuración inicial → ingreso → paciente → cita → nota → receta PDF → respaldo automático.
"""
import http.cookiejar
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PORT = 8765
B = f"http://127.0.0.1:{PORT}"


def main(exe):
    root = Path(tempfile.mkdtemp()) / "GastroMed"
    env = dict(os.environ, GASTROMED_ROOT=str(root), GASTROMED_PORT=str(PORT), GASTROMED_HOST="127.0.0.1", GASTROMED_HTTPS_PORT="8766",
               USERPROFILE=str(root.parent))
    (root.parent / "Desktop").mkdir(parents=True, exist_ok=True)
    log = open(root.parent / "exe.log", "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen([exe, "--sin-navegador"], env=env, stdout=log, stderr=subprocess.STDOUT)
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def get(path):
        return op.open(B + path, timeout=30)

    def post(path, data):
        return op.open(B + path, urllib.parse.urlencode(data).encode(), timeout=60)

    try:
        for _ in range(90):
            try:
                r = get("/")
                break
            except (urllib.error.URLError, ConnectionError):
                if proc.poll() is not None:
                    raise SystemExit("El ejecutable terminó al iniciar")
                time.sleep(1)
        else:
            raise SystemExit("El ejecutable no respondió en 90 s")
        assert r.url.endswith("/configuracion-inicial"), r.url
        html = r.read().decode()
        tok = re.search(r'name="setup_csrf" value="([^"]+)"', html).group(1)
        r = post("/configuracion-inicial", {"setup_csrf": tok, "clinic": "Consultorio prueba", "name": "Dr. Prueba",
                                            "specialty": "Gastroenterología", "email": "dr@prueba.local",
                                            "password": "Prueba-Exe-2026", "password2": "Prueba-Exe-2026"})
        assert r.url.endswith("/ingresar"), r.url
        html = r.read().decode()
        tok = re.search(r'name="login_csrf" value="([^"]+)"', html).group(1)
        r = post("/ingresar", {"login_csrf": tok, "email": "dr@prueba.local", "password": "Prueba-Exe-2026"})
        assert "/agenda/" in r.url, r.url
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.read().decode()).group(1)
        r = post("/pacientes/nuevo", {"csrf_token": csrf, "first_names": "Ana", "last_names": "Ficticia Pérez",
                                      "birth_date": "1980-01-01", "sex": "femenino", "document_type": "sin_documento"})
        pid = r.url.rstrip("/").split("/")[-1]
        assert re.fullmatch(r"[0-9a-f]{32}", pid), r.url
        r = post("/notas/nueva", {"csrf_token": csrf, "patient_id": pid, "kind": "primera", "template": "soap"})
        nid = r.url.split("/")[-1].split("?")[0]
        hx = post(f"/notas/{nid}/historia", {"csrf_token": csrf, "hx-motivo": "dolor_abdominal", "hx-dolor_abdominal-caracter": "colico"}).read().decode()
        assert "consulta por dolor abdominal" in hx and "colico" not in hx, "Asistente de historia"
        ex = post(f"/notas/{nid}/exploracion", {"csrf_token": csrf, "abdomen-normal": "1"}).read().decode()
        assert "Abdomen plano" in ex, "Exploración con clics"
        req = urllib.request.Request(f"{B}/notas/{nid}/guardar", data=b'{"version": 1, "motivo": "Dispepsia"}',
                                     headers={"Content-Type": "application/json", "X-CSRF-Token": csrf})
        assert op.open(req, timeout=30).status == 200
        r = post("/recetas/nueva", {"csrf_token": csrf, "patient_id": pid, "note_id": nid, "ack_allergies": "1",
                                    "item-0-active_ingredient": "Omeprazol", "item-0-dose": "20", "item-0-dose_unit": "mg",
                                    "item-0-route": "oral", "item-0-frequency": "cada 24 h", "item-0-duration": "8 semanas",
                                    "item-0-quantity": "56 cápsulas"})
        rx = r.url.split("/")[-1]
        pdf = get(f"/recetas/{rx}/pdf").read()
        assert pdf.startswith(b"%PDF-") and len(pdf) > 1500, "PDF inválido"
        # Fase 3: informe de endoscopia con imagen, finalización y PDF con fotografía (prueba Pillow dentro del .exe)
        r = post(f"/pacientes/{pid}/procedimientos/nuevo", {"csrf_token": csrf, "kind": "eda"})
        proc_id = r.url.split("/")[-1]
        import io as _io, uuid as _uuid
        jpg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9")
        bnd = "----gm" + _uuid.uuid4().hex
        body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n{csrf}\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"confirm_patient\"\r\n\r\n{pid}\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"imagen\"; filename=\"a.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode() + jpg + f"\r\n--{bnd}--\r\n".encode()
        req = urllib.request.Request(f"{B}/procedimientos/{proc_id}/imagenes", data=body, headers={"Content-Type": f"multipart/form-data; boundary={bnd}",
                                                                                              "X-Requested-With": "fetch"})
        assert op.open(req, timeout=60).status == 200
        # BMP de una torre de endoscopia (2x2 píxeles): debe convertirse a JPG dentro del .exe
        bmp = bytes.fromhex("424d46000000000000003600000028000000020000000200000001001800000000001000000000000000000000000000"
                            "00000000000000ff0000ff00000000ff00ffffff0000")
        body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n{csrf}\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"confirm_patient\"\r\n\r\n{pid}\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"imagen\"; filename=\"torre.bmp\"\r\nContent-Type: image/bmp\r\n\r\n").encode() + bmp + f"\r\n--{bnd}--\r\n".encode()
        req = urllib.request.Request(f"{B}/procedimientos/{proc_id}/imagenes", data=body, headers={"Content-Type": f"multipart/form-data; boundary={bnd}",
                                                                                              "X-Requested-With": "fetch"})
        assert op.open(req, timeout=60).status == 200, "BMP de la torre no se convirtió"
        html = get(f"/procedimientos/{proc_id}").read().decode()
        img_id = re.search(r'/procedimientos/' + proc_id + r'/imagenes/([0-9a-f]{32})', html).group(1)
        ver = re.search(r'name="version" value="(\d+)"', html).group(1)
        post(f"/procedimientos/{proc_id}/imagenes/{img_id}", {"csrf_token": csrf, "in_report": "1", "annotations": '[{"x":0.5,"y":0.5,"text":"lesión"}]'})
        post(f"/procedimientos/{proc_id}/guardar", {"csrf_token": csrf, "version": ver, "performed_on": "2026-10-01", "indication_category": "diagnostica",
                                                 "indication": "Dispepsia", "consent_obtained": "1", "sedation_type": "topica", "extent": "segunda_porcion",
                                                 "conclusion": "Estudio normal.", "zline": "coincide",
                                                 "nar-esofago": "Normal.", "nar-ueg": "Normal.", "nar-estomago": "Normal.", "nar-duodeno": "Normal."})
        html = get(f"/procedimientos/{proc_id}").read().decode()
        ver = re.search(r'name="version" value="(\d+)"', html).group(1)
        post(f"/procedimientos/{proc_id}/finalizar", {"csrf_token": csrf, "version": ver})
        assert "Finalizado" in get(f"/procedimientos/{proc_id}").read().decode(), "El informe de endoscopia no se finalizó"
        assert get("/endoscopia/textos-normales").status == 200
        pdf = get(f"/procedimientos/{proc_id}/pdf").read()
        assert pdf.startswith(b"%PDF-") and b"/Image" in pdf, "PDF de endoscopia sin imagen"
        # Archivos del programa con la versión en la dirección (evita que el navegador use una copia vieja)
        page = get("/agenda/").read().decode()
        js = re.search(r'src="(/static/v[\d.]+/js/app\.js)"', page).group(1)
        assert get(js).read().startswith(b"/*") or len(get(js).read()) > 1000, "app.js versionado no responde"
        # Solicitud de laboratorio tipo hoja (perfil + prueba suelta) y su PDF
        form = get(f"/ordenes/nueva?patient_id={pid}&order_type=laboratorio").read().decode()
        assert "Perfil Pre-operatorio" in form and "Biología molecular" in form, "Hoja de laboratorio incompleta"
        resp = re.search(r'name="responsible_id"><option value="([0-9a-f]{32})"', form).group(1)
        r = post("/ordenes/nueva", {"csrf_token": csrf, "patient_id": pid, "order_type": "laboratorio", "perfil": "perfil-hepatico",
                                    "lab": "calprotectina-fecal", "priority": "rutina", "responsible_id": resp})
        oid = re.search(r"/ordenes/([0-9a-f]{32})", r.geturl()).group(1)
        assert get(f"/ordenes/{oid}/pdf").read().startswith(b"%PDF-"), "PDF de la orden de laboratorio"
        # Frases, documentos clínicos y su PDF
        post("/ajustes/frases/ejemplos", {"csrf_token": csrf})
        assert "Abdomen normal" in get("/ajustes/frases").read().decode(), "Frases de ejemplo"
        r = post(f"/pacientes/{pid}/documentos/nuevo", {"csrf_token": csrf, "kind": "incapacidad", "days": "2", "step": "emitir",
                                                        "body": "Constancia de prueba.", "final_title": "CONSTANCIA DE INCAPACIDAD MEDICA"})
        did = re.search(r"/documentos/([0-9a-f]{32})", r.geturl()).group(1)
        assert get(f"/documentos/{did}/pdf").read().startswith(b"%PDF-"), "PDF del documento clínico"
        # v0.14: imprimir todo (pypdf dentro del .exe), etiquetas, hojas, recomendaciones y resumen del paciente
        allpdf = get(f"/notas/{nid}/imprimir-todo").read()
        assert allpdf.startswith(b"%PDF-"), "Imprimir todo"
        assert get(f"/procedimientos/{proc_id}/etiquetas").read().startswith(b"%PDF-"), "Etiquetas de frascos"
        for path in ("/endoscopia/hojas", "/endoscopia/recomendaciones"):
            assert get(path).status == 200, path
        assert "Resumen" in get(f"/pacientes/{pid}").read().decode(), "Resumen del paciente"
        for path in ("/ajustes/recordatorios", "/ajustes/horarios", "/agenda/recordatorios"):
            assert get(path).status == 200, path
        # Conexión cifrada para el celular (certificado propio)
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        r = urllib.request.urlopen("https://127.0.0.1:8766/ingresar", context=ctx, timeout=30)
        assert r.status == 200 and "GastroMed" in r.read().decode(), "https no responde"
        assert (root / "datos" / "https-cert.pem").exists()
        print("Flujo principal, endoscopia, recordatorios y https correctos. Esperando respaldo automático…", flush=True)
        for _ in range(60):
            lg = root / "datos" / "respaldo.log"
            if list((root / "respaldos").glob("gastromed-*.gmbak")) and lg.exists() and "OK:" in lg.read_text(encoding="utf-8", errors="replace"):
                break
            time.sleep(2)
        backups = list((root / "respaldos").glob("gastromed-*.gmbak"))
        assert backups, "No se creó el respaldo automático"
        assert "OK:" in (root / "datos" / "respaldo.log").read_text(encoding="utf-8")
        assert (root.parent / "Desktop" / "GastroMed - CLAVES (copiar a USB y borrar de aqui).txt").exists()
        print("PRUEBA DEL EJECUTABLE: CORRECTA")
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        print("---- salida del ejecutable ----")
        tail = (root.parent / "exe.log").read_text(encoding="utf-8", errors="replace")[-4000:]
        print(tail)
        global EXE_TAIL
        EXE_TAIL = tail


EXE_TAIL = ""

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    try:
        main(sys.argv[1])
    except BaseException:
        import traceback
        msg = traceback.format_exc()[-2500:] + "\n---- exe ----\n" + EXE_TAIL[-2500:]
        # Anotación visible por la API de GitHub (los registros no se pueden descargar desde el entorno de desarrollo).
        print("::error title=Prueba del ejecutable::" + msg.replace("%", "%25").replace("\r", "").replace("\n", "%0A"), flush=True)
        raise
