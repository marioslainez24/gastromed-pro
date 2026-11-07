"""NeuroMed Pro 1.0: Código ACV (tiempos, ventanas, contraindicaciones, dosis) y su registro inmutable."""
import json
import sqlite3

import pytest
from werkzeug.datastructures import MultiDict

from app import acv as A
from conftest import create_patient, csrf, login


def data(**kw):
    d = A.empty()
    d.update(kw)
    return d


def test_ventana_y_contraindicaciones():
    ev = A.evaluate(data(lkw="08:00", arr="08:40", ct="08:55", pas=170, pad=95, glu=120), "09:30")
    assert ev["elapsed"] == 90 and ev["lysis"][0] == "ok" and "quedan 3 h 0 min" in ev["lysis"][2]
    assert ev["metrics"]["ct"] == 15
    assert A.evaluate(data(lkw="08:00"), "12:31")["lysis"][1].startswith("Fuera de la ventana")      # 271 min
    assert A.evaluate(data(lkw="08:00"), "12:30")["lysis"][0] == "ok"                               # 270 min: aún dentro
    assert A.evaluate(data(lkw="08:00", ci=["doac"]), "09:00")["lysis"][0] == "crit"
    assert A.evaluate(data(lkw="08:00", pas=190, pad=100), "09:00")["lysis"][1].startswith("Bajar la presión")
    assert A.evaluate(data(lkw="08:00", pas=180, pad=110), "09:00")["lysis"][1].startswith("Bajar la presión")
    assert A.evaluate(data(lkw="08:00", glu=45), "09:00")["lysis"][1].startswith("Hipoglucemia")
    assert A.evaluate(data(), "09:00")["lysis"][1].startswith("Falta la hora")
    assert A.evaluate(data(wake=True), "09:00")["lysis"][1].startswith("Inicio desconocido")
    assert A.evaluate(data(lkw="23:30"), "00:45")["elapsed"] == 75                                  # pasa la medianoche


def test_trombectomia():
    assert A.evaluate(data(lkw="08:00", lvo=True, aspects=8), "10:00")["evt"][0] == "crit"
    assert "ASPECTS 3 a 5" in A.evaluate(data(lkw="08:00", lvo=True, aspects=4), "10:00")["evt"][2]
    assert A.evaluate(data(lkw="08:00", lvo=True), "16:00")["evt"][1].startswith("Ventana tardía")
    assert A.evaluate(data(lkw="08:00", lvo=True, prem=3), "09:00")["evt"][1].startswith("Oclusión de gran vaso con discapacidad")
    assert A.evaluate(data(lkw="08:00"), "09:00")["evt"][0] == "ok"


def test_dosis_por_peso_con_maximos():
    assert A.dose(data(w=74, agent="tnk"))["total_mg"] == 18.5
    assert A.dose(data(w=120, agent="tnk"))["total_mg"] == 25.0
    d = A.dose(data(w=70, agent="tpa"))
    assert d["total_mg"] == 63.0 and d["bolo_mg"] == 6.3 and "56.7 mg en infusión de 60 minutos" in d["texto"]
    assert A.dose(data(w=110, agent="tpa"))["total_mg"] == 90.0
    assert A.dose(data()) is None


def test_limpieza_del_formulario():
    d, err = A.clean(MultiDict([("lkw", "25:00"), ("pas", "500"), ("ci", "doac"), ("ci", "inventada"), ("agent", "otro"), ("w", "70,5")]))
    assert d["lkw"] == "" and d["pas"] == "" and len(err) == 2 and d["ci"] == ["doac"] and d["agent"] == "tnk" and d["w"] == 70.5


def test_codigo_acv_de_punta_a_punta(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    assert "Código ACV" in med.get(f"/pacientes/{pid}").get_data(as_text=True)
    r = med.post(f"/pacientes/{pid}/codigo-acv/nuevo", data={"csrf_token": tok})
    assert r.status_code == 302
    cid = r.headers["Location"].rsplit("/", 1)[-1]
    row = env["db"].execute("SELECT * FROM stroke_codes WHERE id = ?", (cid,)).fetchone()
    assert row["status"] == "borrador" and json.loads(row["data"])["arr"]                     # hora de llegada anotada
    html = med.get(f"/codigo-acv/{cid}").get_data(as_text=True)
    assert "Trombólisis intravenosa" in html and "Falta la hora del último momento visto bien" in html
    form = {"csrf_token": tok, "version": row["version"], "lkw": "08:00", "arr": "08:30", "ct": "08:45", "pas": "160", "pad": "90",
            "glu": "110", "nihss": "9", "w": "80", "agent": "tnk", "lvo": "1", "aspects": "8", "prem": "0", "notes": "Testigo: esposa (ficticio)",
            "action": "guardar"}
    assert med.post(f"/codigo-acv/{cid}", data=form).status_code == 302
    html = med.get(f"/codigo-acv/{cid}").get_data(as_text=True)
    assert "Tenecteplasa 20.0 mg" in html and "Puerta–TAC" in html and "15 min" in html
    # versión vieja: no pisa lo guardado
    assert med.post(f"/codigo-acv/{cid}", data=dict(form, nihss="20")).status_code == 302
    assert json.loads(env["db"].execute("SELECT data FROM stroke_codes WHERE id = ?", (cid,)).fetchone()[0])["nihss"] == 9
    v = env["db"].execute("SELECT version FROM stroke_codes WHERE id = ?", (cid,)).fetchone()[0]
    assert med.post(f"/codigo-acv/{cid}", data=dict(form, version=v, needle="09:10", action="finalizar")).status_code == 302
    row = env["db"].execute("SELECT * FROM stroke_codes WHERE id = ?", (cid,)).fetchone()
    assert row["status"] == "finalizado" and "Tenecteplasa iniciada a las 09:10 (puerta-aguja 40 min)" in row["summary"]
    assert "Testigo: esposa (ficticio)" in row["summary"]
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("UPDATE stroke_codes SET summary = 'x' WHERE id = ?", (cid,))
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("DELETE FROM stroke_codes WHERE id = ?", (cid,))
    assert med.post(f"/codigo-acv/{cid}", data=dict(form, version=row["version"])).status_code == 403
    assert "Finalizado" in med.get("/codigo-acv").get_data(as_text=True)
    assert "Código ACV" in med.get(f"/pacientes/{pid}").get_data(as_text=True)
    # recepción no puede iniciar ni ver datos clínicos
    rec = login(env["app"], "recepcion")
    assert rec.post(f"/pacientes/{pid}/codigo-acv/nuevo", data={"csrf_token": csrf(rec)}).status_code == 403
    assert rec.get(f"/codigo-acv/{cid}").status_code == 403
