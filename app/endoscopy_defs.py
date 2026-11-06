"""Definiciones para los informes de endoscopia: tipos, segmentos, extensión y clasificaciones.

Clasificaciones verificadas el 30-oct-2026 contra:
- Jiménez Sánchez J et al. A brief summary of endoscopic classifications in the upper GI tract. Gastroenterol Hepatol 2024;47:194-8
  (Los Ángeles, Praga C/M, Forrest, París, várices).
- SpringerPlus 2015, tabla 1 (Los Ángeles, redacción completa).
- Lai EJ et al. Gastrointest Endosc 2009;69:620-5 (escala de Boston) y Calderwood AH et al. Gastrointest Endosc 2014 (definición de
  preparación adecuada: ≥2 en cada segmento).
Las descripciones están redactadas en español para GastroMed Pro.

Agregadas el 31-oct-2026 (v0.13.0), verificadas contra:
- NICE: Hewett DG et al. Gastroenterology 2012;143:599-607 (PMID 22609383); tabla reproducida en Utsumi T et al. Clin Endosc 2015;48:491-7.
- Kudo (patrón de criptas): Arq Gastroenterol 2019 (tipos I, II, IIIS, IIIL, IV y V) e Iwamoto K et al. Int J Colorectal Dis 2007;22:1409 (Vn).
- Zargar (lesión por cáusticos): Singh AK, Birda CL, Kochhar R. World J Gastrointest Endosc 2026;18(3):114327, tabla 1.
- Sarin (várices gástricas): Butt Z et al. J Pak Med Assoc 2016;66(11):1462.
"""

KINDS = {
    "eda": "Endoscopia digestiva alta",
    "colonoscopia": "Colonoscopia",
    "rectosigmoidoscopia": "Rectosigmoidoscopia",
    "cpre": "CPRE",
    "use": "Ultrasonido endoscópico",
}

SEGMENTS = {
    "eda": ["Esófago proximal", "Esófago medio", "Esófago distal", "Unión esofagogástrica", "Cardias", "Fondo gástrico", "Cuerpo gástrico",
            "Ángulo gástrico", "Antro", "Píloro", "Bulbo duodenal", "Segunda porción duodenal"],
    "colonoscopia": ["Íleon terminal", "Ciego", "Válvula ileocecal", "Colon ascendente", "Ángulo hepático", "Colon transverso",
                     "Ángulo esplénico", "Colon descendente", "Sigmoides", "Recto", "Canal anal"],
    "rectosigmoidoscopia": ["Colon descendente distal", "Sigmoides", "Recto", "Canal anal"],
    "cpre": ["Duodeno", "Papila mayor", "Papila menor", "Colédoco", "Conducto hepático común", "Vía biliar intrahepática",
             "Conducto cístico / vesícula", "Conducto pancreático principal"],
    "use": ["Esófago", "Estómago", "Duodeno", "Cabeza del páncreas", "Cuerpo del páncreas", "Cola del páncreas", "Proceso uncinado",
            "Vía biliar", "Vesícula", "Ganglios", "Hígado", "Otro"],
}

EXTENT = {
    "eda": [("segunda_porcion", "Segunda porción duodenal"), ("bulbo", "Bulbo duodenal"), ("estomago", "Estómago"), ("esofago", "Esófago")],
    "colonoscopia": [("ileon", "Íleon terminal"), ("ciego", "Ciego (orificio apendicular y válvula ileocecal identificados)"),
                     ("ascendente", "Colon ascendente"), ("transverso", "Colon transverso"), ("descendente", "Colon descendente"),
                     ("sigmoides", "Sigmoides"), ("recto", "Recto")],
    "rectosigmoidoscopia": [("descendente", "Colon descendente"), ("sigmoides", "Sigmoides"), ("recto", "Recto")],
    "cpre": [("canulacion_biliar", "Canulación biliar profunda lograda"), ("canulacion_pancreatica", "Canulación pancreática"),
             ("sin_canulacion", "Sin canulación")],
    "use": [("completo", "Evaluación completa de la región objetivo"), ("parcial", "Evaluación parcial")],
}

# Tipo de atención (v0.22.0, para usar el programa también en hospitales)
CARE_SETTINGS = {"externa": "Consulta externa", "sala": "Sala (hospitalizado)", "emergencia": "Emergencia"}


# Servicio (v0.28.0, pedido del Dr. Lainez: menú desplegable aparte de «Atención»). «otro» = escribirlo.
SERVICES = ["Gastroenterología", "Medicina interna", "Cirugía general", "Emergencia", "Unidad de cuidados intensivos", "Pediatría",
            "Ginecología y obstetricia", "Ortopedia", "Neurología", "Cardiología", "Nefrología", "Neumología", "Oncología",
            "Hematología", "Infectología", "Geriatría", "Consulta externa"]


def care_text(d):
    """Texto corto del tipo de atención para el informe: «Sala (hospitalizado) · cama 12». El servicio va aparte."""
    cs = CARE_SETTINGS.get((d or {}).get("care_setting") or "")
    if not cs:
        return ""
    parts = [cs]
    if d.get("care_setting") in ("sala", "emergencia") and d.get("bed"):
        parts.append(f"cama {d['bed']}")
    return " · ".join(parts)


INDICATION_CATEGORIES = {"diagnostica": "Diagnóstica (síntomas o hallazgos)", "tamizaje": "Tamizaje (persona asintomática)",
                         "vigilancia": "Vigilancia (antecedente de pólipos, cáncer, EII, Barrett…)", "terapeutica": "Terapéutica"}
# En el informe solo la palabra (v0.28, pedido del Dr. Lainez): «Diagnóstica», sin «(síntomas o hallazgos)»
INDICATION_SHORT = {k: v.split(" (")[0] for k, v in INDICATION_CATEGORIES.items()}

SEDATION = {"ninguna": "Sin sedación", "topica": "Anestesia tópica faríngea", "minima": "Sedación mínima",
            "moderada": "Sedación moderada (consciente)", "profunda": "Sedación profunda", "general": "Anestesia general"}

ASA = [("I", "ASA I"), ("II", "ASA II"), ("III", "ASA III"), ("IV", "ASA IV"), ("V", "ASA V")]

COMPLICATIONS = {"sangrado": "Sangrado", "perforacion": "Perforación", "cardiopulmonar": "Evento cardiopulmonar / desaturación",
                 "pancreatitis": "Pancreatitis post-CPRE", "colangitis": "Colangitis", "reaccion_sedacion": "Reacción a la sedación",
                 "otra": "Otra"}

# Clasificaciones aplicables a un hallazgo (valor, etiqueta, descripción)
CLASSIFICATIONS = {
    "los_angeles": ("Esofagitis: Los Ángeles", [
        ("LA-A", "A", "Una o más erosiones ≤5 mm que no se extienden entre las crestas de los pliegues"),
        ("LA-B", "B", "Una o más erosiones >5 mm que no se extienden entre las crestas de los pliegues"),
        ("LA-C", "C", "Erosiones continuas entre las crestas de ≥2 pliegues que afectan <75 % de la circunferencia"),
        ("LA-D", "D", "Erosiones que afectan ≥75 % de la circunferencia esofágica")]),
    "forrest": ("Úlcera péptica: Forrest", [
        ("F-Ia", "Ia", "Sangrado activo en chorro"), ("F-Ib", "Ib", "Sangrado activo en capa (rezumante)"),
        ("F-IIa", "IIa", "Vaso visible no sangrante"), ("F-IIb", "IIb", "Coágulo adherido"),
        ("F-IIc", "IIc", "Mancha pigmentada plana en el fondo de la úlcera"), ("F-III", "III", "Fondo limpio, sin estigmas")]),
    "paris": ("Lesión superficial: París", [
        ("P-0-Ip", "0-Ip", "Pediculada"), ("P-0-Is", "0-Is", "Sésil"), ("P-0-IIa", "0-IIa", "Ligeramente elevada"),
        ("P-0-IIb", "0-IIb", "Plana"), ("P-0-IIc", "0-IIc", "Ligeramente deprimida"), ("P-0-III", "0-III", "Excavada (úlcera)")]),
    "varices": ("Várices esofágicas (tamaño)", [
        ("V-peq", "Pequeñas", "Menores de 5 mm"), ("V-gra", "Grandes", "Mayores de 5 mm")]),
    "sarin": ("Várices gástricas: Sarin", [
        ("S-GOV1", "GOV1", "Continuación de várices esofágicas 2–5 cm por debajo de la unión esofagogástrica, por la curvatura menor"),
        ("S-GOV2", "GOV2", "Continuación de várices esofágicas hacia el cardias y el fondo gástrico"),
        ("S-IGV1", "IGV1", "Várices aisladas en el fondo gástrico, sin várices esofágicas"),
        ("S-IGV2", "IGV2", "Várices aisladas en otra parte del estómago (fuera del fondo)")]),
    "zargar": ("Lesión por cáusticos: Zargar", [
        ("Z-0", "0", "Mucosa normal"), ("Z-1", "1", "Edema y eritema de la mucosa"),
        ("Z-2a", "2a", "Úlceras superficiales y localizadas, friabilidad, sangrado y ampollas"),
        ("Z-2b", "2b", "Úlceras profundas (aisladas o circunferenciales), además de lo descrito en 2a"),
        ("Z-3a", "3a", "Áreas pequeñas y dispersas de necrosis"), ("Z-3b", "3b", "Necrosis extensa")]),
    "nice": ("Pólipo colorrectal con NBI: NICE", [
        ("N-1", "Tipo 1", "Color igual o más claro que el fondo; sin vasos o vasos finos aislados; puntos uniformes o sin patrón. "
                          "Más probable: hiperplásico o serrado sésil"),
        ("N-2", "Tipo 2", "Más marrón que el fondo; vasos marrones rodeando estructuras blancas; estructuras blancas ovales, tubulares o "
                          "ramificadas. Más probable: adenoma"),
        ("N-3", "Tipo 3", "Marrón a marrón oscuro, a veces con áreas blanquecinas; vasos interrumpidos o ausentes; patrón amorfo o ausente. "
                          "Más probable: cáncer con invasión submucosa profunda")]),
    "kudo": ("Patrón de criptas: Kudo", [
        ("K-I", "I", "Criptas redondas (mucosa normal)"), ("K-II", "II", "Criptas estrelladas o papilares (no neoplásico: hiperplásico o inflamatorio)"),
        ("K-IIIs", "IIIs", "Criptas redondas o tubulares pequeñas, menores que las normales (neoplásico)"),
        ("K-IIIL", "IIIL", "Criptas tubulares o redondas grandes, mayores que las normales (neoplásico)"),
        ("K-IV", "IV", "Criptas ramificadas o en circunvoluciones (neoplásico)"),
        ("K-V", "V", "Patrón irregular o sin estructura (neoplásico, sospecha de carcinoma)"),
        ("K-Vn", "Vn", "Sin estructura: sugiere invasión submucosa")]),
}
CLASS_LOOKUP = {code: (group, short, desc) for group, (_, opts) in CLASSIFICATIONS.items() for code, short, desc in opts}

FINDING_TYPES = ["Normal", "Esofagitis", "Esófago de Barrett (Praga C/M)", "Várices", "Hernia hiatal", "Gastritis / gastropatía", "Úlcera",
                 "Erosiones", "Pólipo", "Lesión superficial / neoplasia", "Masa / tumor", "Estenosis", "Divertículos", "Angiectasia",
                 "Hemorroides", "Colitis / inflamación", "Cuerpo extraño", "Coledocolitiasis", "Estenosis biliar", "Lesión quística",
                 "Lesión sólida", "Otro"]

BBPS = [(0, "0 · Sin preparar: mucosa no visible por heces sólidas que no se pueden aclarar"),
        (1, "1 · Parte de la mucosa visible; otras áreas no se ven por restos o líquido turbio"),
        (2, "2 · Restos menores o líquido turbio, pero la mucosa se ve bien"),
        (3, "3 · Toda la mucosa se ve bien, sin restos ni líquido turbio")]

RESULT_CATEGORIES = {"normal": "Normal", "inflamatorio": "Inflamatorio", "hiperplasico": "Pólipo hiperplásico",
                     "adenoma_tubular": "Adenoma tubular", "adenoma_tubulovelloso": "Adenoma tubulovelloso", "adenoma_velloso": "Adenoma velloso",
                     "serrado_sesil": "Lesión serrada sésil", "adenocarcinoma": "Adenocarcinoma", "otro_neoplasico": "Otra neoplasia",
                     "otro": "Otro"}
ADENOMA = {"adenoma_tubular", "adenoma_tubulovelloso", "adenoma_velloso"}
DYSPLASIA = {"no_aplica": "No aplica", "sin_displasia": "Sin displasia", "bajo_grado": "Bajo grado", "alto_grado": "Alto grado",
             "indefinida": "Indefinida"}

STENT_KINDS = ["Prótesis biliar plástica", "Prótesis biliar metálica", "Prótesis pancreática", "Prótesis esofágica", "Prótesis duodenal",
               "Prótesis colónica", "Otra"]

# ------------------------------------------------------------------------------------------------ descripción por segmento (v0.8.0)
# Pedido del Dr. Lainez (30-oct-2026): describir con texto libre lo que se ve en cada segmento y un botón «Normal»
# que escriba la descripción normal para ahorrar tiempo. Los textos normales son plantillas redactadas para GastroMed Pro;
# el médico puede cambiarlos en Endoscopia → Textos de estudio normal y siempre revisa el texto antes de finalizar.
NARRATIVE = {
    "eda": [("esofago", "Esófago"), ("ueg", "Unión esofagogástrica"), ("estomago", "Estómago"), ("duodeno", "Duodeno")],
    "colonoscopia": [("colon", "Colonoscopia")],
    "rectosigmoidoscopia": [("rectosigmoides", "Rectosigmoidoscopia")],
    "cpre": [("cpre", "Hallazgos de la CPRE")],
    "use": [("use", "Hallazgos del ultrasonido endoscópico")],
}
NARRATIVE_LABELS = {k: lab for secs in NARRATIVE.values() for k, lab in secs}

ZLINE = {"coincide": "Coincide con la línea Z", "no_coincide": "No coincide con la línea Z"}

DEFAULT_NORMAL_TEXTS = {
    "esofago": "Esófago de calibre y distensibilidad conservados. Mucosa de aspecto normal en todo su trayecto, con patrón vascular "
               "conservado, sin erosiones, úlceras, várices, estenosis ni lesiones.",
    "ueg": "Línea Z regular, que coincide con la impronta diafragmática. Sin hernia hiatal ni lesiones de la mucosa. "
           "En retroflexión, cardias que abraza adecuadamente el endoscopio.",
    "estomago": "Lago mucoso claro y escaso. Mucosa de fondo, cuerpo, ángulo y antro de aspecto normal, con pliegues de grosor "
                "y distribución habituales, sin eritema, erosiones, úlceras ni lesiones. Píloro redondo, permeable y simétrico.",
    "duodeno": "Bulbo y segunda porción duodenal con mucosa de aspecto normal y patrón vellositario conservado, sin úlceras, "
               "erosiones ni lesiones.",
    "colon": "Se avanza el colonoscopio hasta el ciego, identificando el orificio apendicular y la válvula ileocecal. "
             "Mucosa de ciego, colon ascendente, ángulo hepático, colon transverso, ángulo esplénico, colon descendente, "
             "sigmoides y recto de aspecto normal, con patrón vascular conservado, sin pólipos, divertículos, lesiones ni "
             "sangrado. Retroflexión en recto sin alteraciones.",
    "rectosigmoides": "Se avanza el endoscopio hasta el colon descendente distal. Mucosa de colon descendente, sigmoides y recto "
                      "de aspecto normal, con patrón vascular conservado, sin pólipos, divertículos, lesiones ni sangrado. "
                      "Retroflexión en recto sin alteraciones.",
    "cpre": "Papila mayor de aspecto y localización habituales. La colangiografía muestra vía biliar intra y extrahepática de "
            "calibre normal, sin defectos de llenado ni estenosis, con vaciamiento adecuado del medio de contraste.",
    "use": "Páncreas de tamaño y ecogenicidad normales en cabeza, proceso uncinado, cuerpo y cola, sin lesiones focales. "
           "Conducto pancreático principal de calibre normal. Vía biliar extrahepática de calibre normal, sin litos. "
           "Vesícula sin alteraciones. Sin adenopatías en las regiones evaluadas.",
}
DEFAULT_NORMAL_CONCLUSION = {
    "eda": "Endoscopia digestiva alta dentro de límites normales.",
    "colonoscopia": "Colonoscopia completa dentro de límites normales.",
    "rectosigmoidoscopia": "Rectosigmoidoscopia dentro de límites normales.",
    "cpre": "CPRE sin alteraciones de la vía biliar.",
    "use": "Ultrasonido endoscópico sin alteraciones en las regiones evaluadas.",
}


def normal_texts(settings_json):
    """Textos normales vigentes: los del médico (Ajustes) o, si no hay, los predeterminados."""
    import json as _j
    try:
        custom = _j.loads(settings_json) if settings_json else {}
    except ValueError:
        custom = {}
    secs = {k: (custom.get("sec", {}).get(k) or v) for k, v in DEFAULT_NORMAL_TEXTS.items()}
    concl = {k: (custom.get("concl", {}).get(k) or v) for k, v in DEFAULT_NORMAL_CONCLUSION.items()}
    return secs, concl


def zline_text(d):
    """Frase de la unión esofagogástrica según lo marcado (no inventa medidas)."""
    zl = d.get("zline")
    if zl == "coincide":
        return "Coincide con la línea Z."
    if zl == "no_coincide":
        parts = ["No coincide con la línea Z"]
        if d.get("zline_cm") is not None:
            parts.append(f"línea Z a {d['zline_cm']:g} cm de la arcada dentaria")
        if d.get("hiatus_cm") is not None:
            parts.append(f"impronta diafragmática a {d['hiatus_cm']:g} cm")
        return "; ".join(parts) + "."
    return ""
