"""Configuración de la clínica, usuarios (consulta) y bitácora de auditoría."""
import json
from zoneinfo import available_timezones

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db, utcnow, write_tx
from .security import DEFAULT_ROLES, PERMISSIONS, audit, require, verify_audit_chain
from .util import LABELS, local_today

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
    from .views_extras import load_assets
    from .pdf import LOGO_POSITIONS, LOGO_SIZES
    assets = load_assets(g.user["org_id"])
    lay = assets.get("_layout") or {}
    layout = {"logo": lay.get("logo", "izquierda"), "logo2": lay.get("logo2", "derecha"), "logo3": lay.get("logo3", "centro"),
              "custom": bool(lay)}
    for k in ("logo", "logo2", "logo3"):
        layout[f"{k}_size"] = lay.get(f"{k}_size") or lay.get("size") or "grande"
        layout[f"{k}_dx"] = lay.get(f"{k}_dx", 0) or 0
        layout[f"{k}_dy"] = lay.get(f"{k}_dy", 0) or 0
    style = db.execute("SELECT report_style FROM clinic_settings WHERE org_id = ?", (g.user["org_id"],)).fetchone()[0]
    return render_template("ajustes/clinica.html", data=data, errors=errors, tzs=tzs, assets=assets, layout=layout,
                           LOGO_POSITIONS=LOGO_POSITIONS, LOGO_SIZES=LOGO_SIZES, report_style=style), 422 if errors else 200


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


# ------------------------------------------------------------------------------------------------ respaldos y copia en Google Drive
def _backup_status():
    from pathlib import Path
    from flask import current_app
    from .backup import last_backup_age_hours
    cfg = current_app.config["GM"]
    files = sorted(Path(cfg.BACKUP_DIR).glob("neuromed-*.gmbak")) if Path(cfg.BACKUP_DIR).exists() else []
    log = Path(cfg.DATABASE_PATH).parent / "respaldo.log"
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:] if log.exists() else []
    return {"last": files[-1].name if files else None, "size_mb": round(files[-1].stat().st_size / 1048576, 1) if files else None,
            "age_h": last_backup_age_hours(cfg.BACKUP_DIR), "count": len(files), "log": list(reversed(lines)), "dir": cfg.BACKUP_DIR}


@bp.route("/respaldos")
@require("ajustes.editar")
def backups():
    from .backup import OFFSITE_SUBDIR, drive_candidates
    from .views_setup import _is_local
    st = get_db().execute("SELECT * FROM clinic_settings WHERE org_id = ?", (g.user["org_id"],)).fetchone()
    return render_template("ajustes/respaldos.html", st=st, b=_backup_status(), candidates=drive_candidates(), local=_is_local(),
                           sub=OFFSITE_SUBDIR)


# ------------------------------------------------------------------------------------------------ espacio en disco (v0.29.0)
def disk_usage_report(db, org_id, cfg):
    """Cuánto ocupa el programa: base de datos, estudios/fotos (cifrados), respaldos y espacio libre; y por paciente."""
    import shutil
    from pathlib import Path
    from .backup import backup_keep
    dbp = Path(cfg.DATABASE_PATH)
    db_bytes = sum(p.stat().st_size for p in (dbp, Path(str(dbp) + "-wal")) if p.exists())
    fdir = Path(cfg.FILES_DIR)
    per = {}
    files_bytes = 0
    for r in db.execute("SELECT f.patient_id, f.storage_name, f.archived_at FROM files f WHERE f.org_id = ?", (org_id,)):
        try:
            n = (fdir / r["storage_name"]).stat().st_size
        except OSError:
            continue
        files_bytes += n
        e = per.setdefault(r["patient_id"], {"bytes": 0, "files": 0})
        e["bytes"] += n
        e["files"] += 1
    bdir = Path(cfg.BACKUP_DIR)
    backs = sorted(bdir.glob("neuromed-*.gmbak")) if bdir.exists() else []
    back_bytes = sum(p.stat().st_size for p in backs)
    try:
        du = shutil.disk_usage(str(dbp.parent if dbp.parent.exists() else Path.home()))
        free, total = du.free, du.total
    except OSError:
        free = total = None
    keep = backup_keep(cfg.DATABASE_PATH, cfg.BACKUP_KEEP)
    last = backs[-1].stat().st_size if backs else db_bytes + files_bytes
    pats = {r["id"]: r for r in db.execute("SELECT id, first_names, last_names, mrn FROM patients WHERE org_id = ?", (org_id,))}
    n_pat = len(pats)
    top = sorted(per.items(), key=lambda x: -x[1]["bytes"])[:30]
    return {"db": db_bytes, "files": files_bytes, "data": db_bytes + files_bytes, "backups": back_bytes, "n_backups": len(backs),
            "free": free, "total": total, "keep": keep, "backup_dir": str(bdir), "estimate_keep": last * keep,
            "n_patients": n_pat, "avg": (db_bytes + files_bytes) / n_pat if n_pat else 0,
            "top": [{"p": pats[pid], **v} for pid, v in top if pid in pats]}


@bp.route("/espacio", methods=["GET", "POST"])
@require("ajustes.editar")
def disk_space():
    from flask import current_app
    from .backup import BACKUP_KEEP_CHOICES
    db = get_db()
    org = g.user["org_id"]
    if request.method == "POST":
        try:
            keep = int(request.form.get("keep") or 0)
        except ValueError:
            abort(400)
        if keep not in BACKUP_KEEP_CHOICES:
            abort(400)
        with write_tx(db):
            db.execute("UPDATE clinic_settings SET backup_keep = ?, updated_at = ?, updated_by = ?, version = version + 1 WHERE org_id = ?",
                       (keep, utcnow(), g.user["id"], org))
            audit("respaldos_copias_cambiadas", "ajustes", org, {"copias": keep}, db=db)
        flash(f"Se guardarán las últimas {keep} copias de respaldo. Las más viejas se borran en el próximo respaldo automático.", "ok")
        return redirect(url_for("settings.disk_space"))
    rep = disk_usage_report(db, org, current_app.config["GM"])
    audit("espacio_en_disco_consultado", "ajustes", org)
    return render_template("ajustes/espacio.html", r=rep, choices=BACKUP_KEEP_CHOICES)


# ------------------------------------------------------------------------------------------------ personal de endoscopia (v0.20.0)
STAFF_ROLES = {"medico": "Médicos endoscopistas", "asistente": "Asistentes"}


def ensure_owner(db, org_id):
    """Si la clínica aún no tiene ningún médico en la lista, agrega al dueño de la cuenta (nombre profesional de Ajustes)."""
    if db.execute("SELECT 1 FROM endo_staff WHERE org_id = ? AND role = 'medico' LIMIT 1", (org_id,)).fetchone():
        return
    s = db.execute("SELECT doctor_display_name FROM clinic_settings WHERE org_id = ?", (org_id,)).fetchone()
    if s and s[0]:
        from .db import new_id
        with write_tx(db):
            db.execute("INSERT INTO endo_staff(id, org_id, role, name, position, created_at) VALUES (?,?,?,?,0,?)",
                       (new_id(), org_id, "medico", s[0], utcnow()))


def endo_staff(db, org_id, role=None, active_only=True):
    if role in (None, "medico"):
        ensure_owner(db, org_id)
    q = "SELECT * FROM endo_staff WHERE org_id = ?" + (" AND role = ?" if role else "") + (" AND active = 1" if active_only else "")
    return db.execute(q + " ORDER BY role, active DESC, position, name", (org_id, role) if role else (org_id,)).fetchall()


@bp.route("/personal-endoscopia", methods=["GET", "POST"])
@require("ajustes.editar")
def endo_staff_page():
    import re
    from .db import new_id
    db = get_db()
    org = g.user["org_id"]
    if request.method == "POST":
        action = request.form.get("action")
        sid = request.form.get("id") or ""
        if action == "agregar":
            role = request.form.get("role")
            name = (request.form.get("name") or "").strip()[:120]
            detail = (request.form.get("detail") or "").strip()[:120] or None
            if role not in STAFF_ROLES or not name:
                flash("Escriba el nombre.", "error")
                return redirect(url_for("settings.endo_staff_page"))
            if db.execute("SELECT 1 FROM endo_staff WHERE org_id = ? AND role = ? AND lower(name) = lower(?) AND active = 1",
                          (org, role, name)).fetchone():
                flash(f"«{name}» ya está en la lista.", "error")
                return redirect(url_for("settings.endo_staff_page"))
            pos = db.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM endo_staff WHERE org_id = ? AND role = ?", (org, role)).fetchone()[0]
            with write_tx(db):
                db.execute("INSERT INTO endo_staff(id, org_id, role, name, detail, position, created_at) VALUES (?,?,?,?,?,?,?)",
                           (new_id(), org, role, name, detail, pos, utcnow()))
                audit("personal_endoscopia_agregado", "ajustes", org, {"rol": role, "nombre": name}, db=db)
            flash(f"«{name}» agregado.", "ok")
        elif re.fullmatch(r"[0-9a-f]{32}", sid) and action in ("desactivar", "activar", "subir", "editar"):
            row = db.execute("SELECT * FROM endo_staff WHERE id = ? AND org_id = ?", (sid, org)).fetchone() or abort(404)
            with write_tx(db):
                if action in ("desactivar", "activar"):
                    db.execute("UPDATE endo_staff SET active = ? WHERE id = ?", (1 if action == "activar" else 0, sid))
                elif action == "subir":     # el primero de la lista es el que aparece elegido por defecto
                    db.execute("UPDATE endo_staff SET position = position + 1 WHERE org_id = ? AND role = ?", (org, row["role"]))
                    db.execute("UPDATE endo_staff SET position = 0 WHERE id = ?", (sid,))
                else:
                    name = (request.form.get("name") or "").strip()[:120]
                    if name:
                        db.execute("UPDATE endo_staff SET name = ?, detail = ? WHERE id = ?",
                                   (name, (request.form.get("detail") or "").strip()[:120] or None, sid))
                audit("personal_endoscopia_modificado", "ajustes", org, {"accion": action, "nombre": row["name"]}, db=db)
            flash("Cambios guardados.", "ok")
        return redirect(url_for("settings.endo_staff_page"))
    rows = endo_staff(db, org, active_only=False)
    return render_template("ajustes/personal_endoscopia.html", rows=rows, ROLES=STAFF_ROLES)


@bp.route("/respaldos/drive", methods=["POST"])
@require("ajustes.editar")
def backups_drive():
    import os
    import secrets as _s
    from pathlib import Path
    from flask import current_app
    from .backup import OFFSITE_SUBDIR, offsite_copy, run_automatic
    from .views_setup import _is_local
    if not _is_local():
        abort(403, description="Por seguridad, la copia en Google Drive se configura solo desde la PC del consultorio.")
    action = request.form.get("action")
    db = get_db()
    cfg = current_app.config["GM"]
    if action == "activar":
        folder = ((request.form.get("folder_other") or "").strip() or (request.form.get("folder") or "").strip()).strip('"')
        try:
            keep = int(request.form.get("keep") or 7)
        except ValueError:
            keep = 7
        keep = keep if keep in (3, 7, 14, 30) else 7
        p = Path(folder)
        problem = None
        if not folder or not p.is_absolute() or not p.is_dir():
            problem = "No se encontró esa carpeta. Elija la carpeta de Google Drive que aparece en la lista o escriba la ruta completa."
        else:
            try:
                (p / OFFSITE_SUBDIR).mkdir(exist_ok=True)
                probe = p / OFFSITE_SUBDIR / f".prueba-{_s.token_hex(4)}"
                probe.write_bytes(b"ok")
                probe.unlink()
            except OSError as e:
                problem = f"No se pudo escribir en esa carpeta: {e}"
        if problem:
            flash(problem, "error")
            return redirect(url_for("settings.backups"))
        with write_tx(db):
            db.execute("UPDATE clinic_settings SET offsite_enabled = 1, offsite_dir = ?, offsite_keep = ?, updated_at = ?, updated_by = ?,"
                       " version = version + 1 WHERE org_id = ?", (str(p), keep, utcnow(), g.user["id"], g.user["org_id"]))
            audit("copia_drive_activada", "ajustes", g.user["org_id"], {"carpeta": str(p), "conservar": keep}, db=db)
        flash(f"Copia en Google Drive ACTIVADA en {p / OFFSITE_SUBDIR}. Pulse «Copiar ahora» para hacer la primera.", "ok")
    elif action == "desactivar":
        with write_tx(db):
            db.execute("UPDATE clinic_settings SET offsite_enabled = 0, updated_at = ?, updated_by = ?, version = version + 1 WHERE org_id = ?",
                       (utcnow(), g.user["id"], g.user["org_id"]))
            audit("copia_drive_desactivada", "ajustes", g.user["org_id"], db=db)
        flash("Copia en Google Drive desactivada. Las copias que ya están en Drive no se borran.", "ok")
    elif action == "copiar":
        files = sorted(Path(cfg.BACKUP_DIR).glob("neuromed-*.gmbak")) if Path(cfg.BACKUP_DIR).exists() else []
        if not files:
            key = os.environ.get("GASTROMED_BACKUP_KEY", "").encode()
            if not key:
                flash("No hay respaldos todavía y falta la clave de respaldo en esta instalación.", "error")
                return redirect(url_for("settings.backups"))
            from . import APP_VERSION
            from .crypto import load_data_key
            ok, msgs = run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)   # ya incluye la copia a Drive
            flash(" ".join(msgs), "ok" if ok else "error")
        else:
            ok, msg = offsite_copy(cfg.DATABASE_PATH, files[-1])
            flash(msg or "La copia en Google Drive está desactivada.", "ok" if ok and msg else "error")
        audit("copia_drive_manual", "ajustes", g.user["org_id"])
    else:
        abort(400)
    return redirect(url_for("settings.backups"))


# ------------------------------------------------------------------------------------------------ estilo del informe (v0.22.0)
def sample_report_pdf(style, s, assets, size):
    """Informe de EJEMPLO con datos ficticios para ver cómo queda cada estilo (no usa ningún paciente real)."""
    from . import endoscopy_defs as D
    from .pdf import procedure_pdf
    pr = {"id": "0" * 32, "kind": "eda", "status": "finalizado", "performed_on": local_today().isoformat(), "indication_category": "diagnostica",
          "extent": "segunda_porcion", "complete": 1, "withdrawal_minutes": None, "bbps_right": None, "bbps_transverse": None,
          "bbps_left": None, "surveillance_due": None}
    p = {"first_names": "Paciente", "last_names": "De Ejemplo", "mrn": "EJEMPLO", "document_type": "dni", "document_number": "0000-0000-00000",
         "birth_date": "1980-01-01", "sex": "femenino", "allergy_status": "sin_alergias_conocidas", "phone": None, "origin": None,
         "referring_physician": None, "payer": None}
    d = {"indication": "Dispepsia (texto de ejemplo)", "consent_obtained": True, "asa": "I", "sedation_type": "moderada",
         "endoscopist": s["doctor_display_name"], "assistants": "Asistente de ejemplo", "care_setting": "externa",
         "narrative": {"esofago": "Mucosa de aspecto normal (texto de ejemplo).", "estomago": "Eritema leve en antro (texto de ejemplo).",
                       "duodeno": "Sin alteraciones (texto de ejemplo)."},
         "conclusion": "Gastropatía eritematosa leve de antro (ejemplo).", "recommendations": "Texto de ejemplo.", "complications": []}
    return procedure_pdf(pr, d, p, s, size, [], None, [], D, assets, allergies=(), style=style)


@bp.route("/estilo-informe", methods=["GET", "POST"])
@require("ajustes.editar")
def report_style():
    from .pdf import REPORT_STYLES
    db = get_db()
    org = g.user["org_id"]
    if request.method == "POST":
        st = request.form.get("report_style")
        if st not in REPORT_STYLES:
            abort(400)
        with write_tx(db):
            db.execute("UPDATE clinic_settings SET report_style = ?, updated_at = ?, updated_by = ?, version = version + 1 WHERE org_id = ?",
                       (st, utcnow(), g.user["id"], org))
            audit("estilo_informe_cambiado", "ajustes", org, {"estilo": st}, db=db)
        flash(f"Estilo del informe: {REPORT_STYLES[st]}.", "ok")
        return redirect(url_for("settings.report_style"))
    cur = db.execute("SELECT report_style FROM clinic_settings WHERE org_id = ?", (org,)).fetchone()[0]
    return render_template("ajustes/estilo_informe.html", STYLES=REPORT_STYLES, current=cur)


@bp.route("/estilo-informe/ejemplo")
@require("ajustes.editar")
def report_style_sample():
    from flask import make_response
    from .pdf import REPORT_STYLES
    from .views_extras import load_assets
    st = request.args.get("estilo")
    if st not in REPORT_STYLES:
        abort(400)
    s = get_db().execute("SELECT * FROM clinic_settings WHERE org_id = ?", (g.user["org_id"],)).fetchone()
    resp = make_response(sample_report_pdf(st, s, load_assets(g.user["org_id"]), s["paper_size"]))
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="ejemplo-estilo-{st}.pdf"'
    return resp
