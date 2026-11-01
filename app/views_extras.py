"""Recordatorios de citas, logo/firma, horarios de atención y bloqueos."""
import re
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, url_for

from . import reminders as R
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, can, require
from .util import clinic_settings, clinic_tz, local_today, parse_utc
from .views_files import validate as validate_file

bp = Blueprint("extras", __name__)
WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def load_assets(org_id) -> dict:
    f = current_app.config["GM_FERNET"]
    out = {}
    for r in get_db().execute("SELECT kind, data_enc FROM clinic_assets WHERE org_id = ?", (org_id,)):
        try:
            out[r["kind"]] = f.decrypt(r["data_enc"])
        except Exception:  # noqa: BLE001
            pass
    return out


# ------------------------------------------------------------------------------------------------ recordatorios
@bp.route("/ajustes/recordatorios", methods=["GET", "POST"])
@require("ajustes.editar")
def reminders_settings():
    db = get_db()
    s = clinic_settings()
    if request.method == "POST":
        action = request.form.get("action", "guardar")
        if action == "probar":
            to = (request.form.get("test_to") or "").strip()
            if "@" not in to:
                flash("Escriba un correo de destino para la prueba.", "error")
                return redirect(url_for("extras.reminders_settings"))
            try:
                pw = current_app.config["GM_FERNET"].decrypt(s["smtp_password_enc"].encode()).decode() if s["smtp_password_enc"] else ""
                R.send_email(s, pw, to, "Prueba de GastroMed Pro", "Este es un correo de prueba de los recordatorios de citas.")
                flash(f"Correo de prueba enviado a {to}. Revise la bandeja de entrada (y la carpeta de spam).", "ok")
                audit("recordatorio_prueba_ok", "ajustes", g.user["org_id"])
            except Exception as e:  # noqa: BLE001
                flash("No se pudo enviar: " + R.safe_error(e), "error")
                audit("recordatorio_prueba_fallida", "ajustes", g.user["org_id"])
            return redirect(url_for("extras.reminders_settings"))
        template = (request.form.get("reminder_template") or "").strip()[:600]
        try:
            hours = int(request.form.get("reminder_hours_before", "24"))
            port = int(request.form.get("smtp_port", "587"))
            if not 1 <= hours <= 168 or port not in (25, 465, 587, 2525):
                raise ValueError
        except ValueError:
            flash("Horas de anticipación (1–168) o puerto no válidos.", "error")
            return redirect(url_for("extras.reminders_settings"))
        if not template or "{fecha}" not in template or "{hora}" not in template:
            flash("El mensaje debe incluir al menos {fecha} y {hora}.", "error")
            return redirect(url_for("extras.reminders_settings"))
        host = (request.form.get("smtp_host") or "").strip()[:120] or "smtp.gmail.com"
        user = (request.form.get("smtp_user") or "").strip()[:200] or None
        new_pw = (request.form.get("smtp_password") or "").replace(" ", "")
        enc = current_app.config["GM_FERNET"].encrypt(new_pw.encode()).decode() if new_pw else s["smtp_password_enc"]
        enabled = int(request.form.get("reminders_enabled") == "1")
        if enabled and (not user or not enc):
            flash("Para activar los recordatorios por correo, configure la cuenta y la contraseña de aplicación.", "error")
            enabled = 0
        with write_tx(db):
            db.execute("UPDATE clinic_settings SET reminders_enabled = ?, reminder_hours_before = ?, smtp_host = ?, smtp_port = ?, smtp_user = ?,"
                       " smtp_password_enc = ?, reminder_template = ?, updated_at = ?, updated_by = ?, version = version + 1 WHERE org_id = ?",
                       (enabled, hours, host, port, user, enc, template, utcnow(), g.user["id"], g.user["org_id"]))
            audit("recordatorios_configurados", "ajustes", g.user["org_id"], {"activos": bool(enabled)}, db=db)
        flash("Configuración de recordatorios guardada.", "ok")
        return redirect(url_for("extras.reminders_settings"))
    log = db.execute("SELECT r.*, a.starts_at, p.first_names, p.last_names FROM appointment_reminders r JOIN appointments a ON a.id = r.appointment_id"
                     " JOIN patients p ON p.id = a.patient_id WHERE a.org_id = ? ORDER BY r.last_at DESC LIMIT 50", (g.user["org_id"],)).fetchall()
    sample = R.render(s["reminder_template"], s, "María", (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return render_template("extras/recordatorios.html", s=s, log=log, sample=sample, has_pw=bool(s["smtp_password_enc"]))


@bp.route("/agenda/recordatorios")
@require("agenda.ver")
def reminders_today():
    """Citas próximas con su estado de recordatorio y botón de WhatsApp (envío manual, gratuito)."""
    db = get_db()
    s = clinic_settings()
    hours = int(request.args.get("horas") or 48)
    now = datetime.now(timezone.utc)
    rows = db.execute(
        "SELECT a.*, p.first_names, p.last_names, p.phone, p.email, p.reminder_channel, p.reminder_consent_at,"
        " (SELECT status FROM appointment_reminders r WHERE r.appointment_id = a.id AND r.channel = 'correo') AS mail_status,"
        " (SELECT detail FROM appointment_reminders r WHERE r.appointment_id = a.id AND r.channel = 'correo') AS mail_detail,"
        " (SELECT status FROM appointment_reminders r WHERE r.appointment_id = a.id AND r.channel = 'whatsapp') AS wa_status"
        " FROM appointments a JOIN patients p ON p.id = a.patient_id WHERE a.org_id = ? AND a.status IN ('solicitada','confirmada')"
        " AND a.starts_at > ? AND a.starts_at <= ? ORDER BY a.starts_at",
        (g.user["org_id"], now.strftime("%Y-%m-%dT%H:%M:%SZ"), (now + timedelta(hours=min(max(hours, 1), 336))).strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchall()
    resp = make_response(render_template("extras/recordatorios_agenda.html", rows=rows, s=s, hours=hours))
    # El botón de WhatsApp envía un formulario que redirige a wa.me: se permite solo en esta pantalla.
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                               "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'; "
                                               "form-action 'self' https://wa.me https://api.whatsapp.com")
    return resp


@bp.route("/agenda/cita/<appt_id>/whatsapp", methods=["POST"])
@require("agenda.editar")
def whatsapp(appt_id):
    if not re.fullmatch(r"[0-9a-f]{32}", appt_id or ""):
        abort(404)
    db = get_db()
    a = db.execute("SELECT a.*, p.first_names, p.phone, p.reminder_channel, p.reminder_consent_at FROM appointments a JOIN patients p ON p.id = a.patient_id"
                   " WHERE a.id = ? AND a.org_id = ?", (appt_id, g.user["org_id"])).fetchone() or abort(404)
    if a["reminder_channel"] != "whatsapp" or not a["reminder_consent_at"]:
        abort(409, description="El paciente no autorizó recordatorios por WhatsApp. Regístrelo en su ficha.")
    s = clinic_settings()
    link = R.whatsapp_link(a["phone"], s["phone_prefix"], R.render(s["reminder_template"], s, a["first_names"], a["starts_at"]))
    if not link:
        abort(409, description="El paciente no tiene un teléfono válido.")
    R.record(db, a["id"], "whatsapp", "abierto_en_whatsapp", user_id=g.user["id"])
    audit("recordatorio_whatsapp_abierto", "cita", a["id"])
    return redirect(link)


# ------------------------------------------------------------------------------------------------ logo y firma
@bp.route("/ajustes/imagenes", methods=["POST"])
@require("ajustes.editar")
def assets_upload():
    kind = request.form.get("kind")
    if kind not in ("logo", "firma"):
        abort(400)
    db = get_db()
    if request.form.get("remove") == "1":
        with write_tx(db):
            db.execute("DELETE FROM clinic_assets WHERE org_id = ? AND kind = ?", (g.user["org_id"], kind))
            audit(f"{kind}_eliminado", "ajustes", g.user["org_id"], db=db)
        flash("Imagen quitada.", "ok")
        return redirect(url_for("settings.clinic") + "#imagenes")
    up = request.files.get("imagen")
    data = up.read(2 * 1024 * 1024 + 1) if up else b""
    mime, _ext, err = validate_file(data)
    if err or mime not in ("image/png", "image/jpeg") or len(data) > 2 * 1024 * 1024:
        flash(err or "Use una imagen PNG o JPG de máximo 2 MB.", "error")
        return redirect(url_for("settings.clinic") + "#imagenes")
    with write_tx(db):
        db.execute("INSERT INTO clinic_assets(org_id, kind, mime, data_enc, updated_at, updated_by) VALUES (?,?,?,?,?,?)"
                   " ON CONFLICT(org_id, kind) DO UPDATE SET mime = excluded.mime, data_enc = excluded.data_enc,"
                   " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                   (g.user["org_id"], kind, mime, current_app.config["GM_FERNET"].encrypt(data), utcnow(), g.user["id"]))
        audit(f"{kind}_cargado", "ajustes", g.user["org_id"], db=db)
    flash("Imagen guardada. Aparecerá en recetas, órdenes e informes.", "ok")
    return redirect(url_for("settings.clinic") + "#imagenes")


@bp.route("/ajustes/imagenes/<kind>")
@require("ajustes.editar")
def assets_view(kind):
    if kind not in ("logo", "firma"):
        abort(404)
    r = get_db().execute("SELECT mime FROM clinic_assets WHERE org_id = ? AND kind = ?", (g.user["org_id"], kind)).fetchone() or abort(404)
    resp = make_response(load_assets(g.user["org_id"])[kind])
    resp.headers["Content-Type"] = r["mime"]
    return resp


# ------------------------------------------------------------------------------------------------ horarios y bloqueos
@bp.route("/ajustes/horarios", methods=["GET", "POST"])
@require("ajustes.editar")
def schedules():
    db = get_db()
    org = g.user["org_id"]
    pracs = db.execute("SELECT id, full_name FROM users WHERE org_id = ? AND is_practitioner = 1 AND active = 1 ORDER BY full_name", (org,)).fetchall()
    pids = {p["id"] for p in pracs}
    if request.method == "POST":
        action = request.form.get("action")
        with write_tx(db):
            if action == "horario":
                uid = request.form.get("user_id")
                days = [int(d) for d in request.form.getlist("weekday") if d.isdigit() and 0 <= int(d) <= 6]
                st, en = request.form.get("start_time", ""), request.form.get("end_time", "")
                if uid not in pids or not days or not re.fullmatch(r"\d\d:\d\d", st) or not re.fullmatch(r"\d\d:\d\d", en) or en <= st:
                    abort(400, description="Elija profesional, días y un horario válido (fin posterior al inicio).")
                for d in days:
                    db.execute("INSERT INTO practitioner_schedules(id, org_id, user_id, weekday, start_time, end_time) VALUES (?,?,?,?,?,?)",
                               (new_id(), org, uid, d, st, en))
                audit("horario_agregado", "usuario", uid, {"dias": days, "de": st, "a": en}, db=db)
            elif action == "quitar_horario":
                db.execute("DELETE FROM practitioner_schedules WHERE id = ? AND org_id = ?", (request.form.get("id"), org))
                audit("horario_quitado", "ajustes", org, db=db)
            elif action == "bloqueo":
                uid = request.form.get("user_id") or None
                if uid and uid not in pids:
                    abort(400)
                try:
                    sd, ed = date.fromisoformat(request.form.get("start_date", "")), date.fromisoformat(request.form.get("end_date", ""))
                    if ed < sd:
                        raise ValueError
                except ValueError:
                    abort(400, description="Fechas de bloqueo no válidas.")
                bid = new_id()
                db.execute("INSERT INTO schedule_blocks(id, org_id, user_id, start_date, end_date, reason, created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
                           (bid, org, uid, sd.isoformat(), ed.isoformat(), (request.form.get("reason") or "").strip()[:200] or None, g.user["id"], utcnow()))
                audit("bloqueo_agregado", "ajustes", bid, db=db)
            elif action == "quitar_bloqueo":
                db.execute("DELETE FROM schedule_blocks WHERE id = ? AND org_id = ?", (request.form.get("id"), org))
                audit("bloqueo_quitado", "ajustes", org, db=db)
            else:
                abort(400)
        flash("Cambios guardados.", "ok")
        return redirect(url_for("extras.schedules"))
    sched = db.execute("SELECT s.*, u.full_name FROM practitioner_schedules s JOIN users u ON u.id = s.user_id WHERE s.org_id = ?"
                       " ORDER BY u.full_name, s.weekday, s.start_time", (org,)).fetchall()
    blocks = db.execute("SELECT b.*, u.full_name FROM schedule_blocks b LEFT JOIN users u ON u.id = b.user_id WHERE b.org_id = ? AND b.end_date >= ?"
                        " ORDER BY b.start_date", (org, local_today().isoformat())).fetchall()
    return render_template("extras/horarios.html", pracs=pracs, sched=sched, blocks=blocks, WEEKDAYS=WEEKDAYS)


def availability_problems(db, org_id, practitioner_id, start_utc: datetime, end_utc: datetime):
    """Devuelve (bloqueo, fuera_de_horario). El bloqueo impide agendar; fuera de horario solo pide confirmación."""
    tz = clinic_tz()
    ls, le = start_utc.astimezone(tz), end_utc.astimezone(tz)
    block = db.execute("SELECT * FROM schedule_blocks WHERE org_id = ? AND (user_id IS NULL OR user_id = ?) AND start_date <= ? AND end_date >= ?",
                       (org_id, practitioner_id, le.date().isoformat(), ls.date().isoformat())).fetchone()
    rows = db.execute("SELECT * FROM practitioner_schedules WHERE user_id = ? AND weekday = ?", (practitioner_id, ls.weekday())).fetchall()
    has_any = db.execute("SELECT 1 FROM practitioner_schedules WHERE user_id = ? LIMIT 1", (practitioner_id,)).fetchone()
    outside = False
    if has_any:
        st, en = ls.strftime("%H:%M"), le.strftime("%H:%M")
        outside = ls.date() != le.date() or not any(r["start_time"] <= st and en <= r["end_time"] for r in rows)
    return block, outside


def day_blocks(db, org_id, d: date, practitioner_id=None):
    sql = ("SELECT b.*, u.full_name FROM schedule_blocks b LEFT JOIN users u ON u.id = b.user_id WHERE b.org_id = ? AND b.start_date <= ?"
           " AND b.end_date >= ?")
    params = [org_id, d.isoformat(), d.isoformat()]
    if practitioner_id:
        sql += " AND (b.user_id IS NULL OR b.user_id = ?)"
        params.append(practitioner_id)
    return db.execute(sql, params).fetchall()
