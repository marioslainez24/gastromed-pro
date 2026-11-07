"""Cálculos rápidos con los últimos laboratorios del expediente (v0.13.0).

Para cada calculadora de hepatología muestra qué datos encontró (con su fecha), qué falta y, si todos los datos están en el
expediente, un resultado PRELIMINAR. Para guardarlo, el médico abre la calculadora, revisa los valores y sus fechas y confirma
(misma regla de siempre). Los datos clínicos (ascitis, encefalopatía, diálisis…) nunca se suponen.
"""
from datetime import date

from . import calculators as C
from .util import age as age_txt
from .views_labs import latest_values

CODES = ()   # NeuroMed Pro: sin cálculos automáticos de hepatología


def _age_years(birth):
    a = age_txt(birth) if birth else ""
    return a.split()[0] if a.endswith("años") else None


def quick(db, p, approved=None):
    out = []
    for code in CODES:
        calc = C.BY_CODE.get(code)
        if not calc:
            continue
        labs = latest_values(db, p["id"], [f.lab for f in calc.fields if f.lab])
        values, found, missing, oldest = {}, [], [], None
        for f in calc.fields:
            if f.lab and f.lab in labs:
                r = labs[f.lab]
                if (r["unit"] or "") == (f.unit or "") or f.unit.startswith(r["unit"] or "~"):
                    values[f.key] = f"{r['value_num']:g}"
                    found.append((f.label, f"{r['value_num']:g} {r['unit'] or ''}".strip(), r["taken_on"]))
                    oldest = min(oldest or r["taken_on"], r["taken_on"])
                    continue
            if f.key == "edad" and _age_years(p["birth_date"]):
                values["edad"] = _age_years(p["birth_date"])
                continue
            if f.key == "sexo" and p["sex"] in ("femenino", "masculino"):
                values["sexo"] = p["sex"]
                continue
            if not f.required:
                continue
            missing.append(f.label)
        preview = None
        if not missing:
            try:
                preview = C.run(calc, values)["texto"]
            except C.MissingData:
                preview = None
            except Exception:
                preview = None
        if not found:
            continue
        days = (date.today() - date.fromisoformat(oldest)).days if oldest else None
        out.append({"code": code, "name": calc.name, "found": found, "missing": missing, "preview": preview, "oldest": oldest,
                    "old": days is not None and days > 90, "approved": bool(approved and (code, calc.version) in approved)})
    return out
