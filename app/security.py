"""Autenticación, sesiones, CSRF, permisos y auditoría."""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import abort, current_app, g, redirect, request, url_for

from .db import get_db, utcnow, write_tx

SESSION_COOKIE = "gm_sesion"

# ---------------------------------------------------------------------------
# Permisos por acción. Los roles son configurables por organización (tabla role_permissions);
# estos son los valores iniciales de mínimo privilegio.
# ---------------------------------------------------------------------------
PERMISSIONS = {
    "pacientes.ver_admin": "Ver datos administrativos de pacientes",
    "pacientes.editar_admin": "Registrar y editar datos administrativos de pacientes",
    "clinico.ver": "Ver información clínica (alergias, alertas, notas, recetas)",
    "clinico.editar": "Registrar información clínica y notas",
    "notas.finalizar": "Finalizar notas clínicas",
    "recetas.emitir": "Emitir recetas",
    "recetas.anular": "Anular recetas",
    "agenda.ver": "Ver agenda",
    "agenda.editar": "Crear, confirmar, reprogramar y cancelar citas",
    "ajustes.editar": "Editar configuración de la clínica",
    "usuarios.gestionar": "Gestionar usuarios y roles",
    "auditoria.ver": "Ver bitácora de auditoría",
    "resultados.registrar": "Registrar resultados de laboratorio",
    "resultados.revisar": "Revisar y comunicar resultados",
    "ordenes.emitir": "Emitir órdenes de laboratorio, imagen y endoscopia",
    "tareas.gestionar": "Crear y completar tareas",
    "calculadoras.aprobar": "Aprobar calculadoras para uso clínico",
    "endoscopia.reprocesamiento": "Registrar reprocesamiento de endoscopios",
    "preconsulta.registrar": "Registrar signos vitales y motivo antes de la consulta",
}

DEFAULT_ROLES = {
    "propietario": ("Médico propietario y administrador", list(PERMISSIONS)),
    "medico": ("Médico colaborador", ["pacientes.ver_admin", "pacientes.editar_admin", "clinico.ver", "clinico.editar",
                                       "notas.finalizar", "recetas.emitir", "recetas.anular", "agenda.ver", "agenda.editar",
                                       "resultados.registrar", "resultados.revisar", "ordenes.emitir", "tareas.gestionar",
                                       "endoscopia.reprocesamiento", "preconsulta.registrar"]),
    "enfermeria": ("Enfermería", ["pacientes.ver_admin", "clinico.ver", "agenda.ver", "resultados.registrar", "tareas.gestionar",
                                  "endoscopia.reprocesamiento", "preconsulta.registrar"]),
    "recepcion": ("Recepción", ["pacientes.ver_admin", "pacientes.editar_admin", "agenda.ver", "agenda.editar", "tareas.gestionar"]),
    "caja": ("Caja y contabilidad", ["pacientes.ver_admin", "agenda.ver"]),
}


# ---------------------------------------------------------------------------
# Contraseñas: scrypt (biblioteca estándar), parámetros memoria-intensivos.
# ---------------------------------------------------------------------------
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 15, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
                        maxmem=64 * 1024 * 1024, dklen=32)
    return "scrypt${}${}${}${}${}".format(_SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
                                          base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p),
                            maxmem=64 * 1024 * 1024, dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


# Hash ficticio para igualar tiempos cuando el correo no existe.
_DUMMY_HASH = None


def dummy_verify(password: str):
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    verify_password(password, _DUMMY_HASH)


def password_problems(password: str) -> list[str]:
    problems = []
    if len(password) < 12:
        problems.append("Debe tener al menos 12 caracteres.")
    if password.lower() == password or password.upper() == password:
        problems.append("Combine mayúsculas y minúsculas.")
    if not any(c.isdigit() for c in password):
        problems.append("Incluya al menos un número.")
    return problems


# ---------------------------------------------------------------------------
# Sesiones de servidor
# ---------------------------------------------------------------------------
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def client_ip() -> str:
    cfg = current_app.config["GM"]
    if cfg.TRUST_PROXY and request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    return request.remote_addr or "?"


def create_session(user_id: str) -> str:
    cfg = current_app.config["GM"]
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db = get_db()
    with write_tx(db):
        db.execute(
            "INSERT INTO sessions(token_hash, user_id, csrf_token, created_at, last_seen_at, expires_at, ip, user_agent)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (_hash_token(token), user_id, secrets.token_urlsafe(32), utcnow(), utcnow(),
             (now + timedelta(hours=cfg.SESSION_ABSOLUTE_HOURS)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
             client_ip(), (request.user_agent.string or "")[:200]))
    return token


def revoke_current_session():
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db = get_db()
        with write_tx(db):
            db.execute("UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                       (utcnow(), _hash_token(token)))


def load_current_user():
    """Carga g.user y g.perms a partir de la cookie. Aplica expiración por inactividad y absoluta."""
    g.user, g.perms, g.csrf_token = None, frozenset(), None
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return
    db = get_db()
    row = db.execute(
        "SELECT s.*, u.id AS uid, u.org_id, u.full_name, u.email, u.role_id, u.active, u.is_practitioner, r.code AS role_code,"
        " r.name AS role_name, u.must_change_password, u.mfa_enabled, cs.require_mfa FROM sessions s JOIN users u ON u.id = s.user_id"
        " JOIN roles r ON r.id = u.role_id LEFT JOIN clinic_settings cs ON cs.org_id = u.org_id"
        " WHERE s.token_hash = ?", (_hash_token(token),)).fetchone()
    if not row or row["revoked_at"] or not row["active"]:
        return
    now = datetime.now(timezone.utc)
    cfg = current_app.config["GM"]
    expires = _parse(row["expires_at"])
    last_seen = _parse(row["last_seen_at"])
    if now >= expires or now - last_seen > timedelta(minutes=cfg.SESSION_IDLE_MINUTES):
        with write_tx(db):
            db.execute("UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                       (utcnow(), row["token_hash"]))
        g.session_expired = True
        return
    # Actualizar "visto por última vez" como máximo una vez por minuto.
    if now - last_seen > timedelta(seconds=60):
        with write_tx(db):
            db.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (utcnow(), row["token_hash"]))
    perms = {r["permission"] for r in db.execute("SELECT permission FROM role_permissions WHERE role_id = ?", (row["role_id"],))}
    g.user = {"id": row["uid"], "org_id": row["org_id"], "full_name": row["full_name"], "email": row["email"],
              "role_code": row["role_code"], "role_name": row["role_name"], "is_practitioner": bool(row["is_practitioner"]),
              "must_change_password": bool(row["must_change_password"]), "mfa_enabled": bool(row["mfa_enabled"]),
              "mfa_required": bool(row["require_mfa"])}
    g.perms = frozenset(perms)
    g.csrf_token = row["csrf_token"]


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# CSRF (token sincronizado por sesión) para TODA petición que modifica datos.
# ---------------------------------------------------------------------------
def check_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.endpoint in ("auth.login", "auth.mfa_verify", "setup.first_run"):  # usan su propio token
        # El inicio de sesión usa un token de formulario firmado propio (ver auth.py).
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not g.get("csrf_token") or not hmac.compare_digest(sent, g.csrf_token):
        abort(400, description="La solicitud no se pudo verificar (token de seguridad inválido). Recargue la página e intente de nuevo.")


ACCOUNT_EXEMPT = {"account.password", "account.mfa", "account.mfa_enable", "auth.logout", "auth.manifest", "auth.service_worker"}


def enforce_account_requirements():
    """Cambio obligatorio de contraseña y MFA obligatorio (si la clínica lo exige) antes de usar el sistema."""
    u = g.get("user")
    if not u or request.endpoint in ACCOUNT_EXEMPT or request.endpoint == "static":
        return None
    if u["must_change_password"]:
        if request.method != "GET":
            abort(403)
        return redirect(url_for("account.password"))
    if u["mfa_required"] and not u["mfa_enabled"]:
        if request.method != "GET":
            abort(403)
        return redirect(url_for("account.mfa"))
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not g.get("user"):
            if request.accept_mimetypes.best == "application/json" or request.is_json:
                abort(401)
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return view(*a, **kw)
    return wrapped


def require(*perms):
    """Exige todos los permisos indicados. La verificación ocurre siempre en el servidor."""
    def deco(view):
        @wraps(view)
        @login_required
        def wrapped(*a, **kw):
            missing = [p for p in perms if p not in g.perms]
            if missing:
                audit("acceso_denegado", "ruta", request.endpoint, {"faltan": missing})
                abort(403)
            return view(*a, **kw)
        return wrapped
    return deco


def can(perm: str) -> bool:
    return perm in g.get("perms", frozenset())


# ---------------------------------------------------------------------------
# Auditoría encadenada por hash
# ---------------------------------------------------------------------------
def audit(action: str, entity: str | None = None, entity_id: str | None = None, detail: dict | None = None,
          db=None, user_id: str | None = None, org_id: str | None = None):
    """Registra un evento. Si se pasa `db` se asume que ya hay una transacción abierta."""
    own = db is None
    db = db or get_db()
    user = g.get("user") or {}
    uid = user_id or user.get("id")
    oid = org_id or user.get("org_id")
    try:
        ip = client_ip()
    except RuntimeError:
        ip = None
    det = json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)

    def _insert():
        prev = db.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev["hash"] if prev else "0" * 64
        at = utcnow()
        h = hashlib.sha256("|".join([prev_hash, at, oid or "", uid or "", action, entity or "", entity_id or "", ip or "", det]).encode()).hexdigest()
        db.execute("INSERT INTO audit_log(at, org_id, user_id, action, entity, entity_id, ip, detail, prev_hash, hash)"
                   " VALUES (?,?,?,?,?,?,?,?,?,?)", (at, oid, uid, action, entity, entity_id, ip, det, prev_hash, h))

    if own:
        with write_tx(db):
            _insert()
    else:
        _insert()


def verify_audit_chain(db) -> tuple[bool, int | None]:
    prev_hash = "0" * 64
    for r in db.execute("SELECT * FROM audit_log ORDER BY seq"):
        expected = hashlib.sha256("|".join([prev_hash, r["at"], r["org_id"] or "", r["user_id"] or "", r["action"],
                                            r["entity"] or "", r["entity_id"] or "", r["ip"] or "", r["detail"]]).encode()).hexdigest()
        if r["prev_hash"] != prev_hash or r["hash"] != expected:
            return False, r["seq"]
        prev_hash = r["hash"]
    return True, None
