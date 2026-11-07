"""Respaldos de NeuroMed Pro.

  python scripts/respaldo.py generar-clave              → imprime una clave nueva para GASTROMED_BACKUP_KEY
  python scripts/respaldo.py crear [carpeta]            → crea un respaldo cifrado (por defecto en GASTROMED_BACKUP_DIR)
  python scripts/respaldo.py automatico                 → crea, verifica, copia al disco externo y borra los más antiguos
                                                          (lo ejecuta la tarea programada diaria de Windows)
  python scripts/respaldo.py verificar ARCHIVO.gmbak    → restaura en una carpeta temporal y comprueba todo
  python scripts/respaldo.py restaurar ARCHIVO.gmbak CARPETA_NUEVA
  python scripts/respaldo.py exportar SALIDA.zip        → exportación legible completa (NO cifrada)

GASTROMED_BACKUP_KEY debe guardarse fuera del servidor (p. ej., en un gestor de contraseñas y en papel en un lugar seguro).
Sin esa clave los respaldos no se pueden abrir.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cryptography.fernet import Fernet  # noqa: E402

from app import APP_VERSION  # noqa: E402
from app.backup import create_backup, export_all, prune, run_automatic, verify_and_restore  # noqa: E402,F401
from app.config import Config  # noqa: E402
from app.crypto import load_data_key  # noqa: E402


def backup_key() -> bytes:
    k = os.environ.get("GASTROMED_BACKUP_KEY")
    if not k:
        sys.exit("Falta GASTROMED_BACKUP_KEY. Genere una con: python scripts/respaldo.py generar-clave")
    return k.encode()


def show(report):
    print("Resultado:", "CORRECTO" if report["ok"] else "CON ERRORES")
    print("Creado:", report["manifest"]["creado"], "· versión", report["manifest"]["version_app"])
    for t, n in report["conteos"].items():
        print(f"  {t:22s} {n}")
    if "adjuntos_verificados" in report:
        print("  adjuntos verificados  ", report["adjuntos_verificados"])
    for e in report["errores"]:
        print("  ERROR:", e)


def automatic(cfg) -> int:
    ok, msgs = run_automatic(cfg, backup_key(), load_data_key(cfg), APP_VERSION)
    print("\n".join(msgs))
    return 0 if ok else 2


def main(argv):
    cfg = Config()
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "generar-clave":
        print(Fernet.generate_key().decode())
    elif cmd == "crear":
        path = create_backup(cfg.DATABASE_PATH, cfg.FILES_DIR, argv[1] if len(argv) > 1 else cfg.BACKUP_DIR, backup_key(), APP_VERSION)
        print("Respaldo creado:", path, f"({path.stat().st_size / 1024:.0f} KB)")
    elif cmd == "automatico":
        return automatic(cfg)
    elif cmd == "verificar" and len(argv) == 2:
        with tempfile.TemporaryDirectory() as td:
            report = verify_and_restore(argv[1], backup_key(), str(Path(td) / "r"), load_data_key(cfg))
            show(report)
            return 0 if report["ok"] else 2
    elif cmd == "restaurar" and len(argv) == 3:
        report = verify_and_restore(argv[1], backup_key(), argv[2], load_data_key(cfg))
        show(report)
        if report["ok"]:
            print(f"\nPara usar la restauración, configure GASTROMED_DATABASE_PATH={argv[2]}/neuromed.sqlite3 "
                  f"y GASTROMED_FILES_DIR={argv[2]}/archivos y reinicie la aplicación.")
        return 0 if report["ok"] else 2
    elif cmd == "exportar" and len(argv) == 2:
        out = export_all(cfg.DATABASE_PATH, cfg.FILES_DIR, load_data_key(cfg), argv[1])
        print("Exportación creada:", out, "— ATENCIÓN: no está cifrada.")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
