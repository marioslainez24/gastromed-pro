"""v0.12.0: asistente que redacta la historia de la enfermedad actual con lo marcado por el médico (sin inventar)."""
import json

from werkzeug.datastructures import MultiDict

from app.gi_forms import FORMS
from app.hea import compose
from conftest import create_patient, csrf, login

F45 = {"sex": "femenino", "age": "45 años"}


def test_redaccion_cefalea():
    t, data, err = compose("cefalea", MultiDict([("hea_tiempo", "3"), ("hea_unidad", "meses"), ("evolucion", "intermitente"),
                                                 ("localizacion", "hemicraneal_der"), ("localizacion", "periorbitaria"), ("caracter", "pulsatil"),
                                                 ("intensidad", "7"), ("duracion_crisis", "horas"), ("acompanantes", "nausea")]), F45)
    assert t.startswith("Paciente femenina de 45 años que consulta por cefalea de 3 meses de evolución, de curso intermitente.")
    assert "Localización: hemicraneal derecha y periorbitaria." in t and "De carácter pulsátil." in t and "Intensidad 7/10." in t
    assert "Cada episodio dura de 4 a 72 horas." in t and "Se acompaña de náusea." in t
    assert "Niega" not in t and "alarma" not in t            # no escribe negativos si el médico no lo indica
    assert err == [] and data["localizacion"] == ["hemicraneal_der", "periorbitaria"]


def test_negativos_solo_si_el_medico_lo_marca_y_alarmas_presentes():
    base = [("caracter", "opresivo"), ("signos_alarma", "fiebre")]
    t, _, _ = compose("cefalea", MultiDict(base), {"sex": "masculino", "age": "60 años"})
    assert "Signos de alarma: fiebre" in t and "Niega" not in t
    t, _, _ = compose("cefalea", MultiDict(base + [("hea_niega", "1")]), {"sex": "masculino", "age": "60 años"})
    assert "Niega los demás signos de alarma interrogados: inicio súbito" in t and "fiebre" not in t.split("Niega")[1]
    t, _, _ = compose("cefalea", MultiDict([("hea_niega", "1")]), F45)
    assert "Niega inicio súbito" in t


def test_no_inventa_nada_con_formulario_vacio_y_todos_los_motivos_funcionan():
    for code in FORMS:
        t, data, err = compose(code, MultiDict(), {"sex": "no_registrado", "age": "—"})
        assert t.startswith("Paciente que consulta por") and t.count(".") == 1 and data == {}, (code, t)
    # valores falsos se descartan
    t, data, _ = compose("crisis", MultiDict([("postictal", "inventado"), ("testigo", "si")]), F45)
    assert "inventado" not in t and "Los eventos fueron presenciados por un testigo." in t and "postictal" not in data
    # tiempo exacto y singular
    t, _, _ = compose("mareo", MultiDict([("hea_tiempo", "1"), ("hea_unidad", "semanas"), ("tipo", "vertigo")]), F45)
    assert "de 1 semana de evolución" in t and "Describe vértigo" in t


def test_asistente_en_la_nota_redacta_y_guarda_formulario(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    r = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"})
    nid = r.headers["Location"].rsplit("/", 1)[-1]
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Asistente de historia" in html and 'form="hea-form"' in html and 'id="hea-form"' in html
    assert 'name="plan"' in html and 'name="diferenciales"' not in html   # campos de la nota (v0.15: un solo plan)
    r = med.post(f"/notas/{nid}/historia", data={"csrf_token": tok, "hx-motivo": "crisis", "hx-crisis-frecuencia": "2 al mes",
                                                 "hx-crisis-tipo": ["tcg", "ausencias"], "hx-cefalea-intensidad": "9"},
                 headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200, r.get_data(as_text=True)
    t = r.get_json()["texto"]
    assert "consulta por crisis epilépticas" in t and "Frecuencia: 2 al mes." in t and "tónico-clónica generalizada y ausencias" in t
    assert "9" not in t                              # campos de otro motivo no se mezclan
    row = env["db"].execute("SELECT form_code, data FROM clinical_forms WHERE note_id = ?", (nid,)).fetchone()
    assert row["form_code"] == "crisis" and json.loads(row["data"])["frecuencia"] == "2 al mes"
    assert med.post(f"/notas/{nid}/historia", data={"csrf_token": tok}).status_code == 422
    # otro usuario no puede usarlo sobre esta nota
    assert login(env["app"], "recepcion").post(f"/notas/{nid}/historia", data={"csrf_token": tok, "hx-motivo": "cefalea"}).status_code in (403, 400)
