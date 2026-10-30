"""Recordatorios de citas sin costo:
- Correo: se envía desde la cuenta de correo de la clínica (p. ej., Gmail con «contraseña de aplicación»), sin proveedores de pago.
- WhatsApp: enlace oficial gratuito «clic para chatear» (wa.me) con el mensaje ya escrito; el envío lo confirma una persona
  en WhatsApp. La API de WhatsApp Business (de pago) NO se usa.
Los mensajes no contienen información clínica: solo nombre, fecha, hora, consultorio y teléfono.
"""
import smtplib
import ssl
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from zoneinfo import ZoneInfo

from .db import new_id, utcnow, write_tx

PLACEHOLDERS = ("{nombre}", "{fecha}", "{hora}", "{consultorio}", "{telefono}")
MAX_ATTEMPTS = 3
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def render(template: str, settings, first_name: str, starts_at_utc: str) -> str:
    tz = ZoneInfo(settings["timezone"])
    d = datetime.strptime(starts_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(tz)
    values = {"{nombre}": first_name.split()[0] if first_name else "", "{fecha}": f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}",
              "{hora}": d.strftime("%I:%M %p").lstrip("0").replace("AM", "a. m.").replace("PM", "p. m."),
              "{consultorio}": settings["doctor_display_name"] or "", "{telefono}": settings["phones"] or ""}
    out = template
    for k, v in values.items():
        out = out.replace(k, v)
    return out.replace("m..", "m.")


def whatsapp_link(phone: str, prefix: str, text: str) -> str | None:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) < 8:
        return None
    pre = "".join(c for c in (prefix or "") if c.isdigit())
    if pre and not digits.startswith(pre) and len(digits) <= 8:
        digits = pre + digits
    return f"https://wa.me/{digits}?text={urllib.parse.quote(text)}"


def send_email(settings, password: str, to: str, subject: str, body: str, timeout=20):
    """Envía un correo por SMTP con STARTTLS. Lanza excepción si falla: nunca se simula éxito."""
    if not settings["smtp_user"] or not password:
        raise RuntimeError("Falta configurar la cuenta de correo de la clínica.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings["doctor_display_name"] or "Consultorio", settings["smtp_user"]))
    msg["To"] = to
    msg["Message-ID"] = make_msgid(domain="gastromed.local")
    msg.set_content(body)
    port = int(settings["smtp_port"])
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(settings["smtp_host"], port, context=ctx, timeout=timeout) as s:
            s.login(settings["smtp_user"], password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings["smtp_host"], port, timeout=timeout) as s:
            s.ehlo()
            if s.has_extn("starttls"):
                s.starttls(context=ctx)
                s.ehlo()
            elif settings["smtp_host"] not in ("localhost", "127.0.0.1"):
                raise RuntimeError("El servidor de correo no ofrece conexión cifrada (STARTTLS); envío cancelado.")
            s.login(settings["smtp_user"], password)
            s.send_message(msg)


def safe_error(e: Exception) -> str:
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "Usuario o contraseña de aplicación incorrectos (verifique la contraseña de aplicación de Gmail)."
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "La dirección de correo del paciente fue rechazada."
    if isinstance(e, (OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return "No hay conexión con el servidor de correo (¿sin internet?)."
    return f"{type(e).__name__}: {str(e)[:160]}"


def due_email_reminders(db, org_id, hours_before: int, now_utc: datetime | None = None):
    now = now_utc or datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_before)
    return db.execute(
        "SELECT a.id, a.starts_at, p.first_names, p.email, r.status AS rstatus, r.attempts FROM appointments a"
        " JOIN patients p ON p.id = a.patient_id LEFT JOIN appointment_reminders r ON r.appointment_id = a.id AND r.channel = 'correo'"
        " WHERE a.org_id = ? AND a.status IN ('solicitada','confirmada') AND a.starts_at > ? AND a.starts_at <= ?"
        " AND p.reminder_channel = 'correo' AND p.reminder_consent_at IS NOT NULL AND p.email IS NOT NULL"
        " AND (r.id IS NULL OR (r.status = 'fallido' AND r.attempts < ?))",
        (org_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"), MAX_ATTEMPTS)).fetchall()


def record(db, appointment_id, channel, status, detail=None, user_id=None):
    with write_tx(db):
        cur = db.execute("UPDATE appointment_reminders SET status = ?, attempts = attempts + 1, detail = ?, last_at = ?, by_user = ?"
                         " WHERE appointment_id = ? AND channel = ?", (status, detail, utcnow(), user_id, appointment_id, channel))
        if cur.rowcount == 0:
            db.execute("INSERT INTO appointment_reminders(id, appointment_id, channel, status, detail, last_at, by_user) VALUES (?,?,?,?,?,?,?)",
                       (new_id(), appointment_id, channel, status, detail, utcnow(), user_id))


def run_email_reminders(db, fernet, now_utc=None) -> list[str]:
    """Procesa todas las clínicas con recordatorios activos. Devuelve el resultado de cada envío (sin datos de pacientes)."""
    out = []
    for s in db.execute("SELECT * FROM clinic_settings WHERE reminders_enabled = 1 AND smtp_user IS NOT NULL").fetchall():
        try:
            password = fernet.decrypt(s["smtp_password_enc"].encode()).decode() if s["smtp_password_enc"] else ""
        except Exception:  # noqa: BLE001
            password = ""
        for a in due_email_reminders(db, s["org_id"], s["reminder_hours_before"], now_utc):
            body = render(s["reminder_template"], s, a["first_names"], a["starts_at"])
            try:
                send_email(s, password, a["email"], "Recordatorio de su cita", body)
                record(db, a["id"], "correo", "enviado")
                out.append("enviado")
            except Exception as e:  # noqa: BLE001
                record(db, a["id"], "correo", "fallido", safe_error(e))
                out.append("fallido")
    return out
