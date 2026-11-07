"""Configuración inicial en el navegador: crea la clínica y la cuenta del médico propietario.

Solo está disponible mientras NO exista ningún usuario y solo desde la misma PC (localhost),
para que nadie en la red Wi-Fi pueda adelantarse a crear la cuenta de administrador.
"""
import hmac
import ipaddress
import secrets

from flask import Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, url_for

from .bootstrap import create_organization, create_user
from .db import get_db
from .security import password_problems

bp = Blueprint("setup", __name__)
SETUP_COOKIE = "nm_setup_csrf"


def needs_setup() -> bool:
    if current_app.config.get("GM_SETUP_DONE"):
        return False
    done = get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    if done:
        current_app.config["GM_SETUP_DONE"] = True
    return not done


def _is_local() -> bool:
    try:
        return ipaddress.ip_address(request.remote_addr or "").is_loopback
    except ValueError:
        return False


@bp.route("/configuracion-inicial", methods=["GET", "POST"])
def first_run():
    if not needs_setup():
        return redirect(url_for("auth.login"))
    if not _is_local():
        return render_template("setup/solo_local.html"), 403
    errors, form = [], {}
    if request.method == "POST":
        tok = request.cookies.get(SETUP_COOKIE, "")
        if not tok or not hmac.compare_digest(tok, request.form.get("setup_csrf", "")):
            abort(400, description="El formulario caducó. Recargue la página.")
        form = {k: (request.form.get(k) or "").strip() for k in ("clinic", "name", "email", "specialty")}
        pw = request.form.get("password") or ""
        if not form["clinic"] or not form["name"]:
            errors.append("Escriba el nombre del consultorio y su nombre profesional.")
        if "@" not in form["email"] or "." not in form["email"].split("@")[-1]:
            errors.append("Escriba un correo válido (será su usuario para ingresar).")
        errors += password_problems(pw)
        if pw != request.form.get("password2"):
            errors.append("Las contraseñas no coinciden.")
        if not errors:
            db = get_db()
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():   # doble verificación ante doble clic
                return redirect(url_for("auth.login"))
            org = create_organization(db, form["clinic"][:160], doctor_display_name=form["name"][:120],
                                      specialty=form["specialty"][:160] or "Neurología")
            create_user(db, org, form["email"].lower()[:200], form["name"][:120], pw, "propietario", True)
            current_app.config["GM_SETUP_DONE"] = True
            flash("Cuenta creada. Ingrese con su correo y contraseña.", "ok")
            resp = make_response(redirect(url_for("auth.login")))
            resp.delete_cookie(SETUP_COOKIE)
            return resp
    tok = secrets.token_urlsafe(24)
    resp = make_response(render_template("setup/inicio.html", errors=errors, form=form, setup_csrf=tok), 422 if errors else 200)
    resp.set_cookie(SETUP_COOKIE, tok, httponly=True, samesite="Strict", max_age=3600)
    return resp
