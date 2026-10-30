"""Configuración de GastroMed Pro.

Todos los secretos vienen de variables de entorno (o de un archivo .env que NUNCA se sube al
repositorio). No hay secretos en el código ni en el frontend.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Lector mínimo de .env (CLAVE=valor), sin dependencias externas."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Config:
    def __init__(self, **overrides):
        _load_dotenv(BASE_DIR / ".env")
        self.ENV = os.environ.get("GASTROMED_ENV", "desarrollo")  # desarrollo | pruebas | produccion
        self.SECRET_KEY = os.environ.get("GASTROMED_SECRET_KEY", "")
        self.DATABASE_PATH = os.environ.get(
            "GASTROMED_DATABASE_PATH", str(BASE_DIR / "instance" / "gastromed.sqlite3"))
        self.FILES_DIR = os.environ.get("GASTROMED_FILES_DIR", str(BASE_DIR / "instance" / "archivos"))
        # Cookies "Secure" (solo HTTPS) obligatorias en producción.
        self.COOKIE_SECURE = os.environ.get("GASTROMED_COOKIE_SECURE", "1" if self.ENV == "produccion" else "0") == "1"
        self.SESSION_IDLE_MINUTES = int(os.environ.get("GASTROMED_SESSION_IDLE_MINUTES", "30"))
        self.SESSION_ABSOLUTE_HOURS = int(os.environ.get("GASTROMED_SESSION_ABSOLUTE_HOURS", "12"))
        self.LOGIN_MAX_FAILURES = int(os.environ.get("GASTROMED_LOGIN_MAX_FAILURES", "5"))
        self.LOGIN_LOCK_MINUTES = int(os.environ.get("GASTROMED_LOGIN_LOCK_MINUTES", "15"))
        self.LOGIN_IP_LIMIT_PER_15MIN = int(os.environ.get("GASTROMED_LOGIN_IP_LIMIT", "30"))
        self.TRUST_PROXY = os.environ.get("GASTROMED_TRUST_PROXY", "0") == "1"
        for k, v in overrides.items():
            setattr(self, k, v)
        self.validate()

    def validate(self):
        if self.ENV == "produccion":
            if len(self.SECRET_KEY) < 32:
                raise RuntimeError("GASTROMED_SECRET_KEY debe tener al menos 32 caracteres en producción.")
            if not self.COOKIE_SECURE:
                raise RuntimeError("En producción las cookies deben ser Secure (HTTPS).")
        if not self.SECRET_KEY:
            # En desarrollo se genera una clave temporal por proceso (las sesiones se pierden al reiniciar).
            import secrets
            self.SECRET_KEY = secrets.token_hex(32)
