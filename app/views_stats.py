"""Estadísticas del consultorio (v0.19.0).

Cuenta lo registrado en el programa: consultas finalizadas, estudios endoscópicos finalizados, pacientes nuevos, diagnósticos más
frecuentes (texto escrito por el médico, agrupado tal cual) e indicadores de calidad de colonoscopia (los mismos de
Endoscopia → Indicadores de calidad). Se exporta a Excel solo con números agregados: sin nombres ni datos de pacientes.
"""
import json
import re
from collections import Counter
from datetime import date

from flask import Blueprint, abort, g, make_response, render_template, request
from markupsafe import Markup

from . import endoscopy_defs as D
from .charts import bars_svg
from .db import get_db
from .security import audit, require
from .util import clinic_tz, local_today, parse_utc

bp = Blueprint("stats", __name__, url_prefix="/estadisticas")

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
KIND_ORDER = ["eda", "colonoscopia", "rectosigmoidoscopia", "cpre", "use"]


def _months(start, end):
    y, m = start.year, start.month
    out = []
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _label(ym):
    return f"{MESES[int(ym[5:]) - 1]} {ym[2:4]}"


def _dx_lines(text):
    """Líneas de diagnóstico normalizadas para contar: sin viñetas, numeración ni espacios dobles."""
    for line in (text or "").splitlines():
        t = re.sub(r"^\s*(?:[-•*·]|\d+[.)-])\s*", "", line).strip().rstrip(".")
        t = re.sub(r"\s+", " ", t)
        if len(t) >= 3:
            yield t


def _top(counter, n=15):
    # agrupa sin distinguir mayúsculas, mostrando la forma más usada
    groups, shown = Counter(), {}
    for t, c in counter.items():
        k = t.lower()
        groups[k] += c
        if k not in shown or counter[shown[k]] < c:
            shown[k] = t
    return [(shown[k], c) for k, c in groups.most_common(n)]


def compute(db, org, start, end, author=None):
    months = _months(start, end)
    tz = clinic_tz()
    s_iso, e_iso = start.isoformat(), end.isoformat()
    who = " AND author_id = ?" if author else ""
    args = [author] if author else []
    consult = Counter()
    dx_consult = Counter()
    for r in db.execute("SELECT finalized_at, fields FROM clinical_notes WHERE org_id = ? AND status = 'finalizada' AND discarded_at IS NULL"
                        + who, [org] + args):
        d = parse_utc(r["finalized_at"]).astimezone(tz).date()
        if start <= d <= end:
            consult[d.isoformat()[:7]] += 1
            f = json.loads(r["fields"])
            for t in _dx_lines(f.get("diagnosticos") or f.get("impresion")):
                dx_consult[t] += 1
    procs = {k: Counter() for k in KIND_ORDER}
    dx_endo = Counter()
    by_care = Counter()          # v0.22: estudios por tipo de atención y lugar
    for r in db.execute("SELECT kind, performed_on, data FROM procedures WHERE org_id = ? AND status = 'finalizado' AND discarded_at IS NULL"
                        " AND performed_on BETWEEN ? AND ?" + who, [org, s_iso, e_iso] + args):
        procs[r["kind"]][r["performed_on"][:7]] += 1
        pd = json.loads(r["data"])
        by_care[(D.CARE_SETTINGS.get(pd.get("care_setting") or "", "Sin indicar"), (pd.get("facility") or "").strip() or "Su clínica")] += 1
        for t in _dx_lines(pd.get("conclusion")):
            dx_endo[t] += 1
    new_pat = Counter()
    for r in db.execute("SELECT created_at FROM patients WHERE org_id = ?", (org,)):
        d = parse_utc(r["created_at"]).astimezone(tz).date()
        if start <= d <= end:
            new_pat[d.isoformat()[:7]] += 1
    rows = [{"ym": m, "label": _label(m), "consultas": consult[m], "pacientes": new_pat[m],
             **{k: procs[k][m] for k in KIND_ORDER}} for m in months]
    totals = {k: sum(r[k] for r in rows) for k in ["consultas", "pacientes"] + KIND_ORDER}
    from .views_endoscopy import quality_metrics
    return {"rows": rows, "totals": totals, "dx_consult": _top(dx_consult), "dx_endo": _top(dx_endo),
            "by_care": [(c, f, n) for (c, f), n in sorted(by_care.items(), key=lambda x: (-x[1], x[0]))],
            "quality": quality_metrics(db, org, s_iso, e_iso, author)}


def _period():
    today = local_today()
    default_start = date(today.year - 1, today.month, 1) if today.month < 12 else date(today.year, 1, 1)
    try:
        start = date.fromisoformat(request.args.get("desde") or default_start.isoformat())
        end = date.fromisoformat(request.args.get("hasta") or today.isoformat())
    except ValueError:
        abort(400)
    if start > end or (end - start).days > 366 * 5:
        abort(400, description="Periodo no válido (máximo 5 años).")
    return start, end


def _authors(db):
    return db.execute("SELECT DISTINCT u.id, u.full_name FROM users u WHERE u.org_id = ? AND (EXISTS (SELECT 1 FROM procedures p"
                      " WHERE p.author_id = u.id) OR EXISTS (SELECT 1 FROM clinical_notes n WHERE n.author_id = u.id)) ORDER BY u.full_name",
                      (g.user["org_id"],)).fetchall()


@bp.route("")
@require("clinico.ver")
def index():
    db = get_db()
    start, end = _period()
    users = _authors(db)
    author = request.args.get("profesional") or None
    if author and author not in {u["id"] for u in users}:
        author = None
    st = compute(db, g.user["org_id"], start, end, author)
    labels = [r["label"] for r in st["rows"]]
    chart_activity = Markup(bars_svg(labels, [("Consultas", [r["consultas"] for r in st["rows"]], "bar-1"),
                                              ("Endoscopias altas", [r["eda"] for r in st["rows"]], "bar-2"),
                                              ("Colonoscopias", [r["colonoscopia"] for r in st["rows"]], "bar-3")],
                                     title="Consultas y estudios por mes"))
    audit("estadisticas_consultadas", "estadisticas", None, {"desde": start.isoformat(), "hasta": end.isoformat()})
    return render_template("stats/index.html", st=st, start=start.isoformat(), end=end.isoformat(), users=users, author=author,
                           chart=chart_activity, KINDS=D.KINDS, KIND_ORDER=KIND_ORDER)


@bp.route("/excel")
@require("clinico.ver")
def excel():
    from .xlsx import workbook
    db = get_db()
    start, end = _period()
    users = _authors(db)
    author = request.args.get("profesional") or None
    if author and author not in {u["id"] for u in users}:
        author = None
    st = compute(db, g.user["org_id"], start, end, author)
    head = ["Mes", "Consultas finalizadas", "Pacientes nuevos"] + [D.KINDS[k] for k in KIND_ORDER]
    by_month = [head] + [[r["ym"], r["consultas"], r["pacientes"]] + [r[k] for k in KIND_ORDER] for r in st["rows"]]
    by_month.append(["Total", st["totals"]["consultas"], st["totals"]["pacientes"]] + [st["totals"][k] for k in KIND_ORDER])
    quality = [["Indicador", "Numerador", "Denominador", "Porcentaje", "Definición"]] + [
        [n, a, b, round(100 * a / b, 1) if b else "", desc] for n, a, b, desc in st["quality"]]
    who = next((u["full_name"] for u in users if u["id"] == author), "Todos")
    info = [["Dato", "Valor"], ["Periodo", f"{start.isoformat()} a {end.isoformat()}"], ["Profesional", who],
            ["Generado con", "NeuroMed Pro"], ["Contenido", "Solo números agregados; no incluye datos de pacientes."]]
    data = workbook([("Por mes", by_month), ("Diagnósticos de consulta", [["Diagnóstico", "Veces"]] + st["dx_consult"]),
                     ("Diagnósticos endoscópicos", [["Diagnóstico", "Veces"]] + st["dx_endo"]),
                     ("Atención y lugar", [["Atención", "Lugar", "Estudios"]] + [list(x) for x in st["by_care"]]), ("Calidad colonoscopia", quality),
                     ("Información", info)])
    audit("estadisticas_exportadas", "estadisticas", None, {"desde": start.isoformat(), "hasta": end.isoformat()})
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    resp.headers["Content-Disposition"] = f'attachment; filename="estadisticas-{start.isoformat()}-a-{end.isoformat()}.xlsx"'
    return resp
