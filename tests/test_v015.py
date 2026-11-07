"""v0.15.0: nota anterior que se copia, plan único sin diferenciales, otros resultados de laboratorio y solicitudes con estudios para marcar."""
import io
import json

from pypdf import PdfReader

from app import study_catalog as SC
from conftest import create_patient, csrf, login


def _note(med, tok, pid, template="soap"):
    return med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": template}
                    ).headers["Location"].rsplit("/", 1)[-1]


def _ver(env, nid):
    return env["db"].execute("SELECT version FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0]


def test_plan_unico_sin_diferenciales_y_notas_antiguas_intactas(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    nid = _note(med, tok, pid)
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    for gone in ("diferenciales", "plan_terapeutico", "plan_diagnostico", "educacion", "seguimiento"):
        assert f'name="{gone}"' not in html, gone
    assert 'name="plan"' in html and ">Plan<" in html
    med.post(f"/notas/{nid}/guardar", data={"csrf_token": tok, "version": _ver(env, nid), "motivo": "x", "plan": "Plan único (ficticio)."})
    assert json.loads(env["db"].execute("SELECT fields FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0])["plan"] == "Plan único (ficticio)."
    # Nota antigua con campos anteriores: se siguen viendo y no se pierden al guardar
    old = _note(med, tok, pid)
    env["db"].execute("UPDATE clinical_notes SET fields = ? WHERE id = ?",
                      (json.dumps({"vitales": {}, "plan_terapeutico": "Omeprazol (antiguo)", "diferenciales": "Úlcera (antiguo)"}), old))
    env["db"].commit()
    html = med.get(f"/notas/{old}").get_data(as_text=True)
    assert 'name="plan_terapeutico"' in html and "Omeprazol (antiguo)" in html and 'name="diferenciales"' in html
    med.post(f"/notas/{old}/guardar", data={"csrf_token": tok, "version": _ver(env, old), "plan_terapeutico": "Omeprazol (antiguo)",
                                            "diferenciales": "Úlcera (antiguo)", "plan": "Nuevo"})
    f = json.loads(env["db"].execute("SELECT fields FROM clinical_notes WHERE id = ?", (old,)).fetchone()[0])
    assert f["plan_terapeutico"] == "Omeprazol (antiguo)" and f["plan"] == "Nuevo"


def test_nota_anterior_muestra_todo_y_se_puede_copiar(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    n1 = _note(med, tok, pid)
    med.post(f"/notas/{n1}/guardar", data={"csrf_token": tok, "version": _ver(env, n1), "motivo": "Dispepsia",
                                           "hea": "Historia previa (ficticio).", "diagnosticos": "Dispepsia funcional", "plan": "Control en 1 mes"})
    med.post(f"/notas/{n1}/finalizar", data={"csrf_token": tok, "version": _ver(env, n1)})
    n2 = _note(med, tok, pid)
    html = med.get(f"/notas/{n2}").get_data(as_text=True)
    assert "Nota anterior" in html and "Copiar todo a esta nota" in html
    for t in ("Historia previa (ficticio).", "Dispepsia funcional", "Control en 1 mes"):
        assert t in html
    assert 'data-copy-prior="hea"' in html and 'data-copy-prior="plan"' in html and 'data-copy-prior="diagnosticos"' in html
    # nota antigua con plan terapéutico (campos anteriores a v0.15): se ofrece copiarla al «Plan» nuevo
    pid2 = create_patient(med, first_names="Otro", last_names="Ficticio", document_number="0801-1990-00099")
    a = _note(med, tok, pid2)
    env["db"].execute("UPDATE clinical_notes SET fields = ? WHERE id = ?",
                      (json.dumps({"vitales": {}, "motivo": "x", "plan_terapeutico": "Plan viejo (ficticio)"}), a))
    env["db"].commit()
    med.post(f"/notas/{a}/finalizar", data={"csrf_token": tok, "version": _ver(env, a)})
    b = _note(med, tok, pid2)
    html = med.get(f"/notas/{b}").get_data(as_text=True)
    assert "Plan viejo (ficticio)" in html and "Copiar a «Plan»" in html


def test_otros_resultados_de_laboratorio_se_guardan_y_se_recuerdan(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    html = med.get(f"/pacientes/{pid}/laboratorio/registrar").get_data(as_text=True)
    assert "Otros resultados" in html and 'name="otro-0-name"' in html
    r = med.post(f"/pacientes/{pid}/laboratorio/registrar", data={
        "csrf_token": tok, "taken_on": "2026-10-30",
        "otro-0-name": "Elastasa fecal", "otro-0-value": "450", "otro-0-unit": "µg/g", "otro-0-lo": "200",
        "otro-1-name": "Anticuerpos anti-endomisio", "otro-1-value": "Negativo",
        "otro-2-name": "Sin resultado", "otro-2-value": ""})
    assert r.status_code == 422 and "escriba el nombre de la prueba y el resultado" in r.get_data(as_text=True)
    r = med.post(f"/pacientes/{pid}/laboratorio/registrar", data={
        "csrf_token": tok, "taken_on": "2026-10-30",
        "otro-0-name": "Elastasa fecal", "otro-0-value": "450", "otro-0-unit": "µg/g", "otro-0-lo": "200",
        "otro-1-name": "Anticuerpos anti-endomisio", "otro-1-value": "Negativo"})
    assert r.status_code == 302, r.get_data(as_text=True)[:400]
    t = env["db"].execute("SELECT * FROM lab_tests WHERE name = 'Elastasa fecal'").fetchone()
    assert t["grp"] == "Otros (agregados por usted)" and t["kind"] == "numerico"
    res = env["db"].execute("SELECT * FROM lab_results WHERE test_code = ?", (t["code"],)).fetchone()
    assert res["value_num"] == 450 and res["unit"] == "µg/g" and res["flag"] == "normal"
    q = env["db"].execute("SELECT r.value_text FROM lab_results r JOIN lab_tests t ON t.code = r.test_code WHERE t.name = 'Anticuerpos anti-endomisio'").fetchone()
    assert q["value_text"] == "Negativo"
    # la próxima vez aparece en la lista y no se duplica
    assert "Elastasa fecal" in med.get(f"/pacientes/{pid}/laboratorio/registrar").get_data(as_text=True)
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": "2026-10-31",
                                                              "otro-0-name": "elastasa fecal", "otro-0-value": "380"})
    assert env["db"].execute("SELECT COUNT(*) FROM lab_tests WHERE lower(name) = 'elastasa fecal'").fetchone()[0] == 1
    assert env["db"].execute("SELECT COUNT(*) FROM lab_results WHERE test_code = ?", (t["code"],)).fetchone()[0] == 2


def test_solicitudes_de_imagen_endoscopia_y_colonoscopia_con_estudios_para_marcar(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    resp = env["users"]["propietario"]
    names = [n for _, ns in SC.IMAGING for n in ns]
    assert "TAC de cráneo simple" in names and "Doppler carotídeo y vertebral" in names
    for kind, title, pick in (("imagen", "Imagenología", "TAC de cráneo simple"),
                              ("endoscopia", "Neurofisiología", "Electroencefalograma (EEG) de rutina")):
        html = med.get(f"/ordenes/nueva?patient_id={pid}&order_type={kind}").get_data(as_text=True)
        assert pick in html and 'name="study"' in html and title in html
        r = med.post("/ordenes/nueva", data={"csrf_token": tok, "patient_id": pid, "order_type": kind, "study": [pick, "Estudio inventado"],
                                             "items_text": "Otro estudio escrito (ficticio)", "priority": "rutina", "responsible_id": resp})
        assert r.status_code == 302, (kind, r.get_data(as_text=True)[:300])
        oid = r.headers["Location"].rsplit("/", 1)[-1]
        o = env["db"].execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
        items = [i["description"] for i in env["db"].execute("SELECT description FROM order_items WHERE order_id = ? ORDER BY position", (oid,))]
        assert items == [pick, "Otro estudio escrito (ficticio)"], items          # lo inventado se descarta
        assert o["order_type"] == ("imagen" if kind == "imagen" else "endoscopia")
        text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(med.get(f"/ordenes/{oid}/pdf").data)).pages)
        assert f"SOLICITUD DE {title.upper()}" in text and pick in text
    assert "Solicitud de neurofisiología" in med.get(f"/pacientes/{pid}/laboratorio").get_data(as_text=True)
    r = med.post("/ordenes/nueva", data={"csrf_token": tok, "patient_id": pid, "order_type": "endoscopia", "priority": "rutina", "responsible_id": resp})
    assert r.status_code == 422
    assert med.get(f"/ordenes/nueva?patient_id={pid}&order_type=colonoscopia").status_code == 400   # NeuroMed Pro: sin colonoscopia
