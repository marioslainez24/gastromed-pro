"""Código ACV (NeuroMed Pro 1.0): pantalla de atención del ACV agudo por paciente.

El médico registra los tiempos y los datos de la evaluación inicial; el programa muestra la ventana terapéutica, las
contraindicaciones marcadas, la dosis del trombolítico por peso y si corresponde avisar a neurointervención (app/acv.py).
Mientras se atiende es un borrador; al finalizar se guarda un resumen y el registro queda inmutable.
"""
import json
import re
from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import acv as A
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require
from .util import clinic_tz, local_today
from .views_patients import get_patient_or_404

bp = Blueprint("acv", __name__)


def now_hm() -> str:
    return datetime.now(clinic_tz()).strftime("%H:%M")


def _get(code_id):
    if not re.fullmatch(r"[0-9a-f]{32}", code_id or ""):
        abort(404)
    r = get_db().execute("SELECT c.*, u.full_name AS author FROM stroke_codes c JOIN users u ON u.id = c.created_by"
                         " WHERE c.id = ? AND c.org_id = ?", (code_id, g.user["org_id"])).fetchone()
    if not r:
        abort(404)
    return r


def _anticoagulated(db, pid) -> bool:
    meds = " ".join(m["name"].lower() for m in db.execute(
        "SELECT name FROM patient_medications WHERE patient_id = ? AND status = 'activo'", (pid,)))
    return bool(re.search(r"apixab|rivaroxab|dabigatr|edoxab|warfarin|acenocumar|enoxapar", meds))


def codes_for(db, pid):
    return db.execute("SELECT c.*, u.full_name AS author FROM stroke_codes c JOIN users u ON u.id = c.created_by"
                      " WHERE c.patient_id = ? ORDER BY c.created_at DESC", (pid,)).fetchall()


@bp.route("/codigo-acv")
@require("clinico.ver")
def index():
    rows = get_db().execute(
        "SELECT c.*, p.first_names, p.last_names, p.mrn FROM stroke_codes c JOIN patients p ON p.id = c.patient_id"
        " WHERE c.org_id = ? ORDER BY c.created_at DESC LIMIT 50", (g.user["org_id"],)).fetchall()
    return render_template("acv/index.html", rows=rows)


@bp.route("/pacientes/<patient_id>/codigo-acv")
@require("clinico.ver")
def patient_codes(patient_id):
    p = get_patient_or_404(patient_id)
    return render_template("acv/paciente.html", p=p, rows=codes_for(get_db(), p["id"]))


@bp.route("/pacientes/<patient_id>/codigo-acv/nuevo", methods=["POST"])
@require("clinico.editar")
def new(patient_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    d = A.empty()
    d["arr"] = now_hm()
    cid = new_id()
    with write_tx(db):
        db.execute("INSERT INTO stroke_codes(id, org_id, patient_id, on_date, data, created_by, created_at, updated_at)"
                   " VALUES (?,?,?,?,?,?,?,?)", (cid, g.user["org_id"], p["id"], local_today().isoformat(),
                                                  json.dumps(d, ensure_ascii=False), g.user["id"], utcnow(), utcnow()))
        audit("codigo_acv_iniciado", "codigo_acv", cid, {"paciente": p["id"]}, db=db)
    flash("Código ACV iniciado. La hora de llegada es la de ahora; corríjala si hace falta.", "ok")
    return redirect(url_for("acv.edit", code_id=cid))


@bp.route("/codigo-acv/<code_id>", methods=["GET", "POST"])
@require("clinico.ver")
def edit(code_id):
    c = _get(code_id)
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (c["patient_id"],)).fetchone()
    d = {**A.empty(), **json.loads(c["data"])}
    errors = []
    if request.method == "POST":
        from .security import can
        action = request.form.get("action") or "guardar"
        if c["status"] != "borrador" or not can("clinico.editar"):
            abort(403)
        if action == "finalizar" and not can("notas.finalizar"):
            abort(403)
        try:
            if int(request.form.get("version") or 0) != c["version"]:
                flash("Otra persona guardó este código mientras usted lo editaba. Revise los datos y vuelva a guardar.", "warn")
                return redirect(url_for("acv.edit", code_id=c["id"]))
        except ValueError:
            abort(400)
        d, errors = A.clean(request.form)
        if action == "ahora":
            k = next((k for k, _ in A.TIME_KEYS if not d[k]), None)
            if k:
                d[k] = now_hm()
            else:
                flash("Todos los tiempos ya están registrados.", "info")
        if not errors:
            ev = A.evaluate(d, now_hm())
            with write_tx(db):
                if action == "finalizar":
                    text = A.summary(d, ev, A.dose(d))
                    db.execute("UPDATE stroke_codes SET data = ?, summary = ?, status = 'finalizado', version = version + 1, updated_at = ?,"
                               " finalized_by = ?, finalized_at = ? WHERE id = ? AND status = 'borrador'",
                               (json.dumps(d, ensure_ascii=False), text, utcnow(), g.user["id"], utcnow(), c["id"]))
                    audit("codigo_acv_finalizado", "codigo_acv", c["id"], {"paciente": p["id"]}, db=db)
                else:
                    db.execute("UPDATE stroke_codes SET data = ?, version = version + 1, updated_at = ? WHERE id = ? AND status = 'borrador'",
                               (json.dumps(d, ensure_ascii=False), utcnow(), c["id"]))
                    audit("codigo_acv_guardado", "codigo_acv", c["id"], {"paciente": p["id"]}, db=db)
            flash("Código ACV finalizado y guardado en el expediente." if action == "finalizar" else "Guardado.", "ok")
            return redirect(url_for("acv.edit", code_id=c["id"]) + ("" if action == "finalizar" else "#resultado"))
    ev = A.evaluate(d, now_hm())
    ds = A.dose(d)
    return render_template("acv/codigo.html", c=c, p=p, d=d, ev=ev, ds=ds, errors=errors, A=A, hm=A.hm,
                           preview=A.summary(d, ev, ds), anticoag=_anticoagulated(db, p["id"])), (422 if errors else 200)
