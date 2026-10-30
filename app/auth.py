"""Inicio y cierre de sesión."""
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, g, make_response, redirect, render_template, request, url_for

from .db import get_db, utcnow, write_tx
from .security import (SESSION_COOKIE, audit, client_ip, create_session, dummy_verify, login_required,
                       revoke_current_session, verify_password, _parse)

bp = Blueprint("auth", __name__)
LOGIN_CSRF_COOKIE = "gm_login_csrf"


def _safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("agenda.day")


@bp.route("/")
def index():
    return redirect(url_for("agenda.day") if g.user else url_for("auth.login"))


@bp.route("/ingresar", methods=["GET", "POST"])
def login():
    cfg = current_app.config["GM"]
    error = None
    if request.method == "POST":
        cookie_tok = request.cookies.get(LOGIN_CSRF_COOKIE, "")
        form_tok = request.form.get("login_csrf", "")
        if not cookie_tok or not hmac.compare_digest(cookie_tok, form_tok):
            abort(400, description="El formulario caducó. Recargue la página e intente de nuevo.")
        email = (request.form.get("email") or "").strip().lower()[:200]
        password = request.form.get("password") or ""
        db = get_db()
        ip = client_ip()
        since = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        ip_fails = db.execute("SELECT COUNT(*) c FROM login_attempts WHERE ip = ? AND at > ? AND success = 0",
                              (ip, since)).fetchone()["c"]
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        now = datetime.now(timezone.utc)
        locked = bool(user and user["locked_until"] and _parse(user["locked_until"]) > now)
        ok = False
        if ip_fails >= cfg.LOGIN_IP_LIMIT_PER_15MIN or locked:
            dummy_verify(password)
        elif user is None:
            dummy_verify(password)
        else:
            ok = verify_password(password, user["password_hash"]) and bool(user["active"])
        with write_tx(db):
            db.execute("INSERT INTO login_attempts(ip, email, at, success) VALUES (?,?,?,?)", (ip, email, utcnow(), int(ok)))
            if user and not ok and not locked:
                fails = user["failed_logins"] + 1
                lock_until = None
                if fails >= cfg.LOGIN_MAX_FAILURES:
                    lock_until = (now + timedelta(minutes=cfg.LOGIN_LOCK_MINUTES)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    fails = 0
                db.execute("UPDATE users SET failed_logins = ?, locked_until = COALESCE(?, locked_until) WHERE id = ?",
                           (fails, lock_until, user["id"]))
            if user and ok:
                db.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
            audit("inicio_sesion_exitoso" if ok else "inicio_sesion_fallido", "usuario", user["id"] if user else None,
                  {"motivo": "bloqueado" if locked else ("limite_ip" if ip_fails >= cfg.LOGIN_IP_LIMIT_PER_15MIN else None)}
                  if not ok else None, db=db, user_id=user["id"] if user else None, org_id=user["org_id"] if user else None)
        if ok:
            token = create_session(user["id"])
            resp = make_response(redirect(_safe_next(request.args.get("next"))))
            resp.set_cookie(SESSION_COOKIE, token, httponly=True, secure=cfg.COOKIE_SECURE, samesite="Lax",
                            max_age=cfg.SESSION_ABSOLUTE_HOURS * 3600, path="/")
            resp.delete_cookie(LOGIN_CSRF_COOKIE, path="/ingresar")
            return resp
        # Mensaje genérico: no revela si el correo existe o si la cuenta está bloqueada.
        error = "Correo o contraseña incorrectos, o la cuenta está temporalmente bloqueada por intentos fallidos."
    if g.user:
        return redirect(url_for("agenda.day"))
    tok = secrets.token_urlsafe(24)
    resp = make_response(render_template("auth/login.html", error=error, login_csrf=tok,
                                         expired=bool(g.get("session_expired"))), 401 if error else 200)
    resp.set_cookie(LOGIN_CSRF_COOKIE, tok, httponly=True, secure=cfg.COOKIE_SECURE, samesite="Strict",
                    max_age=3600, path="/ingresar")
    return resp


@bp.route("/salir", methods=["POST"])
@login_required
def logout():
    audit("cierre_sesion", "usuario", g.user["id"])
    revoke_current_session()
    resp = make_response(redirect(url_for("auth.login")))
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@bp.route("/manifest.webmanifest")
def manifest():
    return current_app.send_static_file("manifest.webmanifest"), 200, {"Content-Type": "application/manifest+json"}


@bp.route("/sw.js")
def service_worker():
    resp = current_app.send_static_file("js/sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp
