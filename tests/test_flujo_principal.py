"""Pruebas de aceptación del primer flujo: sesión → paciente → cita → nota → receta PDF."""
import io
import re
import sqlite3
import threading

import pytest
from pypdf import PdfReader

from conftest import PASSWORDS, create_patient, csrf, login


def test_login_correcto_e_incorrecto(env):
    app = env["app"]
    c = app.test_client()
    page = c.get("/ingresar").get_data(as_text=True)
    tok = re.search(r'name="login_csrf" value="([^"]+)"', page).group(1)
    bad = c.post("/ingresar", data={"login_csrf": tok, "email": "propietario@prueba.hn", "password": "incorrecta"})
    assert bad.status_code == 401 and "incorrectos" in bad.get_data(as_text=True)
    assert c.get("/agenda/").status_code == 302  # sin sesión → redirige a ingresar
    login(app, "propietario")


def test_bloqueo_tras_intentos_fallidos(env):
    app = env["app"]
    c = app.test_client()
    for _ in range(env["cfg"].LOGIN_MAX_FAILURES):
        page = c.get("/ingresar").get_data(as_text=True)
        tok = re.search(r'name="login_csrf" value="([^"]+)"', page).group(1)
        c.post("/ingresar", data={"login_csrf": tok, "email": "recepcion@prueba.hn", "password": "mala"})
    page = c.get("/ingresar").get_data(as_text=True)
    tok = re.search(r'name="login_csrf" value="([^"]+)"', page).group(1)
    r = c.post("/ingresar", data={"login_csrf": tok, "email": "recepcion@prueba.hn", "password": PASSWORDS["recepcion"]})
    assert r.status_code == 401, "con la cuenta bloqueada ni la contraseña correcta debe entrar"


def test_csrf_obligatorio(env):
    c = login(env["app"], "propietario")
    r = c.post("/pacientes/nuevo", data={"first_names": "X", "last_names": "Y", "sex": "femenino", "document_type": "sin_documento"})
    assert r.status_code == 400


def test_paciente_visible_desde_otro_dispositivo_y_busqueda(env):
    app = env["app"]
    pc = login(app, "recepcion")
    pid = create_patient(pc, first_names="Josefína", last_names="Núñez Ávila")
    celular = login(app, "propietario")  # otra sesión independiente = otro dispositivo
    for q in ["josefina", "NUNEZ", "0801-1980", "GM-000001", "99990000"]:
        r = celular.get("/pacientes/", query_string={"q": q})
        assert pid in r.get_data(as_text=True), q
    j = celular.get("/pacientes/", query_string={"q": "avila", "formato": "json"}).get_json()
    assert j["resultados"][0]["id"] == pid


def test_deteccion_de_duplicados(env):
    c = login(env["app"], "propietario")
    create_patient(c)
    # Mismo documento → bloqueado
    r = c.post("/pacientes/nuevo", data={"csrf_token": csrf(c), "first_names": "Otro", "last_names": "Nombre", "sex": "masculino",
                                         "document_type": "dni", "document_number": "0801-1980-00001"})
    assert r.status_code == 422 and "Ya existe" in r.get_data(as_text=True)
    # Mismo nombre y fecha sin documento → advertencia que exige confirmación
    data = {"csrf_token": csrf(c), "first_names": "Paciente", "last_names": "De Prueba", "birth_date": "1980-05-10",
            "sex": "femenino", "document_type": "sin_documento"}
    r = c.post("/pacientes/nuevo", data=data)
    assert r.status_code == 409 and "Posible paciente duplicado" in r.get_data(as_text=True)
    r = c.post("/pacientes/nuevo", data=dict(data, confirmo_distinto="1"))
    assert r.status_code == 302


def test_flujo_completo_cita_nota_receta_pdf(env):
    app = env["app"]
    med = login(app, "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    # Agendar
    r = med.post("/agenda/nueva", data={"csrf_token": tok, "patient_id": pid, "practitioner_id": env["users"]["propietario"],
                                        "appt_type": "primera_vez", "starts_local": "2026-11-03T09:00", "duration": "40"})
    assert r.status_code == 302
    appt_id = env["db"].execute("SELECT id FROM appointments WHERE patient_id = ?", (pid,)).fetchone()["id"]
    v = lambda: env["db"].execute("SELECT version FROM appointments WHERE id = ?", (appt_id,)).fetchone()["version"]
    for st in ["confirmada", "presente", "en_consulta"]:
        r = med.post(f"/agenda/cita/{appt_id}/estado", data={"csrf_token": tok, "status": st, "version": v()})
        assert r.status_code == 302, st
    assert "/notas/nueva" in r.headers["Location"]
    # Crear nota SOAP
    r = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "appointment_id": appt_id, "kind": "primera", "template": "soap"})
    nid = r.headers["Location"].split("/")[-1]
    # Autoguardado JSON
    r = med.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "Pirosis de 6 meses", "hea": "Ardor retroesternal posprandial.",
                                               "v_peso_kg": "70", "v_talla_cm": "170", "impresion": "Enfermedad por reflujo probable"},
                 headers={"X-CSRF-Token": tok})
    assert r.status_code == 200 and r.get_json()["imc"] == 24.2
    # Persistencia tras cerrar y abrir sesión
    med.post("/salir", data={"csrf_token": tok})
    assert med.get(f"/notas/{nid}").status_code == 302
    med = login(app, "propietario")
    tok = csrf(med)
    assert "Pirosis de 6 meses" in med.get(f"/notas/{nid}").get_data(as_text=True)
    # Finalizar
    r = med.post(f"/notas/{nid}/finalizar", data={"csrf_token": tok, "version": 2})
    assert r.status_code == 302
    row = env["db"].execute("SELECT status, content_sha256 FROM clinical_notes WHERE id = ?", (nid,)).fetchone()
    assert row["status"] == "finalizada" and len(row["content_sha256"]) == 64
    # Receta (paciente con alergias no investigadas → exige confirmación)
    items = {"csrf_token": tok, "patient_id": pid, "note_id": nid, "item-0-active_ingredient": "Omeprazol",
             "item-0-presentation": "cápsulas 20 mg", "item-0-dose": "20", "item-0-dose_unit": "mg", "item-0-route": "oral",
             "item-0-frequency": "cada 24 horas", "item-0-duration": "8 semanas", "item-0-quantity": "56 cápsulas",
             "item-0-instructions": "30 minutos antes del desayuno", "item-1-active_ingredient": "Alginato de sodio",
             "item-1-dose": "10", "item-1-dose_unit": "mL", "item-1-route": "oral", "item-1-frequency": "después de cada comida",
             "item-1-duration": "4 semanas", "item-1-quantity": "1 frasco"}
    r = med.post("/recetas/nueva", data=items)
    assert r.status_code == 422 and "no están investigadas" in r.get_data(as_text=True)
    r = med.post("/recetas/nueva", data=dict(items, ack_allergies="1"))
    assert r.status_code == 302
    rx_id = r.headers["Location"].split("/")[-1]
    for papel, (w, h) in {"carta": (612, 792), "a4": (595.28, 841.89)}.items():
        r = med.get(f"/recetas/{rx_id}/pdf", query_string={"papel": papel})
        assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data[:5] == b"%PDF-"
        assert r.headers["Cache-Control"] == "no-store"
        assert "Paciente" not in r.headers["Content-Disposition"]
        pdf = PdfReader(io.BytesIO(r.data))
        box = pdf.pages[0].mediabox
        assert abs(float(box.width) - w) < 1 and abs(float(box.height) - h) < 1, papel
        text = pdf.pages[0].extract_text()
        for expected in ["Dr. Mario Lainez", "RECETA MÉDICA", "Omeprazol", "cada 24 horas", "8 semanas", "56 cápsulas",
                         "Alginato de sodio", "GM-000001", "Alergias no investigadas", "Firma y sello"]:
            assert expected in text, (papel, expected)


def test_nota_finalizada_inmutable_y_adenda(env):
    app = env["app"]
    med = login(app, "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "narrativa"}
                   ).headers["Location"].split("/")[-1]
    med.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "Original", "narrativa": "Texto original"}, headers={"X-CSRF-Token": tok})
    med.post(f"/notas/{nid}/finalizar", data={"csrf_token": tok, "version": 2})
    # La aplicación lo rechaza
    r = med.post(f"/notas/{nid}/guardar", json={"version": 3, "motivo": "Cambiado"}, headers={"X-CSRF-Token": tok})
    assert r.status_code == 409
    # La base de datos lo rechaza aunque alguien lo intente directamente
    with pytest.raises(sqlite3.IntegrityError, match="nota_finalizada_inmutable"):
        env["db"].execute("UPDATE clinical_notes SET fields = '{}' WHERE id = ?", (nid,))
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("DELETE FROM clinical_notes WHERE id = ?", (nid,))
    r = med.post(f"/notas/{nid}/adenda", data={"csrf_token": tok, "text": "Corrección: dosis aclarada."})
    assert r.status_code == 302
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Texto original" in html and "Corrección: dosis aclarada." in html


def test_concurrencia_no_sobrescribe_en_silencio(env):
    app = env["app"]
    a = login(app, "propietario")
    b = login(app, "recepcion")
    pid = create_patient(a)
    base = {"first_names": "Paciente", "last_names": "De Prueba", "sex": "femenino", "document_type": "dni",
            "document_number": "0801198000001", "version": "1"}
    r1 = a.post(f"/pacientes/{pid}/editar", data=dict(base, csrf_token=csrf(a), phone="1111-1111"))
    r2 = b.post(f"/pacientes/{pid}/editar", data=dict(base, csrf_token=csrf(b), phone="2222-2222"))
    assert r1.status_code == 302 and r2.status_code == 409
    assert env["db"].execute("SELECT phone FROM patients WHERE id = ?", (pid,)).fetchone()["phone"] == "1111-1111"
    # Nota: dos pestañas del mismo autor con la misma versión
    tok = csrf(a)
    nid = a.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                 ).headers["Location"].split("/")[-1]
    ok = a.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "pestaña A"}, headers={"X-CSRF-Token": tok})
    stale = a.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "pestaña B"}, headers={"X-CSRF-Token": tok})
    assert ok.status_code == 200 and stale.status_code == 409


def test_reservas_simultaneas_no_ocupan_el_mismo_horario(env):
    app = env["app"]
    clients = [login(app, "recepcion") for _ in range(6)]
    pid = create_patient(clients[0])
    toks = [csrf(c) for c in clients]
    results = []
    barrier = threading.Barrier(len(clients))

    def book(i):
        barrier.wait()
        r = clients[i].post("/agenda/nueva", data={"csrf_token": toks[i], "patient_id": pid, "practitioner_id": env["users"]["propietario"],
                                                   "appt_type": "seguimiento", "starts_local": "2026-11-04T10:00",
                                                   "duration": str(20 + i * 5)})
        results.append(r.status_code)

    threads = [threading.Thread(target=book, args=(i,)) for i in range(len(clients))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results).count(302) == 1 and results.count(409) == len(clients) - 1, results
    n = env["db"].execute("SELECT COUNT(*) c FROM appointments WHERE practitioner_id = ? AND status <> 'cancelada'",
                          (env["users"]["propietario"],)).fetchone()["c"]
    assert n == 1
    # Un cruce parcial también se rechaza; un horario contiguo sí se permite
    c = clients[0]
    r = c.post("/agenda/nueva", data={"csrf_token": toks[0], "patient_id": pid, "practitioner_id": env["users"]["propietario"],
                                      "appt_type": "seguimiento", "starts_local": "2026-11-04T09:50", "duration": "20"})
    assert r.status_code == 409
    r = c.post("/agenda/nueva", data={"csrf_token": toks[0], "patient_id": pid, "practitioner_id": env["users"]["propietario"],
                                      "appt_type": "seguimiento", "starts_local": "2026-11-04T09:00", "duration": "60"})
    assert r.status_code == 302


def test_cancelar_libera_horario_y_queda_historial(env):
    c = login(env["app"], "recepcion")
    pid = create_patient(c)
    tok = csrf(c)
    data = {"csrf_token": tok, "patient_id": pid, "practitioner_id": env["users"]["propietario"], "appt_type": "seguimiento",
            "starts_local": "2026-11-05T08:00", "duration": "20"}
    assert c.post("/agenda/nueva", data=data).status_code == 302
    aid = env["db"].execute("SELECT id FROM appointments").fetchone()["id"]
    assert c.post(f"/agenda/cita/{aid}/estado", data={"csrf_token": tok, "status": "cancelada", "version": 1}).status_code == 302
    assert c.post("/agenda/nueva", data=data).status_code == 302
    # Transición inválida
    assert c.post(f"/agenda/cita/{aid}/estado", data={"csrf_token": tok, "status": "confirmada", "version": 2}).status_code == 409
    ev = env["db"].execute("SELECT action, to_status FROM appointment_events WHERE appointment_id = ? ORDER BY at", (aid,)).fetchall()
    assert [(e["action"], e["to_status"]) for e in ev] == [("creada", "solicitada"), ("estado", "cancelada")]
