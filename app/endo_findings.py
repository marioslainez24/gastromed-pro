"""Hallazgos de endoscopia con clics (v0.13.0).

El médico elige un hallazgo en un segmento, completa sus datos (grado, tamaño, localización…) y el programa redacta la frase
para ese segmento y SUGIERE el diagnóstico correspondiente del catálogo (endo_diagnoses) para la conclusión; el médico decide
si lo agrega. La frase contiene solo lo marcado. Cada clic en «Agregar» suma una frase (para varios pólipos, agregar uno por vez).
Clasificaciones: las verificadas en endoscopy_defs (Los Ángeles, Forrest, París, Praga, Sarin, Zargar, NICE).
"""
from . import endo_diagnoses as DX

CATALOG = {t: (c, a) for _, _, t, c, a in DX.DIAGNOSES}


def P(name, label, kind="select", options=None, required=True, unit=""):
    return {"name": name, "label": label, "kind": kind, "options": options or [], "required": required, "unit": unit}


LA = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]
FORREST = [("Ia", "Ia (sangrado en chorro)"), ("Ib", "Ib (sangrado en capa)"), ("IIa", "IIa (vaso visible)"), ("IIb", "IIb (coágulo adherido)"),
           ("IIc", "IIc (mancha pigmentada)"), ("III", "III (fondo limpio)")]
GASTRIC_LOC = [("fondo", "fondo"), ("cuerpo", "cuerpo"), ("angulo", "ángulo"), ("antro", "antro"), ("prepilorica", "región prepilórica")]
DUO_LOC = [("bulbo_ant", "cara anterior del bulbo"), ("bulbo_post", "cara posterior del bulbo"), ("bulbo", "bulbo"),
           ("segunda", "segunda porción")]
COLON_LOC = [("ileon", "íleon terminal"), ("ciego", "ciego"), ("ascendente", "colon ascendente"), ("hepatico", "ángulo hepático"),
             ("transverso", "colon transverso"), ("esplenico", "ángulo esplénico"), ("descendente", "colon descendente"),
             ("sigmoides", "sigmoides"), ("recto", "recto")]
PARIS = [("0-Ip", "0-Ip pediculado"), ("0-Is", "0-Is sésil"), ("0-IIa", "0-IIa ligeramente elevado"), ("0-IIb", "0-IIb plano"),
         ("0-IIc", "0-IIc ligeramente deprimido")]
NICE = [("1", "NICE 1"), ("2", "NICE 2"), ("3", "NICE 3")]
RESECTION = [("asa_fria", "asa fría"), ("asa_caliente", "asa caliente"), ("pinza", "pinza de biopsia"), ("mucosectomia", "mucosectomía"),
             ("no", "no resecado")]


def _forrest_dx(organ, f):
    label = dict(FORREST)[f]
    return f"Úlcera {organ} Forrest {label}"


def _polyp_sentence(v, r):
    s = (f"{v['cantidad']} pólipos" if r.get("cantidad") not in (None, "", "1") else "Pólipo") + f" de {v['mm']} mm en {v['loc']}"
    extra = [x for x in [f"París {r['paris']}" if r.get("paris") else None, v.get("nice")] if x]
    if extra:
        s += ", " + ", ".join(extra)
    if r.get("reseccion") == "no":
        s += ", no resecado"
    elif r.get("reseccion"):
        s += f", resecado con {v['reseccion']}"
        if r.get("recuperado") == "si":
            s += " y recuperado"
        elif r.get("recuperado") == "no":
            s += ", no recuperado"
    return s + "."


def _polyp_dx(v, r):
    if r.get("nice") == "3":
        return "Lesión de colon NICE 3 (sospecha de invasión submucosa profunda), pendiente de histología"
    if r.get("loc") == "recto":
        return "Pólipo de recto"
    if r.get("cantidad") not in (None, "", "1"):
        return "Pólipos de colon múltiples"
    return {"1": "Pólipo de colon NICE 1 (aspecto hiperplásico o serrado)", "2": "Pólipo de colon NICE 2 (aspecto adenomatoso)"}.get(
        r.get("nice"), "Pólipo de colon")


def _divert_dx(v, r):
    locs = r.get("loc") or []
    if locs == ["sigmoides"]:
        return "Enfermedad diverticular de colon sigmoides"
    if len(locs) >= 4:
        return "Enfermedad diverticular de colon (pancolónica)"
    return "Enfermedad diverticular de colon"


FINDINGS = {
    "esofago": [
        ("esofagitis", "Esofagitis erosiva (Los Ángeles)", [P("grado", "Grado de Los Ángeles", options=LA)],
         lambda v, r: f"Erosiones de la mucosa del esófago distal compatibles con esofagitis grado {r['grado']} de Los Ángeles.",
         lambda v, r: f"Esofagitis erosiva grado {r['grado']} de Los Ángeles"),
        ("barrett", "Esófago de Barrett (Praga)", [P("c", "Praga C", "number", unit="cm"), P("m", "Praga M", "number", unit="cm")],
         lambda v, r: f"Mucosa de aspecto columnar que asciende por el esófago distal, Praga C{v['c']} M{v['m']}.",
         lambda v, r: ("Esófago de Barrett (Praga C__ M__), pendiente de histología",
                       f"Esófago de Barrett (Praga C{v['c']} M{v['m']}), pendiente de histología")),
        ("varices", "Várices esofágicas", [P("tam", "Tamaño", options=[("pequenas", "pequeñas (< 5 mm)"), ("grandes", "grandes (> 5 mm)")]),
                                           P("rojos", "Signos rojos", options=[("no", "sin signos rojos"), ("si", "con signos rojos")]),
                                           P("sangrado", "Sangrado", required=False,
                                             options=[("activo", "con sangrado activo"), ("estigmas", "con estigmas de sangrado reciente")])],
         lambda v, r: f"Várices esofágicas {v['tam']}, {v['rojos']}" + (f", {v['sangrado']}" if r.get("sangrado") else "") + ".",
         lambda v, r: "Várices esofágicas con sangrado activo o estigmas de sangrado reciente" if r.get("sangrado") else
         f"Várices esofágicas {'pequeñas (< 5 mm)' if r['tam'] == 'pequenas' else 'grandes (> 5 mm)'}, {'con' if r['rojos'] == 'si' else 'sin'} signos rojos"),
        ("candida", "Placas de aspecto candidiásico", [],
         lambda v, r: "Placas blanquecinas adheridas a la mucosa, de aspecto candidiásico.", lambda v, r: "Esofagitis de aspecto candidiásico"),
        ("eosinofilica", "Signos de esofagitis eosinofílica", [P("signos", "Signos", "multi", [("anillos", "anillos"), ("surcos", "surcos longitudinales"),
                                                                                             ("exudados", "exudados blanquecinos"), ("edema", "edema")])],
         lambda v, r: f"Mucosa con {v['signos']}, sugestivos de esofagitis eosinofílica.",
         lambda v, r: "Hallazgos sugestivos de esofagitis eosinofílica (anillos, surcos, exudados), pendiente de histología"),
        ("ulcera", "Úlcera esofágica", [P("mm", "Tamaño", "number", unit="mm"), P("cm", "Distancia de la arcada dentaria", "number", unit="cm", required=False)],
         lambda v, r: f"Úlcera esofágica de {v['mm']} mm" + (f" a {v['cm']} cm de la arcada dentaria" if r.get("cm") else "") + ".",
         lambda v, r: "Úlcera esofágica"),
        ("estenosis", "Estenosis", [P("cm", "Distancia de la arcada dentaria", "number", unit="cm"),
                                    P("paso", "Paso del endoscopio", options=[("si", "que permite el paso del endoscopio"),
                                                                              ("no", "que no permite el paso del endoscopio")])],
         lambda v, r: f"Estenosis a {v['cm']} cm de la arcada dentaria, {v['paso']}.", lambda v, r: "Estenosis esofágica"),
        ("caustico", "Lesión por cáusticos (Zargar)", [P("grado", "Grado de Zargar", options=[(x, x) for x in ("0", "1", "2a", "2b", "3a", "3b")])],
         lambda v, r: f"Lesión de la mucosa esofágica por cáusticos, grado {r['grado']} de Zargar.",
         lambda v, r: ("Lesión esofágica por cáusticos, grado __ de Zargar", f"Lesión esofágica por cáusticos, grado {r['grado']} de Zargar")),
        ("neoplasia", "Lesión de aspecto neoplásico", [P("cm", "Distancia de la arcada dentaria", "number", unit="cm")],
         lambda v, r: f"Lesión de aspecto neoplásico a {v['cm']} cm de la arcada dentaria.",
         lambda v, r: "Lesión esofágica de aspecto neoplásico, pendiente de histología"),
    ],
    "ueg": [
        ("hernia", "Hernia hiatal por deslizamiento", [P("cm", "Tamaño", "number", unit="cm")],
         lambda v, r: f"Hernia hiatal por deslizamiento de {v['cm']} cm.",
         lambda v, r: ("Hernia hiatal por deslizamiento de __ cm", f"Hernia hiatal por deslizamiento de {v['cm']} cm")),
        ("paraesofagica", "Hernia paraesofágica", [], lambda v, r: "Hernia paraesofágica.", lambda v, r: "Hernia paraesofágica"),
        ("mallory", "Desgarro de Mallory-Weiss", [], lambda v, r: "Desgarro longitudinal de la mucosa en la unión esofagogástrica.",
         lambda v, r: "Desgarro de Mallory-Weiss"),
        ("cardias", "Cardias que no abraza el endoscopio", [], lambda v, r: "En retroflexión, cardias que no abraza adecuadamente el endoscopio.",
         lambda v, r: None),
    ],
    "estomago": [
        ("eritema", "Eritema", [P("loc", "Localización", "multi", GASTRIC_LOC)],
         lambda v, r: f"Eritema de la mucosa en {v['loc']}.",
         lambda v, r: "Gastropatía eritematosa de antro" if r["loc"] == ["antro"] else "Gastropatía eritematosa"),
        ("erosiones", "Erosiones", [P("loc", "Localización", "multi", GASTRIC_LOC)],
         lambda v, r: f"Erosiones planas en {v['loc']}.", lambda v, r: "Gastropatía erosiva"),
        ("atrofia", "Aspecto atrófico", [P("loc", "Localización", "multi", GASTRIC_LOC)],
         lambda v, r: f"Mucosa de aspecto atrófico, con patrón vascular visible, en {v['loc']}.",
         lambda v, r: "Gastropatía de aspecto atrófico, pendiente de histología"),
        ("hipertensiva", "Gastropatía hipertensiva portal", [P("grado", "Grado", options=[("leve", "leve"), ("severa", "severa")])],
         lambda v, r: f"Patrón en mosaico de la mucosa compatible con gastropatía hipertensiva portal {v['grado']}.",
         lambda v, r: f"Gastropatía hipertensiva portal {r['grado']}"),
        ("varices_g", "Várices gástricas (Sarin)", [P("tipo", "Tipo de Sarin", options=[("GOV1", "GOV1"), ("GOV2", "GOV2"), ("IGV1", "IGV1"), ("IGV2", "IGV2")])],
         lambda v, r: f"Várices gástricas tipo {r['tipo']} de Sarin.", lambda v, r: f"Várices gástricas {r['tipo']} (Sarin)"),
        ("gave", "Ectasia vascular antral (GAVE)", [], lambda v, r: "Ectasias vasculares en el antro (GAVE).",
         lambda v, r: "Ectasia vascular antral (GAVE)"),
        ("ulcera_g", "Úlcera gástrica (Forrest)", [P("loc", "Localización", options=GASTRIC_LOC), P("mm", "Tamaño", "number", unit="mm"),
                                                   P("forrest", "Forrest", options=FORREST)],
         lambda v, r: f"Úlcera de {v['mm']} mm en {v['loc']}, Forrest {v['forrest']}.", lambda v, r: _forrest_dx("gástrica", r["forrest"])),
        ("polipo_g", "Pólipo gástrico", [P("cantidad", "Cantidad", "number", required=False), P("mm", "Tamaño", "number", unit="mm"),
                                         P("loc", "Localización", options=GASTRIC_LOC)],
         lambda v, r: (f"{v['cantidad']} pólipos" if r.get("cantidad") not in (None, "", "1") else "Pólipo") + f" de {v['mm']} mm en {v['loc']}.",
         lambda v, r: "Pólipo gástrico"),
        ("subepitelial", "Lesión subepitelial", [P("mm", "Tamaño", "number", unit="mm"), P("loc", "Localización", options=GASTRIC_LOC)],
         lambda v, r: f"Lesión subepitelial de {v['mm']} mm en {v['loc']}, con mucosa de superficie de aspecto normal.",
         lambda v, r: "Lesión subepitelial gástrica"),
        ("neoplasia_g", "Lesión de aspecto neoplásico", [P("loc", "Localización", options=GASTRIC_LOC)],
         lambda v, r: f"Lesión de aspecto neoplásico en {v['loc']}.", lambda v, r: "Lesión gástrica de aspecto neoplásico, pendiente de histología"),
        ("restos", "Restos alimentarios", [], lambda v, r: "Restos alimentarios en la cámara gástrica que limitan la evaluación.",
         lambda v, r: "Restos alimentarios en estómago (estudio limitado)"),
    ],
    "duodeno": [
        ("duodenitis", "Duodenitis erosiva de bulbo", [], lambda v, r: "Eritema y erosiones en el bulbo duodenal.",
         lambda v, r: "Duodenitis erosiva de bulbo"),
        ("ulcera_d", "Úlcera duodenal (Forrest)", [P("loc", "Localización", options=DUO_LOC), P("mm", "Tamaño", "number", unit="mm"),
                                                   P("forrest", "Forrest", options=FORREST)],
         lambda v, r: f"Úlcera de {v['mm']} mm en {v['loc']}, Forrest {v['forrest']}.", lambda v, r: _forrest_dx("duodenal", r["forrest"])),
        ("atrofia_d", "Pliegues disminuidos o festoneados", [],
         lambda v, r: "Disminución y festoneado de los pliegues en la segunda porción duodenal.",
         lambda v, r: "Atrofia de vellosidades duodenales (descartar enfermedad celíaca), pendiente de histología"),
        ("polipo_d", "Pólipo duodenal", [P("mm", "Tamaño", "number", unit="mm"), P("loc", "Localización", options=DUO_LOC)],
         lambda v, r: f"Pólipo de {v['mm']} mm en {v['loc']}.", lambda v, r: "Pólipo duodenal"),
        ("papila", "Papila de aspecto neoplásico", [], lambda v, r: "Papila mayor aumentada de tamaño, de aspecto neoplásico.",
         lambda v, r: "Lesión de papila de aspecto neoplásico, pendiente de histología"),
    ],
}
COLON = [
    ("polipo", "Pólipo", [P("cantidad", "Cantidad", "number", required=False), P("mm", "Tamaño", "number", unit="mm"),
                          P("loc", "Localización", options=COLON_LOC), P("paris", "París", options=PARIS, required=False),
                          P("nice", "NICE", options=NICE, required=False), P("reseccion", "Resección", options=RESECTION, required=False),
                          P("recuperado", "Recuperado para patología", options=[("si", "sí"), ("no", "no")], required=False)],
     _polyp_sentence, _polyp_dx),
    ("diverticulos", "Divertículos", [P("loc", "Localización", "multi", COLON_LOC[1:])],
     lambda v, r: f"Divertículos de boca amplia en {v['loc']}, sin signos de complicación.", _divert_dx),
    ("hemorroides", "Hemorroides internas", [P("grado", "Grado", options=[("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV")])],
     lambda v, r: f"Hemorroides internas grado {r['grado']} en la retroflexión rectal.", lambda v, r: f"Hemorroides internas grado {r['grado']}"),
    ("inflamacion", "Inflamación de la mucosa", [P("signos", "Signos", "multi", [("eritema", "eritema"), ("patron", "pérdida del patrón vascular"),
                                                                               ("friabilidad", "friabilidad"), ("erosiones", "erosiones"),
                                                                               ("ulceras", "úlceras"), ("sangrado", "sangrado espontáneo")]),
                                                 P("forma", "Distribución", options=[("continua", "de forma continua"), ("parches", "en parches")]),
                                                 P("hasta", "Extensión", options=[("recto", "limitada al recto"), ("sigmoides", "desde el recto hasta el sigmoides"),
                                                                                  ("esplenico", "desde el recto hasta el ángulo esplénico"),
                                                                                  ("todo", "desde el recto hasta el ciego"),
                                                                                  ("ileon", "en íleon terminal")])],
     lambda v, r: f"Mucosa con {v['signos']}, {v['forma']}, {v['hasta']}.", lambda v, r: "Colitis inespecífica, pendiente de histología"),
    ("angiodisplasia", "Angiodisplasia", [P("loc", "Localización", "multi", COLON_LOC[1:])],
     lambda v, r: f"Angiodisplasia en {v['loc']}.", lambda v, r: "Angiodisplasia de colon"),
    ("neoplasia_c", "Lesión de aspecto neoplásico", [P("loc", "Localización", options=COLON_LOC[1:]),
                                                     P("mm", "Tamaño", "number", unit="mm", required=False),
                                                     P("circ", "Circunferencia", options=[("parcial", "que ocupa parte de la circunferencia"),
                                                                                          ("total", "circunferencial")], required=False),
                                                     P("paso", "Paso del endoscopio", options=[("si", "que permite el paso del endoscopio"),
                                                                                               ("no", "que no permite el paso del endoscopio")], required=False)],
     lambda v, r: "Lesión de aspecto neoplásico" + (f" de {v['mm']} mm" if r.get("mm") else "") + f" en {v['loc']}"
     + "".join(f", {v[k]}" for k in ("circ", "paso") if r.get(k)) + ".",
     lambda v, r: "Lesión de recto de aspecto neoplásico, pendiente de histología" if r["loc"] == "recto"
     else "Lesión de colon de aspecto neoplásico, pendiente de histología"),
    ("melanosis", "Melanosis coli", [], lambda v, r: "Pigmentación oscura difusa de la mucosa colónica (melanosis coli).",
     lambda v, r: "Melanosis coli"),
    ("ileon", "Íleon terminal explorado", [P("cm", "Centímetros explorados", "number", unit="cm", required=False),
                                           P("aspecto", "Aspecto", options=[("normal", "de aspecto normal"), ("aftas", "con úlceras aftosas"),
                                                                            ("ulceras", "con úlceras")])],
     lambda v, r: "Se intuba el íleon terminal" + (f" en {v['cm']} cm" if r.get("cm") else "") + f", {v['aspecto']}.", lambda v, r: None),
    ("preparacion", "Preparación inadecuada", [],
     lambda v, r: "Restos fecales que impiden la evaluación adecuada de la mucosa.", lambda v, r: "Preparación intestinal inadecuada (estudio limitado)"),
]
FINDINGS["colon"] = COLON
FINDINGS["rectosigmoides"] = COLON


def by_key(section):
    return {f[0]: f for f in FINDINGS.get(section, [])}


class Invalid(ValueError):
    pass


def compose(section, finding, src):
    """src: MultiDict con los parámetros (sin prefijo). Devuelve (frase, [sugerencias {t, c, a}])."""
    f = by_key(section).get(finding)
    if not f:
        raise Invalid("Hallazgo no reconocido.")
    key, label, params, sentence, dx = f
    v, r = {}, {}
    for p in params:
        n = p["name"]
        if p["kind"] == "multi":
            opts = dict(p["options"])
            vals = [x for x in src.getlist(n) if x in opts]
            if vals:
                r[n] = vals
                items = [opts[x] for x in vals]
                v[n] = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]
        elif p["kind"] == "number":
            raw = (src.get(n) or "").strip().replace(",", ".")
            if raw:
                try:
                    x = float(raw)
                    if not 0 <= x <= 500:
                        raise ValueError
                except ValueError:
                    raise Invalid(f"«{p['label']}» debe ser un número.") from None
                r[n] = f"{x:g}"
                v[n] = f"{x:g}"
        else:
            x = src.get(n)
            if x in dict(p["options"]):
                r[n] = x
                v[n] = dict(p["options"])[x]
        if p["required"] and n not in r:
            raise Invalid(f"Falta «{p['label']}» para «{label}».")
    text = sentence(v, r)
    out = []
    d = dx(v, r)
    if d:
        cat, shown = (d, d) if isinstance(d, str) else d
        if cat in CATALOG:
            c, a = CATALOG[cat]
            out.append({"t": shown, "c": c, "a": a})
    return text, out
