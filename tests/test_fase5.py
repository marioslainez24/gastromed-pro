"""Etapa 7: recordatorios gratuitos (correo propio y WhatsApp manual), logo/firma, horarios y bloqueos."""
import io
import re
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from zoneinfo import ZoneInfo

import pytest
from PIL import Image
from pypdf import PdfReader

from conftest import create_patient, csrf, login
from app import reminders as R


# ------------------------------------------------------------------ servidor SMTP falso (solo localhost, para pruebas)
class FakeSMTP(socketserver.StreamRequestHandler):
    def handle(self):
        srv = self.server
        w = lambda s: (self.wfile.write((s + "\r\n").encode()), self.wfile.flush())  # noqa: E731
        w("220 prueba ESMTP")
        data_mode, buf = False, []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            if data_mode:
                if line in (b".\r\n", b".\n"):
                    data_mode = False
                    srv.messages.append(b"".join(buf))
                    buf = []
                    w("250 OK")
                else:
                    buf.append(line[1:] if line.startswith(b"..") else line)
                continue
            cmd = line.strip().upper()
            if cmd.startswith((b"EHLO", b"HELO")):
                w("250-prueba")
                w("250 AUTH PLAIN LOGIN")
            elif cmd.startswith(b"AUTH"):
                w("235 OK" if srv.accept_login else "535 5.7.8 Credenciales rechazadas")
            elif cmd.startswith(b"MAIL") or cmd.startswith(b"RCPT"):
                w("250 OK")
            elif cmd == b"DATA":
                data_mode = True
                w("354 Fin con .")
            elif cmd == b"QUIT":
                w("221 Adiós")
                return
            else:
                w("250 OK")


@pytest.fixture()
def smtp():
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeSMTP)
    srv.daemon_threads = True
    srv.messages, srv.accept_login = [], True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def configure_mail(env, smtp, enabled=1):
    f = env["app"].config["GM_FERNET"]
    env["db"].execute("UPDATE clinic_settings SET reminders_enabled = ?, smtp_host = '127.0.0.1', smtp_port = ?, smtp_user = 'consultorio@prueba.hn',"
                      " smtp_password_enc = ?, reminder_hours_before = 24 WHERE org_id = ?",
                      (enabled, smtp.server_address[1], f.encrypt(b"clave-de-aplicacion").decode(), env["org"]["org_id"]))


def local_in(hours, env):
    tz = ZoneInfo(env["db"].execute("SELECT timezone FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0])
    t = (datetime.now(timezone.utc) + timedelta(hours=hours)).astimezone(tz)
    return t.replace(minute=(t.minute // 5) * 5, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def book(c, env, pid, starts_local, **extra):
    data = {"csrf_token": csrf(c), "patient_id": pid, "practitioner_id": env["users"]["propietario"], "appt_type": "seguimiento",
            "starts_local": starts_local, "duration": "20"}
    data.update(extra)
    return c.post("/agenda/nueva", data=data)


_DB = {}


def appt_id(r):
    assert r.status_code == 302, r.get_data(as_text=True)[:600]
    return _DB["db"].execute("SELECT id FROM appointments ORDER BY rowid DESC LIMIT 1").fetchone()[0]


@pytest.fixture(autouse=True)
def _remember_db(env):
    _DB["db"] = env["db"]
    yield


# ------------------------------------------------------------------ consentimiento en la ficha
def test_reminder_channel_requires_consent_and_contact(env):
    c = login(env["app"], "propietario")
    tok = csrf(c)
    base = {"csrf_token": tok, "first_names": "Ana", "last_names": "Ficticia", "birth_date": "1990-01-01", "sex": "femenino",
            "document_type": "dni", "document_number": "0801199000011", "phone": "+504 9999-1111"}
    r = c.post("/pacientes/nuevo", data={**base, "reminder_channel": "correo", "reminder_consent": "1"})
    assert r.status_code == 422 and "correo del paciente" in r.get_data(as_text=True)
    r = c.post("/pacientes/nuevo", data={**base, "reminder_channel": "whatsapp"})
    assert r.status_code == 422 and "autorizó" in r.get_data(as_text=True)
    pid = create_patient(c, document_number="0801199000012", first_names="Bea", reminder_channel="whatsapp", reminder_consent="1")
    row = env["db"].execute("SELECT reminder_channel, reminder_consent_at, reminder_consent_by FROM patients WHERE id = ?", (pid,)).fetchone()
    assert row["reminder_channel"] == "whatsapp" and row["reminder_consent_at"] and row["reminder_consent_by"] == env["users"]["propietario"]


# ------------------------------------------------------------------ correo
def test_email_reminder_sent_once_without_clinical_data(env, smtp):
    c = login(env["app"], "propietario")
    pid = create_patient(c, email="paciente@ejemplo.hn", reminder_channel="correo", reminder_consent="1")
    pid2 = create_patient(c, document_number="0801198000099", first_names="Otro", email="otro@ejemplo.hn")  # sin autorización
    a1 = appt_id(book(c, env, pid, local_in(5, env), admin_note="Dolor epigástrico y sangrado"))
    appt_id(book(c, env, pid2, local_in(6, env)))
    appt_id(book(c, env, pid, local_in(24 * 5, env)))  # fuera de la ventana de 24 h
    configure_mail(env, smtp)
    out = R.run_email_reminders(env["db"], env["app"].config["GM_FERNET"])
    assert out == ["enviado"]
    assert len(smtp.messages) == 1
    msg = message_from_bytes(smtp.messages[0])
    body = msg.get_payload(decode=True).decode()
    assert msg["To"] == "paciente@ejemplo.hn" and "Paciente" in body
    assert "sangrado" not in body.lower() and "epigástrico" not in body.lower()
    st = env["db"].execute("SELECT status, attempts FROM appointment_reminders WHERE appointment_id = ?", (a1,)).fetchone()
    assert st["status"] == "enviado" and st["attempts"] == 1
    # No se duplica
    assert R.run_email_reminders(env["db"], env["app"].config["GM_FERNET"]) == []
    assert len(smtp.messages) == 1


def test_email_failure_is_recorded_not_faked_and_retried_max_3(env, smtp):
    c = login(env["app"], "propietario")
    pid = create_patient(c, email="paciente@ejemplo.hn", reminder_channel="correo", reminder_consent="1")
    a1 = appt_id(book(c, env, pid, local_in(3, env)))
    configure_mail(env, smtp)
    smtp.accept_login = False
    for _ in range(5):
        R.run_email_reminders(env["db"], env["app"].config["GM_FERNET"])
    st = env["db"].execute("SELECT status, attempts, detail FROM appointment_reminders WHERE appointment_id = ?", (a1,)).fetchone()
    assert st["status"] == "fallido" and st["attempts"] == 3 and "contraseña" in st["detail"]
    assert smtp.messages == []
    html = c.get("/agenda/recordatorios").get_data(as_text=True)
    assert "Falló" in html


def test_disabled_reminders_send_nothing(env, smtp):
    c = login(env["app"], "propietario")
    pid = create_patient(c, email="paciente@ejemplo.hn", reminder_channel="correo", reminder_consent="1")
    appt_id(book(c, env, pid, local_in(3, env)))
    configure_mail(env, smtp, enabled=0)
    assert R.run_email_reminders(env["db"], env["app"].config["GM_FERNET"]) == []
    assert smtp.messages == []


def test_reschedule_resets_reminder(env, smtp):
    c = login(env["app"], "propietario")
    pid = create_patient(c, email="paciente@ejemplo.hn", reminder_channel="correo", reminder_consent="1")
    a1 = appt_id(book(c, env, pid, local_in(3, env)))
    configure_mail(env, smtp)
    R.run_email_reminders(env["db"], env["app"].config["GM_FERNET"])
    v = env["db"].execute("SELECT version FROM appointments WHERE id = ?", (a1,)).fetchone()[0]
    r = c.post(f"/agenda/cita/{a1}/reprogramar", data={"csrf_token": csrf(c), "version": v, "starts_local": local_in(8, env), "duration": "20"})
    assert r.status_code == 302, r.get_data(as_text=True)[:400]
    assert R.run_email_reminders(env["db"], env["app"].config["GM_FERNET"]) == ["enviado"]
    assert len(smtp.messages) == 2


def test_settings_page_encrypts_password_and_test_send(env, smtp):
    c = login(env["app"], "propietario")
    tok = csrf(c)
    r = c.post("/ajustes/recordatorios", data={"csrf_token": tok, "action": "guardar", "reminders_enabled": "1", "reminder_hours_before": "24",
                                              "smtp_user": "consultorio@prueba.hn", "smtp_password": "abcd efgh ijkl mnop", "smtp_host": "127.0.0.1",
                                              "smtp_port": "587", "reminder_template": "Hola {nombre}, cita el {fecha} a las {hora}."})
    assert r.status_code == 302
    s = env["db"].execute("SELECT * FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()
    assert s["reminders_enabled"] == 1 and "abcd" not in s["smtp_password_enc"]
    assert env["app"].config["GM_FERNET"].decrypt(s["smtp_password_enc"].encode()) == b"abcdefghijklmnop"
    # Plantilla sin fecha/hora → rechazada
    c.post("/ajustes/recordatorios", data={"csrf_token": tok, "action": "guardar", "reminder_hours_before": "24", "smtp_port": "587",
                                           "reminder_template": "Hola"})
    assert env["db"].execute("SELECT reminder_template FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0].startswith("Hola {nombre}")
    # Correo de prueba usa el puerto real del servidor de pruebas
    env["db"].execute("UPDATE clinic_settings SET smtp_port = ? WHERE org_id = ?", (smtp.server_address[1], env["org"]["org_id"]))
    r = c.post("/ajustes/recordatorios", data={"csrf_token": tok, "action": "probar", "test_to": "medico@ejemplo.hn"}, follow_redirects=True)
    assert "Correo de prueba enviado" in r.get_data(as_text=True) and len(smtp.messages) == 1
    page = c.get("/ajustes/recordatorios").get_data(as_text=True)
    assert "abcdefghijklmnop" not in page and "Guardada" in page
    # Recepción no puede cambiar ajustes
    rc = login(env["app"], "recepcion")
    assert rc.get("/ajustes/recordatorios").status_code == 403


def test_send_email_refuses_plaintext_to_remote_host():
    s = {"smtp_user": "x@y.hn", "smtp_host": "127.0.0.2", "smtp_port": 587, "doctor_display_name": "Dr"}
    with pytest.raises(Exception):
        R.send_email(s, "pw", "a@b.hn", "x", "y", timeout=2)


# ------------------------------------------------------------------ WhatsApp
def test_whatsapp_link_and_consent(env):
    assert R.whatsapp_link("9999-1111", "+504", "Hola mañana") == "https://wa.me/50499991111?text=Hola%20ma%C3%B1ana"
    assert R.whatsapp_link("+504 9999-1111", "+504", "x").startswith("https://wa.me/50499991111")
    assert R.whatsapp_link("123", "+504", "x") is None
    c = login(env["app"], "recepcion")
    pid = create_patient(c, reminder_channel="whatsapp", reminder_consent="1")
    pid2 = create_patient(c, document_number="0801198000077", first_names="Otra")
    a1 = appt_id(book(c, env, pid, local_in(20, env)))
    a2 = appt_id(book(c, env, pid2, local_in(21, env)))
    page = c.get("/agenda/recordatorios")
    assert "https://wa.me" in page.headers["Content-Security-Policy"]
    html = page.get_data(as_text=True)
    assert f"/agenda/cita/{a1}/whatsapp" in html and f"/agenda/cita/{a2}/whatsapp" not in html
    r = c.post(f"/agenda/cita/{a1}/whatsapp", data={"csrf_token": csrf(c)})
    assert r.status_code == 302 and r.headers["Location"].startswith("https://wa.me/50499990000?text=")
    assert env["db"].execute("SELECT status FROM appointment_reminders WHERE appointment_id = ?", (a1,)).fetchone()[0] == "abierto_en_whatsapp"
    assert c.post(f"/agenda/cita/{a2}/whatsapp", data={"csrf_token": csrf(c)}).status_code == 409
    # Otra clínica no puede
    o = login(env["app"], "otra")
    assert o.post(f"/agenda/cita/{a1}/whatsapp", data={"csrf_token": csrf(o)}).status_code == 404


# ------------------------------------------------------------------ dictado (quitado en v0.17.0)
def test_dictado_quitado(env):
    c = login(env["app"], "propietario")
    tok = csrf(c)
    pid = create_patient(c)
    from app.views_notes import TEMPLATES
    note = c.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": next(iter(TEMPLATES))}).headers["Location"]
    page = c.get(note)
    assert "microphone=()" in page.headers["Permissions-Policy"] and "dictado" not in page.get_data(as_text=True)
    assert c.post("/ajustes/dictado", data={"csrf_token": tok, "dictation_enabled": "1"}).status_code in (404, 405)
    assert "Dictado" not in c.get("/ajustes/recordatorios").get_data(as_text=True)


# ------------------------------------------------------------------ logo y firma
def png(color=(10, 110, 100), size=(300, 120)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def test_logo_and_signature_upload_and_pdf(env):
    c = login(env["app"], "propietario")
    tok = csrf(c)
    r = c.post("/ajustes/imagenes", data={"csrf_token": tok, "kind": "logo", "imagen": (io.BytesIO(b"no es imagen"), "x.png")},
               content_type="multipart/form-data")
    assert r.status_code == 302
    assert env["db"].execute("SELECT COUNT(*) FROM clinic_assets").fetchone()[0] == 0
    for kind in ("logo", "firma"):
        r = c.post("/ajustes/imagenes", data={"csrf_token": tok, "kind": kind, "imagen": (io.BytesIO(png((10, 110, 100) if kind == "logo" else (20, 20, 20))), f"{kind}.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 302
    raw = env["db"].execute("SELECT data_enc FROM clinic_assets WHERE kind = 'logo'").fetchone()[0]
    assert not raw.startswith(b"\x89PNG")  # cifrado en disco
    assert c.get("/ajustes/imagenes/logo").data.startswith(b"\x89PNG")
    assert "asset-preview" in c.get("/ajustes/").get_data(as_text=True)
    # Receta con logo y firma
    pid = create_patient(c, allergy_status="sin_alergias_conocidas")
    r = c.post("/recetas/nueva", data={"csrf_token": tok, "patient_id": pid, "ack_allergies": "1", "item-0-active_ingredient": "Omeprazol",
                                      "item-0-dose": "20", "item-0-dose_unit": "mg", "item-0-route": "oral", "item-0-frequency": "cada 24 h",
                                      "item-0-duration": "30 días", "item-0-quantity": "30 cápsulas"})
    assert r.status_code == 302, r.get_data(as_text=True)[:400]
    pdf = c.get(r.headers["Location"] + "/pdf")
    assert pdf.status_code == 200
    reader = PdfReader(io.BytesIO(pdf.data))
    imgs = sum(len(p.images) for p in reader.pages)
    assert imgs >= 2
    # Quitar
    c.post("/ajustes/imagenes", data={"csrf_token": tok, "kind": "firma", "remove": "1"})
    assert env["db"].execute("SELECT COUNT(*) FROM clinic_assets").fetchone()[0] == 1
    # Otra clínica no ve el logo
    assert login(env["app"], "otra").get("/ajustes/imagenes/logo").status_code == 404


# ------------------------------------------------------------------ horarios y bloqueos
def test_blocks_and_working_hours(env):
    c = login(env["app"], "propietario")
    tok = csrf(c)
    pid = create_patient(c)
    prac = env["users"]["propietario"]
    r = c.post("/ajustes/horarios", data={"csrf_token": tok, "action": "bloqueo", "user_id": prac, "start_date": "2026-12-21",
                                         "end_date": "2026-12-31", "reason": "Vacaciones"})
    assert r.status_code == 302
    r = book(c, env, pid, "2026-12-23T09:00")
    assert r.status_code == 422 and "bloquead" in r.get_data(as_text=True).lower()
    assert "Vacaciones" in c.get("/agenda/?fecha=2026-12-23").get_data(as_text=True)
    # Otro profesional no está bloqueado
    ok = c.post("/agenda/nueva", data={"csrf_token": tok, "patient_id": pid, "practitioner_id": env["users"]["medico"], "appt_type": "seguimiento",
                                      "starts_local": "2026-12-23T09:00", "duration": "20"})
    assert ok.status_code == 302
    # Horario: lunes a viernes 08:00–12:00
    r = c.post("/ajustes/horarios", data={"csrf_token": tok, "action": "horario", "user_id": prac, "weekday": ["0", "1", "2", "3", "4"],
                                         "start_time": "08:00", "end_time": "12:00"})
    assert r.status_code == 302
    assert book(c, env, pid, "2026-11-18T09:00").status_code == 302           # miércoles por la mañana
    r = book(c, env, pid, "2026-11-18T15:00")                                 # por la tarde → pide confirmar
    assert r.status_code == 422 and "fuera_horario" in r.get_data(as_text=True)
    assert book(c, env, pid, "2026-11-18T15:00", fuera_horario="1").status_code == 302
    # Reprogramar hacia un bloqueo → 409
    a = appt_id(book(c, env, pid, "2026-11-19T10:00"))
    v = env["db"].execute("SELECT version FROM appointments WHERE id = ?", (a,)).fetchone()[0]
    r = c.post(f"/agenda/cita/{a}/reprogramar", data={"csrf_token": tok, "version": v, "starts_local": "2026-12-22T10:00", "duration": "20"})
    assert r.status_code == 409
    # Quitar bloqueo
    bid = env["db"].execute("SELECT id FROM schedule_blocks").fetchone()[0]
    c.post("/ajustes/horarios", data={"csrf_token": tok, "action": "quitar_bloqueo", "id": bid})
    assert book(c, env, pid, "2026-12-23T10:00").status_code == 302
    # Recepción no configura horarios
    assert login(env["app"], "recepcion").get("/ajustes/horarios").status_code == 403


def test_new_screens_load(env):
    c = login(env["app"], "propietario")
    for url in ("/ajustes/recordatorios", "/ajustes/horarios", "/agenda/recordatorios", "/agenda/recordatorios?horas=168", "/ajustes/"):
        r = c.get(url)
        assert r.status_code == 200, url
        assert "Traceback" not in r.get_data(as_text=True)


def test_lan_http_redirects_to_https(env, monkeypatch):
    monkeypatch.setenv("GASTROMED_HTTPS_PORT", "8443")
    from app import create_app
    app = create_app(env["cfg"])
    c = app.test_client()
    r = c.get("/ingresar", environ_base={"REMOTE_ADDR": "192.168.1.50"}, base_url="http://192.168.1.10:8000")
    assert r.status_code == 302 and r.headers["Location"] == "https://192.168.1.10:8443/ingresar"
    assert c.get("/ingresar", environ_base={"REMOTE_ADDR": "127.0.0.1"}).status_code == 200
    assert c.get("/ingresar", environ_base={"REMOTE_ADDR": "192.168.1.50"}, base_url="https://192.168.1.10:8443").status_code == 200
