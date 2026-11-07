"""Resumen del paciente en una pantalla (v0.13.0): lo esencial para la consulta, tomado del expediente sin interpretar."""
import json

from . import endoscopy_defs as D
from .views_notes import legacy_plan_text
from .db import utcnow


def summary(db, p, approved=None):
    pid = p["id"]
    out = {}
    out["problems"] = [r["description"] for r in db.execute(
        "SELECT description FROM patient_problems WHERE patient_id = ? AND status = 'activo' ORDER BY recorded_at", (pid,))]
    out["meds"] = [(r["name"] + (f" {r['dose']}" if r["dose"] else "")) for r in db.execute(
        "SELECT name, dose FROM patient_medications WHERE patient_id = ? AND status = 'activo' ORDER BY recorded_at", (pid,))]
    # Última consulta finalizada: fecha y diagnósticos escritos
    n = db.execute("SELECT id, finalized_at, fields FROM clinical_notes WHERE patient_id = ? AND status = 'finalizada'"
                   " ORDER BY finalized_at DESC LIMIT 1", (pid,)).fetchone()
    if n:
        f = json.loads(n["fields"])
        dx = (f.get("diagnosticos") or f.get("impresion") or "").strip()
        out["last_note"] = {"id": n["id"], "at": n["finalized_at"], "dx": [x for x in dx.splitlines() if x.strip()][:4],
                            "plan": ((f.get("plan") or "").strip() or legacy_plan_text(f))[:240]}
    # Último estudio endoscópico finalizado de cada tipo
    procs = []
    for r in db.execute("SELECT id, kind, performed_on, data, surveillance_due FROM procedures WHERE patient_id = ? AND status = 'finalizado'"
                        " AND discarded_at IS NULL ORDER BY performed_on DESC", (pid,)):
        if r["kind"] in {x["kind"] for x in procs}:
            continue
        concl = (json.loads(r["data"]).get("conclusion") or "").strip()
        procs.append({"id": r["id"], "kind": r["kind"], "label": D.KINDS[r["kind"]], "on": r["performed_on"],
                      "concl": [x for x in concl.splitlines() if x.strip()][:3], "due": r["surveillance_due"]})
    out["procs"] = procs
    out["path"] = db.execute("SELECT s.jar, s.site, s.status, s.result_category, pr.id AS proc_id, pr.performed_on FROM specimens s"
                             " JOIN procedures pr ON pr.id = s.procedure_id WHERE pr.patient_id = ? AND s.status IN"
                             " ('pendiente_envio','enviado','resultado_recibido') ORDER BY pr.performed_on DESC", (pid,)).fetchall()
    # Últimos laboratorios (uno por prueba) con el valor anterior para la tendencia
    by_code = {}
    for r in db.execute("SELECT r.test_code, t.name, r.value_num, r.value_text, r.unit, r.flag, r.taken_on FROM lab_results r"
                        " JOIN lab_tests t ON t.code = r.test_code WHERE r.patient_id = ? AND r.status <> 'anulado'"
                        " ORDER BY r.taken_on DESC, r.entered_at DESC", (pid,)):
        by_code.setdefault(r["test_code"], []).append(r)
    labs = []
    for code, rows in list(by_code.items())[:10]:
        last = rows[0]
        prev = next((x["value_num"] for x in rows[1:] if x["value_num"] is not None), None)
        trend = None if prev is None or last["value_num"] is None else (
            "↑" if last["value_num"] > prev else "↓" if last["value_num"] < prev else "=")
        labs.append({"code": code, "name": last["name"], "value": last["value_num"], "text": last["value_text"], "unit": last["unit"],
                     "flag": last["flag"], "on": last["taken_on"], "prev": prev, "trend": trend})
    out["labs"] = labs
    # Pendientes
    out["pending"] = {
        "orders": db.execute("SELECT o.id, o.order_type, o.created_at, (SELECT GROUP_CONCAT(description, ', ') FROM order_items i"
                             " WHERE i.order_id = o.id) AS items FROM orders o WHERE o.patient_id = ? AND o.status IN"
                             " ('solicitada','resultado_parcial') ORDER BY o.created_at DESC", (pid,)).fetchall(),
        "to_review": db.execute("SELECT COUNT(*) FROM lab_results WHERE patient_id = ? AND status = 'pendiente_revision'", (pid,)).fetchone()[0],
        "tasks": db.execute("SELECT title, due_on FROM tasks WHERE patient_id = ? AND status = 'abierta' ORDER BY due_on", (pid,)).fetchall(),
        "draft_notes": db.execute("SELECT COUNT(*) FROM clinical_notes WHERE patient_id = ? AND status = 'borrador' AND discarded_at IS NULL",
                                  (pid,)).fetchone()[0],
        "draft_procs": db.execute("SELECT COUNT(*) FROM procedures WHERE patient_id = ? AND status = 'borrador' AND discarded_at IS NULL",
                                  (pid,)).fetchone()[0],
    }
    out["pending"]["drafts"] = out["pending"]["draft_notes"] + out["pending"]["draft_procs"]
    out["next_appt"] = db.execute("SELECT id, starts_at, appt_type FROM appointments WHERE patient_id = ? AND starts_at > ?"
                                  " AND status IN ('solicitada','confirmada') ORDER BY starts_at LIMIT 1", (pid, utcnow())).fetchone()
    due = [x for x in procs if x["due"]]
    out["surveillance"] = min(due, key=lambda x: x["due"]) if due else None
    from .quick_calcs import quick
    out["calcs"] = quick(db, p, approved)
    # NeuroMed Pro: últimos códigos ACV del paciente
    out["acv"] = db.execute("SELECT id, status, created_at, summary FROM stroke_codes WHERE patient_id = ? ORDER BY created_at DESC LIMIT 3",
                            (pid,)).fetchall()
    return out
