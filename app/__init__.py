"""GastroMed Pro — aplicación Flask."""
import ipaddress
import os

from flask import Flask, g, redirect, render_template, request, url_for

from . import util
from .config import Config
from .db import close_db, migrate
from .security import PERMISSIONS, SESSION_COOKIE, can, check_csrf, enforce_account_requirements, load_current_user

APP_VERSION = "0.18.0"


def _loopback(addr) -> bool:
    try:
        return ipaddress.ip_address(addr or "").is_loopback
    except ValueError:
        return False


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config()
    app = Flask(__name__, instance_relative_config=False)
    app.config["GM"] = cfg
    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # formularios; los adjuntos tendrán su propio límite
    app.config["TEMPLATES_AUTO_RELOAD"] = cfg.ENV == "desarrollo"
    # Cookie firmada de Flask: solo transporta mensajes de aviso (flash), nunca datos clínicos.
    app.config.update(SESSION_COOKIE_NAME="gm_avisos", SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SECURE=cfg.COOKIE_SECURE, SESSION_COOKIE_SAMESITE="Lax")

    migrate(cfg.DATABASE_PATH)
    from cryptography.fernet import Fernet
    from .crypto import load_data_key
    app.config["GM_FERNET"] = Fernet(load_data_key(cfg))
    app.config["MAX_CONTENT_LENGTH"] = 21 * 1024 * 1024  # adjuntos hasta 20 MB (+ margen del formulario)
    # Archivos del programa con la versión en la dirección (/static/v0.10.2/js/app.js). Así, al actualizar el .exe el navegador
    # pide la copia nueva aunque tenga guardada una vieja (error corregido en v0.10.2). Mismo «endpoint» que /static.
    app.add_url_rule(f"/static/v{APP_VERSION}/<path:filename>", endpoint="static", view_func=app.view_functions["static"])

    from .auth import bp as auth_bp
    from .views_patients import bp as patients_bp
    from .views_agenda import bp as agenda_bp
    from .views_notes import bp as notes_bp
    from .views_prescriptions import bp as rx_bp
    from .views_settings import bp as settings_bp
    from .views_record import bp as record_bp
    from .views_files import bp as files_bp
    from .views_account import bp as account_bp
    from .views_setup import bp as setup_bp, needs_setup
    from .views_labs import bp as labs_bp
    from .views_gi import bp as gi_bp
    from .views_endoscopy import bp as endo_bp
    from .views_extras import bp as extras_bp
    from .views_texts import bp as texts_bp
    from .views_documents import bp as docs_bp
    for bp in (auth_bp, patients_bp, agenda_bp, notes_bp, rx_bp, settings_bp, record_bp, files_bp, account_bp, setup_bp, labs_bp, gi_bp,
               endo_bp, extras_bp, texts_bp, docs_bp):
        app.register_blueprint(bp)

    app.teardown_appcontext(close_db)

    https_port = os.environ.get("GASTROMED_HTTPS_PORT", "")

    @app.before_request
    def _before():
        # Conexiones desde otros equipos (celular) por http → se envían a https (Wi-Fi cifrado). En esta PC sigue http://localhost.
        if https_port and request.scheme == "http" and not _loopback(request.remote_addr):
            host = (request.host or "").rsplit(":", 1)[0]
            return redirect(f"https://{host}:{https_port}{request.full_path.rstrip('?')}", code=302)
        if request.endpoint in ("static", "auth.manifest", "auth.service_worker"):
            return
        if request.endpoint != "setup.first_run" and needs_setup():
            return redirect(url_for("setup.first_run"))
        load_current_user()
        check_csrf()
        return enforce_account_requirements()

    @app.after_request
    def _headers(resp):
        h = resp.headers
        h.setdefault("Content-Security-Policy", ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
                                        "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; "
                                        "base-uri 'none'; object-src 'none'"))
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        if cfg.COOKIE_SECURE:
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.endpoint != "static":
            # Ninguna página con datos se guarda en caché del navegador ni de intermediarios.
            h["Cache-Control"] = "no-store"
            h["Pragma"] = "no-cache"
        return resp

    def _approved_sheets():
        from .views_endoscopy import approved_sheets
        return approved_sheets()

    def _endo_kinds():
        from .endoscopy_defs import KINDS
        return KINDS

    @app.context_processor
    def _ctx():
        return {"can": can, "label": util.label, "fmt_dt": util.fmt_dt, "fmt_time": util.fmt_time, "age": util.age,
                "fmt_birth": util.fmt_birth, "parse_utc": util.parse_utc, "current_user": g.get("user"), "csrf_token": g.get("csrf_token"),
                "approved_sheets": _approved_sheets, "ENDO_KINDS": _endo_kinds(), "app_version": APP_VERSION, "asset": lambda f: f"/static/v{APP_VERSION}/{f}", "env": cfg.ENV, "demo_mode": cfg.DEMO, "clinic_cfg": util.clinic_settings}

    def _err(code, title, msg):
        def handler(e):
            desc = getattr(e, "description", None)
            if request.is_json or request.accept_mimetypes.best == "application/json":
                return {"error": title, "detalle": desc if isinstance(desc, str) and code in (400, 409) else msg}, code
            return render_template("error.html", code=code, title=title,
                                   message=desc if isinstance(desc, str) and code in (400, 409) else msg), code
        return handler

    app.register_error_handler(400, _err(400, "Solicitud no válida", "Revise los datos e intente de nuevo."))
    app.register_error_handler(401, _err(401, "Sesión requerida", "Inicie sesión para continuar."))
    app.register_error_handler(403, _err(403, "Acceso no autorizado",
                                         "Su rol no tiene permiso para esta acción. Si lo necesita, solicítelo al administrador."))
    app.register_error_handler(404, _err(404, "No encontrado", "El registro no existe o no está disponible para su usuario."))
    app.register_error_handler(409, _err(409, "Conflicto", "El registro cambió mientras lo editaba."))
    app.register_error_handler(413, _err(413, "Contenido demasiado grande", "El envío supera el tamaño permitido."))
    app.register_error_handler(500, _err(500, "Error interno",
                                         "Ocurrió un error inesperado. No se guardaron cambios parciales. Intente de nuevo."))
    app.jinja_env.globals["PERMISSIONS"] = PERMISSIONS
    app.jinja_env.globals["dict"] = dict
    app.jinja_env.filters["zip_self"] = lambda seq: [(x, x) for x in seq]
    app.jinja_env.globals["SESSION_COOKIE"] = SESSION_COOKIE
    return app
