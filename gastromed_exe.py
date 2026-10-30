"""Punto de entrada del programa GastroMedPro.exe (Windows).

Doble clic → prepara la carpeta de datos (la primera vez crea las claves de cifrado), inicia el servidor
para esta PC y el Wi-Fi del consultorio, abre el navegador y hace el respaldo diario en segundo plano.
No requiere instalar Python ni ningún otro programa.
"""
import os
import secrets
import socket
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

PORT = int(os.environ.get("GASTROMED_PORT", "8000"))


def data_root() -> Path:
    """C:\\GastroMed si se puede escribir; si no, la carpeta del usuario."""
    if os.environ.get("GASTROMED_ROOT"):
        return Path(os.environ["GASTROMED_ROOT"])
    for cand in (Path("C:/GastroMed") if os.name == "nt" else None, Path.home() / "GastroMed"):
        if cand is None:
            continue
        try:
            cand.mkdir(parents=True, exist_ok=True)
            probe = cand / ".escritura"
            probe.write_text("ok")
            probe.unlink()
            return cand
        except OSError:
            continue
    raise SystemExit("No se pudo crear la carpeta de datos de GastroMed.")


def desktop() -> Path:
    d = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    if not d.exists():
        one = Path(os.environ.get("OneDrive", "")) / "Desktop"
        d = one if one.exists() else Path.home()
    return d


def first_run_config(root: Path) -> Path:
    """Crea gastromed.env con claves nuevas solo si no existe. Nunca reemplaza claves existentes."""
    from cryptography.fernet import Fernet
    datos, respaldos = root / "datos", root / "respaldos"
    for d in (datos, datos / "archivos", respaldos):
        d.mkdir(parents=True, exist_ok=True)
    env_file = datos / "gastromed.env"
    if env_file.exists():
        return env_file
    lines = [
        "# Configuración de GastroMed Pro en esta PC. NO COMPARTA ESTE ARCHIVO.",
        f"# Creado {datetime.now():%Y-%m-%d %H:%M}",
        "GASTROMED_ENV=consultorio",
        f"GASTROMED_SECRET_KEY={secrets.token_hex(32)}",
        f"GASTROMED_DATA_KEY={Fernet.generate_key().decode()}",
        f"GASTROMED_BACKUP_KEY={Fernet.generate_key().decode()}",
        f"GASTROMED_DATABASE_PATH={datos / 'gastromed.sqlite3'}",
        f"GASTROMED_FILES_DIR={datos / 'archivos'}",
        f"GASTROMED_BACKUP_DIR={respaldos}",
        "# Carpeta de un disco externo o USB para copiar cada respaldo, p. ej.: E:\\RespaldosGastroMed",
        "GASTROMED_BACKUP_COPY_DIR=",
        "GASTROMED_BACKUP_KEEP=30",
        "GASTROMED_COOKIE_SECURE=0",
        "GASTROMED_SESSION_IDLE_MINUTES=30",
    ]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    keys = [l for l in lines if l.startswith(("GASTROMED_DATA_KEY", "GASTROMED_BACKUP_KEY"))]
    try:
        (desktop() / "GastroMed - CLAVES (copiar a USB y borrar de aqui).txt").write_text(
            "CLAVES DE GASTROMED PRO — CONSERVE UNA COPIA FUERA DE ESTA PC\n\n"
            "Sin estas claves no se pueden abrir los respaldos ni los estudios adjuntos si la PC se daña.\n"
            "1. Copie este archivo a una memoria USB o imprímalo.\n2. Guárdelo en un lugar seguro.\n"
            "3. Borre este archivo del escritorio.\n\n" + "\n".join(keys) + "\n"
            f"\nCarpeta de datos: {datos}\nCarpeta de respaldos: {respaldos}\n", encoding="utf-8")
    except OSError:
        pass
    return env_file


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def lan_addresses() -> list[str]:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.0.1", 9))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def backup_loop(app):
    """Respaldo diario: al iniciar si el último tiene más de 24 h, y luego se revisa cada hora."""
    from app import APP_VERSION
    from app.backup import last_backup_age_hours, run_automatic
    from app.crypto import load_data_key
    cfg = app.config["GM"]
    key = os.environ.get("GASTROMED_BACKUP_KEY", "").encode()
    time.sleep(20)
    while True:
        try:
            age = last_backup_age_hours(cfg.BACKUP_DIR)
            if age is None or age >= 24:
                ok, msgs = run_automatic(cfg, key, load_data_key(cfg), APP_VERSION)
                stamp = datetime.now().strftime("%H:%M")
                print(f"  [{stamp}] Respaldo {'correcto' if ok else 'CON ERRORES'}: " + " | ".join(msgs), flush=True)
        except Exception as e:  # noqa: BLE001
            print("  Error en el respaldo automático:", e, flush=True)
        time.sleep(3600)


def main():
    if os.name == "nt":
        os.system("title GastroMed Pro - NO CERRAR esta ventana")
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    no_browser = "--sin-navegador" in sys.argv
    if port_in_use(PORT):
        print("GastroMed Pro ya está abierto. Abriendo el navegador…")
        if not no_browser:
            webbrowser.open(f"http://localhost:{PORT}")
        time.sleep(3)
        return
    root = data_root()
    env_file = first_run_config(root)
    os.environ["GASTROMED_ENV_FILE"] = str(env_file)

    from app import APP_VERSION, create_app
    app = create_app()
    cfg = app.config["GM"]
    print("=" * 66)
    print(f"  GastroMed Pro {APP_VERSION}")
    print("=" * 66)
    print(f"  En esta PC:        http://localhost:{PORT}")
    for ip in lan_addresses():
        print(f"  Desde el celular:  http://{ip}:{PORT}   (mismo Wi-Fi)")
    print(f"  Datos:             {Path(cfg.DATABASE_PATH).parent}")
    print(f"  Respaldos:         {cfg.BACKUP_DIR}  (automático cada 24 h)")
    print("\n  NO CIERRE ESTA VENTANA mientras use el sistema. Para apagarlo, ciérrela.")
    print("=" * 66, flush=True)

    threading.Thread(target=backup_loop, args=(app,), daemon=True).start()
    if not no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    from waitress import serve
    serve(app, host=os.environ.get("GASTROMED_HOST", "0.0.0.0"), port=PORT, threads=8, ident="GastroMed",
          clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        print("\nOcurrió un error al iniciar GastroMed Pro:\n")
        traceback.print_exc()
        print("\nTome una foto de esta ventana y compártala.")
        if os.name == "nt":
            input("Pulse Enter para cerrar…")
        sys.exit(1)
