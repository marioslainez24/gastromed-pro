"""Pantalla de activación (v0.24.0): muestra el código de esta computadora y recibe la clave de activación.

Solo se puede activar desde la misma PC (localhost), igual que la configuración inicial.
"""
import hmac
import secrets

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for

from . import license as L
from .views_setup import _is_local

bp = Blueprint("license", __name__)
COOKIE = "nm_activar_csrf"


@bp.route("/activar", methods=["GET", "POST"])
def activate():
    if L.active():
        return redirect(url_for("auth.login"))
    local = _is_local()
    error = None
    if request.method == "POST":
        if not local:
            abort(403)
        tok = request.cookies.get(COOKIE, "")
        if not tok or not hmac.compare_digest(tok, request.form.get("activar_csrf", "")):
            abort(400, description="El formulario caducó. Recargue la página.")
        try:
            data = L.activate(request.form.get("clave") or "")
        except L.LicenseError as e:
            error = str(e)
        else:
            try:
                from .security import audit
                audit("licencia_activada", "licencia", data["equipo"], {"titular": data["titular"]})
            except Exception:  # noqa: BLE001  (antes de la configuración inicial todavía no hay base lista)
                pass
            flash(f"Programa activado a nombre de {data['titular']}.", "ok")
            resp = make_response(redirect(url_for("auth.login")))
            resp.delete_cookie(COOKIE)
            return resp
    tok = secrets.token_urlsafe(24)
    resp = make_response(render_template("licencia/activar.html", code=L.machine_code(), local=local, error=error, csrf=tok),
                         422 if error else (200 if local else 403))
    resp.set_cookie(COOKIE, tok, httponly=True, samesite="Strict", max_age=3600)
    return resp
