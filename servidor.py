"""Servidor de GastroMed Pro para la PC del consultorio (Windows u otro sistema).

Lo inicia el acceso directo «GastroMed Pro». Atiende en el puerto 8000 a esta PC y a los
celulares/tabletas conectados al mismo Wi-Fi. Cierre esta ventana para detener el sistema.
"""
import os
import socket
import sys
import threading
import webbrowser

from app import APP_VERSION, create_app


def lan_addresses() -> list[str]:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.0.1", 9))  # no envía datos; solo determina la interfaz local
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def main():
    port = int(os.environ.get("GASTROMED_PORT", "8000"))
    host = os.environ.get("GASTROMED_HOST", "0.0.0.0")
    app = create_app()
    cfg = app.config["GM"]
    print("=" * 64)
    print(f"  GastroMed Pro {APP_VERSION}{'  ·  MODO DEMOSTRACIÓN' if cfg.DEMO else ''}")
    print("=" * 64)
    print(f"  En esta PC:          http://localhost:{port}")
    if host == "0.0.0.0":
        for ip in lan_addresses():
            print(f"  Desde el celular:    http://{ip}:{port}   (mismo Wi-Fi)")
    print("  Datos:", os.path.dirname(cfg.DATABASE_PATH))
    print("\n  NO CIERRE ESTA VENTANA mientras use el sistema. Para detenerlo, ciérrela.")
    print("=" * 64, flush=True)
    if "--abrir" in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    try:
        from waitress import serve
    except ImportError:
        if cfg.ENV in ("consultorio", "produccion") and os.environ.get("GASTROMED_ALLOW_DEVSERVER") != "1":
            sys.exit("Falta el componente 'waitress'. Ejecute de nuevo INSTALAR.bat.")
        app.run(host=host, port=port, threaded=True)
        return
    serve(app, host=host, port=port, threads=8, ident="GastroMed", clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
