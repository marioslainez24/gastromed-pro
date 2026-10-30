"""Recetas: emisión, PDF (carta/A4), anulación trazable."""
import re

from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from .db import get_db, new_id, utcnow, write_tx
from .pdf import prescription_pdf
from .security import audit, require
from .util import clinic_settings
from .views_patients import get_patient_or_404

bp = Blueprint("rx", __name__, url_prefix="/recetas")

ITEM_FIELDS = {  # campo: (etiqueta, obligatorio, máx.)
    "active_ingredient": ("Principio activo", True, 160), "presentation": ("Presentación", False, 160),
    "dose": ("Dosis", True, 40), "dose_unit": ("Unidad", True, 40), "route": ("Vía", True, 60),
    "frequency": ("Frecuencia", True, 120), "duration": ("Duración", True, 120), "quantity": ("Cantidad", True, 120),
    "instructions": ("Indicaciones adicionales", False, 600),
}
ROUTES = ["oral", "sublingual", "rectal", "tópica", "subcutánea", "intramuscular", "intravenosa", "inhalada", "otra"]
MAX_ITEMS = 15


def _get_rx(rx_id):
    if not re.fullmatch(r"[0-9a-f]{32}", rx_id or ""):
        abort(404)
    r = get_db().execute("SELECT r.*, u.full_name AS author FROM prescriptions r JOIN users u ON u.id = r.author_id"
                         " WHERE r.id = ? AND r.org_id = ?", (rx_id, g.user["org_id"])).fetchone()
    if not r:
        abort(404)
    return r


def parse_items(form) -> tuple[list[dict], list[str]]:
    items, errors = [], []
    indexes = sorted({int(m.group(1)) for k in form.keys() if (m := re.fullmatch(r"item-(\d{1,2})-active_ingredient", k))})
    for i in indexes:
        row = {f: (form.get(f"item-{i}-{f}") or "").strip() for f in ITEM_FIELDS}
        if not any(row.values()):
            continue
        for f, (lab, req, mx) in ITEM_FIELDS.items():
            if req and not row[f]:
                errors.append(f"Medicamento {len(items) + 1}: falta «{lab}».")
            if len(row[f]) > mx:
                errors.append(f"Medicamento {len(items) + 1}: «{lab}» supera {mx} caracteres.")
        items.append(row)
    if not items:
        errors.append("Agregue al menos un medicamento.")
    if len(items) > MAX_ITEMS:
        errors.append(f"Máximo {MAX_ITEMS} medicamentos por receta.")
    return items, errors


@bp.route("/nueva", methods=["GET", "POST"])
@require("clinico.ver", "recetas.emitir")
def new():
    src = request.form if request.method == "POST" else request.args
    p = get_patient_or_404(src.get("patient_id", ""))
    db = get_db()
    note_id = src.get("note_id") or None
    if note_id and not db.execute("SELECT 1 FROM clinical_notes WHERE id = ? AND patient_id = ? AND org_id = ?",
                                  (note_id, p["id"], g.user["org_id"])).fetchone():
        abort(404)
    allergies = db.execute("SELECT * FROM patient_allergies WHERE patient_id = ? AND active = 1", (p["id"],)).fetchall()
    items, errors = [], []
    general = ""
    if request.method == "POST":
        items, errors = parse_items(request.form)
        general = (request.form.get("general_instructions") or "").strip()[:1000]
        if p["allergy_status"] == "no_investigado" and request.form.get("ack_allergies") != "1":
            errors.append("Las alergias de este paciente no están investigadas. Confirme que lo revisó antes de emitir.")
        if not errors:
            rid = new_id()
            with write_tx(db):
                db.execute("INSERT INTO prescriptions(id, org_id, patient_id, note_id, author_id, issued_at, general_instructions)"
                           " VALUES (?,?,?,?,?,?,?)", (rid, g.user["org_id"], p["id"], note_id, g.user["id"], utcnow(), general or None))
                for pos, it in enumerate(items, 1):
                    db.execute("INSERT INTO prescription_items(id, prescription_id, position, " + ", ".join(ITEM_FIELDS) +
                               ") VALUES (?,?,?," + ",".join("?" * len(ITEM_FIELDS)) + ")",
                               [new_id(), rid, pos] + [it[f] or None for f in ITEM_FIELDS])
                audit("receta_emitida", "receta", rid, {"paciente": p["id"], "items": len(items)}, db=db)
            flash("Receta emitida. Puede imprimirla o descargar el PDF.", "ok")
            return redirect(url_for("rx.view", rx_id=rid))
    return render_template("recetas/nueva.html", p=p, note_id=note_id, allergies=allergies, items=items or [{}],
                           errors=errors, general=general, fields=ITEM_FIELDS, routes=ROUTES), 422 if errors else 200


@bp.route("/<rx_id>")
@require("clinico.ver")
def view(rx_id):
    r = _get_rx(rx_id)
    db = get_db()
    items = db.execute("SELECT * FROM prescription_items WHERE prescription_id = ? ORDER BY position", (r["id"],)).fetchall()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (r["patient_id"],)).fetchone()
    audit("receta_consultada", "receta", r["id"])
    return render_template("recetas/ver.html", r=r, items=items, p=p, settings=clinic_settings())


@bp.route("/<rx_id>/pdf")
@require("clinico.ver")
def pdf(rx_id):
    r = _get_rx(rx_id)
    db = get_db()
    items = db.execute("SELECT * FROM prescription_items WHERE prescription_id = ? ORDER BY position", (r["id"],)).fetchall()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (r["patient_id"],)).fetchone()
    s = clinic_settings()
    size = request.args.get("papel") or s["paper_size"]
    if size not in ("carta", "a4"):
        abort(400)
    allergies = db.execute("SELECT * FROM patient_allergies WHERE patient_id = ? AND active = 1", (p["id"],)).fetchall()
    from .views_extras import load_assets
    data = prescription_pdf(r, items, p, s, size, allergies, load_assets(g.user["org_id"]))
    audit("receta_pdf_generado", "receta", r["id"], {"papel": size})
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/pdf"
    # Nombre de archivo sin datos identificables del paciente.
    resp.headers["Content-Disposition"] = f'inline; filename="receta-{r["id"][:8]}.pdf"'
    return resp


@bp.route("/<rx_id>/anular", methods=["POST"])
@require("clinico.ver", "recetas.anular")
def void(rx_id):
    r = _get_rx(rx_id)
    reason = (request.form.get("reason") or "").strip()[:300]
    if not reason:
        flash("Indique el motivo de la anulación.", "error")
        return redirect(url_for("rx.view", rx_id=r["id"]))
    if r["status"] != "emitida":
        abort(409, description="La receta ya está anulada.")
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE prescriptions SET status = 'anulada', voided_at = ?, voided_by = ?, void_reason = ? WHERE id = ?",
                   (utcnow(), g.user["id"], reason, r["id"]))
        audit("receta_anulada", "receta", r["id"], {"motivo": reason}, db=db)
    flash("Receta anulada. Se conserva en el historial con su motivo.", "ok")
    return redirect(url_for("rx.view", rx_id=r["id"]))
