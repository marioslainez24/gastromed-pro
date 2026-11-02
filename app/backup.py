"""Respaldo cifrado, verificación, restauración y exportación completa.

Formato del respaldo (.gmbak): un archivo TAR cifrado con Fernet usando GASTROMED_BACKUP_KEY, que contiene
  manifest.json           fecha, versión, migraciones, conteos por tabla y huellas SHA-256 de cada pieza
  gastromed.sqlite3       copia consistente de la base (API de respaldo de SQLite)
  archivos/<nombre>.bin   adjuntos tal como están en disco (ya cifrados con la clave de datos)

Para leer los adjuntos de un respaldo restaurado se necesitan AMBAS claves: la de respaldo y la de datos.
"""
import csv
import hashlib
import io
import json
import sqlite3
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

TABLES_COUNTED = ["patients", "patient_allergies", "patient_history", "patient_medications", "patient_problems", "appointments",
                  "appointment_events", "clinical_notes", "note_addenda", "prescriptions", "prescription_items", "files", "users",
                  "audit_log"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _snapshot(db_path: str) -> bytes:
    """Copia consistente aunque la aplicación esté en uso (no copia el archivo «en caliente»)."""
    src = sqlite3.connect(db_path)
    with tempfile.TemporaryDirectory() as td:
        dst_path = Path(td) / "snap.sqlite3"
        dst = sqlite3.connect(dst_path)
        src.backup(dst)
        dst.execute("PRAGMA journal_mode = DELETE")
        dst.close()
        src.close()
        return dst_path.read_bytes()


def _counts(conn) -> dict:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES_COUNTED}


def create_backup(db_path: str, files_dir: str, out_dir: str, backup_key: bytes, app_version: str) -> Path:
    db_bytes = _snapshot(db_path)
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "s.sqlite3"
        snap.write_bytes(db_bytes)
        conn = sqlite3.connect(snap)
        counts = _counts(conn)
        migrations = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
        stored = [r[0] for r in conn.execute("SELECT storage_name FROM files")]
        conn.close()
    manifest = {"formato": "gastromed-respaldo-1", "creado": datetime.now(timezone.utc).isoformat(), "version_app": app_version,
                "migraciones": migrations, "conteos": counts, "piezas": {"gastromed.sqlite3": _sha(db_bytes)}}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        def add(name, data):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mtime = int(datetime.now().timestamp())
            tar.addfile(ti, io.BytesIO(data))
        add("gastromed.sqlite3", db_bytes)
        missing = []
        for name in stored:
            p = Path(files_dir) / name
            if not p.exists():
                missing.append(name)
                continue
            data = p.read_bytes()
            manifest["piezas"][f"archivos/{name}"] = _sha(data)
            add(f"archivos/{name}", data)
        if missing:
            raise RuntimeError(f"Faltan {len(missing)} adjuntos referenciados en la base; respaldo cancelado.")
        add("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"gastromed-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.gmbak"
    path.write_bytes(Fernet(backup_key).encrypt(buf.getvalue()))
    return path


def _open(backup_path: str, backup_key: bytes) -> tuple[tarfile.TarFile, dict]:
    raw = Fernet(backup_key).decrypt(Path(backup_path).read_bytes())  # falla si la clave es incorrecta o el archivo fue alterado
    tar = tarfile.open(fileobj=io.BytesIO(raw), mode="r")
    manifest = json.loads(tar.extractfile("manifest.json").read())
    return tar, manifest


def verify_and_restore(backup_path: str, backup_key: bytes, target_dir: str, data_key: bytes | None = None) -> dict:
    """Descifra, comprueba huellas e integridad, y restaura en un directorio NUEVO (nunca sobrescribe)."""
    target = Path(target_dir)
    if target.exists() and any(target.iterdir()):
        raise RuntimeError("El directorio de destino no está vacío. Restaure en una carpeta nueva.")
    tar, manifest = _open(backup_path, backup_key)
    report = {"manifest": manifest, "errores": []}
    (target / "archivos").mkdir(parents=True, exist_ok=True)
    for member in tar.getmembers():
        name = member.name
        if name == "manifest.json":
            continue
        if name not in manifest["piezas"] or ".." in name or name.startswith("/"):
            report["errores"].append(f"Pieza inesperada: {name}")
            continue
        data = tar.extractfile(member).read()
        if _sha(data) != manifest["piezas"][name]:
            report["errores"].append(f"Huella incorrecta: {name}")
            continue
        dest = target / name
        dest.write_bytes(data)
    db_path = target / "gastromed.sqlite3"
    conn = sqlite3.connect(db_path)
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if ic != "ok":
        report["errores"].append(f"Integridad de la base: {ic}")
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        report["errores"].append(f"Claves foráneas inconsistentes: {len(fk)}")
    counts = _counts(conn)
    if counts != manifest["conteos"]:
        report["errores"].append("Los conteos de registros no coinciden con el manifiesto.")
    report["conteos"] = counts
    if data_key:
        f = Fernet(data_key)
        ok = 0
        for storage, sha in conn.execute("SELECT storage_name, sha256 FROM files"):
            try:
                plain = f.decrypt((target / "archivos" / storage).read_bytes())
                if _sha(plain) == sha:
                    ok += 1
                else:
                    report["errores"].append(f"Contenido alterado: {storage}")
            except Exception:
                report["errores"].append(f"No se pudo descifrar: {storage}")
        report["adjuntos_verificados"] = ok
    conn.close()
    report["ok"] = not report["errores"]
    return report


def export_all(db_path: str, files_dir: str, data_key: bytes, out_zip: str) -> Path:
    """Exportación legible: CSV por tabla clínica/administrativa + adjuntos descifrados por paciente."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    f = Fernet(data_key)
    out = Path(out_zip)
    out.parent.mkdir(parents=True, exist_ok=True)
    skip_cols = {"password_hash", "mfa_secret_enc", "search_text", "storage_name"}
    tables = ["patients", "patient_allergies", "patient_history", "patient_medications", "patient_problems", "appointments",
              "appointment_events", "clinical_notes", "note_addenda", "prescriptions", "prescription_items", "files", "users",
              "clinic_settings", "audit_log"]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for t in tables:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})") if c[1] not in skip_cols]
            s = io.StringIO()
            w = csv.writer(s)
            w.writerow(cols)
            for r in rows:
                w.writerow([r[c] for c in cols])
            z.writestr(f"datos/{t}.csv", "﻿" + s.getvalue())  # BOM para que Excel respete tildes
        ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/heic": "heic"}
        for r in conn.execute("SELECT f.*, p.mrn FROM files f JOIN patients p ON p.id = f.patient_id"):
            data = f.decrypt((Path(files_dir) / r["storage_name"]).read_bytes())
            safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in r["title"])[:60]
            z.writestr(f"adjuntos/{r['mrn']}/{(r['study_date'] or r['uploaded_at'][:10])}_{safe}_{r['id'][:8]}.{ext[r['mime']]}", data)
        z.writestr("LEAME.txt", "Exportación completa de GastroMed Pro.\n"
                   "datos/: un CSV por tabla (UTF-8). Las notas clínicas están en clinical_notes.csv (columna fields, JSON).\n"
                   "adjuntos/: estudios descifrados, agrupados por número de expediente.\n"
                   "ADVERTENCIA: este archivo NO está cifrado y contiene información clínica. Guárdelo en un medio protegido.\n")
    conn.close()
    return out


# ---------------------------------------------------------------------------
# Respaldo automático (usado por el programa .exe en segundo plano y por scripts/respaldo.py)
# ---------------------------------------------------------------------------
def prune(folder: Path, keep: int) -> int:
    """Conserva solo los últimos `keep` respaldos (no toca otros archivos)."""
    olds = sorted(folder.glob("gastromed-*.gmbak"))[:-keep] if keep > 0 else []
    for f in olds:
        f.unlink()
    return len(olds)


def last_backup_age_hours(backup_dir: str) -> float | None:
    files = sorted(Path(backup_dir).glob("gastromed-*.gmbak")) if Path(backup_dir).exists() else []
    if not files:
        return None
    return (datetime.now().timestamp() - files[-1].stat().st_mtime) / 3600


OFFSITE_SUBDIR = "GastroMed-respaldos"


def drive_candidates() -> list[str]:
    """Carpetas de Google Drive para computadora (u OneDrive) que existen en esta PC."""
    import os
    import string
    out = []
    if os.name == "nt":
        for letter in string.ascii_uppercase[3:]:
            for name in ("Mi unidad", "My Drive"):
                p = Path(f"{letter}:/") / name
                try:
                    if p.is_dir():
                        out.append(str(p))
                except OSError:
                    pass
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    # Mac: Google Drive para computadora monta la unidad en ~/Library/CloudStorage/GoogleDrive-<cuenta>/Mi unidad
    cloud = home / "Library" / "CloudStorage"
    try:
        for acct in sorted(cloud.glob("GoogleDrive-*")) if cloud.is_dir() else []:
            for name in ("Mi unidad", "My Drive"):
                if (acct / name).is_dir():
                    out.append(str(acct / name))
    except OSError:
        pass
    for name in ("Google Drive/Mi unidad", "Google Drive/My Drive", "Google Drive", "My Drive", "OneDrive"):
        p = home / name
        if p.is_dir() and str(p) not in out:
            out.append(str(p))
    return out


def offsite_settings(db_path: str):
    import sqlite3
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT offsite_enabled, offsite_dir, offsite_keep FROM clinic_settings ORDER BY offsite_enabled DESC LIMIT 1").fetchone()
    except sqlite3.Error:
        return None
    finally:
        con.close()


def offsite_record(db_path: str, msg: str):
    import sqlite3
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.execute("UPDATE clinic_settings SET offsite_last_at = ?, offsite_last_msg = ? WHERE offsite_enabled = 1",
                    (datetime.now().astimezone().isoformat(timespec="seconds"), msg[:500]))
        con.commit()
    finally:
        con.close()


def offsite_copy(db_path: str, backup_path: Path) -> tuple[bool, str]:
    """Copia el respaldo cifrado a la carpeta sincronizada (si está activada). Conserva los últimos N allí."""
    import shutil
    st = offsite_settings(db_path)
    if not st or not st["offsite_enabled"] or not st["offsite_dir"]:
        return True, ""
    dest = Path(st["offsite_dir"]) / OFFSITE_SUBDIR
    try:
        if not Path(st["offsite_dir"]).is_dir():
            raise FileNotFoundError("no se encontró la carpeta de Google Drive (¿está abierto «Google Drive para computadora»?)")
        dest.mkdir(exist_ok=True)
        tmp = dest / (backup_path.name + ".parcial")
        shutil.copy2(backup_path, tmp)
        tmp.replace(dest / backup_path.name)
        prune(dest, max(1, int(st["offsite_keep"] or 7)))
        msg = f"OK: copia {backup_path.name} en {dest}"
        ok = True
    except Exception as e:  # noqa: BLE001
        msg = f"ALERTA: no se pudo copiar a Google Drive: {e}"
        ok = False
    offsite_record(db_path, msg)
    return ok, msg


def run_automatic(cfg, backup_key: bytes, data_key: bytes, app_version: str) -> tuple[bool, list[str]]:
    """Crear → verificar restaurando → copiar a disco externo → conservar los últimos N. Devuelve (ok, mensajes)."""
    import shutil
    msgs = []
    log = Path(cfg.DATABASE_PATH).parent / "respaldo.log"

    def note(m):
        msgs.append(m)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {m}\n")

    try:
        path = create_backup(cfg.DATABASE_PATH, cfg.FILES_DIR, cfg.BACKUP_DIR, backup_key, app_version)
        with tempfile.TemporaryDirectory() as td:
            report = verify_and_restore(str(path), backup_key, str(Path(td) / "r"), data_key)
        if not report["ok"]:
            note(f"ERROR: el respaldo {path.name} no pasó la verificación: {report['errores']}")
            return False, msgs
        note(f"OK: {path.name} creado y verificado ({path.stat().st_size / 1024:.0f} KB, "
             f"{report['conteos']['patients']} pacientes, {report.get('adjuntos_verificados', 0)} adjuntos)")
        if cfg.BACKUP_COPY_DIR:
            dest = Path(cfg.BACKUP_COPY_DIR)
            if dest.exists():
                shutil.copy2(path, dest / path.name)
                prune(dest, cfg.BACKUP_KEEP)
                note(f"OK: copiado a {dest}")
            else:
                note(f"ALERTA: no se encontró la carpeta de copia externa {dest} (¿está conectado el disco?)")
        ok_off, msg_off = offsite_copy(cfg.DATABASE_PATH, path)
        if msg_off:
            note(msg_off)
        removed = prune(Path(cfg.BACKUP_DIR), cfg.BACKUP_KEEP)
        if removed:
            note(f"Se eliminaron {removed} respaldos antiguos (se conservan los últimos {cfg.BACKUP_KEEP}).")
        return True, msgs
    except Exception as e:  # noqa: BLE001
        note(f"ERROR: {e}")
        return False, msgs
