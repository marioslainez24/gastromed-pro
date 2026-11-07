"""v0.21.0: hojas educativas y dietas (imprimir y enviar por correo) y agenda en el calendario del celular (.ics)."""
import io
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from email import message_from_bytes, policy

from pypdf import PdfReader

from conftest import create_patient, csrf, login
from tests.test_fase5 import FakeSMTP, configure_mail


def _pdf_text(data):
    return "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(data)).pages)


def test_hojas_educativas_imprimir_enviar_y_registro(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    db = env["db"]
    # ejemplos: se cargan sin revisar y no se pueden entregar
    med.post("/hojas-educativas", data={"csrf_token": tok, "action": "ejemplos"})
    ej = db.execute("SELECT id, title, reviewed FROM edu_handouts ORDER BY title").fetchall()
    assert [r["title"] for r in ej] == ["Cómo reconocer un ACV (derrame cerebral)", "Diario de cefalea", "Recomendaciones para personas con epilepsia"] and not any(r["reviewed"] for r in ej)
    pid = create_patient(med, email="paciente.ficticio@prueba.hn")
    page = med.get(f"/pacientes/{pid}/documentos").get_data(as_text=True)
    assert "Hojas educativas y dietas" in page and "(ejemplo sin revisar)" in page
    r = med.post(f"/pacientes/{pid}/hojas-educativas", data={"csrf_token": tok, "handout_id": ej[1]["id"], "accion": "imprimir"},
                 follow_redirects=True)
    assert "ejemplo sin revisar" in r.get_data(as_text=True) and db.execute("SELECT COUNT(*) FROM patient_handouts").fetchone()[0] == 0
    # el médico la revisa y guarda → lista
    med.post("/hojas-educativas", data={"csrf_token": tok, "id": ej[1]["id"], "title": "Dieta rica en fibra",
                                        "body": "DIETA RICA EN FIBRA\n\n• Frijoles, avena y frutas con cáscara (texto del médico)."})
    r = med.post(f"/pacientes/{pid}/hojas-educativas", data={"csrf_token": tok, "handout_id": ej[1]["id"], "accion": "imprimir"})
    assert r.status_code == 200 and r.headers["Content-Type"] == "application/pdf"
    t = _pdf_text(r.data)
    assert "Dieta rica en fibra" in t and "Paciente De Prueba" in t and "texto del médico" in t
    med.post(f"/pacientes/{pid}/hojas-educativas", data={"csrf_token": tok, "handout_id": ej[1]["id"], "accion": "imprimir"})
    assert db.execute("SELECT COUNT(*) FROM patient_handouts").fetchone()[0] == 1                 # reimprimir no duplica
    # hoja propia nueva
    med.post("/hojas-educativas", data={"csrf_token": tok, "title": "Cuidados tras la ligadura de várices", "body": "Dieta líquida (texto del médico)."})
    assert med.post("/hojas-educativas", data={"csrf_token": tok, "title": "cuidados tras la ligadura de várices", "body": "x"},
                    follow_redirects=True).get_data(as_text=True).count("Ya existe una hoja") == 1
    lig = db.execute("SELECT id FROM edu_handouts WHERE title LIKE 'Cuidados%'").fetchone()[0]
    # por correo
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeSMTP)
    srv.daemon_threads, srv.messages, srv.accept_login = True, [], True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        configure_mail(env, srv)
        db.commit()
        med.post(f"/pacientes/{pid}/hojas-educativas", data={"csrf_token": tok, "handout_id": lig, "accion": "correo"})
        assert srv.messages == []                                                     # falta la autorización
        r = med.post(f"/pacientes/{pid}/hojas-educativas", data={"csrf_token": tok, "handout_id": lig, "accion": "correo", "autoriza": "1"},
                     follow_redirects=True)
        assert "Enviado al correo del paciente" in r.get_data(as_text=True) and len(srv.messages) == 1
        msg = message_from_bytes(srv.messages[0], policy=policy.default)
        att = list(msg.iter_attachments())[0]
        assert "Cuidados tras la ligadura" in _pdf_text(att.get_payload(decode=True)) and "ligadura" not in msg.get_body(("plain",)).get_content().lower()
    finally:
        srv.shutdown()
        srv.server_close()
    page = med.get(f"/pacientes/{pid}/documentos").get_data(as_text=True)
    assert "Entregadas a este paciente" in page and "impresa" in page and "por correo" in page
    vias = sorted(r[0] for r in db.execute("SELECT via FROM patient_handouts"))
    assert vias == ["correo", "impresa"]
    # el registro de entrega no se puede cambiar
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE patient_handouts SET title = 'x'")
    assert login(env["app"], "recepcion").get("/hojas-educativas").status_code == 403


def test_agenda_para_el_calendario_del_celular(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    db = env["db"]
    prac = db.execute("SELECT id FROM users WHERE email = 'propietario@prueba.hn'").fetchone()[0]
    site = db.execute("SELECT id FROM sites LIMIT 1").fetchone()[0]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    def add(i, hours, status, kind="seguimiento"):
        st, en = now + timedelta(hours=hours), now + timedelta(hours=hours, minutes=30)
        db.execute("INSERT INTO appointments(id, org_id, site_id, practitioner_id, patient_id, appt_type, status, starts_at, ends_at, created_at,"
                   " created_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (f"{i:032x}", env["org"]["org_id"], site, prac, pid, kind, status, st.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    en.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ"), prac, now.strftime("%Y-%m-%dT%H:%M:%SZ")))
    add(1, 30, "confirmada", "primera_vez")
    add(2, 54, "cancelada")
    add(3, 24 * 40, "solicitada")                                                       # fuera de 30 días
    db.commit()
    assert "Calendario del celular" in med.get("/agenda/").get_data(as_text=True)
    r = med.get("/agenda/calendario.ics?dias=30")
    assert r.status_code == 200 and r.headers["Content-Type"].startswith("text/calendar")
    ics = r.get_data(as_text=True)
    assert ics.startswith("BEGIN:VCALENDAR") and ics.count("BEGIN:VEVENT") == 1 and "SUMMARY:Cita · Primera vez" in ics
    assert "De Prueba" not in ics and "STATUS:CONFIRMED" in ics                         # sin nombres por defecto
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))
    con = med.get("/agenda/calendario.ics?dias=90&nombres=1").get_data(as_text=True)
    assert con.count("BEGIN:VEVENT") == 2 and "Paciente De Prueba" in con.replace("\r\n ", "")
    assert med.get("/agenda/calendario.ics?dias=abc").status_code == 400
