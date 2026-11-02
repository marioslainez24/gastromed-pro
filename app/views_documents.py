"""Documentos clínicos (v0.10.0): constancia de incapacidad, constancia de asistencia, referencia/interconsulta y documento libre.

El sistema arma el texto con los datos que el médico escribe y los del expediente; el médico lo revisa y puede editarlo antes
de emitir. Una vez emitido es inmutable (base de datos) y solo puede anularse con motivo. El PDF requiere firma manuscrita.
"""
import hashlib
import json
import re
from datetime import date, timedelta

from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require
from .util import age, clinic_settings, fmt_birth, local_today
from .views_patients import get_patient_or_404
from .views_texts import phrases_json

bp = Blueprint("docs", __name__)

KINDS = {
    "incapacidad": "Constancia de incapacidad",
    "constancia": "Constancia de atención médica",
    "referencia": "Referencia / interconsulta",
    "libre": "Documento libre",
}
MAX_DAYS = 365

_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
      "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
      "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_D = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_C = {1: "ciento", 2: "doscientos", 3: "trescientos"}


def number_words(n: int) -> str:
    """Número en letras (1–399), como se escribe en constancias: 3 → «tres», 21 → «veintiuno», 100 → «cien»."""
    if n == 100:
        return "cien"
    if n >= 100:
        rest = n % 100
        return _C[n // 100] + (" " + number_words(rest) if rest else "")
    if n < 30:
        return _U[n]
    d, u = divmod(n, 10)
    return _D[d] + (" y " + _U[u] if u else "")


def _patient_phrase(p, on):
    doc = ""
    if p["document_type"] != "sin_documento" and p["document_number"]:
        kind = {"dni": "identidad", "pasaporte": "pasaporte", "carne_residente": "carné de residente"}.get(p["document_type"], "documento")
        doc = f", con {kind} n.º {p['document_number']}"
    a = age(p["birth_date"], on)
    return f"{p['first_names']} {p['last_names']}{doc}" + (f", de {a}" if a and a != "—" else "")


def compose(kind, f, p, s):
    """Texto propuesto del documento a partir de los datos del formulario. Devuelve (título, texto, datos, errores)."""
    errors, data = [], {}
    today = local_today()

    def dt(k, required=True):
        v = (f.get(k) or "").strip()
        if not v:
            if required:
                errors.append("Falta una fecha.")
            return None
        try:
            return date.fromisoformat(v)
        except ValueError:
            errors.append("Fecha no válida.")
            return None

    dx = (f.get("diagnosis") or "").strip()[:500]
    extra = (f.get("extra") or "").strip()[:3000]
    include_dx = f.get("include_dx") == "1"
    seen = dt("seen_on", required=False) or today
    data.update(seen_on=seen.isoformat(), diagnosis=dx or None, include_dx=include_dx, extra=extra or None)
    who = _patient_phrase(p, seen)
    if kind == "incapacidad":
        title = "CONSTANCIA DE INCAPACIDAD MÉDICA"
        try:
            days = int(f.get("days") or 0)
        except ValueError:
            days = 0
        if not 1 <= days <= MAX_DAYS:
            errors.append(f"Indique los días de incapacidad (1 a {MAX_DAYS}).")
            days = max(1, min(days, MAX_DAYS))
        start = dt("start_on", required=False) or seen
        end = start + timedelta(days=days - 1)
        data.update(days=days, start_on=start.isoformat(), end_on=end.isoformat())
        body = (f"Por medio de la presente hago constar que {who}, fue evaluado(a) en esta consulta el día {fmt_birth(seen.isoformat())}"
                + (f" con diagnóstico de {dx}" if dx and include_dx else "")
                + f", por lo que se le indica incapacidad por {days} ({number_words(days)}) {'día' if days == 1 else 'días'}, "
                f"del {fmt_birth(start.isoformat())} al {fmt_birth(end.isoformat())}, ambos inclusive.")
    elif kind == "constancia":
        title = "CONSTANCIA DE ATENCIÓN MÉDICA"
        t1 = (f.get("time_from") or "").strip()[:5]
        t2 = (f.get("time_to") or "").strip()[:5]
        for t in (t1, t2):
            if t and not re.fullmatch(r"\d{2}:\d{2}", t):
                errors.append("Hora no válida.")
        data.update(time_from=t1 or None, time_to=t2 or None)
        horas = f" de {t1} a {t2}" if t1 and t2 else (f" a las {t1}" if t1 else "")
        body = (f"Por medio de la presente hago constar que {who}, asistió a consulta médica en este consultorio el día "
                f"{fmt_birth(seen.isoformat())}{horas}" + (f", con diagnóstico de {dx}" if dx and include_dx else "") + ".")
    elif kind == "referencia":
        title = "REFERENCIA / INTERCONSULTA"
        to = (f.get("refer_to") or "").strip()[:200]
        reason = (f.get("reason") or "").strip()[:2000]
        if not to:
            errors.append("Indique a quién o a qué servicio se refiere.")
        if not reason:
            errors.append("Indique el motivo de la referencia.")
        data.update(refer_to=to or None, reason=reason or None)
        body = (f"Estimado(a) {to or '…'}:\n\nRefiero a {who}, para su valoración.\n\nMotivo: {reason or '…'}"
                + (f"\n\nDiagnóstico: {dx}" if dx else ""))
    else:
        title = ((f.get("title") or "").strip()[:120] or "CONSTANCIA").upper()
        body = ""
    if extra:
        body = (body + "\n\n" + extra).strip()
    if kind != "referencia":
        body += ("\n\n" if body else "") + f"Y para los fines que al interesado(a) convengan, se extiende la presente en {s['address'] or '…'}, " \
                                          f"a los {number_words(today.day)} días del mes de {_MONTHS[today.month - 1]} de {today.year}."
    return title, body.strip(), data, errors


_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _get_doc(doc_id):
    if not re.fullmatch(r"[0-9a-f]{32}", doc_id or ""):
        abort(404)
    d = get_db().execute("SELECT d.*, u.full_name AS author FROM clinical_documents d JOIN users u ON u.id = d.author_id"
                         " WHERE d.id = ? AND d.org_id = ?", (doc_id, g.user["org_id"])).fetchone()
    if not d:
        abort(404)
    return d


@bp.route("/pacientes/<patient_id>/documentos")
@require("clinico.ver")
def patient_docs(patient_id):
    p = get_patient_or_404(patient_id)
    rows = get_db().execute("SELECT d.*, u.full_name AS author FROM clinical_documents d JOIN users u ON u.id = d.author_id"
                            " WHERE d.patient_id = ? ORDER BY d.issued_at DESC", (p["id"],)).fetchall()
    from .views_handouts import given_to, handouts
    db = get_db()
    return render_template("documentos/lista.html", p=p, rows=rows, KINDS=KINDS, handouts=handouts(db), given=given_to(db, p["id"]))


@bp.route("/pacientes/<patient_id>/documentos/nuevo", methods=["GET", "POST"])
@require("clinico.editar", "notas.finalizar")
def doc_new(patient_id):
    p = get_patient_or_404(patient_id)
    kind = request.values.get("kind") or "incapacidad"
    if kind not in KINDS:
        abort(400)
    s = clinic_settings()
    f = request.form if request.method == "POST" else request.args
    title, body, data, errors = compose(kind, f, p, s)
    step = request.form.get("step") if request.method == "POST" else None
    if step == "emitir":
        final_body = (request.form.get("body") or "").replace("\r\n", "\n").strip()[:8000]
        final_title = (request.form.get("final_title") or title).strip()[:120]
        if not final_body:
            errors.append("El documento no tiene texto.")
        if not errors:
            db = get_db()
            did = new_id()
            issued = utcnow()
            digest = hashlib.sha256(json.dumps({"t": final_title, "b": final_body, "d": data, "p": p["id"], "at": issued},
                                               ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            with write_tx(db):
                db.execute("INSERT INTO clinical_documents(id, org_id, patient_id, kind, title, data, body, author_id, issued_at, content_sha256)"
                           " VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (did, g.user["org_id"], p["id"], kind, final_title, json.dumps(data, ensure_ascii=False), final_body,
                            g.user["id"], issued, digest))
                audit("documento_emitido", "documento", did, {"paciente": p["id"], "tipo": kind}, db=db)
            flash("Documento emitido. Imprímalo y fírmelo.", "ok")
            return redirect(url_for("docs.doc_view", doc_id=did))
        step = "revisar"
    return render_template("documentos/nuevo.html", p=p, kind=kind, KINDS=KINDS, f=f, title=title, body=body, errors=errors if step else [],
                           step=step, today=local_today().isoformat(), data=data, phrases_json=phrases_json())


@bp.route("/documentos/<doc_id>")
@require("clinico.ver")
def doc_view(doc_id):
    d = _get_doc(doc_id)
    p = get_db().execute("SELECT * FROM patients WHERE id = ?", (d["patient_id"],)).fetchone()
    audit("documento_consultado", "documento", d["id"])
    return render_template("documentos/ver.html", d=d, p=p, KINDS=KINDS)


@bp.route("/documentos/<doc_id>/pdf")
@require("clinico.ver")
def doc_pdf(doc_id):
    from .pdf import document_pdf
    from .views_extras import load_assets
    d = _get_doc(doc_id)
    p = get_db().execute("SELECT * FROM patients WHERE id = ?", (d["patient_id"],)).fetchone()
    s = clinic_settings()
    size = request.args.get("papel") or s["paper_size"]
    if size not in ("carta", "a4"):
        abort(400)
    data = document_pdf(d, p, s, size, load_assets(g.user["org_id"]))
    audit("documento_pdf_generado", "documento", d["id"], {"papel": size})
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="documento-{d["id"][:8]}.pdf"'
    return resp


@bp.route("/documentos/<doc_id>/anular", methods=["POST"])
@require("clinico.editar", "notas.finalizar")
def doc_void(doc_id):
    d = _get_doc(doc_id)
    reason = (request.form.get("reason") or "").strip()[:300]
    if d["status"] != "emitido":
        abort(409)
    if not reason:
        flash("Indique el motivo de la anulación.", "error")
        return redirect(url_for("docs.doc_view", doc_id=d["id"]))
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE clinical_documents SET status = 'anulado', voided_at = ?, voided_by = ?, void_reason = ? WHERE id = ?",
                   (utcnow(), g.user["id"], reason, d["id"]))
        audit("documento_anulado", "documento", d["id"], {"motivo": reason}, db=db)
    flash("Documento anulado.", "ok")
    return redirect(url_for("docs.doc_view", doc_id=d["id"]))


# ------------------------------------------------------------------------------------------------ carta al médico que refirió
def _who(p, on):
    return _patient_phrase(p, on)


def letter_from_note(db, n, p, s):
    from .views_notes import legacy_plan_text
    f = json.loads(n["fields"])
    seen = date.fromisoformat((n["finalized_at"] or n["created_at"])[:10])
    parts = [f"Estimado(a) Dr(a). {p['referring_physician'] or '______________________'}:",
             f"Agradezco la referencia de {_who(p, seen)}, quien fue evaluado(a) en consulta de gastroenterología el {fmt_birth(seen.isoformat())}."]
    def add(label, key_text):
        t = (key_text or "").strip()
        if t:
            parts.append(f"{label}: {t}")
    add("Motivo de consulta", f.get("motivo"))
    add("Impresión diagnóstica", f.get("impresion"))
    add("Diagnósticos", f.get("diagnosticos"))
    add("Plan", (f.get("plan") or "").strip() or legacy_plan_text(f))
    parts.append("Quedo a sus órdenes para cualquier consulta sobre el paciente.")
    parts.append(f"Atentamente,\n{s['doctor_display_name']}")
    return "\n\n".join(parts)


def letter_from_proc(db, pr, p, s):
    from . import endoscopy_defs as D
    d = json.loads(pr["data"])
    parts = [f"Estimado(a) Dr(a). {p['referring_physician'] or '______________________'}:",
             f"Le informo que a {_who(p, date.fromisoformat(pr['performed_on']))} se le realizó {D.KINDS[pr['kind']].lower()} "
             f"el {fmt_birth(pr['performed_on'])}, con los siguientes resultados."]
    nar = d.get("narrative") or {}
    lines = []
    for key, lab in D.NARRATIVE[pr["kind"]]:
        txt = (nar.get(key) or "").strip()
        if key == "ueg" and d.get("zline"):
            txt = (D.zline_text(d) + " " + txt).strip()
        if txt:
            lines.append(f"{lab}: {txt}" if len(D.NARRATIVE[pr["kind"]]) > 1 else txt)
    if lines:
        parts.append("Hallazgos:\n" + "\n".join(lines))
    if d.get("conclusion"):
        parts.append("Conclusión:\n" + d["conclusion"].strip())
    if d.get("jars"):
        parts.append(f"Se tomaron muestras para estudio histopatológico ({len(d['jars'])} frasco(s)); le comunicaré el resultado.")
    if d.get("recommendations"):
        parts.append("Recomendaciones:\n" + d["recommendations"].strip())
    parts.append("Quedo a sus órdenes para cualquier consulta sobre el paciente.")
    parts.append(f"Atentamente,\n{s['doctor_display_name']}")
    return "\n\n".join(parts)


@bp.route("/carta-referente")
@require("clinico.editar", "notas.finalizar")
def referrer_letter():
    db = get_db()
    s = clinic_settings()
    nid, pid_ = request.args.get("note_id"), request.args.get("proc_id")
    if nid and re.fullmatch(r"[0-9a-f]{32}", nid):
        src = db.execute("SELECT * FROM clinical_notes WHERE id = ? AND org_id = ? AND discarded_at IS NULL", (nid, g.user["org_id"])).fetchone() or abort(404)
        p = get_patient_or_404(src["patient_id"])
        body = letter_from_note(db, src, p, s)
        draft = src["status"] != "finalizada"
    elif pid_ and re.fullmatch(r"[0-9a-f]{32}", pid_):
        src = db.execute("SELECT * FROM procedures WHERE id = ? AND org_id = ? AND discarded_at IS NULL", (pid_, g.user["org_id"])).fetchone() or abort(404)
        p = get_patient_or_404(src["patient_id"])
        body = letter_from_proc(db, src, p, s)
        draft = src["status"] != "finalizado"
    else:
        abort(400)
    note = ("Carta armada con los datos de la " + ("nota" if nid else "endoscopia") + ". Revise y corrija el texto antes de emitirla."
            + (" ATENCIÓN: todavía está en borrador; lo ideal es finalizarla primero." if draft else "")
            + ("" if p["referring_physician"] else " El expediente no tiene médico remitente: escriba su nombre en el saludo."))
    return render_template("documentos/nuevo.html", p=p, kind="libre", KINDS=KINDS, f={"title": "Carta al médico que refirió"},
                           title="CARTA AL MÉDICO QUE REFIRIÓ", body=body, errors=[], step="revisar", today=local_today().isoformat(),
                           data={}, phrases_json=phrases_json(), hide_data=True, letter_note=note,
                           form_action=url_for("docs.doc_new", patient_id=p["id"], kind="libre"))
