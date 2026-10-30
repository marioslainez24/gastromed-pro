"""Utilidades: normalización de texto, fechas en zona horaria de la clínica, etiquetas."""
import unicodedata
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from flask import g

from .db import get_db

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

LABELS = {
    "sex": {"femenino": "Femenino", "masculino": "Masculino", "intersexual": "Intersexual", "no_registrado": "No registrado"},
    "document_type": {"dni": "DNI (identidad)", "pasaporte": "Pasaporte", "carne_residente": "Carné de residente",
                      "otro": "Otro documento", "sin_documento": "Sin documento"},
    "allergy_status": {"no_investigado": "Alergias no investigadas", "sin_alergias_conocidas": "Sin alergias conocidas",
                       "con_alergias": "Con alergias registradas"},
    "severity": {"leve": "Leve", "moderada": "Moderada", "grave": "Grave", "desconocida": "Gravedad desconocida"},
    "appt_type": {"primera_vez": "Primera vez", "seguimiento": "Seguimiento", "procedimiento": "Procedimiento",
                  "teleconsulta": "Teleconsulta"},
    "appt_status": {"solicitada": "Solicitada", "confirmada": "Confirmada", "presente": "Presente (sala de espera)",
                    "en_consulta": "En consulta", "atendida": "Atendida", "cancelada": "Cancelada", "no_asistio": "No asistió"},
    "note_kind": {"primera": "Primera consulta", "subsecuente": "Consulta subsecuente"},
    "note_template": {"soap": "SOAP", "narrativa": "Narrativa"},
    "note_status": {"borrador": "Borrador", "finalizada": "Finalizada"},
}


def label(group: str, key) -> str:
    return LABELS.get(group, {}).get(key, key or "")


def normalize(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def digits(text: str | None) -> str:
    return "".join(c for c in (text or "") if c.isdigit())


def clinic_settings():
    if "clinic_settings" not in g:
        g.clinic_settings = get_db().execute("SELECT * FROM clinic_settings WHERE org_id = ?", (g.user["org_id"],)).fetchone()
    return g.clinic_settings


def clinic_tz() -> ZoneInfo:
    s = clinic_settings() if g.get("user") else None
    return ZoneInfo(s["timezone"] if s else "America/Tegucigalpa")


def parse_utc(ts: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(ts)


def to_utc_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_to_utc(local_str: str, tz: ZoneInfo) -> datetime:
    """'2026-11-02T09:30' en hora de la clínica → datetime UTC."""
    naive = datetime.strptime(local_str, "%Y-%m-%dT%H:%M")
    return naive.replace(tzinfo=tz).astimezone(timezone.utc)


def fmt_dt(ts: str | None, with_time=True) -> str:
    if not ts:
        return ""
    d = parse_utc(ts).astimezone(clinic_tz())
    base = f"{d.day} {MESES[d.month - 1][:3]} {d.year}"
    return f"{base}, {d:%H:%M}" if with_time else base


def fmt_time(ts: str | None) -> str:
    return parse_utc(ts).astimezone(clinic_tz()).strftime("%H:%M") if ts else ""


def fmt_date_long(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def fmt_birth(iso: str | None) -> str:
    if not iso:
        return "No registrada"
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def age(iso: str | None, today: date | None = None) -> str:
    if not iso:
        return "Edad no registrada"
    b = date.fromisoformat(iso)
    today = today or datetime.now(clinic_tz()).date()
    years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    if years >= 2:
        return f"{years} años"
    months = (today.year - b.year) * 12 + today.month - b.month - (today.day < b.day)
    return f"{months} meses" if months >= 1 else f"{(today - b).days} días"


def local_today() -> date:
    return datetime.now(clinic_tz()).date()
