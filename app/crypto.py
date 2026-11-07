"""Cifrado de datos en reposo (archivos adjuntos y secretos MFA) y TOTP (RFC 6238).

Clave de datos: GASTROMED_DATA_KEY (clave Fernet: AES-128-CBC + HMAC-SHA256).
- En producción es obligatoria y debe guardarse también fuera del servidor (sin ella, los adjuntos no se pueden leer).
- En desarrollo/pruebas, si falta, se genera una en instance/clave_datos.key.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

__all__ = ["data_fernet", "InvalidToken", "totp_new_secret", "totp_now", "totp_verify", "totp_uri"]


def load_data_key(cfg) -> bytes:
    key = getattr(cfg, "DATA_KEY", "") or os.environ.get("GASTROMED_DATA_KEY")
    if key:
        return key.encode() if isinstance(key, str) else key
    if cfg.ENV in ("produccion", "consultorio"):
        raise RuntimeError("Falta GASTROMED_DATA_KEY. Ejecute de nuevo el instalador o restaure el archivo .env.")
    path = Path(cfg.DATABASE_PATH).parent / "clave_datos.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path.read_bytes().strip()


def data_fernet() -> Fernet:
    return current_app.config["GM_FERNET"]


# --------------------------------------------------------------------------- TOTP
def totp_new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _b32(secret: str) -> bytes:
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def _hotp(key: bytes, counter: int, digits=6) -> str:
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_now(secret: str, at: float | None = None, step=30) -> str:
    return _hotp(_b32(secret), int((at or time.time()) // step))


def totp_verify(secret: str, code: str, last_counter: int = 0, at: float | None = None, step=30, window=1) -> int | None:
    """Devuelve el contador usado si el código es válido y no se reutilizó; None si no."""
    code = (code or "").strip().replace(" ", "")
    if not (len(code) == 6 and code.isdigit()):
        return None
    now = int((at or time.time()) // step)
    key = _b32(secret)
    for c in range(now - window, now + window + 1):
        if c > last_counter and hmac.compare_digest(_hotp(key, c), code):
            return c
    return None


def totp_uri(secret: str, account: str, issuer="NeuroMed Pro") -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
