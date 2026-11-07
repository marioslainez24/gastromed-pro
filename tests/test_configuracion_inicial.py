"""Configuración inicial en el navegador (primer uso del .exe) y arranque del ejecutable en modo prueba."""
import re

from app import create_app
from app.config import Config


def _fresh_app(tmp_path):
    cfg = Config(ENV="pruebas", DATABASE_PATH=str(tmp_path / "db.sqlite3"), FILES_DIR=str(tmp_path / "a"), SECRET_KEY="s" * 40)
    return create_app(cfg)


def test_sin_usuarios_redirige_a_configuracion_y_crea_propietario(tmp_path):
    app = _fresh_app(tmp_path)
    c = app.test_client()
    r = c.get("/agenda/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/configuracion-inicial")
    html = c.get("/configuracion-inicial").get_data(as_text=True)
    tok = re.search(r'name="setup_csrf" value="([^"]+)"', html).group(1)
    bad = c.post("/configuracion-inicial", data={"setup_csrf": tok, "clinic": "C", "name": "Dr. X", "email": "dr@x.hn",
                                                  "password": "corta", "password2": "corta"})
    assert bad.status_code == 422
    html = bad.get_data(as_text=True)
    tok = re.search(r'name="setup_csrf" value="([^"]+)"', html).group(1)
    r = c.post("/configuracion-inicial", data={"setup_csrf": tok, "clinic": "Consultorio", "name": "Dr. Mario Lainez",
                                                "specialty": "Gastroenterología", "email": "dr@x.hn",
                                                "password": "Primer-Uso-2026", "password2": "Primer-Uso-2026"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/ingresar")
    # Ya no se puede volver a usar
    assert c.get("/configuracion-inicial").headers["Location"].endswith("/ingresar")
    page = c.get("/ingresar").get_data(as_text=True)
    tok = re.search(r'name="login_csrf" value="([^"]+)"', page).group(1)
    r = c.post("/ingresar", data={"login_csrf": tok, "email": "dr@x.hn", "password": "Primer-Uso-2026"})
    assert r.status_code == 302 and "/agenda/" in r.headers["Location"]


def test_configuracion_inicial_solo_desde_la_misma_pc(tmp_path):
    app = _fresh_app(tmp_path)
    c = app.test_client()
    r = c.get("/configuracion-inicial", environ_base={"REMOTE_ADDR": "192.168.1.50"})
    assert r.status_code == 403
    r = c.post("/configuracion-inicial", data={"clinic": "x"}, environ_base={"REMOTE_ADDR": "192.168.1.50"})
    assert r.status_code == 403


def test_primer_arranque_crea_claves_una_sola_vez(tmp_path, monkeypatch):
    import gastromed_exe
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "Desktop").mkdir()
    env1 = gastromed_exe.first_run_config(tmp_path / "GastroMed")
    content = env1.read_text(encoding="utf-8")
    assert "GASTROMED_ENV=consultorio" in content and "GASTROMED_DATA_KEY=" in content
    assert (tmp_path / "Desktop" / "NeuroMed - CLAVES (copiar a USB y borrar de aqui).txt").exists()
    env2 = gastromed_exe.first_run_config(tmp_path / "GastroMed")
    assert env2.read_text(encoding="utf-8") == content   # nunca reemplaza claves existentes
