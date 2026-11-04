"""Archivos privados del paciente: subida (PC o cámara del celular), validación, cifrado en reposo y acceso autorizado."""
import hashlib
import re
import secrets
from datetime import date
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, url_for

from .crypto import InvalidToken, data_fernet
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require
from .views_patients import get_patient_or_404

bp = Blueprint("files", __name__, url_prefix="/archivos")

MAX_BYTES = 20 * 1024 * 1024
CATEGORIES = {"laboratorio": "Laboratorio", "imagen": "Imagenología", "endoscopia": "Endoscopia", "patologia": "Anatomía patológica",
              "referencia": "Referencia / contrarreferencia", "documento": "Documento", "otro": "Otro"}
# Firmas de contenido aceptadas (no se confía en la extensión ni en el tipo declarado por el navegador)
SIGNATURES = [(b"%PDF-", "application/pdf", "pdf"), (b"\xff\xd8\xff", "image/jpeg", "jpg"), (b"\x89PNG\r\n\x1a\n", "image/png", "png")]
PDF_ACTIVE = [b"/JavaScript", b"/JS ", b"/JS(", b"/Launch", b"/EmbeddedFile", b"/OpenAction", b"/AA ", b"/RichMedia", b"/XFA"]


def detect(data: bytes):
    for sig, mime, ext in SIGNATURES:
        if data.startswith(sig):
            return mime, ext
    # HEIC/HEIF (cámara del iPhone): caja 'ftyp' con marca heic/heix/mif1
    if len(data) > 12 and data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"heif"):
        return "image/heic", "heic"
    return None, None


def validate(data: bytes) -> tuple[str | None, str | None, str | None]:
    if not data:
        return None, None, "El archivo está vacío."
    if len(data) > MAX_BYTES:
        return None, None, "El archivo supera 20 MB."
    mime, ext = detect(data)
    if not mime:
        return None, None, "Tipo de archivo no permitido. Se aceptan PDF, JPG, PNG y HEIC."
    if mime == "application/pdf":
        if any(tok in data for tok in PDF_ACTIVE):
            return None, None, ("El PDF contiene contenido activo (scripts, acciones automáticas o archivos incrustados) y fue rechazado "
                                "por seguridad. Imprímalo a PDF de nuevo o fotografíe el documento.")
        if b"%%EOF" not in data[-2048:]:
            return None, None, "El PDF parece incompleto o dañado."
    return mime, ext, None


def storage_dir() -> Path:
    d = Path(current_app.config["GM"].FILES_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_file(file_id):
    if not re.fullmatch(r"[0-9a-f]{32}", file_id or ""):
        abort(404)
    f = get_db().execute("SELECT f.*, u.full_name AS uploader FROM files f JOIN users u ON u.id = f.uploaded_by"
                         " WHERE f.id = ? AND f.org_id = ?", (file_id, g.user["org_id"])).fetchone()
    if not f:
        abort(404)
    return f


@bp.route("/subir", methods=["GET", "POST"])
@require("clinico.editar")
def upload():
    src = request.form if request.method == "POST" else request.args
    p = get_patient_or_404(src.get("patient_id", ""))
    errors = []
    if request.method == "POST":
        up = request.files.get("archivo")
        category = request.form.get("category")
        title = (request.form.get("title") or "").strip()[:160]
        institution = (request.form.get("institution") or "").strip()[:160] or None
        study_date = (request.form.get("study_date") or "").strip() or None
        if category not in CATEGORIES:
            errors.append("Elija la categoría.")
        if not title:
            errors.append("Escriba un título (p. ej., «Hemograma», «USG abdominal»).")
        if study_date:
            try:
                if date.fromisoformat(study_date) > date.today():
                    errors.append("La fecha del estudio no puede ser futura.")
            except ValueError:
                errors.append("Fecha del estudio no válida.")
        data = up.read(MAX_BYTES + 1) if up else b""
        mime, ext, err = validate(data)
        if err:
            errors.append(err)
        if not errors:
            fid = new_id()
            storage = secrets.token_hex(24) + ".bin"
            path = storage_dir() / storage
            path.write_bytes(data_fernet().encrypt(data))
            original = re.sub(r"[^\w.\- ]", "_", (up.filename or f"archivo.{ext}"))[-120:]
            db = get_db()
            try:
                with write_tx(db):
                    db.execute("INSERT INTO files(id, org_id, patient_id, category, title, study_date, institution, original_name, mime,"
                               " size_bytes, sha256, storage_name, uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (fid, g.user["org_id"], p["id"], category, title, study_date, institution, original, mime, len(data),
                                hashlib.sha256(data).hexdigest(), storage, g.user["id"], utcnow()))
                    audit("archivo_subido", "archivo", fid, {"paciente": p["id"], "tipo": mime, "bytes": len(data)}, db=db)
            except Exception:
                path.unlink(missing_ok=True)  # sin registro no debe quedar un archivo huérfano
                raise
            flash("Archivo guardado de forma privada y cifrada.", "ok")
            return redirect(url_for("patients.view", patient_id=p["id"]) + "#archivos")
    return render_template("archivos/subir.html", p=p, errors=errors, categories=CATEGORIES,
                           form=request.form if request.method == "POST" else {}), 422 if errors else 200


@bp.route("/<file_id>")
@require("clinico.ver")
def download(file_id):
    f = _get_file(file_id)
    try:
        data = data_fernet().decrypt((storage_dir() / f["storage_name"]).read_bytes())
    except (FileNotFoundError, InvalidToken):
        audit("archivo_ilegible", "archivo", f["id"])
        abort(500)
    if hashlib.sha256(data).hexdigest() != f["sha256"]:
        audit("archivo_integridad_fallida", "archivo", f["id"])
        abort(500)
    audit("archivo_descargado", "archivo", f["id"])
    resp = make_response(data)
    resp.headers["Content-Type"] = f["mime"]
    disp = "attachment" if request.args.get("descargar") else "inline"
    ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/heic": "heic"}[f["mime"]]
    resp.headers["Content-Disposition"] = f'{disp}; filename="estudio-{f["id"][:8]}.{ext}"'
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
    return resp


@bp.route("/<file_id>/archivar", methods=["POST"])
@require("clinico.editar")
def archive(file_id):
    f = _get_file(file_id)
    reason = (request.form.get("reason") or "").strip()[:300]
    if not reason:
        flash("Indique el motivo (p. ej., «pertenece a otro paciente», «duplicado»).", "error")
        return redirect(url_for("patients.view", patient_id=f["patient_id"]) + "#archivos")
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE files SET archived_at = ?, archived_by = ?, archive_reason = ? WHERE id = ? AND archived_at IS NULL",
                   (utcnow(), g.user["id"], reason, f["id"]))
        audit("archivo_archivado", "archivo", f["id"], {"motivo": reason}, db=db)
    flash("Archivo retirado de la vista del expediente. Se conserva para auditoría.", "ok")
    return redirect(url_for("patients.view", patient_id=f["patient_id"]) + "#archivos")


def group_files(files):
    """Agrupa los archivos del mismo estudio (misma categoría, misma fecha y mismo nombre sin «· imagen N») (v0.22.0).

    Devuelve una lista de grupos en el mismo orden: {"title", "date", "category", "files", "images"}."""
    import re
    groups, index = [], {}
    for f in files:
        base = re.sub(r"\s*[·\-]\s*imagen\s*\d+\s*$", "", f["title"] or "", flags=re.I).strip() or (f["title"] or "")
        date = f["study_date"] or (f["uploaded_at"] or "")[:10]
        key = (f["category"], date, base.lower())
        if key not in index:
            index[key] = {"title": base, "date": date, "has_study_date": bool(f["study_date"]), "category": f["category"],
                          "files": [], "images": 0, "key": f"g{len(groups)}"}
            groups.append(index[key])
        grp = index[key]
        grp["files"].append(f)
        if f["mime"] in ("image/jpeg", "image/png"):
            grp["images"] += 1
    return groups


def list_files(db, patient_id):
    return db.execute("SELECT f.*, u.full_name AS uploader FROM files f JOIN users u ON u.id = f.uploaded_by"
                      " WHERE f.patient_id = ? AND f.archived_at IS NULL ORDER BY COALESCE(f.study_date, substr(f.uploaded_at,1,10)) DESC,"
                      " f.uploaded_at DESC, f.title", (patient_id,)).fetchall()
