"""v0.10.0: frases predefinidas, plantillas de nota y documentos clínicos."""
import io
import json
import re
import sqlite3

import pytest
from pypdf import PdfReader

from app.views_documents import number_words
from conftest import create_patient, csrf, login


def _new_note(med, pid, tok, template="soap"):
    r = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": template})
    return r.headers["Location"].rsplit("/", 1)[-1]


def _ver(env, nid):
    return env["db"].execute("SELECT version FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0]


def test_numero_en_letras():
    assert [number_words(n) for n in (1, 3, 7, 15, 16, 21, 22, 30, 31, 45, 100, 101, 120, 365)] == [
        "uno", "tres", "siete", "quince", "dieciséis", "veintiuno", "veintidós", "treinta", "treinta y uno", "cuarenta y cinco",
        "cien", "ciento uno", "ciento veinte", "trescientos sesenta y cinco"]


def test_frases_crear_editar_desactivar_y_aparecen_en_la_nota(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    assert "Frases predefinidas" in med.get("/ajustes/frases").get_data(as_text=True)
    med.post("/ajustes/frases/nueva", data={"csrf_token": tok, "field": "exploracion_abdominal", "title": "Abdomen ok",
                                             "body": "Abdomen blando, no doloroso (ficticio)."})
    med.post("/ajustes/frases/nueva", data={"csrf_token": tok, "field": "*", "title": "General", "body": "Texto general."})
    r = med.post("/ajustes/frases/nueva", data={"csrf_token": tok, "field": "campo-falso", "title": "x", "body": "y"})
    assert r.status_code == 400
    pid = create_patient(med)
    nid = _new_note(med, pid, tok)
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    m = re.search(r'data-frases="([^"]*)"', html)
    import html as h
    data = json.loads(h.unescape(m.group(1)))
    assert {"f": "exploracion_abdominal", "t": "Abdomen ok", "b": "Abdomen blando, no doloroso (ficticio)."} in data
    assert 'data-phrase-field="exploracion_abdominal"' in html
    ph = env["db"].execute("SELECT id FROM phrases WHERE title = 'Abdomen ok'").fetchone()[0]
    med.post(f"/ajustes/frases/{ph}", data={"csrf_token": tok, "action": "desactivar"})
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Abdomen ok" not in h.unescape(re.search(r'data-frases="([^"]*)"', html).group(1))
    # frases de ejemplo: se cargan una sola vez
    med.post("/ajustes/frases/ejemplos", data={"csrf_token": tok})
    n1 = env["db"].execute("SELECT COUNT(*) FROM phrases").fetchone()[0]
    med.post("/ajustes/frases/ejemplos", data={"csrf_token": tok})
    assert env["db"].execute("SELECT COUNT(*) FROM phrases").fetchone()[0] == n1 > 2
    # recepción no administra frases
    assert login(env["app"], "recepcion").get("/ajustes/frases").status_code == 403


def test_frases_en_informe_de_endoscopia(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    med.post("/ajustes/frases/nueva", data={"csrf_token": tok, "field": "endo:recommendations", "title": "Esperar patología",
                                             "body": "Esperar resultado de patología."})
    pid = create_patient(med)
    r = med.post(f"/pacientes/{pid}/procedimientos/nuevo", data={"csrf_token": tok, "kind": "eda"})
    html = med.get(r.headers["Location"]).get_data(as_text=True)
    assert 'data-phrase-field="endo:recommendations"' in html and "Esperar patología" in html


def test_guardar_nota_como_plantilla_y_aplicarla(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    nid = _new_note(med, pid, tok)
    r = med.post(f"/notas/{nid}/guardar", data={"csrf_token": tok, "version": _ver(env, nid), "motivo": "Control de ERGE",
                                               "plan_terapeutico": "Medidas antirreflujo (ficticio).", "v_peso_kg": "70",
                                               "then": "plantilla", "template_name": "Control ERGE", "template_scope": "ambas"})
    assert r.status_code == 302
    t = env["db"].execute("SELECT * FROM note_templates").fetchone()
    assert t["name"] == "Control ERGE" and t["template"] == "ambas"
    assert json.loads(t["fields"]) == {"motivo": "Control de ERGE", "plan_terapeutico": "Medidas antirreflujo (ficticio)."}
    # aparece en otra nota (narrativa, porque es «ambas»)
    nid2 = _new_note(med, pid, tok, "narrativa")
    html = med.get(f"/notas/{nid2}").get_data(as_text=True)
    assert "Control ERGE" in __import__("html").unescape(html)
    # sin nombre no se crea
    med.post(f"/notas/{nid}/guardar", data={"csrf_token": tok, "version": _ver(env, nid), "motivo": "x", "then": "plantilla"})
    assert env["db"].execute("SELECT COUNT(*) FROM note_templates").fetchone()[0] == 1
    # edición y desactivación desde Ajustes
    med.post(f"/ajustes/plantillas/{t['id']}", data={"csrf_token": tok, "name": "ERGE control", "f-motivo": "Control de ERGE",
                                                     "f-plan_terapeutico": ""})
    t2 = env["db"].execute("SELECT * FROM note_templates").fetchone()
    assert t2["name"] == "ERGE control" and json.loads(t2["fields"]) == {"motivo": "Control de ERGE"}
    med.post(f"/ajustes/plantillas/{t['id']}", data={"csrf_token": tok, "action": "desactivar"})
    html = med.get(f"/notas/{nid2}").get_data(as_text=True)
    assert "ERGE control" not in __import__("html").unescape(html)


def test_incapacidad_texto_pdf_inmutable_y_anulacion(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    base = {"csrf_token": tok, "kind": "incapacidad", "seen_on": "2026-10-28", "days": "3", "start_on": "2026-10-28",
            "diagnosis": "Gastroenteritis aguda (ficticio)"}
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={**base, "step": "revisar"})
    html = r.get_data(as_text=True)
    assert "3 (tres) días" in html and "28/10/2026 al 30/10/2026" in html
    assert "Gastroenteritis" not in html.split('name="body"')[1].split("</textarea>")[0]   # sin diagnóstico salvo que se marque
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={**base, "include_dx": "1", "step": "revisar"})
    assert "con diagnóstico de Gastroenteritis aguda (ficticio)" in r.get_data(as_text=True)
    body = "Texto revisado por el médico: incapacidad de 3 (tres) días (ficticio)."
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={**base, "step": "emitir", "body": body, "final_title": "CONSTANCIA DE INCAPACIDAD MÉDICA"})
    assert r.status_code == 302
    did = r.headers["Location"].rsplit("/", 1)[-1]
    d = env["db"].execute("SELECT * FROM clinical_documents WHERE id = ?", (did,)).fetchone()
    assert d["body"] == body and json.loads(d["data"])["end_on"] == "2026-10-30" and len(d["content_sha256"]) == 64
    pdf = med.get(f"/documentos/{did}/pdf?papel=carta")
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf.data)).pages)
    assert "CONSTANCIA DE INCAPACIDAD" in text and "Texto revisado por el médico" in text
    with pytest.raises(sqlite3.DatabaseError):
        env["db"].execute("UPDATE clinical_documents SET body = 'cambiado' WHERE id = ?", (did,))
    with pytest.raises(sqlite3.DatabaseError):
        env["db"].execute("DELETE FROM clinical_documents WHERE id = ?", (did,))
    med.post(f"/documentos/{did}/anular", data={"csrf_token": tok, "reason": "Error en la fecha"})
    assert env["db"].execute("SELECT status FROM clinical_documents WHERE id = ?", (did,)).fetchone()[0] == "anulado"
    assert "Documentos" in med.get(f"/pacientes/{pid}/documentos").get_data(as_text=True)


def test_constancia_referencia_validaciones_y_permisos(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={"csrf_token": tok, "kind": "constancia", "seen_on": "2026-10-28",
                                                             "time_from": "08:30", "time_to": "09:15", "step": "revisar"})
    assert "asistió a consulta médica" in r.get_data(as_text=True) and "de 08:30 a 09:15" in r.get_data(as_text=True)
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={"csrf_token": tok, "kind": "referencia", "step": "emitir", "body": "x"})
    assert "Indique a quién" in r.get_data(as_text=True)
    assert env["db"].execute("SELECT COUNT(*) FROM clinical_documents").fetchone()[0] == 0
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={"csrf_token": tok, "kind": "incapacidad", "days": "0", "step": "emitir",
                                                             "body": "x"})
    assert "días de incapacidad" in r.get_data(as_text=True)
    assert med.get(f"/pacientes/{pid}/documentos/nuevo?kind=otro").status_code == 400
    rec = login(env["app"], "recepcion")
    assert rec.get(f"/pacientes/{pid}/documentos").status_code == 403
    enf = login(env["app"], "enfermeria")
    assert enf.get(f"/pacientes/{pid}/documentos").status_code == 200
    assert enf.get(f"/pacientes/{pid}/documentos/nuevo").status_code == 403


def test_documento_sin_fechas_usa_la_de_hoy(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    r = med.post(f"/pacientes/{pid}/documentos/nuevo", data={"csrf_token": tok, "kind": "incapacidad", "days": "2", "step": "emitir",
                                                             "body": "Constancia (ficticio)."})
    assert r.status_code == 302
