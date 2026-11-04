"""Fase 3: informes de endoscopia, imágenes, patología, prótesis, vigilancia, calidad y reprocesamiento."""
import io
import json
import re
import sqlite3

import pytest
from PIL import Image
from pypdf import PdfReader

from conftest import create_patient, csrf, login
from app import endoscopy_defs as D


def jpeg(color=(200, 90, 80)):
    b = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(b, "JPEG")
    return b.getvalue()


def new_proc(c, pid, tok, kind="colonoscopia"):
    r = c.post(f"/pacientes/{pid}/procedimientos/nuevo", data={"csrf_token": tok, "kind": kind})
    assert r.status_code == 302, r.get_data(as_text=True)[:300]
    return r.headers["Location"].split("/")[-1]


def version(env, proc_id):
    return env["db"].execute("SELECT version FROM procedures WHERE id = ?", (proc_id,)).fetchone()[0]


def full_form(tok, v, **over):
    f = {"csrf_token": tok, "version": v, "performed_on": "2026-10-28", "indication_category": "tamizaje",
         "indication": "Tamizaje de cáncer colorrectal (ficticio)", "consent_obtained": "1", "consent_version": "Consentimiento v1",
         "asa": "II", "sedation_type": "moderada", "sedation_agents": "Midazolam (documentado por anestesia)", "sedation_by": "Dr. Anestesia",
         "extent": "ciego", "complete": "1", "withdrawal_minutes": "8", "bbps_right": "2", "bbps_transverse": "3", "bbps_left": "3",
         "find-0-segment": "Sigmoides", "find-0-type": "Pólipo", "find-0-class": "P-0-Is", "find-0-size": "6", "find-0-desc": "Pólipo sésil",
         "find-0-removed": "Asa fría", "find-0-jar": "1",
         "find-1-segment": "Recto", "find-1-type": "Hemorroides", "find-1-desc": "Hemorroides internas grado I",
         "jar-0-number": "1", "jar-0-site": "Pólipo de sigmoides", "jar-0-pieces": "1",
         "complications": [], "conclusion": "Pólipo sésil de 6 mm resecado.", "recommendations": "Esperar patología.",
         "surveillance_due": "2027-10-28", "then": "guardar"}
    f.update(over)
    return f


def test_definiciones_de_clasificaciones():
    la = dict((c, d) for c, s, d in D.CLASSIFICATIONS["los_angeles"][1])
    assert "≥75 %" in la["LA-D"] and "<75 %" in la["LA-C"] and "≤5 mm" in la["LA-A"]
    assert [s for _, s, _ in D.CLASSIFICATIONS["forrest"][1]] == ["Ia", "Ib", "IIa", "IIb", "IIc", "III"]
    assert [s for _, s, _ in D.CLASSIFICATIONS["paris"][1]] == ["0-Ip", "0-Is", "0-IIa", "0-IIb", "0-IIc", "0-III"]
    assert [n for n, _ in D.BBPS] == [0, 1, 2, 3]


def test_informe_completo_imagenes_pdf_patologia(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med, birth_date="1970-03-01")
    tok = csrf(med)
    proc = new_proc(med, pid, tok)
    assert med.get(f"/procedimientos/{proc}").status_code == 200
    r = med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc)))
    assert r.status_code == 302
    row = env["db"].execute("SELECT * FROM procedures WHERE id = ?", (proc,)).fetchone()
    d = json.loads(row["data"])
    assert row["cecum_reached"] == 1 and row["bbps_right"] == 2 and row["patient_age_years"] == 56
    assert len(d["findings"]) == 2 and d["findings"][0]["classification"] == "P-0-Is" and d["jars"][0]["site"] == "Pólipo de sigmoides"
    # Imagen importada: exige confirmación del paciente correcto
    r = med.post(f"/procedimientos/{proc}/imagenes", data={"csrf_token": tok, "imagen": (io.BytesIO(jpeg()), "a.jpg")},
                 content_type="multipart/form-data")
    assert r.status_code == 400
    r = med.post(f"/procedimientos/{proc}/imagenes", data={"csrf_token": tok, "confirm_patient": pid,
                                                           "imagen": [(io.BytesIO(jpeg()), "a.jpg"), (io.BytesIO(jpeg((90, 90, 200))), "b.jpg")]},
                 content_type="multipart/form-data")
    assert r.status_code == 302
    # Captura (como la envía captura.js)
    r = med.post(f"/procedimientos/{proc}/imagenes", data={"csrf_token": tok, "confirm_patient": pid, "source": "captura",
                                                           "imagen": (io.BytesIO(jpeg((10, 200, 10))), "captura.jpg")},
                 content_type="multipart/form-data", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.get_json()["agregadas"] == 1
    imgs = env["db"].execute("SELECT * FROM procedure_images WHERE procedure_id = ? ORDER BY position", (proc,)).fetchall()
    assert [i["source"] for i in imgs] == ["importada", "importada", "captura"]
    original = env["db"].execute("SELECT sha256 FROM files WHERE id = ?", (imgs[0]["file_id"],)).fetchone()[0]
    r = med.post(f"/procedimientos/{proc}/imagenes/{imgs[0]['id']}", data={"csrf_token": tok, "location": "Sigmoides", "caption": "Pólipo",
                                                                           "in_report": "1",
                                                                           "annotations": json.dumps([{"x": 0.5, "y": 0.4, "text": "pólipo"}])})
    assert r.status_code == 302
    assert env["db"].execute("SELECT sha256 FROM files WHERE id = ?", (imgs[0]["file_id"],)).fetchone()[0] == original  # original intacto
    # Finalizar
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), then="finalizar"))
    r = med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert r.status_code == 302
    db = env["db"]
    assert db.execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "finalizado"
    assert db.execute("SELECT COUNT(*) FROM specimens WHERE procedure_id = ?", (proc,)).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM tasks WHERE title LIKE 'Seguimiento de patología%'").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE procedures SET data = '{}' WHERE id = ?", (proc,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE procedure_images SET in_report = 0 WHERE procedure_id = ?", (proc,))
    assert med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc))).status_code == 409
    # PDF con imágenes
    r = med.get(f"/procedimientos/{proc}/pdf")
    assert r.status_code == 200
    pdf = PdfReader(io.BytesIO(r.data))
    text = "\n".join(pg.extract_text() for pg in pdf.pages)
    for t in ["INFORME DE COLONOSCOPIA", "Sigmoides", "París 0-Is", "Boston", "total 8/9", "Frasco 1", "Pólipo sésil de 6 mm",
              "1: pólipo"]:
        assert t in text, t
    assert "BORRADOR" not in text          # finalizado (v0.24.1: sin pie «Informe finalizado»)
    assert sum(len(pg.images) for pg in pdf.pages) == 1
    # Patología: enviar → resultado → comunicar y cerrar
    sid = db.execute("SELECT id FROM specimens").fetchone()[0]
    med.post(f"/procedimientos/{proc}/muestras/enviar", data={"csrf_token": tok, "laboratory": "Patología demo", "sent_on": "2026-10-28"})
    assert db.execute("SELECT status FROM specimens").fetchone()[0] == "enviado"
    assert med.post(f"/muestras/{sid}/cerrar", data={"csrf_token": tok, "communication": "x"}).status_code == 409
    med.post(f"/muestras/{sid}/resultado", data={"csrf_token": tok, "result_category": "adenoma_tubular", "dysplasia": "bajo_grado",
                                                 "result_text": "Adenoma tubular con displasia de bajo grado.", "result_on": "2026-10-30"})
    assert med.post(f"/muestras/{sid}/resultado", data={"csrf_token": tok, "result_category": "normal", "result_text": "x"}).status_code == 409
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE specimens SET result_text = 'otro' WHERE id = ?", (sid,))
    med.post(f"/muestras/{sid}/cerrar", data={"csrf_token": tok, "communication": "En consulta de control"})
    assert db.execute("SELECT status FROM specimens").fetchone()[0] == "cerrado"
    # Adenda
    assert med.post(f"/procedimientos/{proc}/adenda", data={"csrf_token": tok, "text": "Se agrega dato omitido."}).status_code == 302
    # Indicadores: 1 colonoscopia de tamizaje, ciego alcanzado, adenoma confirmado, Boston adecuado, retirada ≥6 (tuvo biopsia → excluida)
    from app.views_endoscopy import quality_metrics
    m = {name: (num, den) for name, num, den, _ in quality_metrics(db, env["org"]["org_id"], "2026-01-01", "2026-12-31")}
    assert m["Tasa de intubación cecal"] == (1, 1)
    assert m["Tasa de detección de adenomas (ADR)"] == (1, 1)
    assert m["Preparación adecuada (Boston ≥2 en cada segmento)"] == (1, 1)
    assert m["Tiempo de retirada ≥6 minutos"] == (0, 0)
    assert "Tasa de detección" in med.get("/endoscopia/calidad?desde=2026-01-01&hasta=2026-12-31").get_data(as_text=True)


def test_finalizar_exige_datos_minimos(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    r = med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert r.status_code == 302
    assert env["db"].execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "borrador"
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "No se puede finalizar" in html and "consentimiento" in html


def test_validaciones_de_hallazgos_y_frascos(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    f = {"csrf_token": tok, "version": version(env, proc), "performed_on": "2026-10-28",
         "find-0-segment": "Ciego", "find-0-desc": "segmento que no corresponde a una EDA",
         "find-1-segment": "Esófago distal", "find-1-type": "Esofagitis", "find-1-class": "LA-B", "find-1-jar": "3",
         "jar-0-number": "1", "jar-0-site": "Antro", "jar-1-number": "1", "jar-1-site": "Cuerpo"}
    med.post(f"/procedimientos/{proc}/guardar", data=f)
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "elija el segmento" in html and "repetido" in html and "frasco 3" in html
    d = json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert len(d["findings"]) == 1 and d["findings"][0]["classification"] == "LA-B"


def test_permisos_y_aislamiento_fase3(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok)
    rec = login(env["app"], "recepcion")
    for url in [f"/procedimientos/{proc}", f"/procedimientos/{proc}/pdf", "/endoscopia", f"/pacientes/{pid}/procedimientos"]:
        assert rec.get(url).status_code == 403, url
    otra = login(env["app"], "otra", email="otra@prueba.hn")
    assert otra.get(f"/procedimientos/{proc}").status_code == 404
    col = login(env["app"], "medico")
    assert col.get(f"/procedimientos/{proc}/captura").status_code == 409          # solo el autor captura
    assert col.post(f"/procedimientos/{proc}/guardar", data=full_form(csrf(col), version(env, proc))).status_code == 409
    r = med.get(f"/procedimientos/{proc}/captura")
    assert r.status_code == 200 and "camera=(self)" in r.headers["Permissions-Policy"]
    assert "camera=()" in med.get("/endoscopia").headers["Permissions-Policy"]   # resto del sistema sin cámara


def test_protesis_y_vigilancia(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "cpre")
    f = {"csrf_token": tok, "version": version(env, proc), "performed_on": "2026-09-01", "indication_category": "terapeutica",
         "indication": "Coledocolitiasis", "consent_obtained": "1", "sedation_type": "profunda", "extent": "canulacion_biliar",
         "conclusion": "Extracción parcial; prótesis plástica.", "surveillance_due": "2026-11-15",
         "nar-cpre": "Colédoco dilatado con defectos de llenado (ficticio).",
         "stent-0-kind": "Prótesis biliar plástica", "stent-0-desc": "10 Fr × 9 cm", "stent-0-due": "2026-12-01"}
    med.post(f"/procedimientos/{proc}/guardar", data=f)
    med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    st = env["db"].execute("SELECT * FROM stents").fetchone()
    assert st["kind"] == "Prótesis biliar plástica" and st["review_due"] == "2026-12-01"
    html = med.get("/endoscopia").get_data(as_text=True)
    assert "10 Fr × 9 cm" in html and "15/11/2026" in html
    med.post(f"/protesis/{st['id']}", data={"csrf_token": tok, "status": "retirada"})
    assert env["db"].execute("SELECT status FROM stents").fetchone()[0] == "retirada"


def test_equipos_y_reprocesamiento(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    med.post("/endoscopia/equipos", data={"csrf_token": tok, "action": "nuevo_equipo", "name": "Colonoscopio 1", "kind": "colonoscopio",
                                          "serial": "SN-123"})
    sid = env["db"].execute("SELECT id FROM scopes").fetchone()[0]
    enf = login(env["app"], "enfermeria")
    etok = csrf(enf)
    assert enf.post("/endoscopia/equipos", data={"csrf_token": etok, "action": "nuevo_equipo", "name": "x", "kind": "otro"}).status_code == 403
    enf.post("/endoscopia/equipos", data={"csrf_token": etok, "action": "reprocesamiento", "scope_id": sid, "method": "automatizado",
                                          "leak_test": "fallida", "result": "apto"})
    assert env["db"].execute("SELECT COUNT(*) FROM scope_reprocessing").fetchone()[0] == 0    # fuga fallida no puede ser apto
    enf.post("/endoscopia/equipos", data={"csrf_token": etok, "action": "reprocesamiento", "scope_id": sid, "method": "automatizado",
                                          "leak_test": "aprobada", "result": "apto", "agent": "Ácido peracético", "agent_lot": "L-77"})
    assert env["db"].execute("SELECT result FROM scope_reprocessing").fetchone()[0] == "apto"
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("DELETE FROM scope_reprocessing")
    assert "Ácido peracético" in med.get("/endoscopia/equipos").get_data(as_text=True)


def test_pantallas_fase3_cargan(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    for kind in D.KINDS:
        proc = new_proc(med, pid, tok, kind)
        assert med.get(f"/procedimientos/{proc}").status_code == 200, kind
        assert med.get(f"/procedimientos/{proc}/pdf").status_code == 200, kind
    for url in ["/endoscopia", "/endoscopia/calidad", "/endoscopia/equipos", f"/pacientes/{pid}/procedimientos",
                f"/pacientes/{pid}/procedimientos/nuevo"]:
        assert med.get(url).status_code == 200, url
