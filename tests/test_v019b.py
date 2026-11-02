"""v0.19.0: recetas frecuentes, repetir receta, partir del estudio anterior, estadísticas y búsqueda en expedientes."""
import json

from conftest import create_patient, csrf, login

ITEM = {"item-0-active_ingredient": "omeprazol", "item-0-presentation": "cápsulas de 20 mg", "item-0-dose": "20", "item-0-dose_unit": "mg",
        "item-0-route": "oral", "item-0-frequency": "cada 24 horas", "item-0-duration": "8 semanas", "item-0-quantity": "56 cápsulas",
        "item-0-instructions": "antes del desayuno"}


def test_recetas_frecuentes_y_repetir(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    # crear una receta frecuente desde su pantalla
    assert med.post("/recetas/frecuentes", data={"csrf_token": tok, "name": "", **ITEM}).status_code == 422          # falta nombre
    r = med.post("/recetas/frecuentes", data={"csrf_token": tok, "name": "IBP 8 semanas", "general_instructions": "Dieta antirreflujo", **ITEM})
    assert r.status_code == 302
    assert med.post("/recetas/frecuentes", data={"csrf_token": tok, "name": "ibp 8 SEMANAS", **ITEM}).status_code == 422  # nombre repetido
    tid = env["db"].execute("SELECT id FROM rx_templates").fetchone()[0]
    pid = create_patient(med)
    html = med.get(f"/recetas/nueva?patient_id={pid}").get_data(as_text=True)
    assert "IBP 8 semanas" in html and "Repetir la receta anterior" not in html                            # sin receta previa
    html = med.get(f"/recetas/nueva?patient_id={pid}&frecuente={tid}").get_data(as_text=True)
    assert 'value="omeprazol"' in html and 'value="56 cápsulas"' in html and "Dieta antirreflujo" in html and "Revise dosis" in html
    # emitir y luego repetir
    med.post("/recetas/nueva", data={"csrf_token": tok, "patient_id": pid, "ack_allergies": "1", **ITEM,
                                     "item-0-active_ingredient": "esomeprazol"})
    html = med.get(f"/recetas/nueva?patient_id={pid}").get_data(as_text=True)
    assert "Repetir la receta anterior" in html and "esomeprazol" in html
    html = med.get(f"/recetas/nueva?patient_id={pid}&repetir=1").get_data(as_text=True)
    assert 'value="esomeprazol"' in html and "Receta anterior del paciente" in html
    # guardar una receta emitida como frecuente
    rx = env["db"].execute("SELECT id FROM prescriptions").fetchone()[0]
    med.post(f"/recetas/{rx}/guardar-frecuente", data={"csrf_token": tok, "name": "Esomeprazol"})
    names = [r[0] for r in env["db"].execute("SELECT name FROM rx_templates ORDER BY name")]
    assert names == ["Esomeprazol", "IBP 8 semanas"]
    # desactivar: deja de aparecer al recetar
    med.post(f"/recetas/frecuentes?id={tid}", data={"csrf_token": tok, "action": "desactivar"})
    assert "IBP 8 semanas" not in med.get(f"/recetas/nueva?patient_id={pid}").get_data(as_text=True)
    assert med.get(f"/recetas/nueva?patient_id={pid}&frecuente={tid}").status_code == 404
    # recepción no puede
    assert login(env["app"], "recepcion").get("/recetas/frecuentes").status_code == 403


def test_partir_del_estudio_anterior(env):
    from tests.test_fase3 import full_form, new_proc, version
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    first = new_proc(med, pid, tok, "colonoscopia")
    assert med.post(f"/procedimientos/{first}/copiar-anterior", data={"csrf_token": tok}).status_code == 404   # no hay anterior
    med.post(f"/procedimientos/{first}/guardar", data=full_form(tok, version(env, first), then="finalizar",
                                                                **{"nar-colon": "Pólipo sésil de 6 mm en sigmoides (ficticio).",
                                                                   "recommendations": "Colonoscopia de control en 3 años."}))
    med.post(f"/procedimientos/{first}/finalizar", data={"csrf_token": tok, "version": version(env, first)})
    db = env["db"]
    assert db.execute("SELECT status FROM procedures WHERE id = ?", (first,)).fetchone()[0] == "finalizado"
    old = json.loads(db.execute("SELECT data FROM procedures WHERE id = ?", (first,)).fetchone()[0])
    second = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{second}").get_data(as_text=True)
    assert "Partir del estudio anterior" in html and "Estudio anterior:" in html
    assert new_proc(med, pid, tok, "eda") and "Partir del estudio anterior" not in med.get(
        f"/procedimientos/{db.execute('SELECT id FROM procedures WHERE kind = ?', ('eda',)).fetchone()[0]}").get_data(as_text=True)  # otro tipo
    r = med.post(f"/procedimientos/{second}/copiar-anterior", data={"csrf_token": tok})
    assert r.status_code == 302
    new = json.loads(db.execute("SELECT data FROM procedures WHERE id = ?", (second,)).fetchone()[0])
    assert new["narrative"] == old["narrative"] and new["conclusion"] == old["conclusion"]
    assert new["recommendations"] == "Colonoscopia de control en 3 años." and new["copied_from"]["id"] == first
    assert new["jars"] == [] and not new.get("consent_obtained") and not new.get("indication")               # lo propio del estudio no se copia
    assert all(f["jar"] is None for f in new["findings"])
    assert "Este borrador ya parte de ese estudio" in med.get(f"/procedimientos/{second}").get_data(as_text=True)
    # el estudio anterior no cambió y otro médico no puede copiar en un borrador ajeno
    assert json.loads(db.execute("SELECT data FROM procedures WHERE id = ?", (first,)).fetchone()[0]) == old
    otro = login(env["app"], "medico")
    assert otro.post(f"/procedimientos/{second}/copiar-anterior", data={"csrf_token": csrf(otro)}).status_code == 409


def _finalize_note(env, med, tok, pid, dx, when="2026-10-15T15:00:00Z"):
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                   ).headers["Location"].rsplit("/", 1)[-1]
    db = env["db"]
    f = json.loads(db.execute("SELECT fields FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0])
    f.update({"motivo": "Control (ficticio)", "diagnosticos": dx})
    db.execute("UPDATE clinical_notes SET fields = ?, status = 'finalizada', finalized_at = ?, finalized_by = author_id WHERE id = ?",
               (json.dumps(f, ensure_ascii=False), when, nid))
    db.commit()
    return nid


def test_estadisticas_y_excel(env):
    import io
    import openpyxl
    from tests.test_fase3 import full_form, new_proc, version
    med = login(env["app"], "propietario")
    tok = csrf(med)
    p1, p2 = create_patient(med), create_patient(med, document_number="0801199000002", first_names="Segunda", phone="+504 9999-0002")
    _finalize_note(env, med, tok, p1, "- ERGE sin esofagitis (CIE-10 K21.9)\n- Dispepsia funcional")
    _finalize_note(env, med, tok, p2, "1. erge sin esofagitis (CIE-10 K21.9)")
    proc = new_proc(med, p1, tok, "colonoscopia")
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), then="finalizar", performed_on="2026-10-20"))
    med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    html = med.get("/estadisticas?desde=2026-01-01&hasta=2026-12-31").get_data(as_text=True)
    assert '<svg class="bars"' in html and "Diagnósticos de consulta más frecuentes" in html
    assert "ERGE sin esofagitis (CIE-10 K21.9)</span><b>2</b>" in html          # agrupado sin distinguir mayúsculas ni viñetas
    assert "Tasa de detección de adenomas" in html
    r = med.get("/estadisticas/excel?desde=2026-01-01&hasta=2026-12-31")
    assert r.status_code == 200 and r.headers["Content-Type"].startswith("application/vnd.openxmlformats")
    wb = openpyxl.load_workbook(io.BytesIO(r.data))
    assert wb.sheetnames == ["Por mes", "Diagnósticos de consulta", "Diagnósticos endoscópicos", "Calidad colonoscopia", "Información"]
    oct_row = [row for row in wb["Por mes"].iter_rows(values_only=True) if row[0] == "2026-10"][0]
    assert oct_row[1] == 2 and oct_row[4] == 1                                  # 2 consultas y 1 colonoscopia en octubre
    texto = " ".join(str(c) for ws in wb for row in ws.iter_rows(values_only=True) for c in row if c is not None)
    assert "De Prueba" not in texto and "GM-" not in texto                        # sin datos de pacientes
    assert med.get("/estadisticas?desde=2026-12-31&hasta=2026-01-01").status_code == 400
    assert login(env["app"], "recepcion").get("/estadisticas").status_code == 403


def test_buscar_en_todos_los_expedientes(env):
    from tests.test_fase3 import full_form, new_proc, version
    med = login(env["app"], "propietario")
    tok = csrf(med)
    p1, p2, p3 = create_patient(med), create_patient(med, document_number="0801199000002", first_names="Segunda", phone="+504 9999-0002"), create_patient(med, document_number="0801199000003", first_names="Tercera", phone="+504 9999-0003")
    _finalize_note(env, med, tok, p1, "Esófago de Barrett corto")
    proc = new_proc(med, p2, tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), then="finalizar", performed_on="2025-01-10",
                                                               extent="segunda_porcion", **{"find-0-segment": "Esófago distal",
                                                                                            "find-1-segment": "Antro"},
                                                               conclusion="Esofago de BARRETT (Praga C1 M3), pendiente de histología",
                                                               surveillance_due="2026-01-10"))
    med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert env["db"].execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "finalizado"
    _finalize_note(env, med, tok, p3, "Colitis ulcerosa")
    html = med.get("/buscar-expedientes?q=barrett").get_data(as_text=True)
    assert "<b>2</b> paciente(s)" in html and "Vencido" in html                 # sin tildes ni mayúsculas; control vencido
    assert html.index(p2) < html.index(p1)                                         # primero el control vencido
    assert "Colitis ulcerosa" not in html
    assert "<b>1</b> paciente(s)" in med.get("/buscar-expedientes?q=barrett praga").get_data(as_text=True)   # todas las palabras
    assert "Escriba al menos 3 letras" in med.get("/buscar-expedientes?q=ba").get_data(as_text=True)
    assert login(env["app"], "recepcion").get("/buscar-expedientes?q=barrett").status_code == 403
    # otra clínica no ve nada
    assert "<b>0</b> paciente(s)" in login(env["app"], "otra", email="otra@prueba.hn").get("/buscar-expedientes?q=barrett").get_data(as_text=True)


def test_esquema_anatomico_marcas_pantalla_y_pdf(env):
    import io
    from pypdf import PdfReader
    from tests.test_fase3 import full_form, new_proc, version
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Esquema anatómico" in html and 'data-seg="Sigmoides"' in html and "data-anat" in html
    marks = {"mark-0-x": "200", "mark-0-y": "252", "mark-0-seg": "Sigmoides", "mark-0-kind": "reseccion", "mark-0-label": "Pólipo 6 mm",
             "mark-0-jar": "1",
             "mark-1-x": "76", "mark-1-y": "200", "mark-1-seg": "Colon ascendente", "mark-1-kind": "biopsia",
             "mark-2-x": "999", "mark-2-y": "10", "mark-2-seg": "Recto",                                     # fuera del dibujo: se ignora
             "mark-3-x": "50", "mark-3-y": "50", "mark-3-seg": "Antro"}                                       # no es del colon: se ignora
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), **marks))
    d = json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert [(m["seg"], m["kind"], m["jar"]) for m in d["marks"]] == [("Sigmoides", "reseccion", 1), ("Colon ascendente", "biopsia", None)]
    # frasco inexistente: aviso
    r = med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), **{**marks, "mark-0-jar": "7"}), follow_redirects=True)
    assert "menciona el frasco 7" in r.get_data(as_text=True)
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), **marks))
    pdf = med.get(f"/procedimientos/{proc}/pdf?papel=carta")
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf.data)).pages)
    assert "Esquema anatómico" in text and "Pólipo 6 mm" in text and "Colon ascendente" in text
    # rectosigmoidoscopia usa el nombre de su segmento
    rs = new_proc(med, pid, tok, "rectosigmoidoscopia")
    assert 'data-seg="Colon descendente distal"' in med.get(f"/procedimientos/{rs}").get_data(as_text=True)
    # CPRE no tiene esquema
    cp = new_proc(med, pid, tok, "cpre")
    assert "Esquema anatómico" not in med.get(f"/procedimientos/{cp}").get_data(as_text=True)
