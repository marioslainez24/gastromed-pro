"""Mi cuenta: cambio de contraseña y verificación en dos pasos (TOTP)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .crypto import data_fernet, totp_new_secret, totp_uri, totp_verify
from .db import get_db, utcnow, write_tx
from .security import _hash_token, audit, hash_password, login_required, password_problems, verify_password, SESSION_COOKIE

bp = Blueprint("account", __name__, url_prefix="/cuenta")


@bp.route("/contrasena", methods=["GET", "POST"])
@login_required
def password():
    errors = []
    if request.method == "POST":
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        new = request.form.get("new_password") or ""
        if not verify_password(request.form.get("current_password") or "", user["password_hash"]):
            errors.append("La contraseña actual no es correcta.")
        errors += password_problems(new)
        if new != request.form.get("confirm_password"):
            errors.append("La confirmación no coincide.")
        if not errors and verify_password(new, user["password_hash"]):
            errors.append("La nueva contraseña debe ser distinta de la actual.")
        if not errors:
            current = _hash_token(request.cookies.get(SESSION_COOKIE, ""))
            with write_tx(db):
                db.execute("UPDATE users SET password_hash = ?, must_change_password = 0, password_changed_at = ? WHERE id = ?",
                           (hash_password(new), utcnow(), user["id"]))
                # Cierra las demás sesiones abiertas de este usuario
                db.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND token_hash <> ? AND revoked_at IS NULL",
                           (utcnow(), user["id"], current))
                audit("contrasena_cambiada", "usuario", user["id"], db=db)
            flash("Contraseña actualizada. Se cerraron sus otras sesiones abiertas.", "ok")
            return redirect(url_for("agenda.day"))
    return render_template("cuenta/contrasena.html", errors=errors, forced=g.user["must_change_password"]), 422 if errors else 200


@bp.route("/verificacion", methods=["GET"])
@login_required
def mfa():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    secret = None
    if not user["mfa_enabled"]:
        # Se genera (o reutiliza) un secreto pendiente; solo se activa al confirmar un código válido.
        if user["mfa_secret_enc"]:
            secret = data_fernet().decrypt(user["mfa_secret_enc"].encode()).decode()
        else:
            secret = totp_new_secret()
            with write_tx(db):
                db.execute("UPDATE users SET mfa_secret_enc = ? WHERE id = ? AND mfa_enabled = 0",
                           (data_fernet().encrypt(secret.encode()).decode(), user["id"]))
    grouped = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)) if secret else None
    return render_template("cuenta/mfa.html", enabled=bool(user["mfa_enabled"]), secret=grouped,
                           uri=totp_uri(secret, user["email"]) if secret else None, required=g.user["mfa_required"])


@bp.route("/verificacion/activar", methods=["POST"])
@login_required
def mfa_enable():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if user["mfa_enabled"] or not user["mfa_secret_enc"]:
        abort(409, description="La verificación en dos pasos ya estaba activa o falta generar la clave.")
    secret = data_fernet().decrypt(user["mfa_secret_enc"].encode()).decode()
    counter = totp_verify(secret, request.form.get("code", ""), 0)
    if counter is None:
        flash("Código incorrecto. Revise que la hora del celular esté en automático e intente con el código siguiente.", "error")
        return redirect(url_for("account.mfa"))
    with write_tx(db):
        db.execute("UPDATE users SET mfa_enabled = 1, mfa_last_counter = ? WHERE id = ?", (counter, user["id"]))
        audit("mfa_activado", "usuario", user["id"], db=db)
    flash("Verificación en dos pasos activada. Desde ahora se pedirá el código al ingresar.", "ok")
    return redirect(url_for("agenda.day"))


@bp.route("/verificacion/desactivar", methods=["POST"])
@login_required
def mfa_disable():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if g.user["mfa_required"]:
        abort(403)
    if not verify_password(request.form.get("password") or "", user["password_hash"]):
        flash("Contraseña incorrecta.", "error")
        return redirect(url_for("account.mfa"))
    with write_tx(db):
        db.execute("UPDATE users SET mfa_enabled = 0, mfa_secret_enc = NULL, mfa_last_counter = 0 WHERE id = ?", (user["id"],))
        audit("mfa_desactivado", "usuario", user["id"], db=db)
    flash("Verificación en dos pasos desactivada.", "ok")
    return redirect(url_for("account.mfa"))
