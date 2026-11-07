"""Asistente de configuración inicial de NeuroMed Pro en la PC del consultorio.

Lo ejecuta el instalador. Es seguro ejecutarlo de nuevo: nunca reemplaza claves ni usuarios existentes.

  python windows/configurar.py --datos C:\\NeuroMed\\datos --respaldos C:\\NeuroMed\\respaldos --escritorio <carpeta>
"""
import argparse
import getpass
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ask(prompt: str, default: str = "", env: str = "") -> str:
    """Pregunta en consola. GM_INSTALL_<env> permite responder sin teclado (pruebas automáticas)."""
    if env and os.environ.get("GM_INSTALL_" + env) is not None:
        return os.environ["GM_INSTALL_" + env]
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def write_env(env_file: Path, datos: Path, respaldos: Path, copy_dir: str):
    from cryptography.fernet import Fernet
    lines = [
        "# Configuración de NeuroMed Pro en esta PC. NO COMPARTA ESTE ARCHIVO.",
        f"# Creado {datetime.now():%Y-%m-%d %H:%M}",
        "GASTROMED_ENV=consultorio",
        f"GASTROMED_SECRET_KEY={secrets.token_hex(32)}",
        f"GASTROMED_DATA_KEY={Fernet.generate_key().decode()}",
        f"GASTROMED_BACKUP_KEY={Fernet.generate_key().decode()}",
        f"GASTROMED_DATABASE_PATH={datos / 'neuromed.sqlite3'}",
        f"GASTROMED_FILES_DIR={datos / 'archivos'}",
        f"GASTROMED_BACKUP_DIR={respaldos}",
        f"GASTROMED_BACKUP_COPY_DIR={copy_dir}",
        "GASTROMED_BACKUP_KEEP=30",
        "# Red local (Wi-Fi del consultorio) sin HTTPS: las cookies no pueden marcarse «Secure».",
        "GASTROMED_COOKIE_SECURE=0",
        "GASTROMED_SESSION_IDLE_MINUTES=30",
    ]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_keys_copy(env_file: Path, desktop: Path) -> Path:
    keys = [l for l in env_file.read_text(encoding="utf-8").splitlines() if l.startswith(("GASTROMED_DATA_KEY", "GASTROMED_BACKUP_KEY"))]
    out = desktop / "NeuroMed - CLAVES (copiar a USB y borrar de aqui).txt"
    out.write_text(
        "CLAVES DE GASTROMED PRO — CONSERVE UNA COPIA FUERA DE ESTA PC\n\n"
        "Sin estas claves no se pueden abrir los respaldos ni los estudios adjuntos si la PC se daña.\n"
        "1. Copie este archivo a una memoria USB (distinta de la de los respaldos) o imprímalo.\n"
        "2. Guárdelo en un lugar seguro (caja fuerte).\n"
        "3. Borre este archivo del escritorio.\n\n" + "\n".join(keys) + "\n", encoding="utf-8")
    return out


def create_owner(cfg):
    from app.bootstrap import create_organization, create_user
    from app.db import connect, migrate
    from app.security import password_problems
    migrate(cfg.DATABASE_PATH)
    db = connect(cfg.DATABASE_PATH)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        print("  Ya existen usuarios: se conservan.")
        return
    print("\n--- Cuenta del médico propietario (administrador) ---")
    clinic = ask("Nombre del consultorio", "Consultorio Dr. Mario Lainez", "CLINIC")
    name = ask("Nombre profesional (aparece en recetas)", "Dr. Mario Lainez", "NAME")
    while True:
        email = ask("Correo para ingresar al sistema", "", "EMAIL").lower()
        if "@" in email and "." in email.split("@")[-1]:
            break
        print("  Correo no válido.")
        if os.environ.get("GM_INSTALL_EMAIL") is not None:
            sys.exit(1)
    while True:
        pw = os.environ.get("GM_INSTALL_PASSWORD") or getpass.getpass("Contraseña (no se muestra al escribir): ")
        problems = password_problems(pw)
        if problems:
            print("  " + " ".join(problems))
            if os.environ.get("GM_INSTALL_PASSWORD"):
                sys.exit(1)
            continue
        if not os.environ.get("GM_INSTALL_PASSWORD") and getpass.getpass("Repita la contraseña: ") != pw:
            print("  No coinciden.")
            continue
        break
    org = create_organization(db, clinic, doctor_display_name=name)
    create_user(db, org, email, name, pw, "propietario", True)
    db.close()
    print(f"  Cuenta creada: {email}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True)
    ap.add_argument("--respaldos", required=True)
    ap.add_argument("--escritorio", default=str(Path.home() / "Desktop"))
    a = ap.parse_args()
    datos, respaldos = Path(a.datos), Path(a.respaldos)
    for d in (datos, datos / "archivos", respaldos):
        d.mkdir(parents=True, exist_ok=True)
    env_file = datos / "neuromed.env"
    if env_file.exists():
        print("  Configuración existente encontrada: se conservan las claves.")
    else:
        print("\n--- Copia externa de respaldos ---")
        print("  Recomendado: un disco externo o USB que se quede en el consultorio, p. ej. E:\\RespaldosNeuroMed")
        copy_dir = ask("Carpeta de copia externa (Enter para configurarla después)", "", "COPYDIR")
        write_env(env_file, datos, respaldos, copy_dir)
        keys = save_keys_copy(env_file, Path(a.escritorio))
        print(f"\n  IMPORTANTE: se guardó una copia de las claves en su escritorio:\n  {keys}\n"
              "  Cópiela a una USB o imprímala, guárdela en lugar seguro y luego bórrela del escritorio.")
    os.environ["GASTROMED_ENV_FILE"] = str(env_file)
    from app.config import Config
    cfg = Config()
    create_owner(cfg)
    print("\n  Configuración lista.")


if __name__ == "__main__":
    main()
