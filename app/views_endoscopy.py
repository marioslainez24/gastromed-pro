"""Fase 3: informes de endoscopia, imágenes y captura, patología, vigilancia, prótesis, calidad y reprocesamiento."""
import hashlib
import json
import re
from datetime import date

from flask import Blueprint, abort, current_app, flash, g, jsonify, make_response, redirect, render_template, request, url_for

from . import endoscopy_defs as D
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, can, require
from .util import clinic_settings, local_today
from .views_files import storage_dir, validate as validate_file
from .views_patients import get_patient_or_404

bp = Blueprint("endo", __name__)
MAX_FINDINGS, MAX_JARS = 40, 30


def _id_ok(x):
    return bool(re.fullmatch(r"[0-9a-f]{32}", x or ""))


def _get_proc(pid):
    if not _id_ok(pid):
        abort(404)
    r = get_db().execute("SELECT pr.*, u.full_name AS author FROM procedures pr JOIN users u ON u.id = pr.author_id"
                         " WHERE pr.id = ? AND pr.org_id = ?", (pid, g.user["org_id"])).fetchone()
    if not r:
        abort(404)
    return r


def _age_years(birth, on):
    if not birth:
        return None
    b, d = date.fromisoformat(birth), date.fromisoformat(on)
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def scopes():
    return get_db().execute("SELECT * FROM scopes WHERE org_id = ? AND active = 1 ORDER BY name", (g.user["org_id"],)).fetchall()


# ------------------------------------------------------------------------------------------------ crear
@bp.route("/pacientes/<patient_id>/procedimientos/nuevo", methods=["GET", "POST"])
@require("clinico.editar")
def proc_new(patient_id):
    p = get_patient_or_404(patient_id)
    appt = request.values.get("appointment_id") or None
    db = get_db()
    if appt and not db.execute("SELECT 1 FROM appointments WHERE id = ? AND patient_id = ? AND org_id = ?", (appt, p["id"], g.user["org_id"])).fetchone():
        abort(404)
    if request.method == "POST":
        kind = request.form.get("kind")
        if kind not in D.KINDS:
            abort(400)
        pid = new_id()
        today = local_today().isoformat()
        with write_tx(db):
            db.execute("INSERT INTO procedures(id, org_id, patient_id, appointment_id, kind, performed_on, patient_age_years, data, author_id,"
                       " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (pid, g.user["org_id"], p["id"], appt, kind, today, _age_years(p["birth_date"], today),
                        json.dumps({"findings": [], "jars": [], "stents": []}), g.user["id"], utcnow(), utcnow()))
            audit("procedimiento_creado", "procedimiento", pid, {"paciente": p["id"], "tipo": kind}, db=db)
        return redirect(url_for("endo.proc_view", proc_id=pid))
    return render_template("endo/nuevo.html", p=p, appt=appt, KINDS=D.KINDS)


# ------------------------------------------------------------------------------------------------ ver / editar
def _images(db, proc_id):
    return db.execute("SELECT i.*, f.mime FROM procedure_images i JOIN files f ON f.id = i.file_id WHERE i.procedure_id = ?"
                      " ORDER BY i.position, i.created_at", (proc_id,)).fetchall()


@bp.route("/procedimientos/<proc_id>")
@require("clinico.ver")
def proc_view(proc_id):
    pr = _get_proc(proc_id)
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (pr["patient_id"],)).fetchone()
    data = json.loads(pr["data"])
    editable = pr["status"] == "borrador" and pr["author_id"] == g.user["id"] and can("clinico.editar")
    allergies = db.execute("SELECT * FROM patient_allergies WHERE patient_id = ? AND active = 1", (p["id"],)).fetchall()
    meds = db.execute("SELECT * FROM patient_medications WHERE patient_id = ? AND status = 'activo'", (p["id"],)).fetchall()
    specimens = db.execute("SELECT * FROM specimens WHERE procedure_id = ? ORDER BY jar", (pr["id"],)).fetchall()
    stents = db.execute("SELECT * FROM stents WHERE procedure_id = ? ORDER BY placed_on", (pr["id"],)).fetchall()
    addenda = db.execute("SELECT a.*, u.full_name FROM procedure_addenda a JOIN users u ON u.id = a.author_id WHERE a.procedure_id = ?"
                         " ORDER BY a.created_at", (pr["id"],)).fetchall()
    scope = db.execute("SELECT * FROM scopes WHERE id = ?", (pr["scope_id"],)).fetchone() if pr["scope_id"] else None
    audit("procedimiento_consultado", "procedimiento", pr["id"])
    return render_template("endo/procedimiento.html", pr=pr, p=p, d=data, D=D, editable=editable, allergies=allergies, meds=meds,
                           images=_images(db, pr["id"]), specimens=specimens, stents=stents, addenda=addenda, scopes=scopes(),
                           scope=scope, empty_finding=dict.fromkeys(["segment", "type", "desc", "classification", "size_mm", "prague_c",
                                                                     "prague_m", "removed", "jar"]),
                           empty_jar=dict.fromkeys(["jar", "site", "desc", "pieces"]), users=db.execute("SELECT id, full_name FROM users WHERE org_id = ? AND active = 1 ORDER BY full_name",
                                                         (g.user["org_id"],)).fetchall())


def _txt(src, k, n=4000):
    v = (src.get(k) or "").strip()
    return v[:n] or None


def _num(src, k, lo, hi, as_int=False):
    v = (src.get(k) or "").strip().replace(",", ".")
    if not v:
        return None
    try:
        x = float(v)
    except ValueError:
        return None
    if not lo <= x <= hi:
        return None
    return int(x) if as_int else x


def parse_form(kind, f):
    """Convierte el formulario del informe en (columnas, data JSON, errores)."""
    errors = []
    cols = {}
    try:
        on = date.fromisoformat(f.get("performed_on", ""))
        if on > local_today():
            errors.append("La fecha del procedimiento no puede ser futura.")
        cols["performed_on"] = on.isoformat()
    except ValueError:
        errors.append("Fecha del procedimiento no válida.")
        cols["performed_on"] = local_today().isoformat()
    ic = f.get("indication_category") or None
    cols["indication_category"] = ic if ic in D.INDICATION_CATEGORIES else None
    sid = f.get("scope_id") or None
    cols["scope_id"] = sid if sid in {s["id"] for s in scopes()} else None
    ext = f.get("extent") or None
    cols["extent"] = ext if ext in dict(D.EXTENT[kind]) else None
    cols["cecum_reached"] = (1 if ext in ("ileon", "ciego") else 0) if kind == "colonoscopia" and ext else None
    cols["complete"] = {"1": 1, "0": 0}.get(f.get("complete"))
    cols["withdrawal_minutes"] = _num(f, "withdrawal_minutes", 0, 180) if kind == "colonoscopia" else None
    for seg in ("right", "transverse", "left"):
        v = f.get(f"bbps_{seg}")
        cols[f"bbps_{seg}"] = int(v) if kind == "colonoscopia" and v in ("0", "1", "2", "3") else None
    comps = [c for c in f.getlist("complications") if c in D.COMPLICATIONS]
    cols["had_complication"] = 1 if comps else 0
    sd = f.get("surveillance_due") or None
    if sd:
        try:
            date.fromisoformat(sd)
        except ValueError:
            errors.append("Fecha de control no válida.")
            sd = None
    cols["surveillance_due"] = sd
    data = {
        "indication": _txt(f, "indication"), "consent_obtained": f.get("consent_obtained") == "1", "consent_version": _txt(f, "consent_version", 120),
        "asa": f.get("asa") if f.get("asa") in dict(D.ASA) else None, "comorbidities": _txt(f, "comorbidities"),
        "anticoagulation": _txt(f, "anticoagulation"), "relevant_meds": _txt(f, "relevant_meds"),
        "prep_product": _txt(f, "prep_product", 200), "prep_regimen": _txt(f, "prep_regimen", 300), "fasting_hours": _num(f, "fasting_hours", 0, 72),
        "sedation_type": f.get("sedation_type") if f.get("sedation_type") in D.SEDATION else None,
        "sedation_agents": _txt(f, "sedation_agents", 500), "sedation_by": _txt(f, "sedation_by", 200), "monitoring": _txt(f, "monitoring", 500),
        "assistants": _txt(f, "assistants", 300), "start_time": _txt(f, "start_time", 5), "end_time": _txt(f, "end_time", 5),
        "incomplete_reason": _txt(f, "incomplete_reason", 300), "interventions": _txt(f, "interventions"), "materials": _txt(f, "materials"),
        "complications": comps, "complication_detail": _txt(f, "complication_detail"), "conclusion": _txt(f, "conclusion"),
        "recommendations": _txt(f, "recommendations"), "follow_up": _txt(f, "follow_up", 500),
        "findings": [], "jars": [], "stents": [],
    }
    segs = set(D.SEGMENTS[kind])
    idx = sorted({int(m.group(1)) for k in f.keys() if (m := re.fullmatch(r"find-(\d{1,2})-segment", k))})
    for i in idx[:MAX_FINDINGS]:
        seg = f.get(f"find-{i}-segment")
        desc = _txt(f, f"find-{i}-desc", 1000)
        ftype = f.get(f"find-{i}-type") if f.get(f"find-{i}-type") in D.FINDING_TYPES else None
        if not (seg or desc or ftype):
            continue
        if seg not in segs:
            errors.append(f"Hallazgo {len(data['findings']) + 1}: elija el segmento.")
            continue
        cls = f.get(f"find-{i}-class") or None
        data["findings"].append({
            "segment": seg, "type": ftype, "desc": desc, "classification": cls if cls in D.CLASS_LOOKUP else None,
            "size_mm": _num(f, f"find-{i}-size", 0, 300), "prague_c": _num(f, f"find-{i}-pc", 0, 20),
            "prague_m": _num(f, f"find-{i}-pm", 0, 20), "removed": f.get(f"find-{i}-removed") or None,
            "jar": _num(f, f"find-{i}-jar", 1, 99, as_int=True)})
    jdx = sorted({int(m.group(1)) for k in f.keys() if (m := re.fullmatch(r"jar-(\d{1,2})-site", k))})
    numbers = set()
    for i in jdx[:MAX_JARS]:
        site = _txt(f, f"jar-{i}-site", 200)
        if not site:
            continue
        n = _num(f, f"jar-{i}-number", 1, 99, as_int=True)
        if n is None or n in numbers:
            errors.append(f"Frasco «{site}»: número no válido o repetido.")
            continue
        numbers.add(n)
        data["jars"].append({"jar": n, "site": site, "desc": _txt(f, f"jar-{i}-desc", 500), "pieces": _num(f, f"jar-{i}-pieces", 1, 99, as_int=True)})
    for fi in data["findings"]:
        if fi["jar"] and fi["jar"] not in numbers:
            errors.append(f"El hallazgo en «{fi['segment']}» menciona el frasco {fi['jar']}, que no está en la lista de frascos.")
    sdx = sorted({int(m.group(1)) for k in f.keys() if (m := re.fullmatch(r"stent-(\d{1,2})-kind", k))})
    for i in sdx[:10]:
        kd = f.get(f"stent-{i}-kind")
        if kd not in D.STENT_KINDS:
            continue
        due = f.get(f"stent-{i}-due") or None
        try:
            due = date.fromisoformat(due).isoformat() if due else None
        except ValueError:
            errors.append("Fecha de revisión de prótesis no válida.")
            due = None
        data["stents"].append({"kind": kd, "desc": _txt(f, f"stent-{i}-desc", 300), "review_due": due})
    return cols, data, errors


@bp.route("/procedimientos/<proc_id>/guardar", methods=["POST"])
@require("clinico.editar")
def proc_save(proc_id):
    pr = _get_proc(proc_id)
    if pr["status"] != "borrador" or pr["author_id"] != g.user["id"]:
        abort(409, description="Solo el autor puede editar un informe en borrador.")
    cols, data, errors = parse_form(pr["kind"], request.form)
    db = get_db()
    p = db.execute("SELECT birth_date FROM patients WHERE id = ?", (pr["patient_id"],)).fetchone()
    cols["patient_age_years"] = _age_years(p["birth_date"], cols["performed_on"])
    with write_tx(db):
        cur = db.execute("UPDATE procedures SET " + ", ".join(f"{k} = ?" for k in cols) +
                         ", data = ?, updated_at = ?, version = version + 1 WHERE id = ? AND version = ? AND status = 'borrador'",
                         list(cols.values()) + [json.dumps(data, ensure_ascii=False), utcnow(), pr["id"], int(request.form.get("version", "0"))])
        if cur.rowcount == 0:
            abort(409, description="El informe se modificó en otra ventana. Sus cambios no se guardaron: recargue la página.")
        audit("procedimiento_guardado", "procedimiento", pr["id"], db=db)
    if errors:
        flash("Guardado con observaciones: " + " ".join(errors), "error")
    elif request.form.get("then") == "finalizar":
        return redirect(url_for("endo.proc_view", proc_id=pr["id"], confirmar=1))
    else:
        flash("Informe guardado.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=pr["id"]))


@bp.route("/procedimientos/<proc_id>/finalizar", methods=["POST"])
@require("clinico.editar", "notas.finalizar")
def proc_finalize(proc_id):
    pr = _get_proc(proc_id)
    if pr["status"] != "borrador" or pr["author_id"] != g.user["id"]:
        abort(409, description="El informe ya estaba finalizado o no es su autor.")
    d = json.loads(pr["data"])
    missing = [lab for k, lab in (("indication", "indicación"), ("conclusion", "conclusión")) if not d.get(k)]
    if not pr["indication_category"]:
        missing.append("tipo de indicación")
    if not d.get("consent_obtained"):
        missing.append("confirmación del consentimiento informado")
    if not d.get("sedation_type"):
        missing.append("tipo de sedación")
    if pr["kind"] in ("colonoscopia", "rectosigmoidoscopia", "eda") and not pr["extent"]:
        missing.append("extensión alcanzada")
    if missing:
        flash("No se puede finalizar. Falta: " + ", ".join(missing) + ".", "error")
        return redirect(url_for("endo.proc_view", proc_id=pr["id"]))
    digest = hashlib.sha256(json.dumps({"cols": {k: pr[k] for k in pr.keys() if k not in ("version", "updated_at")}, "data": d},
                                       sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    db = get_db()
    with write_tx(db):
        cur = db.execute("UPDATE procedures SET status = 'finalizado', finalized_at = ?, finalized_by = ?, content_sha256 = ?, version = version + 1"
                         " WHERE id = ? AND version = ? AND status = 'borrador'",
                         (utcnow(), g.user["id"], digest, pr["id"], int(request.form.get("version", "0"))))
        if cur.rowcount == 0:
            abort(409, description="El informe cambió antes de finalizar. Revise y vuelva a finalizar.")
        for j in d.get("jars", []):
            db.execute("INSERT INTO specimens(id, org_id, procedure_id, patient_id, jar, site, description, pieces, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (new_id(), g.user["org_id"], pr["id"], pr["patient_id"], j["jar"], j["site"], j.get("desc"), j.get("pieces"), utcnow()))
        for s in d.get("stents", []):
            db.execute("INSERT INTO stents(id, org_id, patient_id, procedure_id, kind, description, placed_on, review_due, created_by, created_at)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id(), g.user["org_id"], pr["patient_id"], pr["id"], s["kind"], s.get("desc"),
                                                         pr["performed_on"], s.get("review_due"), g.user["id"], utcnow()))
        if d.get("jars"):
            db.execute("INSERT INTO tasks(id, org_id, patient_id, title, due_on, assigned_to, created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
                       (new_id(), g.user["org_id"], pr["patient_id"], f"Seguimiento de patología: {len(d['jars'])} frasco(s) de {D.KINDS[pr['kind']]}",
                        None, g.user["id"], g.user["id"], utcnow()))
        audit("procedimiento_finalizado", "procedimiento", pr["id"], {"sha256": digest, "frascos": len(d.get("jars", []))}, db=db)
    flash("Informe finalizado. Los frascos quedaron registrados para seguimiento de patología.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=pr["id"]))


@bp.route("/procedimientos/<proc_id>/adenda", methods=["POST"])
@require("clinico.editar")
def proc_addendum(proc_id):
    pr = _get_proc(proc_id)
    if pr["status"] != "finalizado":
        abort(409)
    text = (request.form.get("text") or "").strip()[:20000]
    if not text:
        abort(400)
    db = get_db()
    with write_tx(db):
        db.execute("INSERT INTO procedure_addenda(id, procedure_id, author_id, created_at, text) VALUES (?,?,?,?,?)",
                   (new_id(), pr["id"], g.user["id"], utcnow(), text))
        audit("procedimiento_adenda", "procedimiento", pr["id"], db=db)
    flash("Adenda registrada.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=pr["id"]) + "#adendas")


# ------------------------------------------------------------------------------------------------ imágenes
@bp.route("/procedimientos/<proc_id>/imagenes", methods=["POST"])
@require("clinico.editar")
def image_add(proc_id):
    pr = _get_proc(proc_id)
    if pr["status"] != "borrador":
        abort(409, description="El procedimiento está finalizado: no se pueden agregar imágenes.")
    db = get_db()
    # Confirmación explícita del paciente para evitar mezclar imágenes entre estudios
    if request.form.get("confirm_patient") != pr["patient_id"]:
        abort(400, description="Falta la confirmación del paciente para esta imagen.")
    ups = request.files.getlist("imagen")
    source = "captura" if request.form.get("source") == "captura" else "importada"
    added, errors = 0, []
    pos = db.execute("SELECT COALESCE(MAX(position), 0) FROM procedure_images WHERE procedure_id = ?", (pr["id"],)).fetchone()[0]
    for up in ups[:20]:
        data = up.read(20 * 1024 * 1024 + 1)
        mime, ext, err = validate_file(data)
        if err or mime not in ("image/jpeg", "image/png"):
            errors.append(f"{up.filename or 'imagen'}: {err or 'solo se aceptan JPG o PNG para el informe'}")
            continue
        fid, iid = new_id(), new_id()
        import secrets as _s
        storage = _s.token_hex(24) + ".bin"
        path = storage_dir() / storage
        path.write_bytes(current_app.config["GM_FERNET"].encrypt(data))
        pos += 1
        try:
            with write_tx(db):
                db.execute("INSERT INTO files(id, org_id, patient_id, category, title, study_date, original_name, mime, size_bytes, sha256,"
                           " storage_name, uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (fid, g.user["org_id"], pr["patient_id"], "endoscopia", f"{D.KINDS[pr['kind']]} · imagen {pos}", pr["performed_on"],
                            re.sub(r"[^\w.\- ]", "_", up.filename or f"captura.{ext}")[-120:], mime, len(data),
                            hashlib.sha256(data).hexdigest(), storage, g.user["id"], utcnow()))
                db.execute("INSERT INTO procedure_images(id, procedure_id, file_id, source, position, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                           (iid, pr["id"], fid, source, pos, g.user["id"], utcnow()))
                audit("imagen_procedimiento", "procedimiento", pr["id"], {"imagen": iid, "origen": source}, db=db)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        added += 1
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": added > 0, "agregadas": added, "errores": errors}), (200 if added else 422)
    if errors:
        flash(" ".join(errors), "error")
    if added:
        flash(f"{added} imagen(es) agregadas al procedimiento.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=pr["id"]) + "#imagenes")


@bp.route("/procedimientos/<proc_id>/imagenes/<img_id>", methods=["POST"])
@require("clinico.editar")
def image_update(proc_id, img_id):
    pr = _get_proc(proc_id)
    if pr["status"] != "borrador":
        abort(409)
    db = get_db()
    img = db.execute("SELECT * FROM procedure_images WHERE id = ? AND procedure_id = ?", (img_id, pr["id"])).fetchone() if _id_ok(img_id) else None
    if not img:
        abort(404)
    ann = request.form.get("annotations", img["annotations"])
    try:
        items = json.loads(ann)
        clean = [{"x": min(max(float(a["x"]), 0), 1), "y": min(max(float(a["y"]), 0), 1), "text": str(a.get("text", ""))[:60]}
                 for a in items[:12]]
    except (ValueError, TypeError, KeyError):
        abort(400)
    loc = request.form.get("location") or None
    if loc and loc not in D.SEGMENTS[pr["kind"]]:
        loc = None
    with write_tx(db):
        db.execute("UPDATE procedure_images SET location = ?, caption = ?, in_report = ?, annotations = ? WHERE id = ?",
                   (loc, (request.form.get("caption") or "").strip()[:200] or None, int(request.form.get("in_report") == "1"),
                    json.dumps(clean, ensure_ascii=False), img["id"]))
        audit("imagen_editada", "procedimiento", pr["id"], {"imagen": img["id"]}, db=db)
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True})
    flash("Imagen actualizada (el archivo original no se modifica).", "ok")
    return redirect(url_for("endo.proc_view", proc_id=pr["id"]) + "#imagenes")


@bp.route("/procedimientos/<proc_id>/captura")
@require("clinico.editar")
def capture(proc_id):
    pr = _get_proc(proc_id)
    if pr["status"] != "borrador" or pr["author_id"] != g.user["id"]:
        abort(409, description="La captura solo está disponible en informes en borrador de su autoría.")
    p = get_db().execute("SELECT * FROM patients WHERE id = ?", (pr["patient_id"],)).fetchone()
    resp = make_response(render_template("endo/captura.html", pr=pr, p=p, D=D))
    resp.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(), payment=()"
    return resp


# ------------------------------------------------------------------------------------------------ PDF
@bp.route("/procedimientos/<proc_id>/pdf")
@require("clinico.ver")
def proc_pdf(proc_id):
    from .pdf import procedure_pdf
    pr = _get_proc(proc_id)
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (pr["patient_id"],)).fetchone()
    s = clinic_settings()
    size = request.args.get("papel") or s["paper_size"]
    if size not in ("carta", "a4"):
        abort(400)
    imgs = []
    fernet = current_app.config["GM_FERNET"]
    for im in _images(db, pr["id"]):
        if not im["in_report"]:
            continue
        f = db.execute("SELECT * FROM files WHERE id = ?", (im["file_id"],)).fetchone()
        raw = fernet.decrypt((storage_dir() / f["storage_name"]).read_bytes())
        if hashlib.sha256(raw).hexdigest() != f["sha256"]:
            abort(500)
        imgs.append((im, raw))
    scope = db.execute("SELECT * FROM scopes WHERE id = ?", (pr["scope_id"],)).fetchone() if pr["scope_id"] else None
    addenda = db.execute("SELECT a.*, u.full_name FROM procedure_addenda a JOIN users u ON u.id = a.author_id WHERE a.procedure_id = ?"
                         " ORDER BY a.created_at", (pr["id"],)).fetchall()
    data = procedure_pdf(pr, json.loads(pr["data"]), p, s, size, imgs, scope, addenda, D)
    audit("procedimiento_pdf", "procedimiento", pr["id"])
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="informe-{pr["id"][:8]}.pdf"'
    return resp


# ------------------------------------------------------------------------------------------------ patología
@bp.route("/procedimientos/<proc_id>/muestras/enviar", methods=["POST"])
@require("clinico.editar")
def specimens_send(proc_id):
    pr = _get_proc(proc_id)
    lab = (request.form.get("laboratory") or "").strip()[:160] or None
    sent = request.form.get("sent_on") or local_today().isoformat()
    try:
        date.fromisoformat(sent)
    except ValueError:
        abort(400)
    db = get_db()
    with write_tx(db):
        n = db.execute("UPDATE specimens SET status = 'enviado', laboratory = ?, sent_on = ? WHERE procedure_id = ? AND status = 'pendiente_envio'",
                       (lab, sent, pr["id"])).rowcount
        audit("muestras_enviadas", "procedimiento", pr["id"], {"n": n}, db=db)
    flash(f"{n} frasco(s) marcados como enviados.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=pr["id"]) + "#patologia")


def _get_specimen(sid):
    if not _id_ok(sid):
        abort(404)
    s = get_db().execute("SELECT * FROM specimens WHERE id = ? AND org_id = ?", (sid, g.user["org_id"])).fetchone()
    if not s:
        abort(404)
    return s


@bp.route("/muestras/<sid>/resultado", methods=["POST"])
@require("clinico.editar", "resultados.revisar")
def specimen_result(sid):
    s = _get_specimen(sid)
    if s["result_text"]:
        abort(409, description="Este frasco ya tiene resultado. Para corregirlo agregue una adenda al procedimiento.")
    text = (request.form.get("result_text") or "").strip()[:4000]
    cat = request.form.get("result_category")
    dys = request.form.get("dysplasia") or "no_aplica"
    if not text or cat not in D.RESULT_CATEGORIES or dys not in D.DYSPLASIA:
        flash("Escriba el diagnóstico histológico y elija la categoría.", "error")
        return redirect(url_for("endo.proc_view", proc_id=s["procedure_id"]) + "#patologia")
    ron = request.form.get("result_on") or local_today().isoformat()
    try:
        date.fromisoformat(ron)
    except ValueError:
        abort(400)
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE specimens SET result_text = ?, result_category = ?, dysplasia = ?, result_on = ?, result_by = ?, status = 'resultado_recibido'"
                   " WHERE id = ?", (text, cat, dys, ron, g.user["id"], s["id"]))
        audit("patologia_resultado", "muestra", s["id"], {"categoria": cat}, db=db)
    flash(f"Resultado del frasco {s['jar']} registrado.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=s["procedure_id"]) + "#patologia")


@bp.route("/muestras/<sid>/cerrar", methods=["POST"])
@require("clinico.editar", "resultados.revisar")
def specimen_close(sid):
    s = _get_specimen(sid)
    action = request.form.get("action")
    db = get_db()
    with write_tx(db):
        if action == "extraviado":
            db.execute("UPDATE specimens SET status = 'extraviado', closed_by = ?, closed_at = ?, communication = ? WHERE id = ?",
                       (g.user["id"], utcnow(), (request.form.get("communication") or "").strip()[:300] or None, s["id"]))
        else:
            if s["status"] != "resultado_recibido":
                abort(409, description="Primero registre el resultado del frasco.")
            channel = (request.form.get("communication") or "").strip()[:300]
            if not channel:
                abort(400, description="Indique cómo se comunicó el resultado al paciente.")
            db.execute("UPDATE specimens SET status = 'cerrado', communicated_at = ?, communication = ?, closed_by = ?, closed_at = ? WHERE id = ?",
                       (utcnow(), channel, g.user["id"], utcnow(), s["id"]))
        audit("patologia_cerrada", "muestra", s["id"], {"accion": action or "cerrar"}, db=db)
    flash("Seguimiento del frasco actualizado.", "ok")
    return redirect(url_for("endo.proc_view", proc_id=s["procedure_id"]) + "#patologia")


# ------------------------------------------------------------------------------------------------ prótesis
@bp.route("/protesis/<stent_id>", methods=["POST"])
@require("clinico.editar")
def stent_update(stent_id):
    if not _id_ok(stent_id):
        abort(404)
    db = get_db()
    st = db.execute("SELECT * FROM stents WHERE id = ? AND org_id = ?", (stent_id, g.user["org_id"])).fetchone() or abort(404)
    status = request.form.get("status")
    if status not in ("retirada", "recambiada", "migrada"):
        abort(400)
    with write_tx(db):
        db.execute("UPDATE stents SET status = ?, removed_on = ?, notes = ? WHERE id = ?",
                   (status, local_today().isoformat(), (request.form.get("notes") or "").strip()[:500] or None, st["id"]))
        audit("protesis_actualizada", "protesis", st["id"], {"estado": status}, db=db)
    flash("Prótesis actualizada.", "ok")
    return redirect(request.referrer or url_for("endo.index"))


# ------------------------------------------------------------------------------------------------ tablero de endoscopia
@bp.route("/endoscopia")
@require("clinico.ver")
def index():
    db = get_db()
    org = g.user["org_id"]
    today = local_today().isoformat()
    recent = db.execute("SELECT pr.*, p.first_names, p.last_names, p.mrn FROM procedures pr JOIN patients p ON p.id = pr.patient_id"
                        " WHERE pr.org_id = ? ORDER BY pr.performed_on DESC, pr.created_at DESC LIMIT 50", (org,)).fetchall()
    path = db.execute("SELECT s.*, p.first_names, p.last_names, pr.kind, pr.performed_on FROM specimens s JOIN patients p ON p.id = s.patient_id"
                      " JOIN procedures pr ON pr.id = s.procedure_id WHERE s.org_id = ? AND s.status IN ('pendiente_envio','enviado','resultado_recibido')"
                      " ORDER BY pr.performed_on", (org,)).fetchall()
    recalls = db.execute("SELECT pr.*, p.first_names, p.last_names, p.mrn FROM procedures pr JOIN patients p ON p.id = pr.patient_id"
                         " WHERE pr.org_id = ? AND pr.status = 'finalizado' AND pr.surveillance_due IS NOT NULL"
                         " AND pr.surveillance_due <= date(?, '+60 days') AND NOT EXISTS (SELECT 1 FROM procedures p2 WHERE p2.patient_id = pr.patient_id"
                         " AND p2.kind = pr.kind AND p2.performed_on > pr.performed_on) ORDER BY pr.surveillance_due", (org, today)).fetchall()
    stents = db.execute("SELECT s.*, p.first_names, p.last_names FROM stents s JOIN patients p ON p.id = s.patient_id"
                        " WHERE s.org_id = ? AND s.status = 'colocada' ORDER BY COALESCE(s.review_due, '9999')", (org,)).fetchall()
    return render_template("endo/index.html", recent=recent, path=path, recalls=recalls, stents=stents, today=today, D=D)


@bp.route("/pacientes/<patient_id>/procedimientos")
@require("clinico.ver")
def patient_procs(patient_id):
    p = get_patient_or_404(patient_id)
    db = get_db()
    rows = db.execute("SELECT pr.*, u.full_name AS author FROM procedures pr JOIN users u ON u.id = pr.author_id WHERE pr.patient_id = ?"
                      " ORDER BY pr.performed_on DESC", (p["id"],)).fetchall()
    stents = db.execute("SELECT * FROM stents WHERE patient_id = ? ORDER BY placed_on DESC", (p["id"],)).fetchall()
    return render_template("endo/paciente.html", p=p, rows=rows, stents=stents, D=D, today=local_today().isoformat())


# ------------------------------------------------------------------------------------------------ indicadores de calidad
def quality_metrics(db, org, start, end, author=None):
    base = ("SELECT pr.*, (SELECT COUNT(*) FROM specimens s WHERE s.procedure_id = pr.id AND s.result_category IN "
            "('adenoma_tubular','adenoma_tubulovelloso','adenoma_velloso')) AS adenomas FROM procedures pr WHERE pr.org_id = ?"
            " AND pr.status = 'finalizado' AND pr.kind = 'colonoscopia' AND pr.performed_on BETWEEN ? AND ?")
    params = [org, start, end]
    if author:
        base += " AND pr.author_id = ?"
        params.append(author)
    rows = db.execute(base, params).fetchall()
    out = []
    # 1. Intubación cecal
    den = [r for r in rows if r["indication_category"] != "terapeutica" and r["cecum_reached"] is not None]
    num = [r for r in den if r["cecum_reached"]]
    out.append(("Tasa de intubación cecal", len(num), len(den),
                "Numerador: colonoscopias que alcanzan ciego o íleon. Denominador: colonoscopias finalizadas con extensión registrada. "
                "Excluye: indicación terapéutica."))
    # 2. Tasa de detección de adenomas
    den = [r for r in rows if r["indication_category"] == "tamizaje" and (r["patient_age_years"] or 0) >= 45]
    pending = {r["id"] for r in den if db.execute("SELECT COUNT(*) FROM specimens WHERE procedure_id = ? AND result_text IS NULL"
                                                  " AND status <> 'extraviado'", (r["id"],)).fetchone()[0]}
    den_ok = [r for r in den if r["id"] not in pending]
    num = [r for r in den_ok if r["adenomas"]]
    out.append(("Tasa de detección de adenomas (ADR)", len(num), len(den_ok),
                f"Numerador: colonoscopias de tamizaje con ≥1 adenoma confirmado por patología. Denominador: colonoscopias de tamizaje en "
                f"pacientes ≥45 años con patología cerrada. Excluidas por patología pendiente: {len(pending)}."))
    # 3. Preparación adecuada (Boston ≥2 en cada segmento)
    den = [r for r in rows if None not in (r["bbps_right"], r["bbps_transverse"], r["bbps_left"])]
    num = [r for r in den if min(r["bbps_right"], r["bbps_transverse"], r["bbps_left"]) >= 2]
    out.append(("Preparación adecuada (Boston ≥2 en cada segmento)", len(num), len(den),
                "Denominador: colonoscopias con los tres segmentos de Boston registrados."))
    # 4. Tiempo de retirada ≥6 min
    den = [r for r in rows if r["indication_category"] == "tamizaje" and r["cecum_reached"] and r["withdrawal_minutes"] is not None
           and not db.execute("SELECT 1 FROM specimens WHERE procedure_id = ? LIMIT 1", (r["id"],)).fetchone()]
    num = [r for r in den if r["withdrawal_minutes"] >= 6]
    out.append(("Tiempo de retirada ≥6 minutos", len(num), len(den),
                "Denominador: colonoscopias de tamizaje completas, sin toma de muestras (aproximación de «sin intervención»), con tiempo registrado."))
    # 5. Complicaciones registradas
    out.append(("Complicaciones registradas", sum(1 for r in rows if r["had_complication"]), len(rows),
                "Denominador: todas las colonoscopias finalizadas del período. Solo cuenta complicaciones registradas en el informe."))
    return out


@bp.route("/endoscopia/calidad")
@require("clinico.ver")
def quality():
    db = get_db()
    today = local_today()
    start = request.args.get("desde") or date(today.year, 1, 1).isoformat()
    end = request.args.get("hasta") or today.isoformat()
    try:
        date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        abort(400)
    author = request.args.get("endoscopista") or None
    users = db.execute("SELECT DISTINCT u.id, u.full_name FROM procedures pr JOIN users u ON u.id = pr.author_id WHERE pr.org_id = ?",
                       (g.user["org_id"],)).fetchall()
    if author and author not in {u["id"] for u in users}:
        author = None
    metrics = quality_metrics(db, g.user["org_id"], start, end, author)
    return render_template("endo/calidad.html", metrics=metrics, start=start, end=end, users=users, author=author)


# ------------------------------------------------------------------------------------------------ endoscopios y reprocesamiento
@bp.route("/endoscopia/equipos", methods=["GET", "POST"])
@require("clinico.ver")
def equipment():
    db = get_db()
    org = g.user["org_id"]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "nuevo_equipo":
            if not can("ajustes.editar"):
                abort(403)
            name = (request.form.get("name") or "").strip()[:120]
            kind = request.form.get("kind")
            if not name or kind not in ("gastroscopio", "colonoscopio", "duodenoscopio", "ecoendoscopio", "otro"):
                abort(400)
            with write_tx(db):
                sid = new_id()
                db.execute("INSERT INTO scopes(id, org_id, name, kind, serial, created_at) VALUES (?,?,?,?,?,?)",
                           (sid, org, name, kind, (request.form.get("serial") or "").strip()[:80] or None, utcnow()))
                audit("endoscopio_creado", "endoscopio", sid, db=db)
            flash("Equipo registrado.", "ok")
        elif action == "reprocesamiento":
            if not can("endoscopia.reprocesamiento"):
                abort(403)
            sid = request.form.get("scope_id")
            if not db.execute("SELECT 1 FROM scopes WHERE id = ? AND org_id = ?", (sid, org)).fetchone():
                abort(400)
            method, leak, result = request.form.get("method"), request.form.get("leak_test"), request.form.get("result")
            if method not in ("manual", "automatizado") or leak not in ("aprobada", "fallida", "no_realizada") or result not in ("apto", "no_apto"):
                abort(400)
            if leak == "fallida" and result == "apto":
                flash("Una prueba de fuga fallida no puede registrarse como «apto».", "error")
                return redirect(url_for("endo.equipment"))
            proc = request.form.get("procedure_id") or None
            if proc and not db.execute("SELECT 1 FROM procedures WHERE id = ? AND org_id = ?", (proc, org)).fetchone():
                proc = None
            with write_tx(db):
                rid = new_id()
                db.execute("INSERT INTO scope_reprocessing(id, org_id, scope_id, procedure_id, done_at, method, agent, agent_lot, leak_test, result,"
                           " notes, done_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (rid, org, sid, proc, utcnow(), method, (request.form.get("agent") or "").strip()[:120] or None,
                            (request.form.get("agent_lot") or "").strip()[:60] or None, leak, result,
                            (request.form.get("notes") or "").strip()[:500] or None, g.user["id"]))
                audit("reprocesamiento", "endoscopio", sid, {"resultado": result}, db=db)
            flash("Reprocesamiento registrado.", "ok")
        return redirect(url_for("endo.equipment"))
    eq = db.execute("SELECT s.*, (SELECT r.result || '|' || r.done_at FROM scope_reprocessing r WHERE r.scope_id = s.id ORDER BY r.done_at DESC LIMIT 1)"
                    " AS last FROM scopes s WHERE s.org_id = ? ORDER BY s.active DESC, s.name", (org,)).fetchall()
    log = db.execute("SELECT r.*, s.name, u.full_name FROM scope_reprocessing r JOIN scopes s ON s.id = r.scope_id JOIN users u ON u.id = r.done_by"
                     " WHERE r.org_id = ? ORDER BY r.done_at DESC LIMIT 100", (org,)).fetchall()
    recent = db.execute("SELECT pr.id, pr.kind, pr.performed_on, p.last_names FROM procedures pr JOIN patients p ON p.id = pr.patient_id"
                        " WHERE pr.org_id = ? ORDER BY pr.created_at DESC LIMIT 20", (org,)).fetchall()
    return render_template("endo/equipos.html", eq=eq, log=log, recent=recent, D=D)
