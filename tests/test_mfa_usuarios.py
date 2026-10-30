"""Verificación en dos pasos, gestión de usuarios y cambio obligatorio de contraseña."""
import re
import time

from conftest import PASSWORDS, csrf, login
from app.crypto import totp_now, totp_verify


def test_totp_vectores_rfc6238():
    # Vectores oficiales RFC 6238 (SHA-1, clave "12345678901234567890"), truncados a 6 dígitos
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode()
    for t, code in [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037")]:
        assert totp_now(secret, at=t) == code
    assert totp_verify(secret, "287082", 0, at=59) == 1
    assert totp_verify(secret, "287082", 1, at=59) is None  # no se puede reutilizar


def _enable_mfa(env, client):
    html = client.get("/cuenta/verificacion").get_data(as_text=True)
    secret = re.search(r'aria-label="Clave de configuración">([A-Z2-7 ]+)<', html).group(1).replace(" ", "")
    r = client.post("/cuenta/verificacion/activar", data={"csrf_token": csrf(client), "code": totp_now(secret)})
    assert r.status_code == 302
    return secret


def test_activar_mfa_y_login_en_dos_pasos(env):
    app = env["app"]
    med = login(app, "propietario")
    secret = _enable_mfa(env, med)
    c = app.test_client()
    tok = re.search(r'name="login_csrf" value="([^"]+)"', c.get("/ingresar").get_data(as_text=True)).group(1)
    r = c.post("/ingresar", data={"login_csrf": tok, "email": "propietario@prueba.hn", "password": PASSWORDS["propietario"]})
    assert r.status_code == 302 and r.headers["Location"].endswith("/ingresar/verificacion")
    assert c.get("/agenda/").status_code == 302  # aún sin sesión
    assert c.post("/ingresar/verificacion", data={"code": "000000"}).status_code == 401
    # El código usado al activar no puede reutilizarse; se usa el del siguiente intervalo
    code = totp_now(secret, at=time.time() + 30)
    r = c.post("/ingresar/verificacion", data={"code": code})
    assert r.status_code == 302 and c.get("/agenda/").status_code == 200
    # Secreto cifrado en la base
    enc = env["db"].execute("SELECT mfa_secret_enc FROM users WHERE id = ?", (env["users"]["propietario"],)).fetchone()[0]
    assert secret not in enc


def test_desafio_mfa_limita_intentos(env):
    app = env["app"]
    med = login(app, "propietario")
    secret = _enable_mfa(env, med)
    c = app.test_client()
    tok = re.search(r'name="login_csrf" value="([^"]+)"', c.get("/ingresar").get_data(as_text=True)).group(1)
    c.post("/ingresar", data={"login_csrf": tok, "email": "propietario@prueba.hn", "password": PASSWORDS["propietario"]})
    for _ in range(5):
        c.post("/ingresar/verificacion", data={"code": "111111"})
    r = c.post("/ingresar/verificacion", data={"code": totp_now(secret, at=time.time() + 30)})
    assert r.status_code == 302 and r.headers["Location"].endswith("/ingresar")  # desafío agotado: debe empezar de nuevo


def test_crear_usuario_contrasena_temporal_y_cambio_obligatorio(env):
    app = env["app"]
    owner = login(app, "propietario")
    roles = {r["code"]: r["id"] for r in env["db"].execute("SELECT code, id FROM roles WHERE org_id = ?", (env["org"]["org_id"],))}
    r = owner.post("/ajustes/usuarios/nuevo", data={"csrf_token": csrf(owner), "full_name": "Nueva Recepcionista",
                                                     "email": "nueva@prueba.hn", "role_id": roles["recepcion"]})
    assert r.status_code == 200
    temp = re.search(r'class="secret mono">([A-Za-z0-9]{16})<', r.get_data(as_text=True)).group(1)
    c = app.test_client()
    tok = re.search(r'name="login_csrf" value="([^"]+)"', c.get("/ingresar").get_data(as_text=True)).group(1)
    assert c.post("/ingresar", data={"login_csrf": tok, "email": "nueva@prueba.hn", "password": temp}).status_code == 302
    r = c.get("/agenda/")
    assert r.status_code == 302 and "/cuenta/contrasena" in r.headers["Location"]
    tok2 = re.search(r'name="csrf_token" value="([^"]+)"', c.get("/cuenta/contrasena").get_data(as_text=True)).group(1)
    assert c.post("/pacientes/nuevo", data={"csrf_token": tok2}).status_code == 403  # bloqueado hasta cambiarla
    r = c.post("/cuenta/contrasena", data={"csrf_token": tok2, "current_password": temp, "new_password": "corta",
                                           "confirm_password": "corta"})
    assert r.status_code == 422
    r = c.post("/cuenta/contrasena", data={"csrf_token": tok2, "current_password": temp, "new_password": "Recepcion-Nueva-2026",
                                           "confirm_password": "Recepcion-Nueva-2026"})
    assert r.status_code == 302 and c.get("/agenda/").status_code == 200


def test_desactivar_usuario_cierra_sesiones_y_protege_al_ultimo_propietario(env):
    app = env["app"]
    owner = login(app, "propietario")
    rec = login(app, "recepcion")
    assert rec.get("/agenda/").status_code == 200
    tok = csrf(owner)
    assert owner.post(f"/ajustes/usuarios/{env['users']['recepcion']}/estado", data={"csrf_token": tok, "active": "0"}).status_code == 302
    assert rec.get("/agenda/").status_code == 302
    roles = {r["code"]: r["id"] for r in env["db"].execute("SELECT code, id FROM roles WHERE org_id = ?", (env["org"]["org_id"],))}
    # Quitarse el rol de propietario siendo el único → rechazado
    owner.post(f"/ajustes/usuarios/{env['users']['propietario']}/editar", data={"csrf_token": tok, "role_id": roles["medico"]})
    assert env["db"].execute("SELECT r.code FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?",
                             (env["users"]["propietario"],)).fetchone()[0] == "propietario"
    # Otro usuario no puede gestionar usuarios
    medico = login(app, "medico")
    assert medico.post(f"/ajustes/usuarios/{env['users']['caja']}/estado", data={"csrf_token": csrf(medico), "active": "0"}).status_code == 403


def test_politica_mfa_obligatoria(env):
    app = env["app"]
    owner = login(app, "propietario")
    tok = csrf(owner)
    owner.post("/ajustes/seguridad", data={"csrf_token": tok, "require_mfa": "1"})
    assert env["db"].execute("SELECT require_mfa FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0] == 0
    _enable_mfa(env, owner)
    owner.post("/ajustes/seguridad", data={"csrf_token": csrf(owner), "require_mfa": "1"})
    rec = login(app, "recepcion")
    r = rec.get("/agenda/")
    assert r.status_code == 302 and "/cuenta/verificacion" in r.headers["Location"]
