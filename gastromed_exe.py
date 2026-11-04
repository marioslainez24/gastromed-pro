"""Punto de entrada del programa GastroMedPro.exe (Windows) y GastroMedPro para Mac (v0.22.0).

En Mac los datos quedan en ~/GastroMed (carpeta del usuario), la ventana es la Terminal y, mientras el programa está abierto,
se le pide a la Mac que no se duerma (caffeinate) para que el celular pueda conectarse.

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
HTTPS_PORT = int(os.environ.get("GASTROMED_HTTPS_PORT", "8443"))


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


def _foreign_path(value: str) -> bool:
    """Ruta escrita en otra computadora: C:\\... vista desde la Mac, o /Users/... vista desde Windows."""
    import re
    if not value:
        return False
    if os.name == "nt":
        return value.startswith("/")
    return bool(re.match(r"^[A-Za-z]:[\\/]", value)) or "\\" in value


def adapt_paths(env_file: Path, datos: Path, respaldos: Path) -> bool:
    """Si la carpeta «datos» se copió desde otra computadora (p. ej. de Windows a la Mac), corrige las rutas guardadas.

    Las claves NO se tocan: solo se reescriben las líneas de rutas que apuntan a la otra computadora."""
    fixes = {"GASTROMED_DATABASE_PATH": str(datos / "gastromed.sqlite3"), "GASTROMED_FILES_DIR": str(datos / "archivos"),
             "GASTROMED_BACKUP_DIR": str(respaldos), "GASTROMED_BACKUP_COPY_DIR": ""}
    lines, changed = env_file.read_text(encoding="utf-8-sig").splitlines(), False
    for i, line in enumerate(lines):
        key, sep, value = line.partition("=")
        if sep and key.strip() in fixes and _foreign_path(value.strip().strip('"').strip("'")):
            lines[i] = f"{key.strip()}={fixes[key.strip()]}"
            changed = True
    if changed:
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("  Se adaptaron las carpetas de datos copiados desde otra computadora.")
    return changed


def first_run_config(root: Path) -> Path:
    """Crea gastromed.env con claves nuevas solo si no existe. Nunca reemplaza claves existentes."""
    from cryptography.fernet import Fernet
    datos, respaldos = root / "datos", root / "respaldos"
    for d in (datos, datos / "archivos", respaldos):
        d.mkdir(parents=True, exist_ok=True)
    env_file = datos / "gastromed.env"
    if env_file.exists():
        adapt_paths(env_file, datos, respaldos)
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


def ensure_certificate(datos: Path, ips: list[str]):
    """Certificado propio (autofirmado) para cifrar la conexión del celular por Wi-Fi. Gratis, sin terceros.
    Se regenera si cambia la dirección IP de la PC."""
    import ipaddress
    from datetime import timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    crt, key = datos / "https-cert.pem", datos / "https-key.pem"
    wanted = set(ips) | {"127.0.0.1"}
    if crt.exists() and key.exists():
        try:
            c = x509.load_pem_x509_certificate(crt.read_bytes())
            have = {str(i) for i in c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)}
            if wanted <= have and c.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=30):
                return crt, key
        except Exception:  # noqa: BLE001
            pass
    pk = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GastroMed Pro (consultorio)")])
    now = datetime.now(timezone.utc)
    san = [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(i)) for i in sorted(wanted)]
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(pk.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(pk, hashes.SHA256()))
    key.write_bytes(pk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return crt, key


def https_server(app, crt: Path, key: Path):
    """Servidor https para el celular (Wi-Fi cifrado; necesario también para el micrófono del dictado)."""
    import logging
    import ssl
    from werkzeug.serving import make_server
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # sin registrar cada página en la ventana
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(crt), str(key))
    srv = make_server("0.0.0.0", HTTPS_PORT, app, threaded=True, ssl_context=ctx)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def reminder_loop(app):
    """Recordatorios por correo: revisa cada 10 minutos. El resumen no muestra datos de pacientes."""
    from app.db import connect
    from app.reminders import run_email_reminders
    time.sleep(30)
    from app import license as lic
    while True:
        if not lic.active():          # sin licencia, el programa no envía nada
            time.sleep(600)
            continue
        try:
            db = connect(app.config["GM"].DATABASE_PATH)
            try:
                res = run_email_reminders(db, app.config["GM_FERNET"])
                if res:
                    print(f"  [{datetime.now():%H:%M}] Recordatorios por correo: {res.count('enviado')} enviado(s),"
                          f" {res.count('fallido')} con error (ver Ajustes → Recordatorios).", flush=True)
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            print("  Error en recordatorios:", type(e).__name__, flush=True)
        time.sleep(600)


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
    elif sys.platform == "darwin":
        sys.stdout.write("\033]0;GastroMed Pro - NO CERRAR esta ventana\007")
        sys.stdout.flush()
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
    ips = lan_addresses()
    https_ok = False
    try:
        crt, key = ensure_certificate(env_file.parent, ips)
        os.environ["GASTROMED_HTTPS_PORT"] = str(HTTPS_PORT)
        https_ok = True
    except Exception as e:  # noqa: BLE001
        print("  Aviso: no se pudo preparar https para el celular:", e)

    from app import APP_VERSION, create_app
    from app import license as lic
    # v0.24: licencia por computadora OBLIGATORIA en el programa instalado (archivo datos/licencia.txt)
    lic.configure(env_file.parent / "licencia.txt")
    app = create_app()
    cfg = app.config["GM"]
    if https_ok:
        try:
            https_server(app, crt, key)
        except OSError as e:
            https_ok = False
            os.environ.pop("GASTROMED_HTTPS_PORT", None)
            app = create_app()
            print("  Aviso: el puerto", HTTPS_PORT, "está ocupado; el celular usará http sin cifrar.", e)
    print("=" * 66)
    print(f"  GastroMed Pro {APP_VERSION}")
    print("=" * 66)
    print(f"  En esta PC:        http://localhost:{PORT}")
    for ip in ips:
        if https_ok:
            print(f"  Desde el celular:  https://{ip}:{HTTPS_PORT}   (mismo Wi-Fi, conexión cifrada)")
        else:
            print(f"  Desde el celular:  http://{ip}:{PORT}   (mismo Wi-Fi)")
    if https_ok and ips:
        print("    La primera vez el celular dirá «La conexión no es privada»: toque «Configuración")
        print("    avanzada» y luego «Continuar». Es normal: el certificado lo creó esta PC, no una empresa externa.")
    if lic.active():
        print(f"  Licencia de uso:   {lic.holder()}")
    else:
        print("  PROGRAMA SIN ACTIVAR en esta computadora.")
        print(f"  Código de equipo:  {lic.machine_code()}")
        print("  Abra http://localhost:%d/activar y pegue la clave de activación generada para este código." % PORT)
    print(f"  Datos:             {Path(cfg.DATABASE_PATH).parent}")
    print(f"  Respaldos:         {cfg.BACKUP_DIR}  (automático cada 24 h)")
    print("\n  NO CIERRE ESTA VENTANA mientras use el sistema. Para apagarlo, ciérrela"
          + (" (o pulse Ctrl+C)." if sys.platform == "darwin" else "."))
    print("=" * 66, flush=True)

    if sys.platform == "darwin":
        # Que la Mac no se duerma mientras el programa está abierto (se suelta sola al cerrarlo).
        try:
            import subprocess
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
    threading.Thread(target=backup_loop, args=(app,), daemon=True).start()
    threading.Thread(target=reminder_loop, args=(app,), daemon=True).start()
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
