"""Revisión rápida del estado de NeuroMed Pro (lo ejecuta VERIFICAR.bat)."""
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    ok = True

    def line(good, text):
        nonlocal ok
        ok = ok and good
        print(("  [OK]    " if good else "  [ALERTA] ") + text)

    print("Diagnóstico de NeuroMed Pro\n")
    try:
        from app.config import Config
        from app.crypto import load_data_key
        cfg = Config()
        line(True, f"Configuración cargada (modo {cfg.ENV}{', demostración' if cfg.DEMO else ''})")
        load_data_key(cfg)
        line(True, "Clave de datos presente")
    except Exception as e:  # noqa: BLE001
        line(False, f"Configuración: {e}")
        return 1
    line(bool(os.environ.get("GASTROMED_BACKUP_KEY")), "Clave de respaldo presente")
    db = Path(cfg.DATABASE_PATH)
    if db.exists():
        conn = sqlite3.connect(db)
        ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
        line(ic == "ok", f"Integridad de la base de datos: {ic}")
        n = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        u = conn.execute("SELECT COUNT(*) FROM users WHERE active = 1").fetchone()[0]
        print(f"           Pacientes: {n} · usuarios activos: {u}")
        missing = [r[0] for r in conn.execute("SELECT storage_name FROM files") if not (Path(cfg.FILES_DIR) / r[0]).exists()]
        line(not missing, f"Archivos adjuntos en disco ({len(missing)} faltantes)")
        conn.close()
    else:
        line(False, f"No existe la base de datos en {db}")
    backups = sorted(Path(cfg.BACKUP_DIR).glob("neuromed-*.gmbak")) if Path(cfg.BACKUP_DIR).exists() else []
    if backups:
        age_h = (time.time() - backups[-1].stat().st_mtime) / 3600
        line(age_h < 36, f"Último respaldo: {backups[-1].name} (hace {age_h:.0f} h) · total {len(backups)}")
    else:
        line(False, "No hay respaldos todavía")
    if cfg.BACKUP_COPY_DIR:
        line(Path(cfg.BACKUP_COPY_DIR).exists(), f"Copia externa de respaldos: {cfg.BACKUP_COPY_DIR}")
    else:
        line(False, "Sin copia externa de respaldos (configure un disco externo o USB)")
    print("\nResultado:", "TODO CORRECTO" if ok else "REVISE LAS ALERTAS")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
