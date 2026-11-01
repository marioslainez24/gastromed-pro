"""Notas clínicas: borrador con autoguardado, finalización inmutable, adendas trazables."""
import hashlib
import json
import re

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require
from .views_patients import get_patient_or_404
from .gi_forms import BRISTOL as GI_BRISTOL, FORMS as GI_FORMS
from . import consult_diagnoses as CDX, exam as EXAM
from .views_texts import create_template, phrases_json, templates_for

bp = Blueprint("notes", __name__, url_prefix="/notas")

VITALS = [  # clave, etiqueta, unidad, mínimo, máximo (rangos de plausibilidad para atrapar errores de digitación)
    ("pa_sistolica", "PA sistólica", "mmHg", 40, 300), ("pa_diastolica", "PA diastólica", "mmHg", 20, 200),
    ("fc", "Frecuencia cardiaca", "lpm", 20, 250), ("fr", "Frecuencia respiratoria", "rpm", 4, 80),
    ("temperatura", "Temperatura", "°C", 30, 45), ("spo2", "SpO₂", "%", 40, 100),
    ("peso_kg", "Peso", "kg", 0.5, 400), ("talla_cm", "Talla", "cm", 30, 250),
]

TEXT_FIELDS = {
    "motivo": "Motivo de consulta", "hea": "Historia de la enfermedad actual", "revision_sistemas": "Revisión por sistemas",
    "narrativa": "Nota narrativa", "exploracion_general": "Exploración física general",
    "exploracion_abdominal": "Exploración abdominal", "impresion": "Impresión diagnóstica",
    "diferenciales": "Diagnósticos diferenciales", "diagnosticos": "Diagnósticos (texto libre)",
    "plan_diagnostico": "Plan diagnóstico", "plan_terapeutico": "Plan terapéutico", "educacion": "Educación al paciente",
    "signos_alarma": "Signos de alarma explicados", "seguimiento": "Seguimiento y referencia",
}

TEMPLATES = {
    "soap": [
        ("S · Subjetivo", ["motivo", "hea", "revision_sistemas"]),
        ("O · Objetivo", ["__vitales__", "exploracion_general", "exploracion_abdominal"]),
        ("A · Análisis", ["impresion", "diferenciales", "diagnosticos"]),
        ("P · Plan", ["plan_diagnostico", "plan_terapeutico", "educacion", "signos_alarma", "seguimiento"]),
    ],
    "narrativa": [
        ("Consulta", ["motivo", "narrativa"]),
        ("Signos vitales", ["__vitales__"]),
        ("Diagnóstico y plan", ["impresion", "diagnosticos", "plan_terapeutico", "signos_alarma", "seguimiento"]),
    ],
}
MAX_TEXT = 20000


def _get_note(note_id):
    if not re.fullmatch(r"[0-9a-f]{32}", note_id or ""):
        abort(404)
    n = get_db().execute("SELECT n.*, u.full_name AS author, f.full_name AS finalizer FROM clinical_notes n"
                         " JOIN users u ON u.id = n.author_id LEFT JOIN users f ON f.id = n.finalized_by"
                         " WHERE n.id = ? AND n.org_id = ?", (note_id, g.user["org_id"])).fetchone()
    if not n:
        abort(404)
    return n


def _clean_fields(src: dict, template: str) -> tuple[dict, dict]:
    allowed = {k for _, keys in TEMPLATES[template] for k in keys if k != "__vitales__"}
    out, errors = {}, {}
    for k in allowed:
        v = src.get(k)
        if v is None:
            continue
        v = str(v).replace("\r\n", "\n")
        if len(v) > MAX_TEXT:
            errors[k] = f"Máximo {MAX_TEXT} caracteres."
        out[k] = v
    vit = {}
    for key, lab, unit, lo, hi in VITALS:
        raw = src.get(f"v_{key}")
        if raw in (None, ""):
            continue
        try:
            val = float(str(raw).replace(",", "."))
            if not lo <= val <= hi:
                errors[f"v_{key}"] = f"{lab}: valor fuera de rango plausible ({lo}–{hi} {unit}). Verifique."
            vit[key] = val
        except ValueError:
            errors[f"v_{key}"] = f"{lab}: debe ser un número."
    out["vitales"] = vit
    return out, errors


def bmi(vitales: dict):
    """IMC = peso (kg) / talla (m)². Definición de la OMS; se muestra con 1 decimal."""
    w, h = vitales.get("peso_kg"), vitales.get("talla_cm")
    if not w or not h:
        return None
    return round(w / ((h / 100) ** 2), 1)


@bp.route("/nueva", methods=["GET", "POST"])
@require("clinico.editar")
def new():
    src = request.form if request.method == "POST" else request.args
    p = get_patient_or_404(src.get("patient_id", ""))
    db = get_db()
    appt_id = src.get("appointment_id") or None
    if appt_id:
        a = db.execute("SELECT id FROM appointments WHERE id = ? AND patient_id = ? AND org_id = ?",
                       (appt_id, p["id"], g.user["org_id"])).fetchone()
        if not a:
            abort(404)
        existing = db.execute("SELECT id FROM clinical_notes WHERE appointment_id = ? AND status = 'borrador' AND author_id = ?",
                              (appt_id, g.user["id"])).fetchone()
        if existing:
            return redirect(url_for("notes.view", note_id=existing["id"]))
    has_prior = db.execute("SELECT 1 FROM clinical_notes WHERE patient_id = ? AND status = 'finalizada' LIMIT 1", (p["id"],)).fetchone()
    if request.method == "POST":
        kind = request.form.get("kind")
        template = request.form.get("template")
        if kind not in ("primera", "subsecuente") or template not in TEMPLATES:
            abort(400)
        nid = new_id()
        with write_tx(db):
            db.execute("INSERT INTO clinical_notes(id, org_id, patient_id, appointment_id, author_id, kind, template, fields, status,"
                       " created_at, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (nid, g.user["org_id"], p["id"], appt_id, g.user["id"], kind, template,
                        json.dumps({"vitales": {}}, ensure_ascii=False), "borrador", utcnow(), utcnow(), g.user["id"]))
            audit("nota_creada", "nota", nid, {"paciente": p["id"]}, db=db)
        return redirect(url_for("notes.view", note_id=nid))
    return render_template("notas/nueva.html", p=p, appointment_id=appt_id, suggested="subsecuente" if has_prior else "primera")


@bp.route("/<note_id>")
@require("clinico.ver")
def view(note_id):
    from .views_gi import note_forms
    n = _get_note(note_id)
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (n["patient_id"],)).fetchone()
    fields = json.loads(n["fields"])
    addenda = db.execute("SELECT a.*, u.full_name FROM note_addenda a JOIN users u ON u.id = a.author_id"
                         " WHERE a.note_id = ? ORDER BY a.created_at", (n["id"],)).fetchall()
    allergies = db.execute("SELECT * FROM patient_allergies WHERE patient_id = ? AND active = 1", (p["id"],)).fetchall()
    editable = n["status"] == "borrador" and n["author_id"] == g.user["id"] and "clinico.editar" in g.perms
    prior = None
    if editable:
        prior = db.execute("SELECT id, fields, finalized_at, kind FROM clinical_notes WHERE patient_id = ? AND status = 'finalizada'"
                           " AND id <> ? ORDER BY finalized_at DESC LIMIT 1", (p["id"], n["id"])).fetchone()
    prescriptions = db.execute("SELECT id, issued_at, status FROM prescriptions WHERE note_id = ? ORDER BY issued_at", (n["id"],)).fetchall()
    audit("nota_consultada", "nota", n["id"])
    from .views_extras import with_dictation
    return with_dictation(render_template("notas/ver.html", n=n, p=p, fields=fields, addenda=addenda, allergies=allergies, editable=editable,
                           sections=TEMPLATES[n["template"]], text_labels=TEXT_FIELDS, vitals=VITALS, bmi=bmi(fields.get("vitales", {})),
                           prior=prior, prior_fields=json.loads(prior["fields"]) if prior else None, prescriptions=prescriptions,
                           gi_forms=note_forms(db, n["id"]), GI_FORMS=GI_FORMS,
                           orders=db.execute("SELECT o.*, (SELECT GROUP_CONCAT(description, ', ') FROM order_items i WHERE i.order_id = o.id)"
                                             " AS items FROM orders o WHERE o.note_id = ? ORDER BY o.created_at", (n["id"],)).fetchall(),
                           phrases_json=phrases_json(db) if editable else "[]", BRISTOL=GI_BRISTOL,
                           hea_target="hea" if n["template"] == "soap" else "narrativa",
                           exam_target="exploracion_general" if n["template"] == "soap" else "narrativa", EXAM_SYSTEMS=EXAM.SYSTEMS,
                           dx_json=json.dumps(CDX.as_list(), ensure_ascii=False), dx_source=CDX.ICD_SOURCE,
                           note_tpls=json.dumps(templates_for(db, n["template"]), ensure_ascii=False) if editable else "[]",
                           errors={}), editable)


@bp.route("/<note_id>/guardar", methods=["POST"])
@require("clinico.editar")
def save(note_id):
    """Guarda el borrador. Acepta formulario o JSON (autoguardado). Control de versión optimista."""
    n = _get_note(note_id)
    if n["author_id"] != g.user["id"]:
        abort(403)
    if n["status"] != "borrador":
        abort(409, description="La nota ya está finalizada. Para corregirla agregue una adenda.")
    src = request.get_json(silent=True) if request.is_json else request.form
    if src is None:
        abort(400)
    try:
        version = int(src.get("version"))
    except (TypeError, ValueError):
        abort(400)
    fields, errors = _clean_fields(src, n["template"])
    if errors:
        if request.is_json:
            return jsonify({"error": "Datos no válidos", "campos": errors}), 422
        flash("Revise los campos marcados: " + " ".join(errors.values()), "error")
        return redirect(url_for("notes.view", note_id=n["id"]))
    db = get_db()
    with write_tx(db):
        cur = db.execute("UPDATE clinical_notes SET fields = ?, updated_at = ?, updated_by = ?, version = version + 1"
                         " WHERE id = ? AND version = ? AND status = 'borrador'",
                         (json.dumps(fields, ensure_ascii=False, sort_keys=True), utcnow(), g.user["id"], n["id"], version))
        if cur.rowcount == 0:
            abort(409, description="Esta nota se modificó en otra ventana o dispositivo. Sus últimos cambios NO se guardaron: "
                                   "copie su texto, recargue la página y vuelva a aplicarlo.")
        audit("nota_borrador_guardado", "nota", n["id"], db=db)
        new_version = db.execute("SELECT version, updated_at FROM clinical_notes WHERE id = ?", (n["id"],)).fetchone()
    if request.is_json:
        return jsonify({"ok": True, "version": new_version["version"], "guardado": new_version["updated_at"], "imc": bmi(fields["vitales"])})
    if request.form.get("then") == "finalizar":
        return redirect(url_for("notes.view", note_id=n["id"], confirmar="1"))
    if request.form.get("then") == "plantilla":
        name = (request.form.get("template_name") or "").strip()
        if not name:
            flash("Borrador guardado. Para crear la plantilla escriba un nombre.", "error")
            return redirect(url_for("notes.view", note_id=n["id"]))
        scope = request.form.get("template_scope") if request.form.get("template_scope") in ("ambas", n["template"]) else n["template"]
        with write_tx(db):
            tid = create_template(db, name, scope, {k: v for k, v in fields.items() if k != "vitales"})
        flash(f"Borrador guardado y plantilla «{name[:80]}» creada." if tid else "Borrador guardado. La nota no tiene texto para crear una plantilla.",
              "ok" if tid else "error")
        return redirect(url_for("notes.view", note_id=n["id"]))
    flash("Borrador guardado.", "ok")
    return redirect(url_for("notes.view", note_id=n["id"]))


@bp.route("/<note_id>/finalizar", methods=["POST"])
@require("clinico.editar", "notas.finalizar")
def finalize(note_id):
    n = _get_note(note_id)
    if n["author_id"] != g.user["id"]:
        abort(403)
    if n["status"] != "borrador":
        abort(409, description="La nota ya estaba finalizada.")
    fields = json.loads(n["fields"])
    if not (fields.get("motivo") or "").strip():
        flash("No se puede finalizar: el motivo de consulta está vacío.", "error")
        return redirect(url_for("notes.view", note_id=n["id"]))
    canonical = json.dumps({"fields": fields, "patient_id": n["patient_id"], "author_id": n["author_id"], "kind": n["kind"],
                            "template": n["template"]}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    db = get_db()
    with write_tx(db):
        cur = db.execute("UPDATE clinical_notes SET status = 'finalizada', finalized_at = ?, finalized_by = ?, content_sha256 = ?,"
                         " version = version + 1 WHERE id = ? AND version = ? AND status = 'borrador'",
                         (utcnow(), g.user["id"], digest, n["id"], int(request.form.get("version", "0"))))
        if cur.rowcount == 0:
            abort(409, description="La nota cambió antes de finalizar. Revise la versión actual y vuelva a finalizar.")
        audit("nota_finalizada", "nota", n["id"], {"sha256": digest}, db=db)
    flash("Nota finalizada. Ya no puede modificarse; las correcciones se registran como adendas.", "ok")
    return redirect(url_for("notes.view", note_id=n["id"]))


@bp.route("/<note_id>/adenda", methods=["POST"])
@require("clinico.editar")
def addendum(note_id):
    n = _get_note(note_id)
    if n["status"] != "finalizada":
        abort(409, description="Las adendas se agregan a notas finalizadas; un borrador se edita directamente.")
    text = (request.form.get("text") or "").strip()
    if not text or len(text) > MAX_TEXT:
        flash("Escriba el texto de la adenda.", "error")
        return redirect(url_for("notes.view", note_id=n["id"]) + "#adendas")
    db = get_db()
    with write_tx(db):
        aid = new_id()
        db.execute("INSERT INTO note_addenda(id, note_id, author_id, created_at, text) VALUES (?,?,?,?,?)",
                   (aid, n["id"], g.user["id"], utcnow(), text))
        audit("nota_adenda", "nota", n["id"], {"adenda": aid}, db=db)
    flash("Adenda registrada.", "ok")
    return redirect(url_for("notes.view", note_id=n["id"]) + "#adendas")
