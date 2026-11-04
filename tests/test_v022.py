"""v0.22.0: versión para Mac (carpeta de Google Drive de Mac para los respaldos y lanzador)."""
import sys

from app import backup


def test_drive_de_mac_se_detecta(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    mi = tmp_path / "Library" / "CloudStorage" / "GoogleDrive-doctor@example.com" / "Mi unidad"
    mi.mkdir(parents=True)
    (tmp_path / "Library" / "CloudStorage" / "OneDrive-Personal").mkdir()     # no es Google Drive: se ignora
    assert str(mi) in backup.drive_candidates()


def test_sin_drive_no_inventa_carpetas(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert [p for p in backup.drive_candidates() if p.startswith(str(tmp_path))] == []


def test_lanzador_usa_carpeta_del_usuario_fuera_de_windows(tmp_path, monkeypatch):
    import gastromed_exe
    monkeypatch.delenv("GASTROMED_ROOT", raising=False)
    if sys.platform != "win32":
        assert str(gastromed_exe.data_root()).endswith("GastroMed")


def test_datos_copiados_de_windows_se_adaptan_sin_tocar_claves(tmp_path):
    import gastromed_exe as G
    datos, resp = tmp_path / "datos", tmp_path / "respaldos"
    datos.mkdir()
    env = datos / "gastromed.env"
    env.write_text("GASTROMED_ENV=consultorio\nGASTROMED_DATA_KEY=abc=\nGASTROMED_DATABASE_PATH=C:\\GastroMed\\datos\\gastromed.sqlite3\n"
                   "GASTROMED_FILES_DIR=C:\\GastroMed\\datos\\archivos\nGASTROMED_BACKUP_DIR=C:\\GastroMed\\respaldos\n"
                   "GASTROMED_BACKUP_COPY_DIR=G:\\Mi unidad\\GastroMed\n", encoding="utf-8")
    if sys.platform == "win32":
        assert G.adapt_paths(env, datos, resp) is False
        return
    assert G.adapt_paths(env, datos, resp) is True
    txt = env.read_text(encoding="utf-8")
    assert "GASTROMED_DATA_KEY=abc=" in txt and "C:\\" not in txt and "G:\\" not in txt
    assert f"GASTROMED_DATABASE_PATH={datos / 'gastromed.sqlite3'}" in txt and "GASTROMED_BACKUP_COPY_DIR=\n" in txt
    assert G.adapt_paths(env, datos, resp) is False          # la segunda vez ya no hay nada que corregir


def test_datos_propios_no_se_tocan(tmp_path):
    import gastromed_exe as G
    datos = tmp_path / "datos"
    datos.mkdir()
    env = datos / "gastromed.env"
    env.write_text(f"GASTROMED_DATABASE_PATH={datos / 'gastromed.sqlite3'}\n", encoding="utf-8")
    assert G.adapt_paths(env, datos, tmp_path / "respaldos") is False


def _pdf_text(data):
    import io
    from pypdf import PdfReader
    return "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(data)).pages)


def test_informe_con_nombre_del_endoscopista_en_encabezado_y_firma(env):
    from conftest import create_patient, csrf, login
    from tests.test_fase3 import new_proc
    med = login(env["app"], "propietario")
    tok = csrf(med)
    db = env["db"]
    org = env["org"]["org_id"]
    owner = db.execute("SELECT doctor_display_name FROM clinic_settings WHERE org_id = ?", (org,)).fetchone()[0]
    med.post("/ajustes/personal-endoscopia", data={"csrf_token": tok, "action": "agregar", "role": "medico",
                                                   "name": "Dra. Ficticia Prueba", "detail": "Gastroenterología"})
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "eda")
    data = db.execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0]
    import json
    d = json.loads(data)
    d["endoscopist"] = "Dra. Ficticia Prueba"
    db.execute("UPDATE procedures SET data = ? WHERE id = ?", (json.dumps(d), proc))
    db.commit()
    txt = _pdf_text(med.get(f"/procedimientos/{proc}/pdf").data)
    assert "Dra. Ficticia Prueba\nGastroenterología" in txt                  # encabezado = endoscopista con su especialidad
    assert "Dra. Ficticia Prueba\nEndoscopista · Nombre, firma y sello" in txt
    assert owner not in txt
    assert "Dra. Ficticia Prueba" in med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)


def test_informe_sin_endoscopista_usa_medico_de_ajustes(env):
    from conftest import create_patient, csrf, login
    from tests.test_fase3 import new_proc
    from app.views_endoscopy import _person_key
    med = login(env["app"], "propietario")
    tok = csrf(med)
    owner = env["db"].execute("SELECT doctor_display_name FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0]
    proc = new_proc(med, create_patient(med), tok, "eda")
    txt = _pdf_text(med.get(f"/procedimientos/{proc}/pdf").data)
    assert owner + "\nEndoscopista · Nombre, firma y sello" in txt
    assert _person_key("Dr. Mario Láinez") == _person_key("mario lainez")


def test_letra_mas_grande_en_los_pdf():
    from app.pdf import ST
    assert ST["body"].fontSize >= 11.5 and ST["small"].fontSize >= 9.5 and ST["title"].fontSize >= 13
