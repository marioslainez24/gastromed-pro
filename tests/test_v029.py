"""v0.29.0: pantalla de espacio en disco y cuántas copias de respaldo se guardan."""
import io
import time
from pathlib import Path

from cryptography.fernet import Fernet

from app import APP_VERSION
from app.backup import backup_keep, run_automatic
from app.crypto import load_data_key
from conftest import create_patient, csrf, login
from tests.test_expediente_archivos import JPG, PDF_OK, upload


def test_pantalla_de_espacio(env, tmp_path):
    cfg = env["cfg"]
    cfg.BACKUP_DIR = str(tmp_path / "respaldos")
    med = login(env["app"], "propietario")
    pid = create_patient(med, first_names="Pesado", last_names="Ficticio")
    create_patient(med, first_names="Liviano", last_names="Ficticio", document_number="0801-1990-11111")
    upload(med, pid, JPG + b"x" * 50000, name="a.jpg", category="endoscopia", title="Endoscopia · imagen 1")
    upload(med, pid, PDF_OK)
    html = med.get("/ajustes/espacio").get_data(as_text=True)
    assert "Cuánto ocupa el programa en esta PC" in html and "Expedientes que más ocupan" in html
    assert "Pesado Ficticio" in html and "Liviano Ficticio" not in html          # sin fotos no aparece en la lista
    assert "Espacio libre en el disco" in html and "30 copias" in html and 'value="30" checked' in html
    assert 'style="' not in html.split("<main")[1] if "<main" in html else True     # respeta la política de seguridad (sin estilos en línea)
    assert login(env["app"], "recepcion").get("/ajustes/espacio").status_code == 403


def test_elegir_cuantas_copias_y_se_respeta(env, tmp_path):
    cfg = env["cfg"]
    cfg.BACKUP_DIR = str(tmp_path / "respaldos")
    med = login(env["app"], "propietario")
    tok = csrf(med)
    create_patient(med)
    assert backup_keep(cfg.DATABASE_PATH, 30) == 30
    assert med.post("/ajustes/espacio", data={"csrf_token": tok, "keep": "7"}).status_code == 302
    assert backup_keep(cfg.DATABASE_PATH, 30) == 7
    assert med.post("/ajustes/espacio", data={"csrf_token": tok, "keep": "8"}).status_code == 400
    key = Fernet.generate_key()
    # simular 9 respaldos viejos y correr el automático: quedan 7
    d = Path(cfg.BACKUP_DIR)
    d.mkdir(parents=True, exist_ok=True)
    for i in range(9):
        (d / f"neuromed-2026010{i}-000000.gmbak").write_bytes(b"viejo")
    ok, msgs = run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)
    assert ok and len(list(d.glob("neuromed-*.gmbak"))) == 7
    assert any("se conservan los últimos 7" in m for m in msgs)
    assert env["db"].execute("SELECT COUNT(*) FROM audit_log WHERE action = 'respaldos_copias_cambiadas'").fetchone()[0] == 1
