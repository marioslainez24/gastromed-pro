"""Enviar al correo del PACIENTE su informe de endoscopia, su receta o un documento clínico, en PDF (v0.19.0).

Pedido del Dr. Lainez: con un clic, desde el Gmail del consultorio ya configurado en Ajustes → Recordatorios (contraseña de
aplicación, gratis). Reglas:
- Solo documentos definitivos: informe FINALIZADO, receta EMITIDA (no anulada), documento EMITIDO (no anulado).
- Solo al correo registrado en los datos del paciente, y con la confirmación de que el paciente autorizó recibirlo por correo.
- El cuerpo del correo no lleva datos clínicos: todo va en el PDF adjunto. El nombre del archivo no identifica al paciente.
- Si el envío falla se informa el motivo; nunca se da por enviado algo que no salió. Queda en la auditoría.
"""
import re

from flask import Blueprint, abort, current_app, flash, g, redirect, request, url_for

from . import reminders as R
from .db import get_db
from .security import audit, require
from .util import clinic_settings

bp = Blueprint("mail", __name__, url_prefix="/enviar-correo")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

KINDS = {
    "informe": ("informe de endoscopia", "procedimiento"),
    "receta": ("receta", "receta"),
    "documento": ("documento", "documento"),
}


def _back(kind, obj_id):
    return {"informe": url_for("endo.proc_view", proc_id=obj_id), "receta": url_for("rx.view", rx_id=obj_id),
            "documento": url_for("docs.doc_view", doc_id=obj_id)}[kind]


def last_sent(db, kind, obj_id):
    """Fecha del último envío por correo de este documento (de la auditoría), para mostrarla en pantalla."""
    r = db.execute("SELECT at FROM audit_log WHERE action = 'enviado_por_correo_al_paciente' AND entity = ? AND entity_id = ?"
                   " ORDER BY seq DESC LIMIT 1", (KINDS[kind][1], obj_id)).fetchone()
    return r["at"] if r else None


def mail_ready(s):
    return bool(s["smtp_user"] and s["smtp_password_enc"])


@bp.route("/<kind>/<obj_id>", methods=["POST"])
@require("clinico.ver")
def send(kind, obj_id):
    if kind not in KINDS or not re.fullmatch(r"[0-9a-f]{32}", obj_id or ""):
        abort(404)
    db = get_db()
    org = g.user["org_id"]
    if kind == "informe":
        row = db.execute("SELECT id, patient_id, status = 'finalizado' AND discarded_at IS NULL AS ok, kind AS sub FROM procedures"
                         " WHERE id = ? AND org_id = ?", (obj_id, org)).fetchone()
    elif kind == "receta":
        row = db.execute("SELECT id, patient_id, status = 'emitida' AS ok, NULL AS sub FROM prescriptions WHERE id = ? AND org_id = ?",
                         (obj_id, org)).fetchone()
    else:
        row = db.execute("SELECT id, patient_id, status = 'emitido' AS ok, kind AS sub FROM clinical_documents WHERE id = ? AND org_id = ?",
                         (obj_id, org)).fetchone()
    if not row:
        abort(404)
    back = _back(kind, obj_id)
    if not row["ok"]:
        abort(409, description="Solo se envían documentos definitivos (informe finalizado, receta o documento sin anular).")
    p = db.execute("SELECT first_names, email FROM patients WHERE id = ?", (row["patient_id"],)).fetchone()
    to = (p["email"] or "").strip()
    if not EMAIL_RE.match(to):
        flash("El paciente no tiene un correo válido registrado. Agréguelo en «Editar datos» del paciente.", "error")
        return redirect(back)
    if request.form.get("autoriza") != "1":
        flash("Marque que el paciente autorizó recibir este documento por correo.", "error")
        return redirect(back)
    s = clinic_settings()
    if not mail_ready(s):
        flash("Falta configurar el correo del consultorio (Ajustes → Recordatorios → cuenta de Gmail).", "error")
        return redirect(back)
    # Se genera el mismo PDF que se imprime
    if kind == "informe":
        from .views_endoscopy import proc_pdf
        data = proc_pdf(obj_id).get_data()
        name = f"informe-{obj_id[:8]}.pdf"
    elif kind == "receta":
        from .views_prescriptions import pdf as rx_pdf
        data = rx_pdf(obj_id).get_data()
        name = f"receta-{obj_id[:8]}.pdf"
    else:
        from .views_documents import doc_pdf
        data = doc_pdf(obj_id).get_data()
        name = f"documento-{obj_id[:8]}.pdf"
    ok, msg = send_pdf_to_patient(s, p["first_names"], to, KINDS[kind][0], name, data, KINDS[kind][1], obj_id)
    flash(msg, "ok" if ok else "error")
    return redirect(back)


def send_pdf_to_patient(s, first_name, to, label, filename, data, entity, entity_id):
    """Envía un PDF al paciente desde el correo del consultorio. Devuelve (enviado, mensaje). Nunca simula el envío."""
    doctor = s["doctor_display_name"] or "su médico"
    body = (f"Estimado(a) {first_name}:\n\n"
            f"Le enviamos adjunto su {label} en formato PDF, como lo solicitó en la consulta.\n\n"
            "Este correo es confidencial y está dirigido solo a usted. Si lo recibió por error, por favor elimínelo y avísenos.\n"
            + (f"Si tiene dudas, comuníquese al {s['phones']}.\n" if s["phones"] else "")
            + f"\nAtentamente,\n{doctor}")
    try:
        pw = current_app.config["GM_FERNET"].decrypt(s["smtp_password_enc"].encode()).decode()
        R.send_email(s, pw, to, f"Su {label} — {doctor}", body, attachments=[(filename, data)])
    except Exception as e:  # noqa: BLE001
        audit("envio_por_correo_fallido", entity, entity_id, {"motivo": R.safe_error(e)})
        return False, "No se pudo enviar el correo: " + R.safe_error(e)
    masked = re.sub(r"(^.).*(@.*$)", r"\1•••\2", to)
    audit("enviado_por_correo_al_paciente", entity, entity_id, {"a": masked})
    return True, f"Enviado al correo del paciente ({masked})."


@bp.app_context_processor
def _mail_helpers():
    def mail_info(kind, obj_id):
        try:
            return {"ready": mail_ready(clinic_settings()), "sent": last_sent(get_db(), kind, obj_id)}
        except Exception:  # noqa: BLE001
            return {"ready": False, "sent": None}
    return {"mail_info": mail_info}
