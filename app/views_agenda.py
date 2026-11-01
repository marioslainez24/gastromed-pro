"""Agenda: vistas diaria/semanal/mensual, citas, estados, reprogramación con historial."""
import calendar
import json
import re
import sqlite3
from datetime import date, datetime, time, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db, new_id, utcnow, write_tx
from .security import audit, can, require
from .util import LABELS, clinic_settings, clinic_tz, fmt_date_long, local_to_utc, local_today, parse_utc, to_utc_str
from .views_patients import get_patient_or_404

bp = Blueprint("agenda", __name__, url_prefix="/agenda")

# Transiciones de estado permitidas
TRANSITIONS = {
    "solicitada": {"confirmada", "presente", "cancelada", "no_asistio"},
    "confirmada": {"presente", "cancelada", "no_asistio"},
    "presente": {"en_consulta", "cancelada"},
    "en_consulta": {"atendida"},
    "atendida": set(),
    "cancelada": set(),
    "no_asistio": set(),
}


def practitioners():
    return get_db().execute("SELECT id, full_name FROM users WHERE org_id = ? AND is_practitioner = 1 AND active = 1"
                            " ORDER BY full_name", (g.user["org_id"],)).fetchall()


def _day_bounds(d: date):
    tz = clinic_tz()
    start = datetime.combine(d, time.min, tz)
    return to_utc_str(start), to_utc_str(start + timedelta(days=1))


def _parse_day(s: str | None) -> date:
    try:
        return date.fromisoformat(s) if s else local_today()
    except ValueError:
        return local_today()


def _appointments_between(start_utc, end_utc, practitioner_id=None):
    sql = ("SELECT a.*, p.first_names, p.last_names, p.mrn, p.phone, u.full_name AS practitioner FROM appointments a"
           " JOIN patients p ON p.id = a.patient_id JOIN users u ON u.id = a.practitioner_id"
           " WHERE a.org_id = ? AND a.starts_at < ? AND a.ends_at > ?")
    params = [g.user["org_id"], end_utc, start_utc]
    if practitioner_id:
        sql += " AND a.practitioner_id = ?"
        params.append(practitioner_id)
    return get_db().execute(sql + " ORDER BY a.starts_at", params).fetchall()


@bp.route("/")
@require("agenda.ver")
def day():
    d = _parse_day(request.args.get("fecha"))
    prac = request.args.get("profesional") or None
    s, e = _day_bounds(d)
    rows = _appointments_between(s, e, prac)
    waiting = [r for r in rows if r["status"] == "presente"]
    in_consult = [r for r in rows if r["status"] == "en_consulta"]
    intake_ids = {r["appointment_id"] for r in get_db().execute(
        "SELECT appointment_id FROM appointment_intake WHERE appointment_id IN (%s)" % ",".join("?" * len(rows)), [r["id"] for r in rows])} if rows else set()
    from .views_extras import day_blocks
    blocks = day_blocks(get_db(), g.user["org_id"], d, prac)
    return render_template("agenda/dia.html", d=d, d_label=fmt_date_long(d), rows=rows, waiting=waiting, blocks=blocks,
                           in_consult=in_consult, intake_ids=intake_ids, now_utc=utcnow(),
                           prev=d - timedelta(days=1), next=d + timedelta(days=1), today=local_today(),
                           practitioners=practitioners(), prac=prac, transitions=TRANSITIONS)


@bp.route("/semana")
@require("agenda.ver")
def week():
    d = _parse_day(request.args.get("fecha"))
    monday = d - timedelta(days=d.weekday())
    prac = request.args.get("profesional") or None
    s, _ = _day_bounds(monday)
    _, e = _day_bounds(monday + timedelta(days=6))
    rows = _appointments_between(s, e, prac)
    tz = clinic_tz()
    days = [(monday + timedelta(days=i), []) for i in range(7)]
    for r in rows:
        ld = parse_utc(r["starts_at"]).astimezone(tz).date()
        idx = (ld - monday).days
        if 0 <= idx < 7:
            days[idx][1].append(r)
    return render_template("agenda/semana.html", days=[(dd, fmt_date_long(dd), rr) for dd, rr in days], monday=monday,
                           prev=monday - timedelta(days=7), next=monday + timedelta(days=7), today=local_today(),
                           practitioners=practitioners(), prac=prac)


@bp.route("/mes")
@require("agenda.ver")
def month():
    d = _parse_day(request.args.get("fecha"))
    first = d.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    prac = request.args.get("profesional") or None
    s, _ = _day_bounds(first)
    _, e = _day_bounds(last)
    tz = clinic_tz()
    counts = {}
    for r in _appointments_between(s, e, prac):
        if r["status"] in ("cancelada",):
            continue
        ld = parse_utc(r["starts_at"]).astimezone(tz).date()
        counts[ld] = counts.get(ld, 0) + 1
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
    prev_m = (first - timedelta(days=1)).replace(day=1)
    next_m = last + timedelta(days=1)
    from .util import MESES
    return render_template("agenda/mes.html", weeks=weeks, first=first, counts=counts, today=local_today(),
                           title=f"{MESES[first.month - 1].capitalize()} {first.year}", prev=prev_m, next=next_m,
                           practitioners=practitioners(), prac=prac)


def _durations():
    return json.loads(clinic_settings()["appointment_durations"])


@bp.route("/nueva", methods=["GET", "POST"])
@require("agenda.editar")
def new():
    pracs = practitioners()
    durations = _durations()
    form = request.form if request.method == "POST" else request.args
    patient = None
    pid = form.get("patient_id")
    if pid:
        patient = get_patient_or_404(pid)
    errors = {}
    values = {
        "practitioner_id": form.get("practitioner_id") or (g.user["id"] if g.user["is_practitioner"] else (pracs[0]["id"] if pracs else "")),
        "appt_type": form.get("appt_type") or "primera_vez",
        "starts_local": form.get("starts_local") or f"{form.get('fecha') or local_today().isoformat()}T{form.get('hora') or '08:00'}",
        "duration": form.get("duration") or "",
        "admin_note": form.get("admin_note") or "",
    }
    if request.method == "POST":
        if not patient:
            errors["patient_id"] = "Seleccione un paciente."
        if values["practitioner_id"] not in {p["id"] for p in pracs}:
            errors["practitioner_id"] = "Seleccione un profesional válido."
        if values["appt_type"] not in LABELS["appt_type"]:
            errors["appt_type"] = "Tipo no válido."
        try:
            minutes = int(values["duration"] or durations.get(values["appt_type"], 30))
            if not 5 <= minutes <= 480:
                raise ValueError
        except ValueError:
            errors["duration"] = "Duración entre 5 y 480 minutos."
            minutes = 30
        try:
            start = local_to_utc(values["starts_local"], clinic_tz())
        except ValueError:
            errors["starts_local"] = "Fecha y hora no válidas."
        if len(values["admin_note"]) > 300:
            errors["admin_note"] = "Máximo 300 caracteres."
        if not errors:
            from .views_extras import availability_problems
            end = start + timedelta(minutes=minutes)
            block, outside = availability_problems(get_db(), g.user["org_id"], values["practitioner_id"], start, end)
            if block:
                errors["starts_local"] = (f"La agenda está bloqueada del {block['start_date']} al {block['end_date']}"
                                          f"{' (' + block['reason'] + ')' if block['reason'] else ''}. Elija otra fecha.")
            elif outside and request.form.get("fuera_horario") != "1":
                errors["fuera_horario"] = "El horario elegido está fuera del horario de atención del profesional. Marque la casilla para agendar de todas formas."
        if not errors:
            site = get_db().execute("SELECT id FROM sites WHERE org_id = ? AND active = 1 ORDER BY created_at LIMIT 1",
                                    (g.user["org_id"],)).fetchone()
            aid = new_id()
            db = get_db()
            try:
                with write_tx(db):
                    db.execute(
                        "INSERT INTO appointments(id, org_id, site_id, practitioner_id, patient_id, appt_type, status, starts_at, ends_at,"
                        " admin_note, created_at, created_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (aid, g.user["org_id"], site["id"], values["practitioner_id"], patient["id"], values["appt_type"], "solicitada",
                         to_utc_str(start), to_utc_str(end), values["admin_note"] or None, utcnow(), g.user["id"], utcnow()))
                    db.execute("INSERT INTO appointment_events(id, appointment_id, at, user_id, action, to_status, to_starts_at)"
                               " VALUES (?,?,?,?,?,?,?)", (new_id(), aid, utcnow(), g.user["id"], "creada", "solicitada", to_utc_str(start)))
                    audit("cita_creada", "cita", aid, {"paciente": patient["id"]}, db=db)
            except sqlite3.IntegrityError as exc:
                if "cruce_de_horario" in str(exc):
                    errors["starts_local"] = "Ese horario se cruza con otra cita activa del mismo profesional. Elija otro horario."
                else:
                    raise
            if not errors:
                flash("Cita agendada.", "ok")
                return redirect(url_for("agenda.day", fecha=start.astimezone(clinic_tz()).date().isoformat()))
    return render_template("agenda/nueva.html", patient=patient, pracs=pracs, durations=durations, values=values,
                           errors=errors), (409 if "starts_local" in errors and "cruza" in errors["starts_local"] else 422) if errors else 200


def _get_appt(appt_id):
    if not re.fullmatch(r"[0-9a-f]{32}", appt_id or ""):
        abort(404)
    a = get_db().execute("SELECT * FROM appointments WHERE id = ? AND org_id = ?", (appt_id, g.user["org_id"])).fetchone()
    if not a:
        abort(404)
    return a


@bp.route("/cita/<appt_id>")
@require("agenda.ver")
def view(appt_id):
    a = _get_appt(appt_id)
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (a["patient_id"],)).fetchone()
    events = db.execute("SELECT e.*, u.full_name FROM appointment_events e JOIN users u ON u.id = e.user_id"
                        " WHERE e.appointment_id = ? ORDER BY e.at", (a["id"],)).fetchall()
    prac = db.execute("SELECT full_name FROM users WHERE id = ?", (a["practitioner_id"],)).fetchone()
    note = db.execute("SELECT id, status FROM clinical_notes WHERE appointment_id = ? ORDER BY created_at DESC LIMIT 1",
                      (a["id"],)).fetchone() if can("clinico.ver") else None
    start_local = parse_utc(a["starts_at"]).astimezone(clinic_tz())
    minutes = int((parse_utc(a["ends_at"]) - parse_utc(a["starts_at"])).total_seconds() // 60)
    intake = db.execute("SELECT i.*, u.full_name FROM appointment_intake i JOIN users u ON u.id = i.recorded_by WHERE i.appointment_id = ?",
                        (a["id"],)).fetchone() if can("clinico.ver") else None
    return render_template("agenda/cita.html", a=a, p=p, events=events, prac=prac, note=note, transitions=TRANSITIONS,
                           intake=intake, intake_v=json.loads(intake["vitals"]) if intake else {},
                           start_local=start_local.strftime("%Y-%m-%dT%H:%M"), minutes=minutes)


@bp.route("/cita/<appt_id>/estado", methods=["POST"])
@require("agenda.editar")
def change_status(appt_id):
    a = _get_appt(appt_id)
    to = request.form.get("status")
    if to not in TRANSITIONS.get(a["status"], set()):
        abort(409, description=f"No se puede pasar de «{LABELS['appt_status'][a['status']]}» a «{LABELS['appt_status'].get(to, to)}».")
    if to in ("en_consulta", "atendida") and not can("clinico.editar"):
        abort(403)
    db = get_db()
    try:
        with write_tx(db):
            cur = db.execute("UPDATE appointments SET status = ?, arrived_at = CASE WHEN ? = 'presente' THEN ? ELSE arrived_at END,"
                             " updated_at = ?, version = version + 1 WHERE id = ? AND version = ?",
                             (to, to, utcnow(), utcnow(), a["id"], int(request.form.get("version", "0"))))
            if cur.rowcount == 0:
                abort(409, description="La cita cambió mientras la editaba. Recargue la página.")
            db.execute("INSERT INTO appointment_events(id, appointment_id, at, user_id, action, from_status, to_status, detail)"
                       " VALUES (?,?,?,?,?,?,?,?)", (new_id(), a["id"], utcnow(), g.user["id"], "estado", a["status"], to,
                                                     (request.form.get("detail") or "")[:300] or None))
            audit("cita_estado", "cita", a["id"], {"de": a["status"], "a": to}, db=db)
    except sqlite3.IntegrityError as exc:
        if "cruce_de_horario" in str(exc):
            abort(409, description="No se puede reactivar: el horario ya está ocupado.")
        raise
    if to == "en_consulta" and can("clinico.editar"):
        return redirect(url_for("notes.new", patient_id=a["patient_id"], appointment_id=a["id"], auto=1))
    back = request.form.get("back")
    if back and back.startswith("/") and not back.startswith("//"):
        return redirect(back)
    return redirect(url_for("agenda.view", appt_id=a["id"]))


@bp.route("/cita/<appt_id>/reprogramar", methods=["POST"])
@require("agenda.editar")
def reschedule(appt_id):
    a = _get_appt(appt_id)
    if a["status"] not in ("solicitada", "confirmada"):
        abort(409, description="Solo se pueden reprogramar citas solicitadas o confirmadas.")
    try:
        start = local_to_utc(request.form.get("starts_local", ""), clinic_tz())
        minutes = int(request.form.get("duration", "0"))
        if not 5 <= minutes <= 480:
            raise ValueError
    except ValueError:
        abort(400, description="Fecha, hora o duración no válidas.")
    reason = (request.form.get("detail") or "").strip()[:300] or None
    from .views_extras import availability_problems
    block, _ = availability_problems(get_db(), g.user["org_id"], a["practitioner_id"], start, start + timedelta(minutes=minutes))
    if block:
        abort(409, description=f"La agenda está bloqueada del {block['start_date']} al {block['end_date']}. Elija otra fecha.")
    db = get_db()
    try:
        with write_tx(db):
            cur = db.execute("UPDATE appointments SET starts_at = ?, ends_at = ?, status = 'solicitada', updated_at = ?,"
                             " version = version + 1 WHERE id = ? AND version = ?",
                             (to_utc_str(start), to_utc_str(start + timedelta(minutes=minutes)), utcnow(), a["id"],
                              int(request.form.get("version", "0"))))
            if cur.rowcount == 0:
                abort(409, description="La cita cambió mientras la editaba. Recargue la página.")
            db.execute("INSERT INTO appointment_events(id, appointment_id, at, user_id, action, from_status, to_status, from_starts_at,"
                       " to_starts_at, detail) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (new_id(), a["id"], utcnow(), g.user["id"], "reprogramada", a["status"], "solicitada", a["starts_at"],
                        to_utc_str(start), reason))
            # Nueva fecha → el recordatorio debe enviarse de nuevo con la fecha correcta.
            db.execute("DELETE FROM appointment_reminders WHERE appointment_id = ?", (a["id"],))
            audit("cita_reprogramada", "cita", a["id"], {"de": a["starts_at"], "a": to_utc_str(start)}, db=db)
    except sqlite3.IntegrityError as exc:
        if "cruce_de_horario" in str(exc):
            abort(409, description="El nuevo horario se cruza con otra cita activa del mismo profesional.")
        raise
    flash("Cita reprogramada. Quedó en estado «Solicitada» hasta confirmar con el paciente.", "ok")
    return redirect(url_for("agenda.view", appt_id=a["id"]))


# ------------------------------------------------------------------------------------------------ preconsulta (enfermería)
@bp.route("/cita/<appt_id>/preconsulta", methods=["GET", "POST"])
@require("preconsulta.registrar")
def intake(appt_id):
    from .views_notes import VITALS, _clean_fields
    a = _get_appt(appt_id)
    if a["status"] in ("atendida", "cancelada", "no_asistio"):
        abort(409, description="La cita ya terminó: los signos vitales se registran en la nota.")
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (a["patient_id"],)).fetchone()
    row = db.execute("SELECT * FROM appointment_intake WHERE appointment_id = ?", (a["id"],)).fetchone()
    data = {"vitales": json.loads(row["vitals"]) if row else {}, "motivo": row["motivo"] if row else ""}
    errors = {}
    if request.method == "POST":
        fields, errors = _clean_fields({k: v for k, v in request.form.items() if k.startswith("v_") or k == "motivo"}, "soap")
        motivo = (fields.get("motivo") or "").strip()[:2000] or None
        if not errors:
            with write_tx(db):
                if row:
                    db.execute("UPDATE appointment_intake SET vitals = ?, motivo = ?, recorded_by = ?, updated_at = ? WHERE appointment_id = ?",
                               (json.dumps(fields["vitales"]), motivo, g.user["id"], utcnow(), a["id"]))
                else:
                    db.execute("INSERT INTO appointment_intake(appointment_id, org_id, vitals, motivo, recorded_by, recorded_at, updated_at)"
                               " VALUES (?,?,?,?,?,?,?)", (a["id"], g.user["org_id"], json.dumps(fields["vitales"]), motivo, g.user["id"],
                                                          utcnow(), utcnow()))
                # si el médico ya abrió la nota en borrador y está vacía en esos campos, se completan
                n = db.execute("SELECT id, fields FROM clinical_notes WHERE appointment_id = ? AND status = 'borrador'", (a["id"],)).fetchone()
                if n:
                    f = json.loads(n["fields"])
                    changed = False
                    if not f.get("vitales") and fields["vitales"]:
                        f["vitales"] = fields["vitales"]
                        changed = True
                    if not f.get("motivo") and motivo:
                        f["motivo"] = motivo
                        changed = True
                    if changed:
                        db.execute("UPDATE clinical_notes SET fields = ?, updated_at = ?, version = version + 1 WHERE id = ?",
                                   (json.dumps(f, ensure_ascii=False, sort_keys=True), utcnow(), n["id"]))
                audit("preconsulta_registrada", "cita", a["id"], {"paciente": a["patient_id"]}, db=db)
            flash("Preconsulta guardada: el médico la encontrará en la nota.", "ok")
            back = request.form.get("back") or ""
            return redirect(back if back.startswith("/") and not back.startswith("//") else url_for("agenda.view", appt_id=a["id"]))
        data = {"vitales": {k[2:]: request.form.get(k) for k in request.form if k.startswith("v_")}, "motivo": request.form.get("motivo", "")}
    return render_template("agenda/preconsulta.html", a=a, p=p, data=data, errors=errors, vitals=VITALS), 422 if errors else 200
