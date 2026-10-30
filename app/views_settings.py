"""Configuración de la clínica, usuarios (consulta) y bitácora de auditoría."""
import json
from zoneinfo import available_timezones

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db, utcnow, write_tx
from .security import DEFAULT_ROLES, PERMISSIONS, audit, require, verify_audit_chain
from .util import LABELS

bp = Blueprint("settings", __name__, url_prefix="/ajustes")

TEXT = {"doctor_display_name": ("Nombre profesional", True, 120), "specialty": ("Especialidad", False, 160),
        "license_number": ("Número de colegiación", False, 60), "address": ("Dirección", False, 300),
        "phones": ("Teléfonos", False, 120), "contact_email": ("Correo de contacto", False, 160),
        "currency": ("Moneda (código ISO)", True, 3), "locale": ("Configuración regional", True, 10),
        "phone_prefix": ("Prefijo telefónico", True, 6)}


@bp.route("/", methods=["GET", "POST"])
@require("ajustes.editar")
def clinic():
    db = get_db()
    s = db.execute("SELECT * FROM clinic_settings WHERE org_id = ?", (g.user["org_id"],)).fetchone()
    errors = {}
    data = dict(s)
    data["durations"] = json.loads(s["appointment_durations"])
    if request.method == "POST":
        for k, (lab, req, mx) in TEXT.items():
            v = (request.form.get(k) or "").strip()
            if req and not v:
                errors[k] = "Obligatorio."
            if len(v) > mx:
                errors[k] = f"Máximo {mx} caracteres."
            data[k] = v or None
        tzname = request.form.get("timezone", "")
        if tzname not in available_timezones():
            errors["timezone"] = "Zona horaria no válida."
        data["timezone"] = tzname
        paper = request.form.get("paper_size")
        if paper not in ("carta", "a4"):
            errors["paper_size"] = "Elija carta o A4."
        data["paper_size"] = paper
        durs = {}
        for t in LABELS["appt_type"]:
            try:
                m = int(request.form.get(f"dur_{t}", ""))
                if not 5 <= m <= 480:
                    raise ValueError
                durs[t] = m
            except ValueError:
                errors[f"dur_{t}"] = "Entre 5 y 480 minutos."
        data["durations"] = durs or data["durations"]
        if not errors:
            with write_tx(db):
                cur = db.execute(
                    "UPDATE clinic_settings SET " + ", ".join(f"{k} = ?" for k in TEXT) +
                    ", timezone = ?, paper_size = ?, appointment_durations = ?, updated_at = ?, updated_by = ?, version = version + 1"
                    " WHERE org_id = ? AND version = ?",
                    [data[k] for k in TEXT] + [tzname, paper, json.dumps(durs), utcnow(), g.user["id"], g.user["org_id"],
                                               int(request.form.get("version", "0"))])
                if cur.rowcount == 0:
                    abort(409, description="La configuración cambió mientras la editaba. Recargue la página.")
                audit("ajustes_editados", "ajustes", g.user["org_id"], db=db)
            flash("Configuración guardada.", "ok")
            return redirect(url_for("settings.clinic"))
    tzs = sorted(t for t in available_timezones() if t.startswith("America/"))
    return render_template("ajustes/clinica.html", data=data, errors=errors, tzs=tzs), 422 if errors else 200


@bp.route("/usuarios")
@require("usuarios.gestionar")
def users():
    db = get_db()
    rows = db.execute("SELECT u.*, r.name AS role_name, r.code AS role_code FROM users u JOIN roles r ON r.id = u.role_id"
                      " WHERE u.org_id = ? ORDER BY u.active DESC, u.full_name", (g.user["org_id"],)).fetchall()
    roles = db.execute("SELECT * FROM roles WHERE org_id = ? ORDER BY name", (g.user["org_id"],)).fetchall()
    perms = {r["id"]: {x["permission"] for x in db.execute("SELECT permission FROM role_permissions WHERE role_id = ?", (r["id"],))}
             for r in roles}
    return render_template("ajustes/usuarios.html", rows=rows, roles=roles, perms=perms, PERMISSIONS=PERMISSIONS)


@bp.route("/auditoria")
@require("auditoria.ver")
def audit_log():
    db = get_db()
    rows = db.execute("SELECT a.*, u.full_name FROM audit_log a LEFT JOIN users u ON u.id = a.user_id"
                      " WHERE a.org_id = ? ORDER BY a.seq DESC LIMIT 200", (g.user["org_id"],)).fetchall()
    ok, broken = verify_audit_chain(db)
    return render_template("ajustes/auditoria.html", rows=rows, chain_ok=ok, broken=broken)
