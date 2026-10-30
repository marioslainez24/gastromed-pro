"""Respaldo cifrado → restauración en otra ubicación → la aplicación funciona con los datos y adjuntos restaurados."""
import io
import zipfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

from conftest import create_patient, csrf, login
from test_expediente_archivos import PDF_OK, JPG, upload
from app import APP_VERSION, create_app
from app.backup import create_backup, export_all, verify_and_restore
from app.config import Config
from app.crypto import load_data_key


def _populate(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med, first_names="Respaldo", last_names="Ficticio")
    tok = csrf(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}).headers["Location"].split("/")[-1]
    med.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "Texto que debe sobrevivir"}, headers={"X-CSRF-Token": tok})
    med.post(f"/notas/{nid}/finalizar", data={"csrf_token": tok, "version": 2})
    upload(med, pid, PDF_OK)
    upload(med, pid, JPG, name="foto.jpg", title="Foto")
    return pid, nid


def test_respaldo_y_restauracion_completa(env, tmp_path):
    pid, nid = _populate(env)
    cfg = env["cfg"]
    key = Fernet.generate_key()
    bk = create_backup(cfg.DATABASE_PATH, cfg.FILES_DIR, str(tmp_path / "respaldos"), key, APP_VERSION)
    raw = bk.read_bytes()
    assert b"Respaldo" not in raw and b"SQLite format" not in raw and b"%PDF" not in raw  # cifrado
    data_key = load_data_key(cfg)
    report = verify_and_restore(str(bk), key, str(tmp_path / "restaurado"), data_key)
    assert report["ok"], report["errores"]
    assert report["conteos"]["patients"] == 1 and report["conteos"]["files"] == 2 and report["adjuntos_verificados"] == 2
    # Levantar la aplicación sobre los datos restaurados y comprobar registros y adjuntos
    rcfg = Config(ENV="pruebas", DATABASE_PATH=str(tmp_path / "restaurado" / "gastromed.sqlite3"),
                  FILES_DIR=str(tmp_path / "restaurado" / "archivos"), SECRET_KEY="z" * 40, DATA_KEY=data_key)
    rapp = create_app(rcfg)
    c = login(rapp, "propietario")
    assert "Texto que debe sobrevivir" in c.get(f"/notas/{nid}").get_data(as_text=True)
    fid = env["db"].execute("SELECT id FROM files WHERE mime = 'application/pdf'").fetchone()["id"]
    assert c.get(f"/archivos/{fid}").data == PDF_OK


def test_respaldo_alterado_o_clave_incorrecta(env, tmp_path):
    _populate(env)
    cfg = env["cfg"]
    key = Fernet.generate_key()
    bk = create_backup(cfg.DATABASE_PATH, cfg.FILES_DIR, str(tmp_path), key, APP_VERSION)
    with pytest.raises(InvalidToken):
        verify_and_restore(str(bk), Fernet.generate_key(), str(tmp_path / "a"))
    b = bytearray(bk.read_bytes())
    b[len(b) // 2] ^= 0x01
    bk.write_bytes(bytes(b))
    with pytest.raises(InvalidToken):
        verify_and_restore(str(bk), key, str(tmp_path / "b"))


def test_no_restaura_sobre_datos_existentes(env, tmp_path):
    cfg = env["cfg"]
    key = Fernet.generate_key()
    bk = create_backup(cfg.DATABASE_PATH, cfg.FILES_DIR, str(tmp_path), key, APP_VERSION)
    (tmp_path / "ocupado").mkdir()
    (tmp_path / "ocupado" / "x.txt").write_text("datos")
    with pytest.raises(RuntimeError):
        verify_and_restore(str(bk), key, str(tmp_path / "ocupado"))


def test_exportacion_completa(env, tmp_path):
    pid, nid = _populate(env)
    cfg = env["cfg"]
    out = export_all(cfg.DATABASE_PATH, cfg.FILES_DIR, load_data_key(cfg), str(tmp_path / "exportacion.zip"))
    z = zipfile.ZipFile(out)
    names = z.namelist()
    assert "datos/patients.csv" in names and "datos/clinical_notes.csv" in names and "LEAME.txt" in names
    assert "Texto que debe sobrevivir" in z.read("datos/clinical_notes.csv").decode("utf-8-sig")
    pdfs = [n for n in names if n.startswith("adjuntos/GM-000001/") and n.endswith(".pdf")]
    assert len(pdfs) == 1 and z.read(pdfs[0]) == PDF_OK
    users_csv = z.read("datos/users.csv").decode("utf-8-sig")
    assert "password_hash" not in users_csv and "mfa_secret" not in users_csv
