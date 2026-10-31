"""v0.12.0: asistente que redacta la historia de la enfermedad actual con lo marcado por el médico (sin inventar)."""
import json

from werkzeug.datastructures import MultiDict

from app.gi_forms import FORMS
from app.hea import compose
from conftest import create_patient, csrf, login

F45 = {"sex": "femenino", "age": "45 años"}


def test_redaccion_dolor_abdominal():
    t, data, err = compose("dolor_abdominal", MultiDict([("hea_tiempo", "3"), ("hea_unidad", "meses"), ("evolucion", "intermitente"),
                                                         ("localizacion", "epigastrio"), ("localizacion", "hipocondrio_der"), ("caracter", "colico"),
                                                         ("intensidad", "7"), ("relacion_comidas", "empeora"), ("acompanantes", "nausea")]), F45)
    assert t.startswith("Paciente femenina de 45 años que consulta por dolor abdominal de 3 meses de evolución, de curso intermitente.")
    assert "El dolor se localiza en epigastrio y hipocondrio derecho." in t and "Es de carácter cólico." in t and "Intensidad 7/10." in t
    assert "Empeora al comer." in t and "Se acompaña de náusea." in t
    assert "Niega" not in t and "alarma" not in t            # no escribe negativos si el médico no lo indica
    assert err == [] and data["localizacion"] == ["epigastrio", "hipocondrio_der"]


def test_negativos_solo_si_el_medico_lo_marca_y_alarmas_presentes():
    base = [("sintomas", "pirosis"), ("signos_alarma", "sangrado")]
    t, _, _ = compose("reflujo_dispepsia", MultiDict(base), {"sex": "masculino", "age": "60 años"})
    assert "Signos de alarma: sangrado digestivo" in t and "Niega" not in t
    t, _, _ = compose("reflujo_dispepsia", MultiDict(base + [("hea_niega", "1")]), {"sex": "masculino", "age": "60 años"})
    assert "Niega los demás signos de alarma interrogados: pérdida de peso involuntaria" in t and "sangrado digestivo (hema" not in t.split("Niega")[1]
    t, _, _ = compose("reflujo_dispepsia", MultiDict([("hea_niega", "1")]), F45)
    assert "Niega pérdida de peso involuntaria" in t


def test_no_inventa_nada_con_formulario_vacio_y_todos_los_motivos_funcionan():
    for code in FORMS:
        t, data, err = compose(code, MultiDict(), {"sex": "no_registrado", "age": "—"})
        assert t.startswith("Paciente que consulta por") and t.count(".") == 1 and data == {}, (code, t)
    # valores falsos se descartan
    t, data, _ = compose("disfagia", MultiDict([("tipo", "inventado"), ("odinofagia", "si")]), F45)
    assert "inventado" not in t and "Refiere odinofagia." in t and "tipo" not in data
    # tiempo exacto y singular
    t, _, _ = compose("diarrea", MultiDict([("hea_tiempo", "1"), ("hea_unidad", "semanas"), ("bristol", "6")]), F45)
    assert "de 1 semana de evolución" in t and "tipo 6 de Bristol" in t


def test_asistente_en_la_nota_redacta_y_guarda_formulario(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    r = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"})
    nid = r.headers["Location"].rsplit("/", 1)[-1]
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Asistente de historia" in html and 'form="hea-form"' in html and 'id="hea-form"' in html
    assert 'name="signos_alarma"' in html          # el campo de la nota sigue intacto
    r = med.post(f"/notas/{nid}/historia", data={"csrf_token": tok, "hx-motivo": "estrenimiento", "hx-estrenimiento-frecuencia": "2",
                                                 "hx-estrenimiento-sintomas": ["esfuerzo", "incompleta"], "hx-diarrea-frecuencia": "9"},
                 headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200, r.get_data(as_text=True)
    t = r.get_json()["texto"]
    assert "consulta por estreñimiento" in t and "Presenta 2 evacuaciones por semana." in t and "esfuerzo excesivo" in t
    assert "9" not in t                              # campos de otro motivo no se mezclan
    row = env["db"].execute("SELECT form_code, data FROM clinical_forms WHERE note_id = ?", (nid,)).fetchone()
    assert row["form_code"] == "estrenimiento" and json.loads(row["data"])["frecuencia"] == 2
    assert med.post(f"/notas/{nid}/historia", data={"csrf_token": tok}).status_code == 422
    # otro usuario no puede usarlo sobre esta nota
    assert login(env["app"], "recepcion").post(f"/notas/{nid}/historia", data={"csrf_token": tok, "hx-motivo": "diarrea"}).status_code in (403, 400)
