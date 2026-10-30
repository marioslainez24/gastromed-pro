"""Fase 2: formularios GI en la nota, diario de síntomas y calculadoras."""
import json
import re
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from markupsafe import Markup

from . import calculators as C
from . import gi_forms
from .charts import trend_svg
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, can, require
from .util import fmt_birth, local_today
from .views_labs import latest_values
from .views_patients import get_patient_or_404

bp = Blueprint("gi", __name__)


def _get_note(note_id):
    if not re.fullmatch(r"[0-9a-f]{32}", note_id or ""):
        abort(404)
    n = get_db().execute("SELECT * FROM clinical_notes WHERE id = ? AND org_id = ?", (note_id, g.user["org_id"])).fetchone()
    if not n:
        abort(404)
    return n


# ------------------------------------------------------------------------------------------------ formularios GI
@bp.route("/notas/<note_id>/formulario/<form_code>", methods=["GET", "POST"])
@require("clinico.editar")
def form_edit(note_id, form_code):
    n = _get_note(note_id)
    if form_code not in gi_forms.FORMS:
        abort(404)
    if n["status"] != "borrador" or n["author_id"] != g.user["id"]:
        abort(409, description="Solo el autor puede agregar formularios mientras la nota está en borrador.")
    db = get_db()
    existing = db.execute("SELECT * FROM clinical_forms WHERE note_id = ? AND form_code = ?", (n["id"], form_code)).fetchone()
    data = json.loads(existing["data"]) if existing else {}
    errors = []
    if request.method == "POST":
        data, errors = gi_forms.clean(form_code, request.form)
        if not errors:
            with write_tx(db):
                if existing:
                    cur = db.execute("UPDATE clinical_forms SET data = ?, updated_at = ?, version = version + 1 WHERE id = ? AND version = ?",
                                     (json.dumps(data, ensure_ascii=False), utcnow(), existing["id"], int(request.form.get("version", "0"))))
                    if cur.rowcount == 0:
                        abort(409, description="El formulario cambió en otra ventana. Recargue la página.")
                    fid = existing["id"]
                else:
                    fid = new_id()
                    db.execute("INSERT INTO clinical_forms(id, org_id, patient_id, note_id, form_code, form_version, data, author_id, created_at,"
                               " updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (fid, g.user["org_id"], n["patient_id"], n["id"], form_code, gi_forms.VERSION,
                                json.dumps(data, ensure_ascii=False), g.user["id"], utcnow(), utcnow()))
                audit("formulario_gi_guardado", "nota", n["id"], {"formulario": form_code}, db=db)
            flash(f"Formulario «{gi_forms.FORMS[form_code][0]}» guardado en la nota.", "ok")
            return redirect(url_for("notes.view", note_id=n["id"]) + "#formularios")
    p = db.execute("SELECT * FROM patients WHERE id = ?", (n["patient_id"],)).fetchone()
    title, fields = gi_forms.FORMS[form_code]
    return render_template("gi/formulario.html", n=n, p=p, form_code=form_code, title=title, fields=fields, data=data,
                           errors=errors, existing=existing, BRISTOL=gi_forms.BRISTOL), 422 if errors else 200


def note_forms(db, note_id):
    rows = db.execute("SELECT * FROM clinical_forms WHERE note_id = ? ORDER BY created_at", (note_id,)).fetchall()
    return [{"code": r["form_code"], "title": gi_forms.FORMS.get(r["form_code"], (r["form_code"],))[0],
             "summary": gi_forms.render_summary(r["form_code"], json.loads(r["data"])) if r["form_code"] in gi_forms.FORMS else []}
            for r in rows]


# ------------------------------------------------------------------------------------------------ diario de síntomas
@bp.route("/pacientes/<patient_id>/diario", methods=["GET", "POST"])
@require("clinico.ver")
def diary(patient_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    if request.method == "POST":
        if not can("clinico.editar") and not can("resultados.registrar"):
            abort(403)
        try:
            d = date.fromisoformat(request.form.get("entry_date", ""))
            if d > local_today():
                raise ValueError
        except ValueError:
            flash("Fecha no válida.", "error")
            return redirect(url_for("gi.diary", patient_id=p["id"]))

        def opt_int(k, lo, hi):
            v = (request.form.get(k) or "").strip()
            if not v:
                return None
            try:
                x = int(v)
            except ValueError:
                return None
            return x if lo <= x <= hi else None
        with write_tx(db):
            did = new_id()
            db.execute("INSERT INTO symptom_diary(id, org_id, patient_id, entry_date, stools, bristol, blood, urgency, nocturnal, pain, notes,"
                       " recorded_by, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (did, g.user["org_id"], p["id"], d.isoformat(), opt_int("stools", 0, 60), opt_int("bristol", 1, 7),
                        int(request.form.get("blood") == "1"), int(request.form.get("urgency") == "1"), int(request.form.get("nocturnal") == "1"),
                        opt_int("pain", 0, 10), (request.form.get("notes") or "").strip()[:500] or None, g.user["id"], utcnow()))
            audit("diario_registrado", "paciente", p["id"], db=db)
        flash("Registro del diario agregado.", "ok")
        return redirect(url_for("gi.diary", patient_id=p["id"]))
    rows = db.execute("SELECT * FROM symptom_diary WHERE patient_id = ? ORDER BY entry_date, recorded_at", (p["id"],)).fetchall()
    stools = Markup(trend_svg([(fmt_birth(r["entry_date"])[:5], r["stools"], None) for r in rows if r["stools"] is not None][-30:],
                              unit="evacuaciones", title="Evacuaciones por día")) if rows else None
    pain = Markup(trend_svg([(fmt_birth(r["entry_date"])[:5], r["pain"], None) for r in rows if r["pain"] is not None][-30:],
                            unit="/10", title="Dolor (0–10)")) if rows else None
    audit("diario_consultado", "paciente", p["id"])
    return render_template("gi/diario.html", p=p, rows=list(reversed(rows)), stools=stools, pain=pain, BRISTOL=gi_forms.BRISTOL,
                           today=local_today().isoformat())


# ------------------------------------------------------------------------------------------------ calculadoras
def approvals():
    return {(r["calc_code"], r["calc_version"]): r for r in get_db().execute(
        "SELECT a.*, u.full_name FROM calculator_approvals a JOIN users u ON u.id = a.approved_by WHERE a.org_id = ?", (g.user["org_id"],))}


@bp.route("/calculadoras")
@require("clinico.ver")
def calc_index():
    ap = approvals()
    groups = {}
    for c in C.ALL:
        groups.setdefault(c.group, []).append((c, ap.get((c.code, c.version))))
    return render_template("gi/calculadoras.html", groups=groups, pid=request.args.get("patient_id"),
                           note_id=request.args.get("note_id"), licencias=gi_forms.LICENSE_PENDING)


@bp.route("/calculadoras/<code>/revision", methods=["GET", "POST"])
@require("clinico.ver")
def calc_review(code):
    calc = C.BY_CODE.get(code) or abort(404)
    ap = approvals().get((calc.code, calc.version))
    checks = C.self_check(calc)
    if request.method == "POST":
        if not can("calculadoras.aprobar"):
            abort(403)
        if not all(ok for *_, ok in checks):
            abort(409, description="Hay casos de referencia que no coinciden: no se puede aprobar.")
        if request.form.get("confirm") != "1":
            flash("Marque la confirmación de revisión.", "error")
            return redirect(url_for("gi.calc_review", code=code))
        db = get_db()
        with write_tx(db):
            db.execute("INSERT OR IGNORE INTO calculator_approvals(org_id, calc_code, calc_version, approved_by, approved_at, comment)"
                       " VALUES (?,?,?,?,?,?)", (g.user["org_id"], calc.code, calc.version, g.user["id"], utcnow(),
                                                 (request.form.get("comment") or "").strip()[:500] or None))
            audit("calculadora_aprobada", "calculadora", calc.code, {"version": calc.version}, db=db)
        flash(f"«{calc.name}» aprobada para uso clínico en esta clínica.", "ok")
        return redirect(url_for("gi.calc_index"))
    return render_template("gi/revision.html", calc=calc, ap=ap, checks=checks)


@bp.route("/calculadoras/<code>", methods=["GET", "POST"])
@require("clinico.ver")
def calc_use(code):
    calc = C.BY_CODE.get(code) or abort(404)
    ap = approvals().get((calc.code, calc.version))
    db = get_db()
    src = request.form if request.method == "POST" else request.args
    p = get_patient_or_404(src["patient_id"]) if src.get("patient_id") else None
    note_id = src.get("note_id") or None
    imported = {}
    if p:
        lab_codes = [f.lab for f in calc.fields if f.lab]
        imported = latest_values(db, p["id"], lab_codes)
    values = dict(request.form) if request.method == "POST" else {}
    if request.method == "GET" and p:
        # Precarga desde el expediente SOLO si la unidad coincide; se muestra la fecha y debe confirmarse.
        for f in calc.fields:
            if f.lab and f.lab in imported:
                r = imported[f.lab]
                if (r["unit"] or "") == (f.unit or "") or f.unit.startswith(r["unit"] or "~"):
                    values[f.key] = f"{r['value_num']:g}"
            if f.key == "edad" and p["birth_date"]:
                from .util import age as age_txt
                a = age_txt(p["birth_date"])
                if a.endswith("años"):
                    values["edad"] = a.split()[0]
            if f.key == "sexo" and p["sex"] in ("femenino", "masculino"):
                values["sexo"] = p["sex"]
    result, error = None, None
    if request.method == "POST":
        try:
            result = C.run(calc, request.form)
        except C.MissingData as e:
            error = str(e)
        if result and request.form.get("save") == "1":
            if not ap:
                abort(403, description="Esta calculadora aún no ha sido aprobada para uso clínico.")
            if not p or not can("clinico.editar"):
                abort(403)
            if request.form.get("confirm_inputs") != "1":
                error = "Confirme que revisó los datos (y sus fechas) antes de guardar el resultado."
            else:
                inputs = {}
                for f in calc.fields:
                    origin = "manual"
                    if f.lab and f.lab in imported and request.form.get(f.key, "") == f"{imported[f.lab]['value_num']:g}":
                        origin = f"expediente ({imported[f.lab]['taken_on']})"
                    inputs[f.key] = {"valor": request.form.get(f.key, ""), "unidad": f.unit, "origen": origin}
                with write_tx(db):
                    cid = new_id()
                    db.execute("INSERT INTO calc_results(id, org_id, patient_id, note_id, calc_code, calc_version, inputs, result, author_id,"
                               " created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (cid, g.user["org_id"], p["id"], note_id if note_id and re.fullmatch(r"[0-9a-f]{32}", note_id) else None,
                                calc.code, calc.version, json.dumps(inputs, ensure_ascii=False),
                                json.dumps(result, ensure_ascii=False, default=str), g.user["id"], utcnow()))
                    audit("calculo_guardado", "paciente", p["id"], {"calculadora": calc.code, "version": calc.version}, db=db)
                flash(f"Resultado guardado en el expediente: {result['texto']}", "ok")
                return redirect(url_for("gi.patient_calcs", patient_id=p["id"]))
    return render_template("gi/calcular.html", calc=calc, ap=ap, p=p, note_id=note_id, values=values, imported=imported,
                           result=result, error=error)


@bp.route("/pacientes/<patient_id>/calculos")
@require("clinico.ver")
def patient_calcs(patient_id):
    p = get_patient_or_404(patient_id)
    rows = get_db().execute("SELECT c.*, u.full_name FROM calc_results c JOIN users u ON u.id = c.author_id WHERE c.patient_id = ?"
                            " ORDER BY c.created_at DESC", (p["id"],)).fetchall()
    items = [{"r": r, "calc": C.BY_CODE.get(r["calc_code"]), "res": json.loads(r["result"]), "inp": json.loads(r["inputs"])} for r in rows]
    audit("calculos_consultados", "paciente", p["id"])
    return render_template("gi/calculos_paciente.html", p=p, items=items)
