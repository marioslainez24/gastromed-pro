"""Licencia de uso por computadora (v0.24.0, pedido del Dr. Lainez: que nadie copie el programa y lo use en su clínica).

Cómo funciona:
- Cada computadora tiene un «código de equipo» (se calcula del identificador de Windows / Mac; no cambia al reiniciar).
- La «clave de activación» es ese código + el nombre del titular, FIRMADOS con una llave privada que solo existe como secreto en la
  cuenta de GitHub del Dr. Lainez. El programa solo trae la llave pública: puede comprobar una clave, pero no puede fabricarla.
- Copiado a otra PC, el código cambia y la clave deja de servir: el programa pide activación y no abre ninguna otra pantalla.

Límite honesto: esto detiene la copia y el uso no autorizado normales; una persona experta con mucho tiempo podría modificar el
ejecutable. Por eso, además, el nombre del titular sale en el programa y en todos los documentos.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Llave PÚBLICA (Ed25519). La privada NO está en el código: es el secreto GM_LICENCIA_CLAVE de GitHub.
PUBLIC_KEY_B64 = "uqiL9A3pdQN1pMLjHOUKGUXHWX/t3TP1JhQyNpPVmxw="
PREFIX = "GM1"
CODE_RE = re.compile(r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")


class LicenseError(Exception):
    pass


def _public_key_b64():
    # Solo para pruebas desde el código fuente (no en el .exe): permite usar una llave de prueba.
    if not getattr(sys, "frozen", False) and os.environ.get("GASTROMED_LICENSE_PUBKEY"):
        return os.environ["GASTROMED_LICENSE_PUBKEY"]
    return PUBLIC_KEY_B64


def machine_id() -> str:
    """Identificador estable de esta computadora."""
    if os.environ.get("GASTROMED_MACHINE_ID_TEST") and not getattr(sys, "frozen", False):
        return os.environ["GASTROMED_MACHINE_ID_TEST"]
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
                return "win:" + str(winreg.QueryValueEx(k, "MachineGuid")[0]).strip().lower()
        except OSError:
            pass
    elif sys.platform == "darwin":
        try:
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            if m:
                return "mac:" + m.group(1).lower()
        except (OSError, subprocess.SubprocessError):
            pass
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            v = Path(p).read_text().strip()
            if v:
                return "lin:" + v.lower()
        except OSError:
            pass
    import uuid
    return "mac-addr:" + format(uuid.getnode(), "x")


def machine_code(mid: str | None = None) -> str:
    """Código de equipo que el médico copia para pedir su clave: 16 caracteres en 4 grupos (ej.: 3F2A-91C0-7B44-0DE1)."""
    h = hashlib.sha256(("GastroMedPro|" + (mid or machine_id())).encode()).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(private_key_b64: str, code: str, holder: str, issued: str) -> str:
    """Fabrica una clave (solo lo hace el generador de GitHub, que tiene la llave privada)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    code = code.strip().upper()
    if not CODE_RE.match(code):
        raise LicenseError("Código de equipo no válido.")
    payload = json.dumps({"v": 1, "equipo": code, "titular": holder.strip()[:120], "emitida": issued}, ensure_ascii=False,
                         separators=(",", ":"), sort_keys=True).encode()
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64.strip()))
    return f"{PREFIX}.{_b64u(payload)}.{_b64u(key.sign(payload))}"


def verify(text: str, code: str | None = None) -> dict:
    """Comprueba la clave para ESTA computadora. Devuelve {"equipo", "titular", "emitida"} o lanza LicenseError."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    text = re.sub(r"\s+", "", text or "")
    parts = text.split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise LicenseError("La clave no tiene el formato correcto. Cópiela completa, sin cortar.")
    try:
        payload, sig = _unb64u(parts[1]), _unb64u(parts[2])
        Ed25519PublicKey.from_public_bytes(base64.b64decode(_public_key_b64())).verify(sig, payload)
        data = json.loads(payload)
    except (InvalidSignature, ValueError):
        raise LicenseError("La clave no es válida (no fue generada para NeuroMed Pro o está incompleta).")
    if data.get("v") != 1 or not data.get("titular"):
        raise LicenseError("La clave no es válida.")
    if data.get("equipo") != (code or machine_code()):
        raise LicenseError("Esta clave es de OTRA computadora. Pida una clave con el código de esta PC.")
    return {"equipo": data["equipo"], "titular": data["titular"], "emitida": data.get("emitida", "")}


# ---- estado en memoria del programa en marcha ------------------------------------------------------------------------------------
_STATE = {"file": None, "info": None}


def configure(path) -> None:
    """El lanzador del .exe indica dónde está el archivo de licencia; desde ese momento la licencia es obligatoria."""
    _STATE["file"] = Path(path) if path else None
    _STATE["info"] = None
    if _STATE["file"] and _STATE["file"].exists():
        try:
            _STATE["info"] = verify(_STATE["file"].read_text(encoding="utf-8"))
        except (LicenseError, OSError):
            _STATE["info"] = None


def required() -> bool:
    return _STATE["file"] is not None


def active() -> bool:
    return not required() or _STATE["info"] is not None


def info() -> dict | None:
    return _STATE["info"]


def holder() -> str:
    """Nombre del titular para el pie del programa y de los documentos (vacío si no hay licencia, p. ej. en pruebas)."""
    return (_STATE["info"] or {}).get("titular", "")


def activate(text: str) -> dict:
    data = verify(text)
    _STATE["file"].parent.mkdir(parents=True, exist_ok=True)
    _STATE["file"].write_text(re.sub(r"\s+", "", text) + "\n", encoding="utf-8")
    _STATE["info"] = data
    return data
