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
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Config:
    def __init__(self, **overrides):
        # En la PC del consultorio el instalador guarda la configuración junto a los datos (no dentro del programa),
        # para que actualizar el programa nunca borre las claves.
        _load_dotenv(Path(os.environ.get("GASTROMED_ENV_FILE", str(BASE_DIR / ".env"))))
        # desarrollo | pruebas | consultorio (servidor privado en la PC del consultorio) | produccion (internet + HTTPS)
        self.ENV = os.environ.get("GASTROMED_ENV", "desarrollo")
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
        self.DEMO = os.environ.get("GASTROMED_DEMO", "0") == "1"
        self.BACKUP_DIR = os.environ.get("GASTROMED_BACKUP_DIR", str(BASE_DIR / "respaldos"))
        self.BACKUP_COPY_DIR = os.environ.get("GASTROMED_BACKUP_COPY_DIR", "")  # p. ej., disco externo o USB
        self.BACKUP_KEEP = int(os.environ.get("GASTROMED_BACKUP_KEEP", "30"))
        for k, v in overrides.items():
            setattr(self, k, v)
        self.validate()

    @property
    def REAL_DATA(self) -> bool:
        """Entornos donde puede haber pacientes reales: exigen claves explícitas."""
        return self.ENV in ("consultorio", "produccion")

    def validate(self):
        if self.ENV not in ("desarrollo", "pruebas", "consultorio", "produccion"):
            raise RuntimeError(f"GASTROMED_ENV no válido: {self.ENV}")
        if self.ENV == "consultorio" and len(self.SECRET_KEY) < 32:
            raise RuntimeError("GASTROMED_SECRET_KEY debe tener al menos 32 caracteres. Ejecute de nuevo el instalador.")
        if self.ENV == "produccion":
            if len(self.SECRET_KEY) < 32:
                raise RuntimeError("GASTROMED_SECRET_KEY debe tener al menos 32 caracteres en producción.")
            if not self.COOKIE_SECURE:
                raise RuntimeError("En producción las cookies deben ser Secure (HTTPS).")
        if not self.SECRET_KEY:
            # En desarrollo se genera una clave temporal por proceso (las sesiones se pierden al reiniciar).
            import secrets
            self.SECRET_KEY = secrets.token_hex(32)
