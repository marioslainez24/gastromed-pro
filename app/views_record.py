"""Expediente clínico: antecedentes, medicamentos actuales (con conciliación) y lista de problemas.

Nada se borra: los registros se inactivan, suspenden o resuelven conservando autor y fecha.
"""
from flask import Blueprint, abort, flash, g, redirect, request, url_for

from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require
from .views_patients import get_patient_or_404

bp = Blueprint("record", __name__, url_prefix="/pacientes/<patient_id>/expediente")

HISTORY_CATEGORIES = {"personal": "Patológicos personales", "quirurgico": "Quirúrgicos", "familiar": "Familiares",
                      "habito": "Hábitos (tabaco, alcohol, otros)", "hospitalizacion": "Hospitalizaciones",
                      "procedimiento": "Procedimientos previos (endoscopias, imágenes, etc.)"}
MED_SOURCES = {"referido_paciente": "Referido por el paciente", "prescrito_aqui": "Prescrito en esta clínica",
               "otro_medico": "Indicado por otro médico"}


def _txt(name, maxlen, required=False):
    v = (request.form.get(name) or "").strip()
    if required and not v:
        return None
    return v[:maxlen] or None


def _back(p, anchor):
    return redirect(url_for("patients.view", patient_id=p["id"]) + "#" + anchor)


@bp.route("/antecedentes", methods=["POST"])
@require("clinico.editar")
def add_history(patient_id):
    p = get_patient_or_404(patient_id)
    cat = request.form.get("category")
    desc = _txt("description", 600, required=True)
    if cat not in HISTORY_CATEGORIES or not desc:
        flash("Indique la categoría y la descripción del antecedente.", "error")
        return _back(p, "antecedentes")
    db = get_db()
    with write_tx(db):
        hid = new_id()
        db.execute("INSERT INTO patient_history(id, patient_id, category, description, when_text, notes, recorded_by, recorded_at)"
                   " VALUES (?,?,?,?,?,?,?,?)", (hid, p["id"], cat, desc, _txt("when_text", 80), _txt("notes", 600), g.user["id"], utcnow()))
        audit("antecedente_registrado", "paciente", p["id"], {"antecedente": hid, "categoria": cat}, db=db)
    flash("Antecedente registrado.", "ok")
    return _back(p, "antecedentes")


@bp.route("/antecedentes/<item_id>/inactivar", methods=["POST"])
@require("clinico.editar")
def inactivate_history(patient_id, item_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    with write_tx(db):
        if db.execute("UPDATE patient_history SET active = 0, inactivated_by = ?, inactivated_at = ? WHERE id = ? AND patient_id = ? AND active = 1",
                      (g.user["id"], utcnow(), item_id, p["id"])).rowcount == 0:
            abort(404)
        audit("antecedente_inactivado", "paciente", p["id"], {"antecedente": item_id}, db=db)
    flash("Antecedente marcado como registrado por error / no vigente (se conserva en el historial).", "ok")
    return _back(p, "antecedentes")


@bp.route("/medicamentos", methods=["POST"])
@require("clinico.editar")
def add_medication(patient_id):
    p = get_patient_or_404(patient_id)
    name = _txt("name", 160, required=True)
    source = request.form.get("source") or "referido_paciente"
    if not name or source not in MED_SOURCES:
        flash("Indique el nombre del medicamento.", "error")
        return _back(p, "medicamentos")
    db = get_db()
    with write_tx(db):
        mid = new_id()
        db.execute("INSERT INTO patient_medications(id, patient_id, name, dose, frequency, route, indication, source, recorded_by, recorded_at)"
                   " VALUES (?,?,?,?,?,?,?,?,?,?)", (mid, p["id"], name, _txt("dose", 80), _txt("frequency", 120), _txt("route", 60),
                                                     _txt("indication", 200), source, g.user["id"], utcnow()))
        audit("medicamento_registrado", "paciente", p["id"], {"medicamento": mid}, db=db)
    flash("Medicamento agregado a la lista actual.", "ok")
    return _back(p, "medicamentos")


@bp.route("/medicamentos/<item_id>/suspender", methods=["POST"])
@require("clinico.editar")
def stop_medication(patient_id, item_id):
    p = get_patient_or_404(patient_id)
    reason = _txt("stop_reason", 300) or "Sin motivo especificado"
    db = get_db()
    with write_tx(db):
        if db.execute("UPDATE patient_medications SET status = 'suspendido', stop_reason = ?, stopped_by = ?, stopped_at = ?"
                      " WHERE id = ? AND patient_id = ? AND status = 'activo'", (reason, g.user["id"], utcnow(), item_id, p["id"])).rowcount == 0:
            abort(404)
        audit("medicamento_suspendido", "paciente", p["id"], {"medicamento": item_id}, db=db)
    flash("Medicamento suspendido (queda en el historial).", "ok")
    return _back(p, "medicamentos")


@bp.route("/medicamentos/conciliar", methods=["POST"])
@require("clinico.editar")
def reconcile(patient_id):
    p = get_patient_or_404(patient_id)
    if request.form.get("confirm") != "1":
        abort(400)
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE patients SET meds_reconciled_at = ?, meds_reconciled_by = ?, version = version + 1 WHERE id = ?",
                   (utcnow(), g.user["id"], p["id"]))
        n = db.execute("SELECT COUNT(*) c FROM patient_medications WHERE patient_id = ? AND status = 'activo'", (p["id"],)).fetchone()["c"]
        audit("medicamentos_conciliados", "paciente", p["id"], {"activos": n}, db=db)
    flash("Conciliación registrada: confirmó con el paciente que la lista de medicamentos actuales está completa.", "ok")
    return _back(p, "medicamentos")


@bp.route("/problemas", methods=["POST"])
@require("clinico.editar")
def add_problem(patient_id):
    p = get_patient_or_404(patient_id)
    desc = _txt("description", 300, required=True)
    if not desc:
        flash("Describa el problema.", "error")
        return _back(p, "problemas")
    db = get_db()
    with write_tx(db):
        pid = new_id()
        db.execute("INSERT INTO patient_problems(id, patient_id, description, onset_text, recorded_by, recorded_at) VALUES (?,?,?,?,?,?)",
                   (pid, p["id"], desc, _txt("onset_text", 80), g.user["id"], utcnow()))
        audit("problema_registrado", "paciente", p["id"], {"problema": pid}, db=db)
    flash("Problema agregado a la lista.", "ok")
    return _back(p, "problemas")


@bp.route("/problemas/<item_id>/resolver", methods=["POST"])
@require("clinico.editar")
def resolve_problem(patient_id, item_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    with write_tx(db):
        if db.execute("UPDATE patient_problems SET status = 'resuelto', resolved_at = ?, resolved_by = ? WHERE id = ? AND patient_id = ?"
                      " AND status = 'activo'", (utcnow(), g.user["id"], item_id, p["id"])).rowcount == 0:
            abort(404)
        audit("problema_resuelto", "paciente", p["id"], {"problema": item_id}, db=db)
    flash("Problema marcado como resuelto.", "ok")
    return _back(p, "problemas")


def load_record(db, patient_id):
    """Datos clínicos del expediente para la vista del paciente."""
    return {
        "history": db.execute("SELECT h.*, u.full_name AS author FROM patient_history h JOIN users u ON u.id = h.recorded_by"
                              " WHERE h.patient_id = ? AND h.active = 1 ORDER BY h.category, h.recorded_at", (patient_id,)).fetchall(),
        "meds": db.execute("SELECT m.*, u.full_name AS author FROM patient_medications m JOIN users u ON u.id = m.recorded_by"
                           " WHERE m.patient_id = ? ORDER BY m.status, m.recorded_at DESC", (patient_id,)).fetchall(),
        "problems": db.execute("SELECT * FROM patient_problems WHERE patient_id = ? ORDER BY status, recorded_at DESC", (patient_id,)).fetchall(),
        "history_categories": HISTORY_CATEGORIES, "med_sources": MED_SOURCES,
    }
