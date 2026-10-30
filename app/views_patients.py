"""Pacientes: búsqueda global, registro, expediente, alergias."""
import re
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db, new_id, next_counter, utcnow, write_tx
from .security import audit, can, require
from .util import LABELS, digits, local_today, normalize

bp = Blueprint("patients", __name__, url_prefix="/pacientes")

ADMIN_FIELDS = {  # campo: (obligatorio, longitud máxima)
    "first_names": (True, 120), "last_names": (True, 120), "birth_date": (False, 10), "sex": (True, 20),
    "document_type": (True, 20), "document_number": (False, 40), "phone": (False, 40), "email": (False, 160),
    "address": (False, 300), "origin": (False, 120), "emergency_contact_name": (False, 160),
    "emergency_contact_phone": (False, 40), "referring_physician": (False, 160), "payer": (False, 160),
}
FIELD_NAMES = {"first_names": "Nombres", "last_names": "Apellidos", "birth_date": "Fecha de nacimiento", "sex": "Sexo",
               "document_type": "Tipo de documento", "document_number": "Número de documento", "email": "Correo"}


def get_patient_or_404(patient_id: str):
    """Siempre filtra por organización: cambiar el identificador en la URL no expone otro expediente."""
    if not re.fullmatch(r"[0-9a-f]{32}", patient_id or ""):
        abort(404)
    p = get_db().execute("SELECT * FROM patients WHERE id = ? AND org_id = ?", (patient_id, g.user["org_id"])).fetchone()
    if not p:
        abort(404)
    return p


def _search_text(d) -> str:
    return " ".join(filter(None, [normalize(d.get("first_names")), normalize(d.get("last_names")), (d.get("mrn") or "").lower(),
                                  digits(d.get("document_number")), digits(d.get("phone"))]))


def validate_admin(form) -> tuple[dict, dict]:
    data, errors = {}, {}
    for f, (required, maxlen) in ADMIN_FIELDS.items():
        v = (form.get(f) or "").strip()
        if len(v) > maxlen:
            errors[f] = f"Máximo {maxlen} caracteres."
        if required and not v:
            errors[f] = "Campo obligatorio."
        data[f] = v or None
    if data["sex"] and data["sex"] not in LABELS["sex"]:
        errors["sex"] = "Valor no válido."
    if data["document_type"] and data["document_type"] not in LABELS["document_type"]:
        errors["document_type"] = "Valor no válido."
    if data["document_type"] == "sin_documento":
        data["document_number"] = None
    elif data["document_type"] and not data["document_number"]:
        errors["document_number"] = "Indique el número o elija «Sin documento»."
    if data["document_type"] == "dni" and data["document_number"]:
        d = digits(data["document_number"])
        if len(d) != 13:
            errors["document_number"] = "El DNI hondureño tiene 13 dígitos."
        else:
            data["document_number"] = f"{d[:4]}-{d[4:8]}-{d[8:]}"
    if data["birth_date"]:
        try:
            b = date.fromisoformat(data["birth_date"])
            if b > local_today() or b.year < 1900:
                errors["birth_date"] = "Fecha fuera de rango."
        except ValueError:
            errors["birth_date"] = "Fecha no válida."
    if data["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", data["email"]):
        errors["email"] = "Correo no válido."
    return data, errors


def find_duplicates(db, org_id, data, exclude_id=None):
    rows = db.execute(
        "SELECT * FROM patients WHERE org_id = ? AND merged_into IS NULL AND id <> COALESCE(?, '') AND ("
        " (document_number IS NOT NULL AND document_type = ? AND document_number = ?)"
        " OR (birth_date = ? AND search_text LIKE ? || '%'))",
        (org_id, exclude_id, data["document_type"], data["document_number"], data["birth_date"],
         (normalize(data["first_names"]) + " " + normalize(data["last_names"])).strip())).fetchall()
    if data["phone"] and len(digits(data["phone"])) >= 8:
        rows += db.execute("SELECT * FROM patients WHERE org_id = ? AND merged_into IS NULL AND id <> COALESCE(?, '')"
                           " AND search_text LIKE '%' || ? || '%' AND search_text LIKE ? || '%'",
                           (org_id, exclude_id, digits(data["phone"]), normalize(data["first_names"]).split(" ")[0])).fetchall()
    seen, out = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


@bp.route("/")
@require("pacientes.ver_admin")
def search():
    q = (request.args.get("q") or "").strip()[:100]
    db = get_db()
    rows = []
    if q:
        terms = [t for t in normalize(q).split(" ") if t][:5]
        sql = "SELECT * FROM patients WHERE org_id = ? AND merged_into IS NULL"
        params = [g.user["org_id"]]
        for t in terms:
            dt = digits(t)
            sql += " AND (search_text LIKE ? ESCAPE '\\'" + (" OR search_text LIKE ? ESCAPE '\\'" if dt and dt != t else "") + ")"
            esc = t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{esc}%")
            if dt and dt != t:
                params.append(f"%{dt}%")
        sql += " ORDER BY last_names, first_names LIMIT 50"
        rows = db.execute(sql, params).fetchall()
        audit("busqueda_pacientes", "paciente", None, {"resultados": len(rows)})
    else:
        rows = db.execute("SELECT * FROM patients WHERE org_id = ? AND merged_into IS NULL ORDER BY updated_at DESC LIMIT 20",
                          (g.user["org_id"],)).fetchall()
    if request.args.get("formato") == "json":
        return {"resultados": [{"id": r["id"], "nombre": f'{r["first_names"]} {r["last_names"]}', "mrn": r["mrn"],
                                "documento": r["document_number"], "url": url_for("patients.view", patient_id=r["id"])}
                               for r in rows[:8]]}
    return render_template("pacientes/buscar.html", q=q, rows=rows)


@bp.route("/nuevo", methods=["GET", "POST"])
@require("pacientes.editar_admin")
def new():
    data, errors, dups = {}, {}, []
    if request.method == "POST":
        data, errors = validate_admin(request.form)
        db = get_db()
        if not errors:
            dups = find_duplicates(db, g.user["org_id"], data)
            exact_doc = [d for d in dups if data["document_number"] and d["document_number"] == data["document_number"]
                         and d["document_type"] == data["document_type"]]
            if exact_doc:
                errors["document_number"] = f"Ya existe un expediente con este documento ({exact_doc[0]['mrn']})."
            elif dups and request.form.get("confirmo_distinto") != "1":
                return render_template("pacientes/form.html", data=data, errors={}, dups=dups, mode="new"), 409
        if not errors:
            pid = new_id()
            now = utcnow()
            with write_tx(db):
                n = next_counter(db, g.user["org_id"], "mrn")
                mrn = f"GM-{n:06d}"
                data_full = dict(data, mrn=mrn)
                db.execute(
                    "INSERT INTO patients(id, org_id, mrn, first_names, last_names, birth_date, sex, document_type, document_number,"
                    " phone, email, address, origin, emergency_contact_name, emergency_contact_phone, referring_physician, payer,"
                    " search_text, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, g.user["org_id"], mrn, data["first_names"], data["last_names"], data["birth_date"], data["sex"],
                     data["document_type"], data["document_number"], data["phone"], data["email"], data["address"], data["origin"],
                     data["emergency_contact_name"], data["emergency_contact_phone"], data["referring_physician"], data["payer"],
                     _search_text(data_full), now, g.user["id"], now, g.user["id"]))
                audit("paciente_creado", "paciente", pid, {"mrn": mrn, "posible_duplicado_confirmado": bool(dups)}, db=db)
            flash(f"Paciente registrado con el identificador {mrn}.", "ok")
            return redirect(url_for("patients.view", patient_id=pid))
    return render_template("pacientes/form.html", data=data, errors=errors, dups=dups, mode="new"), 422 if errors else 200


@bp.route("/<patient_id>")
@require("pacientes.ver_admin")
def view(patient_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    ctx = {"p": p, "allergies": [], "notes": [], "prescriptions": []}
    ctx["appointments"] = db.execute(
        "SELECT a.*, u.full_name AS practitioner FROM appointments a JOIN users u ON u.id = a.practitioner_id"
        " WHERE a.patient_id = ? AND a.org_id = ? ORDER BY a.starts_at DESC LIMIT 30", (p["id"], g.user["org_id"])).fetchall() \
        if can("agenda.ver") else []
    if can("clinico.ver"):
        ctx["allergies"] = db.execute("SELECT * FROM patient_allergies WHERE patient_id = ? AND active = 1 ORDER BY recorded_at",
                                      (p["id"],)).fetchall()
        ctx["notes"] = db.execute(
            "SELECT n.*, u.full_name AS author, (SELECT COUNT(*) FROM note_addenda x WHERE x.note_id = n.id) AS addenda"
            " FROM clinical_notes n JOIN users u ON u.id = n.author_id WHERE n.patient_id = ? AND n.org_id = ?"
            " ORDER BY n.created_at DESC", (p["id"], g.user["org_id"])).fetchall()
        ctx["prescriptions"] = db.execute(
            "SELECT r.*, u.full_name AS author, (SELECT GROUP_CONCAT(active_ingredient, ', ') FROM prescription_items i"
            " WHERE i.prescription_id = r.id) AS meds FROM prescriptions r JOIN users u ON u.id = r.author_id"
            " WHERE r.patient_id = ? AND r.org_id = ? ORDER BY r.issued_at DESC", (p["id"], g.user["org_id"])).fetchall()
        audit("expediente_consultado", "paciente", p["id"])
    else:
        audit("ficha_administrativa_consultada", "paciente", p["id"])
    return render_template("pacientes/ver.html", **ctx)


@bp.route("/<patient_id>/editar", methods=["GET", "POST"])
@require("pacientes.editar_admin")
def edit(patient_id):
    p = get_patient_or_404(patient_id)
    data, errors = dict(p), {}
    if request.method == "POST":
        data, errors = validate_admin(request.form)
        try:
            version = int(request.form.get("version", ""))
        except ValueError:
            abort(400)
        if not errors:
            db = get_db()
            dup_doc = data["document_number"] and db.execute(
                "SELECT mrn FROM patients WHERE org_id = ? AND id <> ? AND document_type = ? AND document_number = ? AND merged_into IS NULL",
                (g.user["org_id"], p["id"], data["document_type"], data["document_number"])).fetchone()
            if dup_doc:
                errors["document_number"] = f"Ya existe un expediente con este documento ({dup_doc['mrn']})."
        if not errors:
            changed = [f for f in ADMIN_FIELDS if (p[f] or None) != data[f]]
            with write_tx(db):
                cur = db.execute(
                    "UPDATE patients SET " + ", ".join(f"{f} = ?" for f in ADMIN_FIELDS) +
                    ", search_text = ?, updated_at = ?, updated_by = ?, version = version + 1"
                    " WHERE id = ? AND org_id = ? AND version = ?",
                    [data[f] for f in ADMIN_FIELDS] + [_search_text(dict(data, mrn=p["mrn"])), utcnow(), g.user["id"],
                                                        p["id"], g.user["org_id"], version])
                if cur.rowcount == 0:
                    abort(409, description="Otro usuario modificó este expediente mientras usted lo editaba. "
                                           "Sus cambios NO se guardaron. Abra el expediente de nuevo y repita la edición.")
                audit("paciente_editado", "paciente", p["id"], {"campos": changed}, db=db)
            flash("Datos del paciente actualizados.", "ok")
            return redirect(url_for("patients.view", patient_id=p["id"]))
        data["version"] = request.form.get("version")
        data["id"] = p["id"]
        data["mrn"] = p["mrn"]
    return render_template("pacientes/form.html", data=data, errors=errors, dups=[], mode="edit"), 422 if errors else 200


@bp.route("/<patient_id>/clinico", methods=["POST"])
@require("clinico.editar")
def update_clinical_header(patient_id):
    """Estado de alergias y alertas clínicas (cabecera clínica del expediente)."""
    p = get_patient_or_404(patient_id)
    status = request.form.get("allergy_status")
    alerts = (request.form.get("clinical_alerts") or "").strip()[:1000] or None
    if status not in LABELS["allergy_status"]:
        abort(400)
    db = get_db()
    with write_tx(db):
        active = db.execute("SELECT COUNT(*) c FROM patient_allergies WHERE patient_id = ? AND active = 1", (p["id"],)).fetchone()["c"]
        if status == "sin_alergias_conocidas" and active:
            abort(409, description="Hay alergias activas registradas: no puede marcarse «Sin alergias conocidas».")
        cur = db.execute("UPDATE patients SET allergy_status = ?, clinical_alerts = ?, updated_at = ?, updated_by = ?,"
                         " version = version + 1 WHERE id = ? AND org_id = ? AND version = ?",
                         (status, alerts, utcnow(), g.user["id"], p["id"], g.user["org_id"], int(request.form.get("version", "0"))))
        if cur.rowcount == 0:
            abort(409, description="El expediente cambió mientras lo editaba. Recargue la página.")
        audit("cabecera_clinica_editada", "paciente", p["id"], {"estado_alergias": status}, db=db)
    flash("Información clínica actualizada.", "ok")
    return redirect(url_for("patients.view", patient_id=p["id"]))


@bp.route("/<patient_id>/alergias", methods=["POST"])
@require("clinico.editar")
def add_allergy(patient_id):
    p = get_patient_or_404(patient_id)
    substance = (request.form.get("substance") or "").strip()[:160]
    reaction = (request.form.get("reaction") or "").strip()[:300] or None
    severity = request.form.get("severity") or "desconocida"
    if not substance or severity not in LABELS["severity"]:
        flash("Indique la sustancia y una gravedad válida.", "error")
        return redirect(url_for("patients.view", patient_id=p["id"]) + "#alergias")
    db = get_db()
    with write_tx(db):
        aid = new_id()
        db.execute("INSERT INTO patient_allergies(id, patient_id, substance, reaction, severity, recorded_by, recorded_at)"
                   " VALUES (?,?,?,?,?,?,?)", (aid, p["id"], substance, reaction, severity, g.user["id"], utcnow()))
        db.execute("UPDATE patients SET allergy_status = 'con_alergias', updated_at = ?, updated_by = ?, version = version + 1"
                   " WHERE id = ?", (utcnow(), g.user["id"], p["id"]))
        audit("alergia_registrada", "paciente", p["id"], {"alergia_id": aid}, db=db)
    flash("Alergia registrada.", "ok")
    return redirect(url_for("patients.view", patient_id=p["id"]) + "#alergias")


@bp.route("/<patient_id>/alergias/<allergy_id>/inactivar", methods=["POST"])
@require("clinico.editar")
def deactivate_allergy(patient_id, allergy_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    with write_tx(db):
        cur = db.execute("UPDATE patient_allergies SET active = 0 WHERE id = ? AND patient_id = ?", (allergy_id, p["id"]))
        if cur.rowcount == 0:
            abort(404)
        remaining = db.execute("SELECT COUNT(*) c FROM patient_allergies WHERE patient_id = ? AND active = 1", (p["id"],)).fetchone()["c"]
        if not remaining:
            # Al retirar la última alergia el estado vuelve a «no investigado»: el médico debe reafirmarlo explícitamente.
            db.execute("UPDATE patients SET allergy_status = 'no_investigado', version = version + 1 WHERE id = ?", (p["id"],))
        audit("alergia_inactivada", "paciente", p["id"], {"alergia_id": allergy_id}, db=db)
    flash("Alergia marcada como inactiva (se conserva en el historial).", "ok")
    return redirect(url_for("patients.view", patient_id=p["id"]) + "#alergias")
