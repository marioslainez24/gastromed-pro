"""Código ACV (NeuroMed Pro 1.0): tiempos, elegibilidad para reperfusión, dosis del trombolítico y resumen.

Herramienta de APOYO para el médico que atiende un ACV agudo. No decide ni ordena: muestra qué criterio falta o está presente y
calcula la dosis por peso; el médico confirma cada dato y sigue el protocolo de su hospital.

Fuentes:
- Powers WJ et al. Guidelines for the early management of patients with acute ischemic stroke: 2019 update. Stroke 2019;50:e344-e418
  (ventana de 4.5 h, PA < 185/110 antes y < 180/105 después, glucosa, contraindicaciones, metas puerta-TC ≤ 20 min y puerta-aguja ≤ 60 min).
- Berge E et al. ESO guidelines on intravenous thrombolysis. Eur Stroke J 2021;6:I-LXII; Alamowitch S et al. ESO 2023 (tenecteplasa 0.25 mg/kg).
- Nogueira RG et al. N Engl J Med 2018;378:11-21 (DAWN) y Albers GW et al. N Engl J Med 2018;378:708-18 (DEFUSE 3): trombectomía 6–24 h.
- Sarraj A et al. N Engl J Med 2023;388:1259-71 (SELECT2) y Huo X et al. N Engl J Med 2023;388:1272-83 (ANGEL-ASPECT): núcleo extenso.
Dosis: alteplasa 0.9 mg/kg (máximo 90 mg), 10 % en bolo en 1 minuto y el resto en 60 minutos; tenecteplasa 0.25 mg/kg (máximo 25 mg)
en bolo único. Concentraciones: alteplasa 1 mg/mL y tenecteplasa 5 mg/mL una vez reconstituidas.
"""
import re

TIME_KEYS = [("lkw", "Último momento visto bien"), ("arr", "Llegada a urgencias"), ("ct", "TAC de cráneo"),
             ("needle", "Inicio del trombolítico"), ("groin", "Punción femoral")]

CONTRAINDICATIONS = [
    ("hic", "Hemorragia intracraneal en la TAC"),
    ("hypo", "Hipodensidad extensa y clara en la TAC (infarto ya establecido)"),
    ("sah", "Clínica sugestiva de hemorragia subaracnoidea"),
    ("isc3", "ACV isquémico en los últimos 3 meses"),
    ("tce3", "Traumatismo craneoencefálico grave en los últimos 3 meses"),
    ("neuro3", "Cirugía intracraneal o medular en los últimos 3 meses"),
    ("prevhic", "Antecedente de hemorragia intracraneal"),
    ("neo", "Neoplasia intracraneal intraaxial"),
    ("gi", "Neoplasia o sangrado gastrointestinal en los últimos 21 días"),
    ("coag", "Plaquetas < 100 000, INR > 1.7, TTPa > 40 s o TP > 15 s"),
    ("lmwh", "Heparina de bajo peso molecular a dosis plena en las últimas 24 h"),
    ("doac", "Anticoagulante oral directo en las últimas 48 h (salvo pruebas específicas normales)"),
    ("endo", "Sospecha de endocarditis infecciosa"),
    ("dis", "Sospecha de disección del arco aórtico"),
]
CI_LABEL = dict(CONTRAINDICATIONS)
AGENTS = {"tnk": "Tenecteplasa 0.25 mg/kg", "tpa": "Alteplasa 0.9 mg/kg"}
WINDOW_LYSIS = 270      # 4.5 h
WINDOW_EARLY_EVT = 360  # 6 h
WINDOW_LATE_EVT = 1440  # 24 h
GOALS = {"ct": 20, "needle": 60, "groin": 90}
_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
NUMS = {"w": (1, 400), "pas": (40, 300), "pad": (20, 200), "glu": (10, 1500), "nihss": (0, 42), "aspects": (0, 10)}


def empty():
    return {"lkw": "", "arr": "", "ct": "", "needle": "", "groin": "", "wake": False, "w": "", "pas": "", "pad": "", "glu": "",
            "nihss": "", "agent": "tnk", "lvo": False, "aspects": "", "prem": 0, "ci": [], "notes": ""}


def clean(src) -> tuple[dict, list]:
    """De un formulario (MultiDict) a datos validados. Devuelve (datos, errores)."""
    d, errors = empty(), []
    for k, label in TIME_KEYS:
        v = (src.get(k) or "").strip()
        if v and not _HM.match(v):
            errors.append(f"«{label}»: escriba la hora como 14:35.")
            v = ""
        d[k] = v
    for k, (lo, hi) in NUMS.items():
        raw = (src.get(k) or "").strip().replace(",", ".")
        if not raw:
            continue
        try:
            x = float(raw)
        except ValueError:
            errors.append(f"Valor no válido en {k}.")
            continue
        if not lo <= x <= hi:
            errors.append(f"Valor fuera de rango plausible ({lo}–{hi}). Revíselo.")
            continue
        d[k] = int(x) if x.is_integer() else x
    d["wake"] = src.get("wake") == "1"
    d["lvo"] = src.get("lvo") == "1"
    d["agent"] = src.get("agent") if src.get("agent") in AGENTS else "tnk"
    try:
        d["prem"] = max(0, min(5, int(src.get("prem") or 0)))
    except ValueError:
        d["prem"] = 0
    d["ci"] = [k for k, _ in CONTRAINDICATIONS if k in src.getlist("ci")]
    d["notes"] = (src.get("notes") or "").replace("\r\n", "\n").strip()[:3000]
    return d, errors


def span(a: str, b: str):
    """Minutos de a hasta b (hh:mm); si b es menor, se asume que pasó la medianoche."""
    if not a or not b:
        return None
    ma, mb = int(a[:2]) * 60 + int(a[3:]), int(b[:2]) * 60 + int(b[3:])
    return (mb - ma) % 1440


def hm(m) -> str:
    if m is None:
        return "—"
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def evaluate(d: dict, now_hm: str) -> dict:
    """Estado de la trombólisis y de la trombectomía. now_hm = hora actual de la clínica (hh:mm)."""
    el = span(d["lkw"], d["needle"] or now_hm) if d["lkw"] else None
    if not d["lkw"] and not d["wake"]:
        lysis = ("warn", "Falta la hora del último momento visto bien", "Es el dato que define la ventana terapéutica.")
    elif d["ci"]:
        lysis = ("crit", "Trombólisis contraindicada", "; ".join(CI_LABEL[k] for k in d["ci"]) + ".")
    elif d["wake"]:
        lysis = ("warn", "Inicio desconocido o al despertar",
                 "Valorar resonancia (desacople difusión-FLAIR) o perfusión para decidir la trombólisis.")
    elif el > WINDOW_LYSIS:
        lysis = ("warn", "Fuera de la ventana de trombólisis intravenosa (más de 4.5 h)",
                 "Si hay oclusión de gran vaso, valorar trombectomía hasta 24 h con criterios de imagen.")
    elif d["glu"] != "" and d["glu"] < 50:
        lysis = ("warn", "Hipoglucemia: corregir y reevaluar", "La hipoglucemia puede simular un ACV.")
    elif d["pas"] != "" and (d["pas"] >= 185 or (d["pad"] != "" and d["pad"] >= 110)):
        lysis = ("warn", "Bajar la presión arterial antes de iniciar",
                 "Meta menor de 185/110 mmHg antes del trombolítico y menor de 180/105 mmHg durante 24 horas.")
    else:
        lysis = ("ok", "Sin contraindicaciones marcadas: candidato a trombólisis intravenosa",
                 f"Dentro de la ventana: {hm(el)} desde el último momento visto bien; quedan {hm(WINDOW_LYSIS - el)}.")
    if not d["lvo"]:
        evt = ("ok", "Trombectomía no indicada sin oclusión de gran vaso",
               "Si la sospecha clínica es alta (NIHSS 6 o más, signos corticales), confirmar con angio-TAC.")
    elif d["prem"] >= 2:
        evt = ("warn", "Oclusión de gran vaso con discapacidad previa (Rankin 2 o más)",
               "Decidir individualmente con neurointervención y la familia.")
    elif el is not None and el <= WINDOW_EARLY_EVT:
        note = ""
        if d["aspects"] != "" and d["aspects"] < 3:
            note = "ASPECTS menor de 3: evidencia limitada, decidir con neurointervención. "
        elif d["aspects"] != "" and d["aspects"] < 6:
            note = "ASPECTS 3 a 5: beneficio demostrado en pacientes seleccionados (ensayos de 2023). "
        evt = ("crit", "Activar neurointervención: candidato a trombectomía",
               note + "No retrasar la trombólisis si está indicada: se hacen en paralelo.")
    elif el is not None and el <= WINDOW_LATE_EVT:
        evt = ("warn", "Ventana tardía (6 a 24 h): requiere imagen de perfusión",
               "Seleccionar con criterios DAWN o DEFUSE 3 (desacople clínica-núcleo o núcleo-penumbra).")
    elif el is not None:
        evt = ("warn", "Más de 24 horas desde el último momento visto bien", "Fuera de las ventanas de los ensayos de trombectomía.")
    else:
        evt = ("warn", "Registre la hora del último momento visto bien", "Sin ella no se puede definir la ventana de trombectomía.")
    metrics = {k: span(d["arr"], d[k]) for k in GOALS}
    return {"elapsed": el, "lysis": lysis, "evt": evt, "metrics": metrics}


def dose(d: dict):
    """Dosis del trombolítico elegido según el peso. None si no hay peso."""
    if d["w"] == "":
        return None
    w = float(d["w"])
    if d["agent"] == "tnk":
        mg = min(0.25 * w, 25.0)
        return {"total_mg": round(mg, 1), "texto": f"Tenecteplasa {mg:.1f} mg en bolo intravenoso único de 5 segundos "
                                                    f"({mg / 5:.1f} mL a 5 mg/mL)" + (" · dosis máxima" if 0.25 * w >= 25 else "") + "."}
    mg = min(0.9 * w, 90.0)
    bolus = round(mg * 0.1, 1)
    return {"total_mg": round(mg, 1), "bolo_mg": bolus,
            "texto": f"Alteplasa {mg:.1f} mg en total: bolo de {bolus:.1f} mg intravenoso en 1 minuto y {mg - bolus:.1f} mg en "
                     "infusión de 60 minutos (1 mg/mL)" + (" · dosis máxima" if 0.9 * w >= 90 else "") + "."}


def summary(d: dict, ev: dict, ds) -> str:
    parts = []
    parts.append("Inicio desconocido o al despertar." if d["wake"] else f"Último momento visto bien: {d['lkw']}." if d["lkw"] else "")
    if d["arr"]:
        parts.append(f"Llegada: {d['arr']}.")
    if d["ct"]:
        parts.append(f"TAC: {d['ct']} (puerta-TAC {hm(ev['metrics']['ct'])}).")
    parts.append(f"PA {d['pas'] or '—'}/{d['pad'] or '—'} mmHg, glucosa {d['glu'] if d['glu'] != '' else '—'} mg/dL, "
                 f"NIHSS {d['nihss'] if d['nihss'] != '' else '—'}, Rankin previo {d['prem']}.")
    parts.append("Contraindicaciones para trombólisis: " + "; ".join(CI_LABEL[k].lower() for k in d["ci"]) + "." if d["ci"]
                 else "Sin contraindicaciones para trombólisis registradas.")
    if d["needle"]:
        parts.append(f"{AGENTS[d['agent']].split(' ')[0]} iniciada a las {d['needle']} (puerta-aguja {hm(ev['metrics']['needle'])})."
                     + (f" {ds['texto']}" if ds else ""))
    else:
        lab = ev["lysis"][1]
        parts.append(f"Trombólisis: {lab[0].lower() + lab[1:]}.")
    if d["lvo"]:
        parts.append("Oclusión de gran vaso" + (f", ASPECTS {d['aspects']}" if d["aspects"] != "" else "") + ". "
                     + (f"Punción femoral {d['groin']} (puerta-punción {hm(ev['metrics']['groin'])})." if d["groin"] else ev["evt"][1] + "."))
    else:
        parts.append("Sin oclusión de gran vaso registrada.")
    if d["notes"]:
        parts.append(d["notes"])
    return " ".join(p for p in parts if p)
