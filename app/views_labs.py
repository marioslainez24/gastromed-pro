"""Fase 2: órdenes, resultados de laboratorio estructurados, tendencias, pendientes y tareas."""
import re
from datetime import date, timedelta

from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for
from markupsafe import Markup

from .charts import trend_svg
from . import lab_order_catalog as LC
from . import study_catalog as SC
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, can, require
from .util import clinic_settings, fmt_birth, local_today
from .views_patients import get_patient_or_404

bp = Blueprint("labs", __name__)

ORDER_TYPES = {"laboratorio": "Laboratorio", "imagen": "Imagenología", "endoscopia": "Endoscopia"}
PRIORITIES = {"rutina": "Rutina", "preferente": "Preferente", "urgente": "Urgente"}
ORDER_STATUS = {"solicitada": "Solicitada", "resultado_parcial": "Resultado parcial", "resultado_recibido": "Resultado recibido",
                "cerrada": "Cerrada", "anulada": "Anulada"}
QUAL = ["Negativo", "Positivo", "No reactivo", "Reactivo", "Indeterminado"]


def _id_ok(x):
    return bool(re.fullmatch(r"[0-9a-f]{32}", x or ""))


def catalog():
    return get_db().execute("SELECT * FROM lab_tests ORDER BY position").fetchall()


def clinicians():
    return get_db().execute("SELECT u.id, u.full_name FROM users u JOIN role_permissions rp ON rp.role_id = u.role_id"
                            " WHERE u.org_id = ? AND u.active = 1 AND rp.permission = 'resultados.revisar' ORDER BY u.full_name",
                            (g.user["org_id"],)).fetchall()


def _flag(v, lo, hi):
    if v is None:
        return None
    if lo is None and hi is None:
        return "sin_rango"
    if lo is not None and v < lo:
        return "bajo"
    if hi is not None and v > hi:
        return "alto"
    return "normal"


def _get_order(order_id):
    if not _id_ok(order_id):
        abort(404)
    o = get_db().execute("SELECT o.*, u.full_name AS author, r.full_name AS responsible FROM orders o JOIN users u ON u.id = o.author_id"
                         " JOIN users r ON r.id = o.responsible_id WHERE o.id = ? AND o.org_id = ?", (order_id, g.user["org_id"])).fetchone()
    if not o:
        abort(404)
    return o


def refresh_order_status(db, order_id):
    o = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not o or o["order_type"] != "laboratorio" or o["status"] in ("cerrada", "anulada"):
        return
    items = db.execute("SELECT test_code FROM order_items WHERE order_id = ? AND test_code IS NOT NULL", (order_id,)).fetchall()
    got = {r["test_code"] for r in db.execute("SELECT DISTINCT test_code FROM lab_results WHERE order_id = ? AND status <> 'anulado'",
                                              (order_id,))}
    need = {i["test_code"] for i in items}
    st = "resultado_recibido" if need and need <= got else ("resultado_parcial" if got else "solicitada")
    db.execute("UPDATE orders SET status = ?, version = version + 1 WHERE id = ? AND status <> ?", (st, order_id, st))


# ------------------------------------------------------------------------------------------------ órdenes
@bp.route("/ordenes/nueva", methods=["GET", "POST"])
@require("clinico.ver", "ordenes.emitir")
def order_new():
    src = request.form if request.method == "POST" else request.args
    p = get_patient_or_404(src.get("patient_id", ""))
    db = get_db()
    note_id = src.get("note_id") or None
    if note_id and not db.execute("SELECT 1 FROM clinical_notes WHERE id = ? AND patient_id = ?", (note_id, p["id"])).fetchone():
        abort(404)
    otype = src.get("order_type") or "laboratorio"     # laboratorio | imagen | endoscopia | colonoscopia (pantalla)
    if otype != "laboratorio" and otype not in SC.KINDS:
        abort(400)
    db_type, study_label = ("laboratorio", None) if otype == "laboratorio" else SC.KINDS[otype][:2]
    errors = []
    if request.method == "POST":
        tests = request.form.getlist("tests") if otype == "laboratorio" else []
        free = [l.strip() for l in (request.form.get("items_text") or "").splitlines() if l.strip()][:30]
        valid = {t["code"]: t["name"] for t in catalog()}
        tests = [t for t in tests if t in valid]
        sel_profiles = [k for k in dict.fromkeys(request.form.getlist("perfil")) if k in LC.PROFILE_KEYS] if otype == "laboratorio" else []
        chosen = set(request.form.getlist("lab")) if otype == "laboratorio" else set()
        covered = {k for pk in sel_profiles for k, _ in LC.profile_components(LC.PROFILE_KEYS[pk][1]) if k}
        lab_keys = [k for k in LC.TESTS if k in chosen and k not in covered]
        studies = []
        if otype != "laboratorio":
            known = SC.lookup(otype)
            studies = [x for x in dict.fromkeys(request.form.getlist("study")) if x in known]
        if not tests and not free and not sel_profiles and not lab_keys and not studies:
            errors.append("Seleccione al menos un estudio.")
        resp = request.form.get("responsible_id")
        if resp not in {c["id"] for c in clinicians()}:
            errors.append("Elija quién revisará el resultado.")
        prio = request.form.get("priority") or "rutina"
        if prio not in PRIORITIES:
            abort(400)
        expected = request.form.get("expected_by") or None
        if expected:
            try:
                date.fromisoformat(expected)
            except ValueError:
                errors.append("Fecha esperada no válida.")
        if not errors:
            oid = new_id()
            with write_tx(db):
                db.execute("INSERT INTO orders(id, org_id, patient_id, note_id, order_type, indication, priority, responsible_id, expected_by,"
                           " author_id, created_at, study_label) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (oid, g.user["org_id"], p["id"], note_id, db_type, (request.form.get("indication") or "").strip()[:1000] or None,
                            prio, resp, expected, g.user["id"], utcnow(), study_label))
                pos = 0
                for st in studies:
                    pos += 1
                    db.execute("INSERT INTO order_items(id, order_id, position, description, grp) VALUES (?,?,?,?,?)",
                               (new_id(), oid, pos, st, known[st]))
                for pk in sel_profiles:
                    pos += 1
                    name, comps = LC.PROFILE_KEYS[pk]
                    db.execute("INSERT INTO order_items(id, order_id, position, description, grp) VALUES (?,?,?,?,?)",
                               (new_id(), oid, pos, f"Perfil {name}: " + ", ".join(comps), "Perfiles"))
                for k in lab_keys:
                    pos += 1
                    sec, name = LC.TESTS[k]
                    code = LC.RESULT_CODE.get(name)
                    db.execute("INSERT INTO order_items(id, order_id, position, test_code, description, grp) VALUES (?,?,?,?,?,?)",
                               (new_id(), oid, pos, code if code in valid else None, name, sec))
                for t in tests:
                    pos += 1
                    db.execute("INSERT INTO order_items(id, order_id, position, test_code, description) VALUES (?,?,?,?,?)",
                               (new_id(), oid, pos, t, valid[t]))
                for line in free:
                    pos += 1
                    db.execute("INSERT INTO order_items(id, order_id, position, description, grp) VALUES (?,?,?,?,?)",
                               (new_id(), oid, pos, line[:300], "Otras pruebas" if otype == "laboratorio" else ("Otros" if studies else None)))
                audit("orden_emitida", "orden", oid, {"paciente": p["id"], "tipo": otype, "items": pos}, db=db)
            flash("Orden emitida. Puede imprimirla en PDF.", "ok")
            return redirect(url_for("labs.order_view", order_id=oid))
    default_expected = (local_today() + timedelta(days=7)).isoformat()
    return render_template("labs/orden_nueva.html", p=p, otype=otype, note_id=note_id, catalog=catalog(), clinicians=clinicians(),
                           errors=errors, LC=LC, SC=SC, ORDER_TYPES=ORDER_TYPES, page_title=study_label or ORDER_TYPES[db_type], PRIORITIES=PRIORITIES, default_expected=default_expected,
                           form=request.form), 422 if errors else 200


@bp.route("/ordenes/<order_id>")
@require("clinico.ver")
def order_view(order_id):
    o = _get_order(order_id)
    db = get_db()
    items = db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY position", (o["id"],)).fetchall()
    results = db.execute("SELECT r.*, t.name FROM lab_results r JOIN lab_tests t ON t.code = r.test_code WHERE r.order_id = ?"
                         " ORDER BY t.position", (o["id"],)).fetchall()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (o["patient_id"],)).fetchone()
    audit("orden_consultada", "orden", o["id"])
    return render_template("labs/orden.html", o=o, items=items, results=results, p=p, ORDER_TYPES=ORDER_TYPES,
                           PRIORITIES=PRIORITIES, ORDER_STATUS=ORDER_STATUS)


@bp.route("/ordenes/<order_id>/estado", methods=["POST"])
@require("clinico.ver", "ordenes.emitir")
def order_status(order_id):
    o = _get_order(order_id)
    action = request.form.get("action")
    db = get_db()
    with write_tx(db):
        if action == "cerrar" and o["status"] not in ("cerrada", "anulada"):
            db.execute("UPDATE orders SET status = 'cerrada', closed_at = ?, version = version + 1 WHERE id = ?", (utcnow(), o["id"]))
        elif action == "anular" and o["status"] not in ("cerrada", "anulada"):
            reason = (request.form.get("reason") or "").strip()[:300]
            if not reason:
                abort(400, description="Indique el motivo de la anulación.")
            db.execute("UPDATE orders SET status = 'anulada', void_reason = ?, closed_at = ?, version = version + 1 WHERE id = ?",
                       (reason, utcnow(), o["id"]))
        else:
            abort(409, description="La orden ya estaba cerrada o anulada.")
        audit(f"orden_{action}", "orden", o["id"], db=db)
    flash("Orden actualizada.", "ok")
    return redirect(url_for("labs.order_view", order_id=o["id"]))


@bp.route("/ordenes/<order_id>/pdf")
@require("clinico.ver")
def order_pdf(order_id):
    from .pdf import order_pdf as make
    o = _get_order(order_id)
    db = get_db()
    items = db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY position", (o["id"],)).fetchall()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (o["patient_id"],)).fetchone()
    s = clinic_settings()
    size = request.args.get("papel") or s["paper_size"]
    if size not in ("carta", "a4"):
        abort(400)
    from .views_extras import load_assets
    data = make(o, items, p, s, size, o["study_label"] or ORDER_TYPES[o["order_type"]], PRIORITIES[o["priority"]], load_assets(g.user["org_id"]))
    audit("orden_pdf", "orden", o["id"])
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="orden-{o["id"][:8]}.pdf"'
    return resp


# ------------------------------------------------------------------------------------------------ resultados
@bp.route("/pacientes/<patient_id>/laboratorio")
@require("clinico.ver")
def patient_labs(patient_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    rows = db.execute("SELECT r.*, t.name, t.grp, t.position, t.kind FROM lab_results r JOIN lab_tests t ON t.code = r.test_code"
                      " WHERE r.patient_id = ? AND r.status <> 'anulado' ORDER BY t.position, r.taken_on", (p["id"],)).fetchall()
    dates = sorted({r["taken_on"] for r in rows}, reverse=True)[:8]
    table = {}
    for r in rows:
        table.setdefault(r["test_code"], {"name": r["name"], "grp": r["grp"], "unit": r["unit"], "cells": {}, "series": []})
        table[r["test_code"]]["cells"][r["taken_on"]] = r
        if r["value_num"] is not None:
            table[r["test_code"]]["series"].append(r)
    focus = request.args.get("prueba")
    chart, focus_name = None, None
    if focus in table and table[focus]["series"]:
        s = table[focus]["series"]
        last = s[-1]
        chart = Markup(trend_svg([(fmt_birth(r["taken_on"]), r["value_num"], r["flag"]) for r in s], last["ref_low"], last["ref_high"],
                                 last["unit"] or "", title=table[focus]["name"]))
        focus_name = table[focus]["name"]
    orders = db.execute("SELECT o.*, (SELECT GROUP_CONCAT(description, ', ') FROM order_items i WHERE i.order_id = o.id) AS items"
                        " FROM orders o WHERE o.patient_id = ? ORDER BY o.created_at DESC LIMIT 30", (p["id"],)).fetchall()
    audit("laboratorio_consultado", "paciente", p["id"])
    return render_template("labs/paciente.html", p=p, table=table, dates=dates, chart=chart, focus=focus, focus_name=focus_name,
                           orders=orders, ORDER_TYPES=ORDER_TYPES, ORDER_STATUS=ORDER_STATUS)


@bp.route("/pacientes/<patient_id>/laboratorio/registrar", methods=["GET", "POST"])
@require("clinico.ver", "resultados.registrar")
def results_new(patient_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    order_id = (request.form.get("order_id") if request.method == "POST" else request.args.get("order_id")) or None
    order = None
    if order_id:
        order = db.execute("SELECT * FROM orders WHERE id = ? AND patient_id = ? AND org_id = ?", (order_id, p["id"], g.user["org_id"])).fetchone()
        if not order:
            abort(404)
    tests = catalog()
    selected = [i["test_code"] for i in db.execute("SELECT test_code FROM order_items WHERE order_id = ? AND test_code IS NOT NULL"
                                                     " ORDER BY position", (order_id,))] if order else []
    # Rangos sugeridos: los últimos usados para cada prueba en esta clínica (vienen de informes reales, no inventados)
    last_ranges = {r["test_code"]: r for r in db.execute(
        "SELECT * FROM (SELECT test_code, ref_low, ref_high, unit, ROW_NUMBER() OVER (PARTITION BY test_code ORDER BY entered_at DESC) rn"
        " FROM lab_results WHERE org_id = ? AND status <> 'anulado') WHERE rn = 1", (g.user["org_id"],))}
    files = db.execute("SELECT id, title, study_date FROM files WHERE patient_id = ? AND archived_at IS NULL AND category = 'laboratorio'"
                       " ORDER BY uploaded_at DESC LIMIT 20", (p["id"],)).fetchall()
    errors = []
    if request.method == "POST":
        taken = request.form.get("taken_on") or ""
        try:
            if date.fromisoformat(taken) > local_today():
                errors.append("La fecha de toma no puede ser futura.")
        except ValueError:
            errors.append("Indique la fecha de toma de la muestra.")
        file_id = request.form.get("file_id") or None
        if file_id and file_id not in {f["id"] for f in files}:
            abort(400)
        valid = {t["code"]: t for t in tests}
        rows = []
        for code in request.form.getlist("code"):
            if code not in valid:
                continue
            t = valid[code]
            raw = (request.form.get(f"v_{code}") or "").strip()
            if not raw:
                continue
            vnum = vtext = None
            if t["kind"] == "numerico":
                try:
                    vnum = float(raw.replace(",", "."))
                except ValueError:
                    errors.append(f"{t['name']}: «{raw}» no es un número.")
                    continue
            else:
                vtext = raw[:100]

            def rng(k):
                x = (request.form.get(f"{k}_{code}") or "").strip().replace(",", ".")
                if not x:
                    return None
                try:
                    return float(x)
                except ValueError:
                    errors.append(f"{t['name']}: rango no válido.")
                    return None
            lo, hi = rng("lo"), rng("hi")
            if lo is not None and hi is not None and lo > hi:
                errors.append(f"{t['name']}: el límite inferior es mayor que el superior.")
            unit = (request.form.get(f"u_{code}") or t["unit"] or "").strip()[:30] or None
            rows.append((code, vnum, vtext, unit, lo, hi))
        # Otros resultados que no están en la lista: se guardan y la prueba queda en el catálogo para la próxima vez
        new_tests = {}
        idx = sorted({int(m.group(1)) for k in request.form.keys() if (m := re.fullmatch(r"otro-(\d{1,2})-name", k))})
        for i in idx[:30]:
            name = re.sub(r"\s+", " ", (request.form.get(f"otro-{i}-name") or "").strip())[:120]
            raw = (request.form.get(f"otro-{i}-value") or "").strip()
            if not name and not raw:
                continue
            if not name or not raw:
                errors.append(f"Otro resultado {i + 1}: escriba el nombre de la prueba y el resultado.")
                continue
            try:
                vnum, vtext = float(raw.replace(",", ".")), None
            except ValueError:
                vnum, vtext = None, raw[:100]

            def orng(k):
                x = (request.form.get(f"otro-{i}-{k}") or "").strip().replace(",", ".")
                if not x:
                    return None
                try:
                    return float(x)
                except ValueError:
                    errors.append(f"{name}: rango no válido.")
                    return None
            lo, hi = orng("lo"), orng("hi")
            if lo is not None and hi is not None and lo > hi:
                errors.append(f"{name}: el límite inferior es mayor que el superior.")
            unit = (request.form.get(f"otro-{i}-unit") or "").strip()[:30] or None
            key = name.casefold()
            code = next((t["code"] for t in tests if t["name"].casefold() == key), None) or new_tests.get(key, (None,))[0]
            if not code:
                base = "x_" + (re.sub(r"[^a-z0-9]+", "_", key.encode("ascii", "ignore").decode()).strip("_")[:40] or "prueba")
                code, n = base, 2
                while db.execute("SELECT 1 FROM lab_tests WHERE code = ?", (code,)).fetchone() or code in {v[0] for v in new_tests.values()}:
                    code, n = f"{base}_{n}", n + 1
                new_tests[key] = (code, name, unit, "numerico" if vnum is not None else "cualitativo")
            rows.append((code, vnum, vtext, unit, lo, hi))
        if not rows and not errors:
            errors.append("Escriba al menos un resultado.")
        if not errors:
            lab = (request.form.get("laboratory") or "").strip()[:160] or None
            with write_tx(db):
                for code, name, unit, kind in new_tests.values():
                    db.execute("INSERT INTO lab_tests(code, name, unit, kind, grp, position) VALUES (?,?,?,?,?,?)",
                               (code, name, unit, kind, "Otros (agregados por usted)", 900))
                    audit("prueba_laboratorio_agregada", "laboratorio", code, {"nombre": name}, db=db)
                for code, vnum, vtext, unit, lo, hi in rows:
                    rid = new_id()
                    db.execute("INSERT INTO lab_results(id, org_id, patient_id, order_id, file_id, test_code, value_num, value_text, unit,"
                               " ref_low, ref_high, flag, taken_on, laboratory, entered_by, entered_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (rid, g.user["org_id"], p["id"], order_id, file_id, code, vnum, vtext, unit, lo, hi,
                                _flag(vnum, lo, hi) if vnum is not None else None, taken, lab, g.user["id"], utcnow()))
                if order_id:
                    refresh_order_status(db, order_id)
                audit("resultados_registrados", "paciente", p["id"], {"n": len(rows), "orden": order_id}, db=db)
            flash(f"{len(rows)} resultado(s) registrados. Quedan pendientes de revisión médica.", "ok")
            return redirect(url_for("labs.patient_labs", patient_id=p["id"]))
    selected_groups = {t["grp"] for t in tests if t["code"] in selected}
    return render_template("labs/registrar.html", p=p, tests=tests, selected=selected, selected_groups=selected_groups,
                           order=order, last_ranges=last_ranges,
                           files=files, errors=errors, form=request.form, QUAL=QUAL, today=local_today().isoformat()), 422 if errors else 200


def _get_result(rid):
    if not _id_ok(rid):
        abort(404)
    r = get_db().execute("SELECT r.*, t.name FROM lab_results r JOIN lab_tests t ON t.code = r.test_code WHERE r.id = ? AND r.org_id = ?",
                         (rid, g.user["org_id"])).fetchone()
    if not r:
        abort(404)
    return r


@bp.route("/resultados/revisar", methods=["POST"])
@require("clinico.ver", "resultados.revisar")
def results_review():
    ids = [i for i in request.form.getlist("result_id") if _id_ok(i)]
    comment = (request.form.get("review_comment") or "").strip()[:500] or None
    communicated = request.form.get("communicated") == "1"
    channel = (request.form.get("communication") or "").strip()[:200] or None
    if not ids:
        flash("Seleccione al menos un resultado.", "error")
        return redirect(request.referrer or url_for("labs.pending"))
    if communicated and not channel:
        flash("Indique cómo se comunicó al paciente (p. ej., «en consulta», «llamada telefónica»).", "error")
        return redirect(request.referrer or url_for("labs.pending"))
    db = get_db()
    with write_tx(db):
        n = 0
        for rid in ids:
            n += db.execute("UPDATE lab_results SET status = 'revisado', reviewed_by = ?, reviewed_at = ?, review_comment = ?,"
                            " communicated_at = CASE WHEN ? THEN ? ELSE communicated_at END,"
                            " communicated_by = CASE WHEN ? THEN ? ELSE communicated_by END,"
                            " communication = CASE WHEN ? THEN ? ELSE communication END"
                            " WHERE id = ? AND org_id = ? AND status = 'pendiente_revision'",
                            (g.user["id"], utcnow(), comment, communicated, utcnow(), communicated, g.user["id"], communicated, channel,
                             rid, g.user["org_id"])).rowcount
        audit("resultados_revisados", "resultado", None, {"n": n, "comunicado": communicated}, db=db)
    flash(f"{n} resultado(s) marcados como revisados.", "ok")
    nxt = request.form.get("next") or ""
    return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("labs.pending"))


@bp.route("/resultados/<rid>/anular", methods=["POST"])
@require("clinico.ver", "resultados.registrar")
def result_void(rid):
    r = _get_result(rid)
    reason = (request.form.get("reason") or "").strip()[:300]
    if not reason:
        abort(400, description="Indique el motivo de la anulación.")
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE lab_results SET status = 'anulado', void_reason = ? WHERE id = ?", (reason, r["id"]))
        if r["order_id"]:
            refresh_order_status(db, r["order_id"])
        audit("resultado_anulado", "resultado", r["id"], {"motivo": reason}, db=db)
    flash("Resultado anulado (se conserva en el historial). Puede registrarlo de nuevo con el valor correcto.", "ok")
    return redirect(url_for("labs.patient_labs", patient_id=r["patient_id"]))


# ------------------------------------------------------------------------------------------------ pendientes y tareas
@bp.route("/pendientes")
@require("clinico.ver")
def pending():
    db = get_db()
    org = g.user["org_id"]
    mine = request.args.get("todos") != "1"
    results = db.execute(
        "SELECT r.*, t.name, p.first_names, p.last_names, p.mrn, o.responsible_id FROM lab_results r JOIN lab_tests t ON t.code = r.test_code"
        " JOIN patients p ON p.id = r.patient_id LEFT JOIN orders o ON o.id = r.order_id"
        " WHERE r.org_id = ? AND r.status = 'pendiente_revision'" + (" AND (o.responsible_id = ? OR o.responsible_id IS NULL)" if mine else "") +
        " ORDER BY CASE r.flag WHEN 'alto' THEN 0 WHEN 'bajo' THEN 0 ELSE 1 END, r.taken_on DESC LIMIT 200",
        (org, g.user["id"]) if mine else (org,)).fetchall()
    today = local_today().isoformat()
    overdue = db.execute(
        "SELECT o.*, p.first_names, p.last_names, p.mrn, u.full_name AS responsible,"
        " (SELECT GROUP_CONCAT(description, ', ') FROM order_items i WHERE i.order_id = o.id) AS items"
        " FROM orders o JOIN patients p ON p.id = o.patient_id JOIN users u ON u.id = o.responsible_id"
        " WHERE o.org_id = ? AND o.status IN ('solicitada','resultado_parcial')" + (" AND o.responsible_id = ?" if mine else "") +
        " ORDER BY COALESCE(o.expected_by, '9999') LIMIT 200", (org, g.user["id"]) if mine else (org,)).fetchall()
    tasks = db.execute(
        "SELECT t.*, p.first_names, p.last_names, u.full_name AS assignee FROM tasks t LEFT JOIN patients p ON p.id = t.patient_id"
        " JOIN users u ON u.id = t.assigned_to WHERE t.org_id = ? AND t.status = 'abierta'" + (" AND t.assigned_to = ?" if mine else "") +
        " ORDER BY COALESCE(t.due_on, '9999') LIMIT 200", (org, g.user["id"]) if mine else (org,)).fetchall()
    users = db.execute("SELECT id, full_name FROM users WHERE org_id = ? AND active = 1 ORDER BY full_name", (org,)).fetchall()
    return render_template("labs/pendientes.html", results=results, overdue=overdue, tasks=tasks, today=today, mine=mine, users=users)


@bp.route("/tareas/nueva", methods=["POST"])
@require("tareas.gestionar")
def task_new():
    db = get_db()
    title = (request.form.get("title") or "").strip()[:200]
    assigned = request.form.get("assigned_to")
    if not title or not db.execute("SELECT 1 FROM users WHERE id = ? AND org_id = ? AND active = 1", (assigned, g.user["org_id"])).fetchone():
        flash("Escriba la tarea y elija a quién se asigna.", "error")
        return redirect(request.referrer or url_for("labs.pending"))
    pid = request.form.get("patient_id") or None
    if pid:
        get_patient_or_404(pid)
    due = request.form.get("due_on") or None
    if due:
        try:
            date.fromisoformat(due)
        except ValueError:
            due = None
    with write_tx(db):
        tid = new_id()
        db.execute("INSERT INTO tasks(id, org_id, patient_id, title, detail, due_on, assigned_to, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (tid, g.user["org_id"], pid, title, (request.form.get("detail") or "").strip()[:1000] or None, due, assigned,
                    g.user["id"], utcnow()))
        audit("tarea_creada", "tarea", tid, db=db)
    flash("Tarea creada.", "ok")
    nxt = request.form.get("next") or ""
    return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("labs.pending"))


@bp.route("/tareas/<task_id>/completar", methods=["POST"])
@require("tareas.gestionar")
def task_done(task_id):
    if not _id_ok(task_id):
        abort(404)
    db = get_db()
    st = "cancelada" if request.form.get("cancel") == "1" else "hecha"
    with write_tx(db):
        n = db.execute("UPDATE tasks SET status = ?, done_by = ?, done_at = ?, done_note = ? WHERE id = ? AND org_id = ? AND status = 'abierta'",
                       (st, g.user["id"], utcnow(), (request.form.get("done_note") or "").strip()[:300] or None, task_id,
                        g.user["org_id"])).rowcount
        if not n:
            abort(404)
        audit(f"tarea_{st}", "tarea", task_id, db=db)
    flash("Tarea actualizada.", "ok")
    return redirect(request.referrer or url_for("labs.pending"))


def latest_values(db, patient_id, codes):
    """Último valor numérico revisado o pendiente de cada prueba, con fecha (para importar a calculadoras)."""
    out = {}
    for c in codes:
        r = db.execute("SELECT value_num, unit, taken_on, status FROM lab_results WHERE patient_id = ? AND test_code = ?"
                       " AND status <> 'anulado' AND value_num IS NOT NULL ORDER BY taken_on DESC, entered_at DESC LIMIT 1",
                       (patient_id, c)).fetchone()
        if r:
            out[c] = r
    return out
