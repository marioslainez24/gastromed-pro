"""Frases predefinidas y plantillas de nota (v0.10.0).

Las frases y plantillas las escribe el médico; el sistema solo las inserta donde él hace clic y nunca rellena
nada por su cuenta. Las «frases de ejemplo» son un punto de partida opcional que se carga con un botón y se puede editar o quitar.
"""
import json
import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import endoscopy_defs as D
from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require

bp = Blueprint("texts", __name__, url_prefix="/ajustes")

MAX_BODY = 6000


def field_choices():
    from .views_notes import ACTIVE_FIELDS
    out = [("*", "Cualquier campo")]
    out += [(k, f"Nota · {v}") for k, v in ACTIVE_FIELDS.items()]
    seen = set()
    for secs in D.NARRATIVE.values():
        for k, lab in secs:
            if k not in seen:
                seen.add(k)
                out.append((f"endo:{k}", f"Endoscopia · {lab}"))
    out += [("endo:conclusion", "Endoscopia · Conclusión"), ("endo:recommendations", "Endoscopia · Recomendaciones"),
            ("doc:body", "Documentos clínicos · Texto")]
    return out


# Frases de ejemplo (opcionales): descripciones habituales que el médico revisa y adapta. No contienen dosis ni fórmulas.
EXAMPLE_PHRASES = [
    ("exploracion_abdominal", "Abdomen normal",
     "Abdomen plano, blando, depresible, no doloroso a la palpación superficial ni profunda, sin masas ni visceromegalias, "
     "peristalsis presente, sin signos de irritación peritoneal."),
    ("exploracion_general", "Exploración general normal",
     "Paciente consciente, orientado, hidratado, con mucosas de coloración normal, sin ictericia. Cardiopulmonar sin alteraciones."),
    ("plan", "Signos de alarma digestivos",
     "Se explican signos de alarma: vómito con sangre o en «pozo de café», heces negras o con sangre, dolor abdominal intenso, "
     "fiebre, coloración amarilla de piel u ojos, o vómitos persistentes. Si se presentan, acudir de inmediato a emergencia."),
    ("plan", "Medidas antirreflujo",
     "Se indican medidas generales: cenar al menos 3 horas antes de acostarse, elevar la cabecera de la cama, evitar comidas "
     "abundantes, grasas, alcohol y tabaco, y control del peso."),
    ("plan", "Control con resultados", "Control en consulta con resultados de los estudios solicitados."),
    ("endo:recommendations", "Esperar patología", "Pendiente resultado de patología; se comentará en la consulta de control."),
    ("endo:recommendations", "Dieta tras sedación",
     "Iniciar dieta líquida y luego blanda según tolerancia. No conducir ni firmar documentos el resto del día por la sedación."),
]


def phrases_for_org(db, org_id):
    return [dict(r) for r in db.execute("SELECT id, field, title, body FROM phrases WHERE org_id = ? AND active = 1"
                                        " ORDER BY field, position, title", (org_id,))]


def phrases_json(db=None):
    """JSON para el editor (atributo data-*); lo usa el JS para el botón «Frases» de cada campo."""
    db = db or get_db()
    return json.dumps([{"f": p["field"], "t": p["title"], "b": p["body"]} for p in phrases_for_org(db, g.user["org_id"])],
                      ensure_ascii=False)


def templates_for(db, template):
    rows = db.execute("SELECT id, name, template, fields FROM note_templates WHERE org_id = ? AND active = 1"
                      " AND template IN (?, 'ambas') ORDER BY name", (g.user["org_id"], template)).fetchall()
    from .views_notes import LEGACY_FIELDS
    out = []
    for r in rows:
        f = json.loads(r["fields"])
        # Plantillas guardadas antes de v0.15: los campos de plan anteriores se juntan en «Plan» y los diferenciales en «Diagnósticos»
        legacy = [f.pop(k) for k in LEGACY_FIELDS if k != "diferenciales" and f.get(k)]
        if legacy:
            f["plan"] = "\n".join(([f["plan"]] if f.get("plan") else []) + legacy)
        if f.get("diferenciales"):
            d = f.pop("diferenciales")
            f["diagnosticos"] = (f["diagnosticos"] + "\n" + d) if f.get("diagnosticos") else d
        out.append({"id": r["id"], "name": r["name"], "fields": f})
    return out


def _id_ok(x):
    return bool(re.fullmatch(r"[0-9a-f]{32}", x or ""))


# ------------------------------------------------------------------------------------------------ frases
@bp.route("/frases", methods=["GET"])
@require("clinico.editar")
def phrases():
    db = get_db()
    rows = db.execute("SELECT * FROM phrases WHERE org_id = ? ORDER BY active DESC, field, position, title", (g.user["org_id"],)).fetchall()
    tpls = db.execute("SELECT * FROM note_templates WHERE org_id = ? ORDER BY active DESC, name", (g.user["org_id"],)).fetchall()
    from .views_notes import TEXT_FIELDS
    from . import exam
    from .util import clinic_settings
    return render_template("ajustes/frases.html", rows=rows, choices=field_choices(), labels=dict(field_choices()),
                           tpls=[dict(t, fields=json.loads(t["fields"])) for t in tpls], text_labels=TEXT_FIELDS,
                           exam_normals=exam.normal_texts(clinic_settings()["exam_normal_texts"]), EXAM_SYSTEMS=exam.SYSTEMS)


@bp.route("/exploracion-normal", methods=["POST"])
@require("clinico.editar", "notas.finalizar")
def exam_normals():
    from . import exam
    if request.form.get("action") == "restaurar":
        value = None
    else:
        custom = {k: t for k in exam.DEFAULT_NORMAL
                  if (t := (request.form.get(f"normal-{k}") or "").replace("\r\n", "\n").strip()[:3000]) and t != exam.DEFAULT_NORMAL[k]}
        value = json.dumps(custom, ensure_ascii=False) if custom else None
    db = get_db()
    with write_tx(db):
        db.execute("UPDATE clinic_settings SET exam_normal_texts = ?, updated_at = ?, updated_by = ?, version = version + 1 WHERE org_id = ?",
                   (value, utcnow(), g.user["id"], g.user["org_id"]))
        audit("exploracion_normal_actualizada", "ajustes", g.user["org_id"], db=db)
    flash("Textos predeterminados restaurados." if request.form.get("action") == "restaurar" else "Textos de exploración normal guardados.", "ok")
    return redirect(url_for("texts.phrases") + "#exploracion")


def _read_phrase_form():
    f = request.form
    field = f.get("field") or "*"
    if field not in dict(field_choices()):
        abort(400)
    title = (f.get("title") or "").strip()[:80]
    body = (f.get("body") or "").replace("\r\n", "\n").strip()[:MAX_BODY]
    return field, title, body


@bp.route("/frases/nueva", methods=["POST"])
@require("clinico.editar")
def phrase_new():
    field, title, body = _read_phrase_form()
    if not title or not body:
        flash("Escriba un nombre corto y el texto de la frase.", "error")
        return redirect(url_for("texts.phrases"))
    db = get_db()
    with write_tx(db):
        pid = new_id()
        db.execute("INSERT INTO phrases(id, org_id, field, title, body, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                   (pid, g.user["org_id"], field, title, body, g.user["id"], utcnow(), utcnow()))
        audit("frase_creada", "frase", pid, db=db)
    flash(f"Frase «{title}» guardada.", "ok")
    return redirect(url_for("texts.phrases"))


@bp.route("/frases/<pid>", methods=["POST"])
@require("clinico.editar")
def phrase_update(pid):
    if not _id_ok(pid):
        abort(404)
    db = get_db()
    row = db.execute("SELECT * FROM phrases WHERE id = ? AND org_id = ?", (pid, g.user["org_id"])).fetchone()
    if not row:
        abort(404)
    action = request.form.get("action")
    with write_tx(db):
        if action in ("desactivar", "activar"):
            db.execute("UPDATE phrases SET active = ?, updated_at = ? WHERE id = ?", (1 if action == "activar" else 0, utcnow(), pid))
        else:
            field, title, body = _read_phrase_form()
            if not title or not body:
                flash("La frase necesita nombre y texto.", "error")
                return redirect(url_for("texts.phrases"))
            db.execute("UPDATE phrases SET field = ?, title = ?, body = ?, updated_at = ? WHERE id = ?", (field, title, body, utcnow(), pid))
        audit("frase_modificada", "frase", pid, {"accion": action or "editar"}, db=db)
    flash("Cambios guardados.", "ok")
    return redirect(url_for("texts.phrases"))


@bp.route("/frases/ejemplos", methods=["POST"])
@require("clinico.editar")
def phrase_examples():
    db = get_db()
    have = {(r["field"], r["title"]) for r in db.execute("SELECT field, title FROM phrases WHERE org_id = ?", (g.user["org_id"],))}
    n = 0
    with write_tx(db):
        for field, title, body in EXAMPLE_PHRASES:
            if (field, title) in have:
                continue
            db.execute("INSERT INTO phrases(id, org_id, field, title, body, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                       (new_id(), g.user["org_id"], field, title, body, g.user["id"], utcnow(), utcnow()))
            n += 1
        audit("frases_ejemplo_cargadas", "frase", None, {"n": n}, db=db)
    flash(f"Se agregaron {n} frases de ejemplo. Revíselas y adáptelas a su forma de escribir." if n else "Las frases de ejemplo ya estaban cargadas.", "ok")
    return redirect(url_for("texts.phrases"))


# ------------------------------------------------------------------------------------------------ plantillas de nota
def create_template(db, name, template, fields):
    from .views_notes import TEXT_FIELDS
    clean = {k: v.strip()[:20000] for k, v in fields.items() if k in TEXT_FIELDS and isinstance(v, str) and v.strip()}
    if not clean:
        return None
    tid = new_id()
    db.execute("INSERT INTO note_templates(id, org_id, name, template, fields, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
               (tid, g.user["org_id"], name[:80], template, json.dumps(clean, ensure_ascii=False), g.user["id"], utcnow(), utcnow()))
    audit("plantilla_nota_creada", "plantilla", tid, {"nombre": name[:80]}, db=db)
    return tid


@bp.route("/plantillas/<tid>", methods=["POST"])
@require("clinico.editar")
def template_update(tid):
    from .views_notes import TEXT_FIELDS
    if not _id_ok(tid):
        abort(404)
    db = get_db()
    row = db.execute("SELECT * FROM note_templates WHERE id = ? AND org_id = ?", (tid, g.user["org_id"])).fetchone()
    if not row:
        abort(404)
    action = request.form.get("action")
    with write_tx(db):
        if action in ("desactivar", "activar"):
            db.execute("UPDATE note_templates SET active = ?, updated_at = ? WHERE id = ?", (1 if action == "activar" else 0, utcnow(), tid))
        else:
            name = (request.form.get("name") or "").strip()[:80]
            fields = {k: (request.form.get(f"f-{k}") or "").replace("\r\n", "\n").strip()[:20000] for k in TEXT_FIELDS}
            fields = {k: v for k, v in fields.items() if v}
            if not name or not fields:
                flash("La plantilla necesita nombre y al menos un campo con texto.", "error")
                return redirect(url_for("texts.phrases") + "#plantillas")
            db.execute("UPDATE note_templates SET name = ?, fields = ?, updated_at = ? WHERE id = ?",
                       (name, json.dumps(fields, ensure_ascii=False), utcnow(), tid))
        audit("plantilla_nota_modificada", "plantilla", tid, {"accion": action or "editar"}, db=db)
    flash("Plantilla actualizada.", "ok")
    return redirect(url_for("texts.phrases") + "#plantillas")
