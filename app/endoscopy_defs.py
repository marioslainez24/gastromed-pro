"""Definiciones para los informes de endoscopia: tipos, segmentos, extensión y clasificaciones.

Clasificaciones verificadas el 30-oct-2026 contra:
- Jiménez Sánchez J et al. A brief summary of endoscopic classifications in the upper GI tract. Gastroenterol Hepatol 2024;47:194-8
  (Los Ángeles, Praga C/M, Forrest, París, várices).
- SpringerPlus 2015, tabla 1 (Los Ángeles, redacción completa).
- Lai EJ et al. Gastrointest Endosc 2009;69:620-5 (escala de Boston) y Calderwood AH et al. Gastrointest Endosc 2014 (definición de
  preparación adecuada: ≥2 en cada segmento).
Las descripciones están redactadas en español para GastroMed Pro.
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

INDICATION_CATEGORIES = {"diagnostica": "Diagnóstica (síntomas o hallazgos)", "tamizaje": "Tamizaje (persona asintomática)",
                         "vigilancia": "Vigilancia (antecedente de pólipos, cáncer, EII, Barrett…)", "terapeutica": "Terapéutica"}

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
