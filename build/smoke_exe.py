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
    env = dict(os.environ, GASTROMED_ROOT=str(root), GASTROMED_PORT=str(PORT), GASTROMED_HOST="127.0.0.1",
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
        req = urllib.request.Request(f"{B}/notas/{nid}/guardar", data=b'{"version": 1, "motivo": "Dispepsia"}',
                                     headers={"Content-Type": "application/json", "X-CSRF-Token": csrf})
        assert op.open(req, timeout=30).status == 200
        r = post("/recetas/nueva", {"csrf_token": csrf, "patient_id": pid, "ack_allergies": "1",
                                    "item-0-active_ingredient": "Omeprazol", "item-0-dose": "20", "item-0-dose_unit": "mg",
                                    "item-0-route": "oral", "item-0-frequency": "cada 24 h", "item-0-duration": "8 semanas",
                                    "item-0-quantity": "56 cápsulas"})
        rx = r.url.split("/")[-1]
        pdf = get(f"/recetas/{rx}/pdf").read()
        assert pdf.startswith(b"%PDF-") and len(pdf) > 1500, "PDF inválido"
        print("Flujo principal correcto. Esperando respaldo automático…", flush=True)
        for _ in range(60):
            if list((root / "respaldos").glob("gastromed-*.gmbak")):
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
        print((root.parent / "exe.log").read_text(encoding="utf-8", errors="replace")[-4000:])


if __name__ == "__main__":
    main(sys.argv[1])
