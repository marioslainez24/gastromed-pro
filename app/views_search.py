"""Búsqueda en todos los expedientes (v0.19.0).

El médico escribe un diagnóstico o palabra (p. ej., «Barrett», «colitis ulcerosa») y ve los pacientes donde aparece: lista de
problemas activos, antecedentes, diagnósticos de consultas finalizadas y conclusiones de estudios endoscópicos finalizados. Para cada
paciente muestra el último estudio y la fecha de control indicada. No distingue mayúsculas ni tildes. Solo personal clínico.
"""
import json
import unicodedata

from flask import Blueprint, g, render_template, request

from . import endoscopy_defs as D
from .db import get_db
from .security import audit, require
from .util import local_today

bp = Blueprint("search", __name__, url_prefix="/buscar-expedientes")

MAX_PATIENTS = 200


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _lines(text):
    return [x.strip(" -•*·") for x in (text or "").splitlines() if x.strip()]


def search(db, org, q):
    terms = [t for t in norm(q).split() if t]
    if not terms:
        return []

    def hit(text):
        n = norm(text)
        return all(t in n for t in terms)

    found = {}

    def add(pid, source, text, on, link=None):
        found.setdefault(pid, []).append({"source": source, "text": text[:220], "on": on, "link": link})

    for r in db.execute("SELECT pp.patient_id, pp.description, pp.recorded_at FROM patient_problems pp JOIN patients p ON p.id = pp.patient_id"
                        " WHERE p.org_id = ? AND pp.status = 'activo'", (org,)):
        if hit(r["description"]):
            add(r["patient_id"], "Problema activo", r["description"], r["recorded_at"][:10])
    for r in db.execute("SELECT h.patient_id, h.description, h.category, h.recorded_at FROM patient_history h JOIN patients p ON p.id = h.patient_id"
                        " WHERE p.org_id = ? AND h.active = 1", (org,)):
        if hit(r["description"]):
            add(r["patient_id"], "Antecedente", r["description"], r["recorded_at"][:10])
    for r in db.execute("SELECT id, patient_id, finalized_at, fields FROM clinical_notes WHERE org_id = ? AND status = 'finalizada'"
                        " AND discarded_at IS NULL", (org,)):
        f = json.loads(r["fields"])
        for line in _lines(f.get("diagnosticos") or f.get("impresion")):
            if hit(line):
                add(r["patient_id"], "Diagnóstico de consulta", line, r["finalized_at"][:10], ("notes.view", {"note_id": r["id"]}))
    for r in db.execute("SELECT id, patient_id, kind, performed_on, data FROM procedures WHERE org_id = ? AND status = 'finalizado'"
                        " AND discarded_at IS NULL", (org,)):
        for line in _lines(json.loads(r["data"]).get("conclusion")):
            if hit(line):
                add(r["patient_id"], D.KINDS[r["kind"]], line, r["performed_on"], ("endo.proc_view", {"proc_id": r["id"]}))
    if not found:
        return []
    out = []
    ids = list(found)[:MAX_PATIENTS * 5]
    marks = ",".join("?" * len(ids))
    pats = {r["id"]: r for r in db.execute(f"SELECT id, first_names, last_names, mrn, birth_date FROM patients WHERE id IN ({marks})", ids)}
    today = local_today().isoformat()
    for pid, hits in found.items():
        p = pats.get(pid)
        if not p:
            continue
        last = db.execute("SELECT id, kind, performed_on, surveillance_due FROM procedures WHERE patient_id = ? AND status = 'finalizado'"
                          " AND discarded_at IS NULL ORDER BY performed_on DESC LIMIT 1", (pid,)).fetchone()
        due = db.execute("SELECT MIN(surveillance_due) FROM procedures pr WHERE patient_id = ? AND status = 'finalizado' AND discarded_at IS NULL"
                         " AND surveillance_due IS NOT NULL AND NOT EXISTS (SELECT 1 FROM procedures p2 WHERE p2.patient_id = pr.patient_id"
                         " AND p2.kind = pr.kind AND p2.status = 'finalizado' AND p2.discarded_at IS NULL AND p2.performed_on > pr.performed_on)",
                         (pid,)).fetchone()[0]
        hits.sort(key=lambda h: h["on"] or "", reverse=True)
        out.append({"p": p, "hits": hits, "last": last, "due": due, "overdue": bool(due and due < today)})
    out.sort(key=lambda x: (not x["overdue"], x["due"] or "9999", (x["p"]["last_names"] or "").lower()))
    return out[:MAX_PATIENTS]


@bp.route("")
@require("clinico.ver")
def index():
    q = (request.args.get("q") or "").strip()[:80]
    rows = None
    if len(q) >= 3:
        rows = search(get_db(), g.user["org_id"], q)
        audit("busqueda_expedientes", "busqueda", None, {"texto": q, "pacientes": len(rows)})
    return render_template("search/index.html", q=q, rows=rows, KINDS=D.KINDS, today=local_today().isoformat(), MAX=MAX_PATIENTS)
