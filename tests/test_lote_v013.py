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
