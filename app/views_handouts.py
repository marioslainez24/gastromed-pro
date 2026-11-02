"""Hojas educativas y dietas para pacientes (v0.21.0).

Pedido del Dr. Lainez (visto en Doctoralia y Doctocliq): escribir una vez sus hojas («Dieta para reflujo», «Dieta rica en fibra»…)
y entregarlas impresas o por correo con un clic. Las escribe y aprueba el médico. Se ofrecen ejemplos opcionales de medidas
generales (sin medicamentos ni dosis) que NO se pueden entregar hasta que el médico los revise y guarde.
Cada entrega queda registrada en el expediente del paciente con el texto tal como se entregó.
"""
import re

from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from .db import get_db, new_id, utcnow, write_tx
from .security import audit, require
from .util import clinic_settings, fmt_birth, local_today
from .views_patients import get_patient_or_404

bp = Blueprint("edu", __name__)

EXAMPLES = [
    ("Medidas para el reflujo", """MEDIDAS PARA EL REFLUJO

• Cene por lo menos 3 horas antes de acostarse.
• Eleve la cabecera de la cama (con bloques bajo las patas de la cabecera, no solo con almohadas).
• Coma porciones pequeñas; evite comidas abundantes.
• Si tiene sobrepeso, bajar de peso ayuda a disminuir los síntomas.
• No fume y evite el alcohol.
• Observe qué alimentos le causan molestias (por ejemplo comidas grasosas, chocolate, café, menta, cítricos o picante) y evítelos.
• Evite acostarse o agacharse inmediatamente después de comer.

Si tiene dificultad o dolor para tragar, vómito con sangre, heces negras o pérdida de peso sin explicación, consulte de inmediato."""),
    ("Dieta rica en fibra", """DIETA RICA EN FIBRA

• Aumente la fibra poco a poco, en una o dos semanas, para evitar gases e inflamación.
• Coma frutas (de preferencia con cáscara) y verduras todos los días.
• Prefiera cereales integrales: avena, pan y tortilla integral, arroz integral.
• Incluya leguminosas: frijoles, lentejas, garbanzos.
• Tome suficiente agua durante el día; la fibra funciona mejor con líquidos.
• Haga actividad física con regularidad.
• Vaya al baño cuando sienta la necesidad; no la aguante."""),
    ("Dieta baja en grasa", """DIETA BAJA EN GRASA

• Evite frituras, chicharrón, embutidos, mantequilla, manteca y quesos grasosos.
• Prepare los alimentos cocidos, asados, a la plancha o al vapor.
• Prefiera carnes magras (pollo sin piel, pescado) y retire la grasa visible.
• Use poco aceite al cocinar.
• Prefiera lácteos descremados.
• Coma porciones moderadas, varias veces al día."""),
]


def _id_ok(x):
    return bool(re.fullmatch(r"[0-9a-f]{32}", x or ""))


def handouts(db, active_only=True):
    return db.execute("SELECT * FROM edu_handouts WHERE org_id = ?" + (" AND active = 1" if active_only else "") + " ORDER BY active DESC, title",
                      (g.user["org_id"],)).fetchall()


# ------------------------------------------------------------------------------------------------ administrar
@bp.route("/hojas-educativas", methods=["GET", "POST"])
@require("clinico.editar")
def manage():
    db = get_db()
    edit = None
    hid = request.values.get("id")
    if hid:
        edit = db.execute("SELECT * FROM edu_handouts WHERE id = ? AND org_id = ?", (hid, g.user["org_id"])).fetchone() if _id_ok(hid) else None
        if not edit:
            abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "ejemplos":
            have = {r["title"].lower() for r in handouts(db, active_only=False)}
            n = 0
            with write_tx(db):
                for title, body in EXAMPLES:
                    if title.lower() not in have:
                        db.execute("INSERT INTO edu_handouts(id, org_id, title, body, reviewed, created_by, created_at, updated_at)"
                                   " VALUES (?,?,?,?,0,?,?,?)", (new_id(), g.user["org_id"], title, body, g.user["id"], utcnow(), utcnow()))
                        n += 1
                audit("hojas_educativas_ejemplo_cargadas", "ajustes", g.user["org_id"], {"n": n}, db=db)
            flash(f"Se agregaron {n} ejemplos. Revíselos, ajústelos y pulse «Guardar» en cada uno: hasta entonces no se pueden entregar."
                  if n else "Los ejemplos ya estaban cargados.", "ok")
            return redirect(url_for("edu.manage"))
        if edit and action in ("desactivar", "activar"):
            with write_tx(db):
                db.execute("UPDATE edu_handouts SET active = ?, updated_at = ? WHERE id = ?", (1 if action == "activar" else 0, utcnow(), edit["id"]))
                audit("hoja_educativa_" + ("activada" if action == "activar" else "desactivada"), "hoja_educativa", edit["id"], db=db)
            return redirect(url_for("edu.manage"))
        title = (request.form.get("title") or "").strip()[:100]
        body = (request.form.get("body") or "").replace("\r\n", "\n").strip()[:12000]
        if not title or not body:
            flash("Escriba el título y el texto de la hoja.", "error")
            return redirect(url_for("edu.manage", id=edit["id"]) if edit else url_for("edu.manage"))
        dup = db.execute("SELECT id FROM edu_handouts WHERE org_id = ? AND lower(title) = lower(?) AND active = 1", (g.user["org_id"], title)).fetchone()
        if dup and (not edit or dup["id"] != edit["id"]):
            flash(f"Ya existe una hoja llamada «{title}».", "error")
            return redirect(url_for("edu.manage"))
        with write_tx(db):
            if edit:
                db.execute("UPDATE edu_handouts SET title = ?, body = ?, reviewed = 1, updated_at = ? WHERE id = ?", (title, body, utcnow(), edit["id"]))
                audit("hoja_educativa_modificada", "hoja_educativa", edit["id"], {"titulo": title}, db=db)
            else:
                nid = new_id()
                db.execute("INSERT INTO edu_handouts(id, org_id, title, body, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                           (nid, g.user["org_id"], title, body, g.user["id"], utcnow(), utcnow()))
                audit("hoja_educativa_creada", "hoja_educativa", nid, {"titulo": title}, db=db)
        flash(f"Hoja «{title}» guardada y lista para entregar.", "ok")
        return redirect(url_for("edu.manage"))
    return render_template("educativas/administrar.html", rows=handouts(db, active_only=False), edit=edit)


# ------------------------------------------------------------------------------------------------ entregar al paciente
def _pdf(p, h):
    from .pdf import sheet_pdf
    from .views_extras import load_assets
    s = clinic_settings()
    body = f"Paciente: {p['first_names']} {p['last_names']}\nFecha: {fmt_birth(local_today().isoformat())}\n\n{h['body']}"
    return sheet_pdf(h["title"], body, s, s["paper_size"], load_assets(g.user["org_id"]))


@bp.route("/pacientes/<patient_id>/hojas-educativas", methods=["POST"])
@require("clinico.ver")
def give(patient_id):
    from .views_mail import EMAIL_RE, mail_ready, send_pdf_to_patient
    p = get_patient_or_404(patient_id)
    db = get_db()
    hid = request.form.get("handout_id")
    h = db.execute("SELECT * FROM edu_handouts WHERE id = ? AND org_id = ? AND active = 1", (hid, g.user["org_id"])).fetchone() if _id_ok(hid) else None
    back = url_for("docs.patient_docs", patient_id=p["id"]) + "#educativas"
    if not h:
        flash("Elija una hoja.", "error")
        return redirect(back)
    if not h["reviewed"]:
        flash(f"La hoja «{h['title']}» es un ejemplo sin revisar: ábrala en «Mis hojas educativas», revísela y guárdela antes de entregarla.", "error")
        return redirect(back)
    data = _pdf(p, h)
    name = f"hoja-{h['id'][:8]}.pdf"
    via = "correo" if request.form.get("accion") == "correo" else "impresa"
    if via == "correo":
        to = (p["email"] or "").strip()
        s = clinic_settings()
        if not EMAIL_RE.match(to):
            flash("El paciente no tiene un correo válido registrado. Agréguelo en «Editar datos» del paciente.", "error")
            return redirect(back)
        if request.form.get("autoriza") != "1":
            flash("Marque que el paciente autorizó recibir la hoja por correo.", "error")
            return redirect(back)
        if not mail_ready(s):
            flash("Falta configurar el correo del consultorio (Ajustes → Recordatorios).", "error")
            return redirect(back)
        ok, msg = send_pdf_to_patient(s, p["first_names"], to, "hoja de indicaciones", name, data, "hoja_educativa", h["id"])
        if ok:
            _record(db, p, h, "correo")
        flash(msg, "ok" if ok else "error")
        return redirect(back)
    _record(db, p, h, "impresa")
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="{name}"'
    return resp


def _record(db, p, h, via):
    # volver a imprimir la misma hoja el mismo día no duplica el registro
    if db.execute("SELECT 1 FROM patient_handouts WHERE patient_id = ? AND handout_id = ? AND via = ? AND substr(given_at, 1, 10) = ?",
                  (p["id"], h["id"], via, utcnow()[:10])).fetchone():
        return
    with write_tx(db):
        rid = new_id()
        db.execute("INSERT INTO patient_handouts(id, org_id, patient_id, handout_id, title, body, via, given_by, given_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (rid, g.user["org_id"], p["id"], h["id"], h["title"], h["body"], via, g.user["id"], utcnow()))
        audit("hoja_educativa_entregada", "paciente", p["id"], {"hoja": h["title"], "via": via}, db=db)


def given_to(db, patient_id):
    return db.execute("SELECT ph.*, u.full_name FROM patient_handouts ph JOIN users u ON u.id = ph.given_by WHERE ph.patient_id = ?"
                      " ORDER BY ph.given_at DESC LIMIT 30", (patient_id,)).fetchall()
