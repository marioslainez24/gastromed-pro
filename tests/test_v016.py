"""v0.16.0: antecedentes con clics que se arrastran a cada consulta y carta al médico que refirió."""
import io
import json

from pypdf import PdfReader

from conftest import create_patient, csrf, login
from tests.test_fase3 import new_proc, version


def _note(med, tok, pid, template="soap"):
    return med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": template}
                    ).headers["Location"].rsplit("/", 1)[-1]


def _fields(env, nid):
    return json.loads(env["db"].execute("SELECT fields FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0])


def test_antecedentes_con_clics_se_guardan_y_aparecen_en_la_nota_siguiente(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    url = f"/pacientes/{pid}/expediente/antecedentes/clic"
    H = {"X-Requested-With": "fetch"}
    assert med.post(url, data={"csrf_token": tok, "category": "personal", "item": "Diabetes mellitus tipo 2"}, headers=H).get_json()["agregado"]
    assert not med.post(url, data={"csrf_token": tok, "category": "personal", "item": "Diabetes mellitus tipo 2"}, headers=H).get_json()["agregado"]
    med.post(url, data={"csrf_token": tok, "category": "quirurgico", "item": "Craneotomía", "when_text": "2018"}, headers=H)
    med.post(url, data={"csrf_token": tok, "category": "familiar", "item": "Epilepsia", "relative": ["madre", "inventado"]}, headers=H)
    med.post(url, data={"csrf_token": tok, "category": "habito", "habit": "Tabaco", "value": "Fumador actual", "detail": "10 al día"}, headers=H)
    r = med.post(url, data={"csrf_token": tok, "category": "habito", "habit": "Tabaco", "value": "Exfumador"}, headers=H)
    r = med.post(url, data={"csrf_token": tok, "category": "personal", "item": "__otro__", "other": "Lupus (ficticio)"}, headers=H)
    t = r.get_json()["texto"]
    assert "Patológicos: Diabetes mellitus tipo 2; Lupus (ficticio)." in t
    assert "Quirúrgicos: Craneotomía (2018)." in t and "Familiares: Epilepsia en madre." in t
    assert "Hábitos: Tabaco: exfumador." in t and "fumador actual" not in t          # el hábito nuevo reemplaza al anterior
    assert med.post(url, data={"csrf_token": tok, "category": "personal", "item": "Inventado"}, headers=H).status_code == 422
    assert med.post(url, data={"csrf_token": tok, "category": "habito", "habit": "Tabaco", "value": "x"}, headers=H).status_code == 422
    # la nota nueva los trae escritos
    nid = _note(med, tok, pid)
    assert _fields(env, nid)["antecedentes"] == t
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Antecedentes con clics" in html and 'data-target="f-antecedentes"' in html and "✓ Diabetes mellitus tipo 2" in html
    # narrativa también, y el expediente muestra el panel
    assert "antecedentes" in _fields(env, _note(med, tok, pid, "narrativa"))
    assert "Antecedentes con clics" in med.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert med.get(f"/pacientes/{pid}/expediente/antecedentes/texto").get_json()["texto"] == t
    rec = login(env["app"], "recepcion")
    assert rec.post(url, data={"csrf_token": csrf(rec), "category": "personal", "item": "Obesidad"}).status_code == 403


def test_carta_al_medico_que_refirio_desde_nota_y_endoscopia(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med, referring_physician="Dr. Juan Referente (ficticio)")
    nid = _note(med, tok, pid)
    v = env["db"].execute("SELECT version FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0]
    med.post(f"/notas/{nid}/guardar", data={"csrf_token": tok, "version": v, "motivo": "Dispepsia", "diagnosticos": "Dispepsia funcional (CIE-10 K30)",
                                            "plan": "Endoscopia digestiva alta."})
    assert "Preparar carta" in med.get(f"/notas/{nid}").get_data(as_text=True)
    html = med.get(f"/carta-referente?note_id={nid}").get_data(as_text=True)
    assert "Estimado(a) Dr(a). Dr. Juan Referente (ficticio):" in html and "Dispepsia funcional (CIE-10 K30)" in html
    assert "Plan: Endoscopia digestiva alta." in html and "todavía está en borrador" in html
    r = med.post(f"/pacientes/{pid}/documentos/nuevo?kind=libre", data={"csrf_token": tok, "kind": "libre", "step": "emitir",
                                                                       "final_title": "CARTA AL MÉDICO QUE REFIRIÓ", "body": "Texto revisado de la carta (ficticio)."})
    assert r.status_code == 302
    did = r.headers["Location"].rsplit("/", 1)[-1]
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(med.get(f"/documentos/{did}/pdf").data)).pages)
    assert "CARTA AL MÉDICO QUE REFIRIÓ" in text and "Texto revisado de la carta" in text
    # desde la endoscopia
    proc = new_proc(med, pid, tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data={"csrf_token": tok, "version": version(env, proc), "performed_on": "2026-10-30",
                                                     "nar-estomago": "Eritema en antro.", "zline": "coincide",
                                                     "conclusion": "Gastropatía eritematosa de antro (CIE-10 K29.7)",
                                                     "recommendations": "Esperar patología.", "jar-0-number": "1", "jar-0-site": "Antro"})
    html = med.get(f"/carta-referente?proc_id={proc}").get_data(as_text=True)
    for t in ("endoscopia digestiva alta", "Estómago: Eritema en antro.", "Unión esofagogástrica: Coincide con la línea Z.",
              "Gastropatía eritematosa de antro", "1 frasco(s)", "Esperar patología."):
        assert t in html, t
    assert "Carta al médico que refirió" in med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert med.get("/carta-referente").status_code == 400
    assert login(env["app"], "enfermeria").get(f"/carta-referente?note_id={nid}").status_code == 403
