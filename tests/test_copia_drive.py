"""v0.14.0: copia de los respaldos cifrados en la carpeta de Google Drive (apagada por defecto, se activa con un botón en Ajustes)."""
from pathlib import Path

from cryptography.fernet import Fernet

from app import APP_VERSION
from app.backup import OFFSITE_SUBDIR, run_automatic
from app.crypto import load_data_key
from conftest import create_patient, csrf, login


def test_apagada_por_defecto_activar_copiar_conservar_y_desactivar(env, tmp_path):
    cfg = env["cfg"]
    cfg.BACKUP_DIR = str(tmp_path / "respaldos")
    drive = tmp_path / "G" / "Mi unidad"
    drive.mkdir(parents=True)
    med = login(env["app"], "propietario")
    tok = csrf(med)
    create_patient(med, first_names="Drive", last_names="Ficticio")
    html = med.get("/ajustes/respaldos").get_data(as_text=True)
    assert "Desactivada" in html and "Activar copia en Google Drive" in html and "la suba a Drive" in html
    key = Fernet.generate_key()
    # apagada: el respaldo diario NO copia nada a Drive
    ok, msgs = run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)
    assert ok and not (drive / OFFSITE_SUBDIR).exists()
    # carpeta inválida
    med.post("/ajustes/respaldos/drive", data={"csrf_token": tok, "action": "activar", "folder_other": str(tmp_path / "no-existe")})
    assert env["db"].execute("SELECT offsite_enabled FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0] == 0
    # activar
    r = med.post("/ajustes/respaldos/drive", data={"csrf_token": tok, "action": "activar", "folder_other": str(drive), "keep": "3"})
    assert r.status_code == 302
    st = env["db"].execute("SELECT offsite_enabled, offsite_dir, offsite_keep FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()
    assert st["offsite_enabled"] == 1 and st["offsite_dir"] == str(drive) and st["offsite_keep"] == 3
    assert "ACTIVADA" in med.get("/ajustes/respaldos").get_data(as_text=True)
    # copiar ahora: copia el último respaldo local, cifrado
    med.post("/ajustes/respaldos/drive", data={"csrf_token": tok, "action": "copiar"})
    copies = sorted((drive / OFFSITE_SUBDIR).glob("neuromed-*.gmbak"))
    assert len(copies) == 1 and b"Drive" not in copies[0].read_bytes() and b"SQLite format" not in copies[0].read_bytes()
    # el respaldo diario copia y se conservan solo los últimos 3
    import time
    for _ in range(4):
        time.sleep(1.05)
        assert run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)[0]
    copies = sorted((drive / OFFSITE_SUBDIR).glob("neuromed-*.gmbak"))
    assert len(copies) == 3 and not list((drive / OFFSITE_SUBDIR).glob("*.parcial"))
    last = env["db"].execute("SELECT offsite_last_msg FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0]
    assert last.startswith("OK: copia")
    # si Drive no está disponible, avisa sin romper el respaldo local
    drive.rename(tmp_path / "G" / "desconectado")
    ok, msgs = run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)
    assert ok and any("ALERTA: no se pudo copiar a Google Drive" in m for m in msgs)
    (tmp_path / "G" / "desconectado").rename(drive)
    # desactivar: no borra lo que ya está en Drive
    med.post("/ajustes/respaldos/drive", data={"csrf_token": tok, "action": "desactivar"})
    n = len(list((drive / OFFSITE_SUBDIR).glob("*.gmbak")))
    time.sleep(1.05)
    run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)
    assert len(list((drive / OFFSITE_SUBDIR).glob("*.gmbak"))) == n == 3


def test_solo_el_propietario_y_desde_la_pc(env, tmp_path):
    drive = tmp_path / "Mi unidad"
    drive.mkdir()
    assert login(env["app"], "medico").get("/ajustes/respaldos").status_code == 403
    med = login(env["app"], "propietario")
    tok = csrf(med)
    r = med.post("/ajustes/respaldos/drive", data={"csrf_token": tok, "action": "activar", "folder_other": str(drive)},
                 environ_base={"REMOTE_ADDR": "192.168.1.50"})
    assert r.status_code in (302, 403)
    assert env["db"].execute("SELECT offsite_enabled FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0] == 0
    assert "solo desde la PC" in med.get("/ajustes/respaldos", environ_base={"REMOTE_ADDR": "192.168.1.50"}).get_data(as_text=True)
