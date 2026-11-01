"""v0.13.0 (lote 2): clasificaciones, etiquetas de frascos, cálculos rápidos, hallazgos con clics, recomendaciones, hojas, sala de espera,
preconsulta, imprimir todo y resumen del paciente."""
import io
import json

from pypdf import PdfReader

from app import endoscopy_defs as D
from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def pdf_text(data):
    return "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(data)).pages)


def test_clasificaciones_nuevas_verificadas():
    for grp in ("sarin", "zargar", "nice", "kudo"):
        assert grp in D.CLASSIFICATIONS
    assert [s for _, s, _ in D.CLASSIFICATIONS["zargar"][1]] == ["0", "1", "2a", "2b", "3a", "3b"]
    assert [s for _, s, _ in D.CLASSIFICATIONS["sarin"][1]] == ["GOV1", "GOV2", "IGV1", "IGV2"]
    assert "adenoma" in D.CLASS_LOOKUP["N-2"][2]
    assert "Hewett" in D.__doc__ and "Zargar" in D.__doc__ and "Sarin" in D.__doc__


def test_etiquetas_de_frascos(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok)
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), **{
        "jar-1-number": "2", "jar-1-site": "Recto, biopsias aleatorias", "jar-1-pieces": "4"}))
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Etiquetas de frascos (2)" in html
    r = med.get(f"/procedimientos/{proc}/etiquetas?papel=carta")
    t = pdf_text(r.data)
    assert r.status_code == 200 and "FRASCO 1" in t and "FRASCO 2" in t and "Recto, biopsias aleatorias" in t and "4 fragmento(s)" in t
    assert "Exp. GM-" in t


def test_hallazgos_con_clics_frases_y_sugerencias_existen_en_catalogo():
    import itertools
    from werkzeug.datastructures import MultiDict
    from app import endo_findings as EF
    checked = 0
    for section, items in EF.FINDINGS.items():
        for key, label, params, _s, _d in items:
            # combinaciones de todas las opciones de cada parámetro (números en 3)
            choices = []
            for p in params:
                if p["kind"] == "number":
                    choices.append([(p["name"], ["3"])])
                elif p["kind"] == "multi":
                    choices.append([(p["name"], [p["options"][0][0]]), (p["name"], [o[0] for o in p["options"]])])
                else:
                    choices.append([(p["name"], [o[0]]) for o in p["options"]])
            for combo in itertools.product(*choices) if choices else [()]:
                src = MultiDict([(n, v) for n, vs in combo for v in vs])
                text, dx = EF.compose(section, key, src)
                assert text.endswith(".") and "{" not in text and "None" not in text, (section, key, text)
                for d in dx:
                    assert d["t"] and "__" not in d["t"], (key, d)
                checked += 1
    assert checked > 100
    t, dx = EF.compose("esofago", "esofagitis", MultiDict([("grado", "B")]))
    assert t == "Erosiones de la mucosa del esófago distal compatibles con esofagitis grado B de Los Ángeles."
    assert dx == [{"t": "Esofagitis erosiva grado B de Los Ángeles", "c": "K21.0", "a": False}]
    t, dx = EF.compose("ueg", "hernia", MultiDict([("cm", "3")]))
    assert t == "Hernia hiatal por deslizamiento de 3 cm." and dx[0] == {"t": "Hernia hiatal por deslizamiento de 3 cm", "c": "K44.9", "a": False}
    t, dx = EF.compose("colon", "polipo", MultiDict([("mm", "6"), ("loc", "sigmoides"), ("paris", "0-Is"), ("nice", "2"),
                                                      ("reseccion", "asa_fria"), ("recuperado", "si")]))
    assert t == "Pólipo de 6 mm en sigmoides, París 0-Is, NICE 2, resecado con asa fría y recuperado."
    assert dx[0]["t"] == "Pólipo de colon NICE 2 (aspecto adenomatoso)"
    import pytest
    with pytest.raises(EF.Invalid):
        EF.compose("esofago", "esofagitis", MultiDict())          # falta el grado
    with pytest.raises(EF.Invalid):
        EF.compose("esofago", "inventado", MultiDict())


def test_hallazgo_con_clics_en_el_informe(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Hallazgo con clics" in html and 'id="efind-form"' in html and "data-dx-suggest" in html
    r = med.post(f"/procedimientos/{proc}/hallazgo", data={"csrf_token": tok, "section": "estomago", "finding": "ulcera_g",
                                                         "ef-estomago-ulcera_g-loc": "antro", "ef-estomago-ulcera_g-mm": "8",
                                                         "ef-estomago-ulcera_g-forrest": "III"})
    assert r.status_code == 200 and r.get_json()["texto"] == "Úlcera de 8 mm en antro, Forrest III (fondo limpio)."
    assert r.get_json()["dx"][0]["c"] == "K25.9"
    assert med.post(f"/procedimientos/{proc}/hallazgo", data={"csrf_token": tok, "section": "colon", "finding": "polipo"}).status_code == 422


def test_recomendaciones_por_diagnostico(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    assert "Recomendaciones por diagnóstico" in med.get("/endoscopia/recomendaciones").get_data(as_text=True)
    med.post("/endoscopia/recomendaciones", data={"csrf_token": tok, "dx": "Pólipo de colon", "text": "Esperar patología (ficticio)."})
    assert med.post("/endoscopia/recomendaciones", data={"csrf_token": tok, "dx": "inventado", "text": "x"}).status_code == 400
    assert json.loads(env["db"].execute("SELECT endo_recs FROM clinic_settings").fetchone()[0]) == {"Pólipo de colon": "Esperar patología (ficticio)."}
    pid = create_patient(med)
    html = med.get(f"/procedimientos/{new_proc(med, pid, tok)}").get_data(as_text=True)
    assert "data-rec-suggest" in html and "Esperar patología (ficticio)." in html
    med.post("/endoscopia/recomendaciones", data={"csrf_token": tok, "dx": "Pólipo de colon", "text": ""})
    assert env["db"].execute("SELECT endo_recs FROM clinic_settings").fetchone()[0] is None


def test_hojas_preparacion_y_consentimiento(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    # sin aprobar no se imprime
    assert med.get(f"/pacientes/{pid}/hoja/prep/colonoscopia").status_code == 409
    html = med.get("/endoscopia/hojas?tipo=colonoscopia").get_data(as_text=True)
    assert "Borrador sin revisar" in html and "{fecha_cita}" in html
    med.post("/endoscopia/hojas", data={"csrf_token": tok, "tipo": "colonoscopia",
                                        "prep": "Paciente: {paciente}\nCita: {fecha_cita} a las {hora_cita}\n\nDieta líquida (texto del médico, ficticio).",
                                        "consent": "Yo, {paciente}, autorizo la {procedimiento}. Fecha {fecha_hoy}."})
    r = med.get(f"/pacientes/{pid}/hoja/prep/colonoscopia")
    t = pdf_text(r.data)
    assert r.status_code == 200 and "INDICACIONES DE PREPARACIÓN" in t and "Dieta líquida (texto del médico, ficticio)." in t
    assert "{paciente}" not in t and "__________" in t           # sin cita: fecha en blanco para llenar a mano
    assert "colonoscopia" in pdf_text(med.get(f"/pacientes/{pid}/hoja/consent/colonoscopia").data)
    assert "Hojas para el paciente" in med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    # recepción puede imprimir la preparación pero no el consentimiento
    rec = login(env["app"], "recepcion")
    assert rec.get(f"/pacientes/{pid}/hoja/prep/colonoscopia").status_code == 200
    assert rec.get(f"/pacientes/{pid}/hoja/consent/colonoscopia").status_code == 403
    assert med.get(f"/pacientes/{pid}/hoja/otra/colonoscopia").status_code == 404


def _appt(env, c, tok, pid, when="2026-11-03T09:00"):
    r = c.post("/agenda/nueva", data={"csrf_token": tok, "patient_id": pid, "practitioner_id": env["users"]["propietario"],
                                      "appt_type": "seguimiento", "starts_local": when, "duration": "30"})
    assert r.status_code == 302, r.get_data(as_text=True)[:400]
    return env["db"].execute("SELECT id FROM appointments WHERE patient_id = ? ORDER BY rowid DESC LIMIT 1", (pid,)).fetchone()["id"]


def test_sala_de_espera_preconsulta_atender_y_atendida(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    aid = _appt(env, med, tok, pid)
    v = lambda: env["db"].execute("SELECT version FROM appointments WHERE id = ?", (aid,)).fetchone()["version"]
    med.post(f"/agenda/cita/{aid}/estado", data={"csrf_token": tok, "status": "presente", "version": v()})
    day = med.get("/agenda/?fecha=2026-11-03").get_data(as_text=True)
    assert "Sala de espera" in day and "Atender →" in day and "Signos vitales" in day
    # enfermería registra la preconsulta
    enf = login(env["app"], "enfermeria")
    etok = csrf(enf)
    r = enf.post(f"/agenda/cita/{aid}/preconsulta", data={"csrf_token": etok, "v_pa_sistolica": "120", "v_pa_diastolica": "80",
                                                          "v_peso_kg": "70", "motivo": "Ardor en el estómago (ficticio)"})
    assert r.status_code == 302
    bad = enf.post(f"/agenda/cita/{aid}/preconsulta", data={"csrf_token": etok, "v_fc": "999"})
    assert bad.status_code == 422
    assert "✓ Preconsulta" in med.get("/agenda/?fecha=2026-11-03").get_data(as_text=True)
    assert login(env["app"], "recepcion").get(f"/agenda/cita/{aid}/preconsulta").status_code == 403
    # Atender: crea la nota directamente con signos vitales y motivo
    r = med.post(f"/agenda/cita/{aid}/estado", data={"csrf_token": tok, "status": "en_consulta", "version": v()})
    r = med.get(r.headers["Location"])
    assert r.status_code == 302 and "/notas/" in r.headers["Location"] and "nueva" not in r.headers["Location"]
    nid = r.headers["Location"].rsplit("/", 1)[-1]
    f = json.loads(env["db"].execute("SELECT fields FROM clinical_notes WHERE id = ?", (nid,)).fetchone()["fields"])
    assert f["vitales"]["pa_sistolica"] == 120 and f["vitales"]["peso_kg"] == 70 and f["motivo"] == "Ardor en el estómago (ficticio)"
    # al finalizar la nota la cita pasa a atendida
    nv = env["db"].execute("SELECT version FROM clinical_notes WHERE id = ?", (nid,)).fetchone()["version"]
    med.post(f"/notas/{nid}/finalizar", data={"csrf_token": tok, "version": nv})
    assert env["db"].execute("SELECT status FROM clinical_notes WHERE id = ?", (nid,)).fetchone()["status"] == "finalizada"
    assert env["db"].execute("SELECT status FROM appointments WHERE id = ?", (aid,)).fetchone()["status"] == "atendida"


def test_hoja_con_fecha_y_hora_de_la_cita(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    aid = _appt(env, med, tok, pid, "2026-11-10T07:30")
    med.post("/endoscopia/hojas", data={"csrf_token": tok, "tipo": "eda", "prep": "Cita: {fecha_cita} a las {hora_cita}.", "consent": "x {paciente}"})
    t = pdf_text(med.get(f"/pacientes/{pid}/hoja/prep/eda?cita={aid}").data)
    assert "10 de noviembre de 2026" in t and "7:30 a. m." in t, t
    assert "Hojas para el paciente" in med.get(f"/agenda/cita/{aid}").get_data(as_text=True)


def test_imprimir_todo_une_receta_orden_y_documento(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                   ).headers["Location"].rsplit("/", 1)[-1]
    assert "Imprimir todo" not in med.get(f"/notas/{nid}").get_data(as_text=True)
    assert med.get(f"/notas/{nid}/imprimir-todo").status_code == 409
    r = med.post("/recetas/nueva", data={"csrf_token": tok, "patient_id": pid, "note_id": nid, "ack_allergies": "1",
                                         "item-0-active_ingredient": "Omeprazol", "item-0-dose": "20", "item-0-dose_unit": "mg",
                                         "item-0-route": "oral", "item-0-frequency": "cada 24 h", "item-0-duration": "8 semanas",
                                         "item-0-quantity": "56 cápsulas"})
    assert r.status_code == 302, r.get_data(as_text=True)[:300]
    r = med.post("/ordenes/nueva", data={"csrf_token": tok, "patient_id": pid, "note_id": nid, "order_type": "laboratorio",
                                         "lab": "ferritina", "priority": "rutina", "responsible_id": env["users"]["propietario"]})
    assert r.status_code == 302
    med.post(f"/pacientes/{pid}/documentos/nuevo", data={"csrf_token": tok, "kind": "constancia", "step": "emitir",
                                                         "body": "Constancia de atención (ficticio).", "final_title": "CONSTANCIA DE ATENCIÓN MÉDICA"})
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "1 receta(s), 1 orden(es) y 1 documento(s)" in html
    r = med.get(f"/notas/{nid}/imprimir-todo?papel=carta")
    t = pdf_text(r.data)
    assert r.status_code == 200 and "Omeprazol" in t and "Ferritina" in t and "Constancia de atención (ficticio)." in t
    assert len(PdfReader(io.BytesIO(r.data)).pages) >= 3


def test_resumen_del_paciente_y_calculos_rapidos(env):
    from app import calculators as C
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med, birth_date="1966-05-01")
    for day, vals in (("2026-09-01", {"ast": "40", "alt": "30", "plt": "150"}), ("2026-10-20", {"ast": "80", "alt": "60", "plt": "120"})):
        r = med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": day, "code": list(vals),
                                                                      **{f"v_{k}": v for k, v in vals.items()}})
        assert r.status_code == 302
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": "2026-10-20", "code": ["bt", "inr"],
                                                              "v_bt": "2", "v_inr": "1.5"})
    html = med.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert "Resumen" in html and "Últimos laboratorios" in html and "Cálculos con los últimos laboratorios" in html
    assert "↑" in html                                   # AST subió de 40 a 80
    # FIB-4 se puede calcular solo con el expediente; Child-Pugh pide datos clínicos y no los supone
    from app.patient_summary import summary
    with env["app"].test_request_context():
        p = env["db"].execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone()
        s = summary(env["db"], p)
    calcs = {c["code"]: c for c in s["calcs"]}
    expected = C.run(C.BY_CODE["fib4"], {"edad": "60", "ast": "80", "alt": "60", "plt": "120"})["texto"]
    assert calcs["fib4"]["preview"] == expected and not calcs["fib4"]["missing"]
    assert "Child-Pugh" == calcs["child_pugh"]["name"] and calcs["child_pugh"]["preview"] is None and calcs["child_pugh"]["missing"]
    assert any("Albúmina" in m for m in calcs["child_pugh"]["missing"])
    assert "Nada pendiente." in html or "por revisar" in html
