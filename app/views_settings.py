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
    s = db.execute("SELECT require_mfa FROM clinic_settings WHERE org_id = ?", (g.user["org_id"],)).fetchone()
    return render_template("ajustes/usuarios.html", rows=rows, roles=roles, perms=perms, PERMISSIONS=PERMISSIONS,
                           require_mfa=bool(s["require_mfa"]))


@bp.route("/auditoria")
@require("auditoria.ver")
def audit_log():
    db = get_db()
    rows = db.execute("SELECT a.*, u.full_name FROM audit_log a LEFT JOIN users u ON u.id = a.user_id"
                      " WHERE a.org_id = ? ORDER BY a.seq DESC LIMIT 200", (g.user["org_id"],)).fetchall()
    ok, broken = verify_audit_chain(db)
    return render_template("ajustes/auditoria.html", rows=rows, chain_ok=ok, broken=broken)


# ---------------------------------------------------------------------------
# Gestión de usuarios (alta, rol, desactivación, contraseña temporal, MFA)
# ---------------------------------------------------------------------------
import re as _re
import secrets as _secrets

from .db import new_id
from .security import hash_password


def _temp_password() -> str:
    # 16 caracteres con mayúsculas, minúsculas y dígitos; se muestra una sola vez.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    while True:
        p = "".join(_secrets.choice(alphabet) for _ in range(16))
        if any(c.isdigit() for c in p) and any(c.islower() for c in p) and any(c.isupper() for c in p):
            return p


def _get_user(user_id):
    u = get_db().execute("SELECT * FROM users WHERE id = ? AND org_id = ?", (user_id, g.user["org_id"])).fetchone()
    if not u:
        abort(404)
    return u


def _owners_active(db, exclude=None):
    return db.execute("SELECT COUNT(*) c FROM users u JOIN roles r ON r.id = u.role_id WHERE u.org_id = ? AND u.active = 1"
                      " AND r.code = 'propietario' AND u.id <> COALESCE(?, '')", (g.user["org_id"], exclude)).fetchone()["c"]


@bp.route("/usuarios/nuevo", methods=["POST"])
@require("usuarios.gestionar")
def user_create():
    db = get_db()
    email = (request.form.get("email") or "").strip().lower()[:200]
    name = (request.form.get("full_name") or "").strip()[:120]
    role = db.execute("SELECT * FROM roles WHERE id = ? AND org_id = ?", (request.form.get("role_id"), g.user["org_id"])).fetchone()
    if not _re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not name or not role:
        flash("Complete nombre, correo válido y rol.", "error")
        return redirect(url_for("settings.users"))
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        flash("Ya existe un usuario con ese correo.", "error")
        return redirect(url_for("settings.users"))
    temp = _temp_password()
    uid = new_id()
    site = db.execute("SELECT id FROM sites WHERE org_id = ? ORDER BY created_at LIMIT 1", (g.user["org_id"],)).fetchone()
    with write_tx(db):
        db.execute("INSERT INTO users(id, org_id, email, full_name, password_hash, role_id, is_practitioner, must_change_password, created_at)"
                   " VALUES (?,?,?,?,?,?,?,1,?)", (uid, g.user["org_id"], email, name, hash_password(temp), role["id"],
                                                   int(request.form.get("is_practitioner") == "1"), utcnow()))
        db.execute("INSERT INTO user_sites(user_id, site_id) VALUES (?,?)", (uid, site["id"]))
        audit("usuario_creado", "usuario", uid, {"rol": role["code"]}, db=db)
    return render_template("ajustes/clave_temporal.html", email=email, name=name, temp=temp)


@bp.route("/usuarios/<user_id>/editar", methods=["POST"])
@require("usuarios.gestionar")
def user_update(user_id):
    u = _get_user(user_id)
    db = get_db()
    role = db.execute("SELECT * FROM roles WHERE id = ? AND org_id = ?", (request.form.get("role_id"), g.user["org_id"])).fetchone()
    if not role:
        abort(400)
    if role["code"] != "propietario" and _owners_active(db, exclude=u["id"]) == 0:
        flash("Debe quedar al menos un propietario activo.", "error")
        return redirect(url_for("settings.users"))
    with write_tx(db):
        db.execute("UPDATE users SET role_id = ?, is_practitioner = ?, version = version + 1 WHERE id = ?",
                   (role["id"], int(request.form.get("is_practitioner") == "1"), u["id"]))
        audit("usuario_editado", "usuario", u["id"], {"rol": role["code"]}, db=db)
    flash("Usuario actualizado.", "ok")
    return redirect(url_for("settings.users"))


@bp.route("/usuarios/<user_id>/estado", methods=["POST"])
@require("usuarios.gestionar")
def user_toggle(user_id):
    u = _get_user(user_id)
    db = get_db()
    activate = request.form.get("active") == "1"
    if not activate and (u["id"] == g.user["id"] or _owners_active(db, exclude=u["id"]) == 0):
        flash("No puede desactivar su propio usuario ni al último propietario activo.", "error")
        return redirect(url_for("settings.users"))
    with write_tx(db):
        db.execute("UPDATE users SET active = ?, deactivated_at = ? WHERE id = ?", (int(activate), None if activate else utcnow(), u["id"]))
        if not activate:
            db.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (utcnow(), u["id"]))
        audit("usuario_activado" if activate else "usuario_desactivado", "usuario", u["id"], db=db)
    flash("Usuario reactivado." if activate else "Usuario desactivado; sus sesiones se cerraron y sus registros conservan la autoría.", "ok")
    return redirect(url_for("settings.users"))


@bp.route("/usuarios/<user_id>/restablecer", methods=["POST"])
@require("usuarios.gestionar")
def user_reset(user_id):
    u = _get_user(user_id)
    db = get_db()
    temp = _temp_password()
    reset_mfa = request.form.get("reset_mfa") == "1"
    with write_tx(db):
        db.execute("UPDATE users SET password_hash = ?, must_change_password = 1, failed_logins = 0, locked_until = NULL WHERE id = ?",
                   (hash_password(temp), u["id"]))
        if reset_mfa:
            db.execute("UPDATE users SET mfa_enabled = 0, mfa_secret_enc = NULL, mfa_last_counter = 0 WHERE id = ?", (u["id"],))
        db.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (utcnow(), u["id"]))
        audit("usuario_restablecido", "usuario", u["id"], {"mfa_reiniciado": reset_mfa}, db=db)
    return render_template("ajustes/clave_temporal.html", email=u["email"], name=u["full_name"], temp=temp)


@bp.route("/seguridad", methods=["POST"])
@require("ajustes.editar")
def security_settings():
    db = get_db()
    require_mfa = int(request.form.get("require_mfa") == "1")
    if require_mfa and not g.user["mfa_enabled"]:
        flash("Active primero su propia verificación en dos pasos (Mi cuenta) antes de exigirla a todos.", "error")
        return redirect(url_for("settings.users"))
    with write_tx(db):
        db.execute("UPDATE clinic_settings SET require_mfa = ?, version = version + 1 WHERE org_id = ?", (require_mfa, g.user["org_id"]))
        audit("politica_mfa", "ajustes", g.user["org_id"], {"obligatoria": bool(require_mfa)}, db=db)
    flash("Política de verificación en dos pasos actualizada.", "ok")
    return redirect(url_for("settings.users"))
