"""Fase 2: órdenes, resultados, tendencias, pendientes, tareas, formularios GI, diario y calculadoras."""
import io
import json
import re
import sqlite3

import pytest
from pypdf import PdfReader

from conftest import create_patient, csrf, login
from app import calculators as C


# ------------------------------------------------------------------------------------------------ calculadoras
@pytest.mark.parametrize("calc", C.ALL, ids=[c.code for c in C.ALL])
def test_casos_de_referencia(calc):
    for inp, expected, res, ok in C.self_check(calc):
        assert ok, (calc.code, inp, expected, {k: res.get(k) for k in expected})


@pytest.mark.parametrize("calc", C.ALL, ids=[c.code for c in C.ALL])
def test_cada_calculadora_documentada(calc):
    for attr in ("source", "verified_against", "population", "formula", "rounding", "missing", "limitations"):
        assert getattr(calc, attr), (calc.code, attr)
    assert len(calc.reference_cases) >= 2


def test_datos_ausentes_no_se_calcula():
    with pytest.raises(C.MissingData):
        C.run(C.MELD_NA, {"creat": "1", "bt": "1", "inr": "1"})           # falta sodio
    with pytest.raises(C.MissingData):
        C.run(C.FIB4, {"edad": "50", "ast": "40", "alt": "abc", "plt": "200"})
    with pytest.raises(C.MissingData):
        C.run(C.CHILD, {"bt": "1", "alb": "4", "inr": "1", "ascitis": "ausente", "encefalopatia": "otra"})
    with pytest.raises(C.MissingData):                                  # fuera de rango plausible (¿unidad errónea?)
        C.run(C.MELD3, {"sexo": "masculino", "bt": "1", "na": "137", "inr": "1", "creat": "1", "alb": "35"})


def test_meld_na_y_meld3_diferenciados():
    inp = {"sexo": "femenino", "creat": "2", "bt": "3", "inr": "1.5", "na": "130", "alb": "2.8"}
    a, b = C.run(C.MELD_NA, inp), C.run(C.MELD3, inp)
    assert a["texto"].startswith("MELD-Na") and b["texto"].startswith("MELD 3.0")
    assert C.MELD_NA.version != C.MELD3.version


def test_rockall_clinico_vs_completo():
    a = C.run(C.ROCKALL, {"edad": "70", "choque": "no", "comorbilidad": "ninguna"})
    b = C.run(C.ROCKALL, {"edad": "70", "choque": "no", "comorbilidad": "ninguna", "diagnostico": "otros", "estigmas": "ninguno"})
    assert a["tipo"] == "clinico" and "pre-endoscópico" in a["texto"] and b["tipo"] == "completo"


# ------------------------------------------------------------------------------------------------ flujo de laboratorio
def _order(med, pid, tok, tests=("bt", "alb", "inr")):
    r = med.post("/ordenes/nueva", data={"csrf_token": tok, "patient_id": pid, "order_type": "laboratorio", "tests": list(tests),
                                         "priority": "rutina", "responsible_id": med.uid, "indication": "Control de cirrosis (ficticio)"})
    assert r.status_code == 302, r.get_data(as_text=True)[:500]
    return r.headers["Location"].split("/")[-1]


def test_orden_resultados_tendencia_y_revision(env):
    med = login(env["app"], "propietario")
    med.uid = env["users"]["propietario"]
    pid = create_patient(med)
    tok = csrf(med)
    oid = _order(med, pid, tok)
    # PDF de la orden
    r = med.get(f"/ordenes/{oid}/pdf")
    assert r.status_code == 200 and "Bilirrubina total" in PdfReader(io.BytesIO(r.data)).pages[0].extract_text()
    # Resultado parcial
    r = med.post(f"/pacientes/{pid}/laboratorio/registrar", data={
        "csrf_token": tok, "order_id": oid, "taken_on": "2026-10-01", "laboratory": "Lab demo",
        "code": ["bt", "alb", "inr"], "v_bt": "2.5", "lo_bt": "0.2", "hi_bt": "1.2", "u_bt": "mg/dL"})
    assert r.status_code == 302
    db = env["db"]
    assert db.execute("SELECT status FROM orders WHERE id = ?", (oid,)).fetchone()[0] == "resultado_parcial"
    row = db.execute("SELECT * FROM lab_results WHERE test_code = 'bt'").fetchone()
    assert row["flag"] == "alto" and row["status"] == "pendiente_revision"
    # Completar la orden
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "order_id": oid, "taken_on": "2026-10-01",
                                                              "code": ["alb", "inr"], "v_alb": "3.1", "v_inr": "1.4"})
    assert db.execute("SELECT status FROM orders WHERE id = ?", (oid,)).fetchone()[0] == "resultado_recibido"
    # Segunda toma para tendencia
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": "2026-10-20", "code": ["bt"],
                                                              "v_bt": "1,8", "lo_bt": "0.2", "hi_bt": "1.2"})
    html = med.get(f"/pacientes/{pid}/laboratorio?prueba=bt").get_data(as_text=True)
    assert "<svg class=\"trend\"" in html and "1.8" in html and "2.5" in html
    # Pendientes y revisión con comunicación
    page = med.get("/pendientes").get_data(as_text=True)
    assert page.count('name="result_id"') == 4
    ids = [r["id"] for r in db.execute("SELECT id FROM lab_results")]
    r = med.post("/resultados/revisar", data={"csrf_token": tok, "result_id": ids, "communicated": "1"})
    assert db.execute("SELECT COUNT(*) FROM lab_results WHERE status = 'revisado'").fetchone()[0] == 0  # falta el medio
    med.post("/resultados/revisar", data={"csrf_token": tok, "result_id": ids, "communicated": "1", "communication": "En consulta"})
    assert db.execute("SELECT COUNT(*) FROM lab_results WHERE status = 'revisado' AND communication = 'En consulta'").fetchone()[0] == 4
    # El valor no se puede modificar en la base de datos
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE lab_results SET value_num = 1 WHERE id = ?", (ids[0],))


def test_rango_no_se_inventa(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": "2026-10-01", "code": ["hb"], "v_hb": "9"})
    row = env["db"].execute("SELECT flag, ref_low, ref_high FROM lab_results").fetchone()
    assert row["flag"] == "sin_rango" and row["ref_low"] is None


def test_permisos_fase2(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    rec = login(env["app"], "recepcion")
    for url in [f"/pacientes/{pid}/laboratorio", f"/pacientes/{pid}/diario", f"/pacientes/{pid}/calculos", "/pendientes", "/calculadoras",
                f"/ordenes/nueva?patient_id={pid}"]:
        assert rec.get(url).status_code == 403, url
    enf = login(env["app"], "enfermeria")
    assert enf.get(f"/pacientes/{pid}/laboratorio/registrar").status_code == 200        # enfermería registra
    assert enf.get(f"/ordenes/nueva?patient_id={pid}").status_code == 403               # pero no ordena
    assert enf.post("/resultados/revisar", data={"csrf_token": csrf(enf), "result_id": "x" * 32}).status_code == 403
    otra = login(env["app"], "otra", email="otra@prueba.hn")
    assert otra.get(f"/pacientes/{pid}/laboratorio").status_code == 404


def test_tareas(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    r = med.post("/tareas/nueva", data={"csrf_token": tok, "title": "Llamar por resultado de biopsia", "patient_id": pid,
                                        "assigned_to": env["users"]["enfermeria"], "due_on": "2026-11-05"})
    assert r.status_code == 302
    enf = login(env["app"], "enfermeria")
    assert "Llamar por resultado de biopsia" in enf.get("/pendientes").get_data(as_text=True)
    tid = env["db"].execute("SELECT id FROM tasks").fetchone()[0]
    assert enf.post(f"/tareas/{tid}/completar", data={"csrf_token": csrf(enf)}).status_code == 302
    assert env["db"].execute("SELECT status FROM tasks").fetchone()[0] == "hecha"


# ------------------------------------------------------------------------------------------------ formularios y diario
def test_formulario_gi_en_nota_y_bloqueo(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}).headers["Location"].split("/")[-1]
    assert med.get(f"/notas/{nid}/formulario/diarrea").status_code == 200
    r = med.post(f"/notas/{nid}/formulario/diarrea", data={"csrf_token": tok, "tipo": "cronica", "duracion": "3-6m", "frecuencia": "5",
                                                           "bristol": "6", "caracteristicas": ["sangre", "nocturna", "invalida"],
                                                           "signos_alarma": ["perdida_peso"]})
    assert r.status_code == 302
    data = json.loads(env["db"].execute("SELECT data FROM clinical_forms").fetchone()[0])
    assert data["bristol"] == 6 and data["caracteristicas"] == ["sangre", "nocturna"]
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Diarrea aguda y crónica" in html and "Tipo 6" in html and "Pérdida de peso involuntaria" in html
    med.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "Diarrea"}, headers={"X-CSRF-Token": tok})
    med.post(f"/notas/{nid}/finalizar", data={"csrf_token": tok, "version": 2})
    assert med.post(f"/notas/{nid}/formulario/diarrea", data={"csrf_token": tok, "tipo": "aguda"}).status_code == 409
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("UPDATE clinical_forms SET data = '{}'")


def test_todos_los_formularios_cargan(env):
    from app.gi_forms import FORMS
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}).headers["Location"].split("/")[-1]
    assert len(FORMS) == 13
    for code in FORMS:
        assert med.get(f"/notas/{nid}/formulario/{code}").status_code == 200, code


def test_diario(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    for d, n, pain in [("2026-10-01", "6", "5"), ("2026-10-02", "4", "3"), ("2026-10-03", "2", "1")]:
        assert med.post(f"/pacientes/{pid}/diario", data={"csrf_token": tok, "entry_date": d, "stools": n, "bristol": "6", "pain": pain,
                                                          "blood": "1"}).status_code == 302
    html = med.get(f"/pacientes/{pid}/diario").get_data(as_text=True)
    assert html.count('<svg class="trend"') == 2


# ------------------------------------------------------------------------------------------------ calculadora con expediente
def test_calculadora_importa_con_fecha_y_exige_aprobacion(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med, sex="masculino", birth_date="1970-01-01")
    tok = csrf(med)
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": "2026-10-10",
                                                              "code": ["creat", "bt", "inr", "na"], "v_creat": "2", "v_bt": "3",
                                                              "v_inr": "1.5", "v_na": "130"})
    html = med.get(f"/calculadoras/meld_na?patient_id={pid}").get_data(as_text=True)
    assert 'value="2"' in html and "10/10/2026" in html and "Modo prueba" in html
    form = {"csrf_token": tok, "patient_id": pid, "creat": "2", "bt": "3", "inr": "1.5", "na": "130"}
    r = med.post("/calculadoras/meld_na", data=form)
    assert "MELD-Na 26" in r.get_data(as_text=True)
    assert med.post("/calculadoras/meld_na", data=dict(form, save="1", confirm_inputs="1")).status_code == 403   # no aprobada
    # Aprobación (solo propietario)
    col = login(env["app"], "medico")
    assert col.post("/calculadoras/meld_na/revision", data={"csrf_token": csrf(col), "confirm": "1"}).status_code == 403
    assert med.post("/calculadoras/meld_na/revision", data={"csrf_token": tok, "confirm": "1"}).status_code == 302
    r = med.post("/calculadoras/meld_na", data=dict(form, save="1"))
    assert "Confirme que revisó" in r.get_data(as_text=True)
    r = med.post("/calculadoras/meld_na", data=dict(form, save="1", confirm_inputs="1"))
    assert r.status_code == 302
    row = env["db"].execute("SELECT * FROM calc_results").fetchone()
    inputs = json.loads(row["inputs"])
    assert row["calc_version"] == "OPTN-2016" and json.loads(row["result"])["valor"] == 26
    assert inputs["creat"]["origen"] == "expediente (2026-10-10)"
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("DELETE FROM calc_results")
    assert "MELD-Na 26" in med.get(f"/pacientes/{pid}/calculos").get_data(as_text=True)


def test_pantallas_fase2_cargan(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    for url in ["/calculadoras", "/pendientes", "/pendientes?todos=1", f"/pacientes/{pid}/laboratorio",
                f"/pacientes/{pid}/laboratorio/registrar", f"/ordenes/nueva?patient_id={pid}&order_type=imagen",
                f"/ordenes/nueva?patient_id={pid}&order_type=endoscopia"] + \
               [f"/calculadoras/{c.code}" for c in C.ALL] + [f"/calculadoras/{c.code}/revision" for c in C.ALL] + \
               [f"/calculadoras/{c.code}?patient_id={pid}" for c in C.ALL]:
        assert med.get(url).status_code == 200, url
