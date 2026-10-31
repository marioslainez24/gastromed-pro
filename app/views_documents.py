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
    return render_template("documentos/lista.html", p=p, rows=rows, KINDS=KINDS)


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
