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
    assert ST["body"].fontSize == 12 and ST["small"].fontSize >= 10 and ST["title"].fontSize >= 13


def test_estudios_se_agrupan_por_fecha_y_nombre(env):
    from conftest import create_patient, login
    from tests.test_expediente_archivos import JPG, PDF_OK, upload
    from app.views_files import group_files, list_files
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    for i in range(1, 6):
        assert upload(med, pid, JPG + bytes([i]), name=f"f{i}.jpg", category="endoscopia", title=f"Endoscopia digestiva alta · imagen {i}",
                      study_date="2026-11-03").status_code == 302
    upload(med, pid, JPG + b"x", name="o.jpg", category="endoscopia", title="Endoscopia digestiva alta · imagen 1", study_date="2026-09-01")
    upload(med, pid, PDF_OK, category="laboratorio", title="Pruebas hepáticas", study_date="2026-11-03")
    groups = group_files(list_files(env["db"], pid))
    by = {(g["title"], g["date"]): g for g in groups}
    assert len(groups) == 3
    assert by[("Endoscopia digestiva alta", "2026-11-03")]["images"] == 5
    assert len(by[("Endoscopia digestiva alta", "2026-09-01")]["files"]) == 1
    html = med.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert html.count('class="file-group"') == 1 and "5 imágenes" in html and "Ver las imágenes en grande" in html
    key = by[("Endoscopia digestiva alta", "2026-11-03")]["key"]
    assert html.count(f'data-gal="{key}"') == 5 and f'data-gal-open="{key}"' in html and "Pruebas hepáticas" in html


def test_informe_muestra_dni_nacimiento_edad_y_mas(env):
    from conftest import create_patient, csrf, login
    from tests.test_fase3 import new_proc
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    db = env["db"]
    db.execute("UPDATE patients SET birth_date = '1980-05-15', document_type = 'dni', document_number = '0801-1980-99999', "
               "referring_physician = 'Dr. Remitente Ficticio' WHERE id = ?", (pid,))
    db.commit()
    proc = new_proc(med, pid, tok, "eda")
    db.execute("UPDATE procedures SET performed_on = '2026-11-03' WHERE id = ?", (proc,))
    db.commit()
    txt = " ".join(_pdf_text(med.get(f"/procedimientos/{proc}/pdf").data).split())
    for x in ("0801-1980-99999", "Fecha de nacimiento: 15/05/1980", "Edad: 46 años", "Expediente:", "Sexo:",
              "Médico que refiere: Dr. Remitente Ficticio"):
        assert x in txt, x


def test_tipo_de_atencion_sala_o_consulta_externa(env):
    import json
    from conftest import create_patient, csrf, login
    from tests.test_fase3 import full_form, new_proc, version
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Tipo de atención y lugar" in html and '<option value="externa" selected>Consulta externa</option>' in html
    r = med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), care_setting="sala", ward="Medicina interna",
                                                                  bed="12", facility="Hospital Ficticio", facility_record="H-555"))
    assert r.status_code == 302
    d = json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert (d["care_setting"], d["ward"], d["bed"], d["facility"], d["facility_record"]) == ("sala", "Medicina interna", "12", "Hospital Ficticio", "H-555")
    txt = " ".join(_pdf_text(med.get(f"/procedimientos/{proc}/pdf").data).split())
    assert "Atención: Sala (hospitalizado) · Medicina interna · cama 12" in txt and "Lugar: Hospital Ficticio" in txt and "Exp. del hospital: H-555" in txt
    assert "Hospital Ficticio" in med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert ">Sala<" in med.get("/endoscopia").get_data(as_text=True)
    # consulta externa: la sala y la cama no se guardan aunque vengan escritas
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), care_setting="externa", ward="X", bed="9"))
    d = json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert d["care_setting"] == "externa" and d["ward"] is None and d["bed"] is None
    txt = " ".join(_pdf_text(med.get(f"/procedimientos/{proc}/pdf").data).split())
    assert "Atención: Consulta externa" in txt and "cama" not in txt
    # valor no válido: no se guarda
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), care_setting="inventado"))
    assert json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])["care_setting"] is None


def test_estadisticas_por_atencion_y_lugar(env):
    from conftest import create_patient, csrf, login
    from tests.test_fase3 import full_form, new_proc, version
    from app.views_stats import compute
    from datetime import date
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    for care, fac in (("sala", "Hospital Ficticio"), ("externa", "")):
        proc = new_proc(med, pid, tok, "colonoscopia")
        med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), care_setting=care, facility=fac, then="finalizar"))
        med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    with env["app"].test_request_context():
        from app.db import get_db
        st = compute(get_db(), env["org"]["org_id"], date(2026, 1, 1), date(2026, 12, 31))
    assert ("Sala (hospitalizado)", "Hospital Ficticio", 1) in st["by_care"] and ("Consulta externa", "Su clínica", 1) in st["by_care"]
    html = med.get("/estadisticas?desde=2026-01-01&hasta=2026-12-31").get_data(as_text=True)
    assert "Estudios por tipo de atención y lugar" in html and "Hospital Ficticio" in html


def test_informe_sin_folio(env):
    from conftest import create_patient, csrf, login
    from tests.test_fase3 import new_proc
    med = login(env["app"], "propietario")
    tok = csrf(med)
    proc = new_proc(med, create_patient(med), tok, "eda")
    assert "Folio" not in _pdf_text(med.get(f"/procedimientos/{proc}/pdf").data)
    assert "Folio" not in med.get(f"/procedimientos/{proc}").get_data(as_text=True)


def test_ningun_documento_muestra_folio():
    import inspect
    from pathlib import Path
    from app import pdf
    assert "Folio" not in inspect.getsource(pdf)
    root = Path(pdf.__file__).parent / "templates"
    assert not [p.name for p in root.rglob("*.html") if "folio" in p.read_text(encoding="utf-8").lower()]
