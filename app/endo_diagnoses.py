"""Diagnósticos endoscópicos frecuentes para la conclusión del informe (v0.11.0).

Terminología habitual en gastroenterología, redactada en español para GastroMed Pro, con las clasificaciones ya verificadas
en endoscopy_defs.py (Los Ángeles, Forrest, Praga, várices).

Códigos CIE-10: versión de la OMS (5.ª edición, 2016), comprobados el 31-oct-2026 en el navegador oficial publicado por el NHS
(classbrowser.nhs.uk/ICD-10-5TH-Edition): bloques C15-C26, D10-D36, I80-I89, K20-K31, K40-K46, K50-K52, K55-K64, K70-K77,
K80-K87 y K90-K93.
- code: código cuyo título o inclusión corresponde directamente al diagnóstico.
- approx=True: no hay código propio; se indica la categoría general («otras enfermedades especificadas…»). Se muestra con *.
- code=None: no se asigna código (p. ej., sospecha de neoplasia sin histología: el código C/D se pone con la patología).
El médico revisa siempre el texto y el código antes de finalizar.
"""

UPPER = ("eda", "use", "cpre")
LOWER = ("colonoscopia", "rectosigmoidoscopia")
BILIO = ("cpre", "use")

# (grupo, tipos de estudio, texto, código, aproximado)
DIAGNOSES = [
    # ---------------------------------------------------------------- normal
    ("Normal", UPPER, "Endoscopia digestiva alta dentro de límites normales", None, False),
    ("Normal", LOWER, "Colonoscopia completa dentro de límites normales", None, False),
    # ---------------------------------------------------------------- esófago
    ("Esófago", UPPER, "Esofagitis erosiva grado A de Los Ángeles", "K21.0", False),
    ("Esófago", UPPER, "Esofagitis erosiva grado B de Los Ángeles", "K21.0", False),
    ("Esófago", UPPER, "Esofagitis erosiva grado C de Los Ángeles", "K21.0", False),
    ("Esófago", UPPER, "Esofagitis erosiva grado D de Los Ángeles", "K21.0", False),
    ("Esófago", UPPER, "Esófago de Barrett (Praga C__ M__), pendiente de histología", "K22.7", False),
    ("Esófago", UPPER, "Hernia hiatal por deslizamiento de __ cm", "K44.9", False),
    ("Esófago", UPPER, "Hernia paraesofágica", "K44.9", False),
    ("Esófago", UPPER, "Várices esofágicas pequeñas (< 5 mm), sin signos rojos", "I85.9", False),
    ("Esófago", UPPER, "Várices esofágicas pequeñas (< 5 mm), con signos rojos", "I85.9", False),
    ("Esófago", UPPER, "Várices esofágicas grandes (> 5 mm), sin signos rojos", "I85.9", False),
    ("Esófago", UPPER, "Várices esofágicas grandes (> 5 mm), con signos rojos", "I85.9", False),
    ("Esófago", UPPER, "Várices esofágicas con sangrado activo o estigmas de sangrado reciente", "I85.0", False),
    ("Esófago", UPPER, "Esofagitis de aspecto candidiásico", "K20", False),
    ("Esófago", UPPER, "Hallazgos sugestivos de esofagitis eosinofílica (anillos, surcos, exudados), pendiente de histología", "K20", False),
    ("Esófago", UPPER, "Úlcera esofágica", "K22.1", False),
    ("Esófago", UPPER, "Desgarro de Mallory-Weiss", "K22.6", False),
    ("Esófago", UPPER, "Estenosis esofágica", "K22.2", False),
    ("Esófago", UPPER, "Divertículo esofágico", "K22.5", False),
    ("Esófago", UPPER, "Hallazgos compatibles con acalasia", "K22.0", False),
    ("Esófago", UPPER, "Lesión esofágica de aspecto neoplásico, pendiente de histología", None, False),
    ("Esófago", UPPER, "Lesión esofágica por cáusticos, grado __ de Zargar", None, False),
    # ---------------------------------------------------------------- estómago
    ("Estómago", UPPER, "Gastropatía eritematosa", "K29.7", False),
    ("Estómago", UPPER, "Gastropatía eritematosa de antro", "K29.7", False),
    ("Estómago", UPPER, "Gastropatía erosiva", "K29.7", False),
    ("Estómago", UPPER, "Gastritis hemorrágica aguda", "K29.0", False),
    ("Estómago", UPPER, "Gastropatía de aspecto atrófico, pendiente de histología", "K29.4", False),
    ("Estómago", UPPER, "Gastropatía hipertensiva portal leve", "K31.8", True),
    ("Estómago", UPPER, "Gastropatía hipertensiva portal severa", "K31.8", True),
    ("Estómago", UPPER, "Várices gástricas", "I86.4", False),
    ("Estómago", UPPER, "Várices gástricas GOV1 (Sarin)", "I86.4", False),
    ("Estómago", UPPER, "Várices gástricas GOV2 (Sarin)", "I86.4", False),
    ("Estómago", UPPER, "Várices gástricas IGV1 (Sarin)", "I86.4", False),
    ("Estómago", UPPER, "Várices gástricas IGV2 (Sarin)", "I86.4", False),
    ("Estómago", UPPER, "Ectasia vascular antral (GAVE)", "K31.8", True),
    ("Estómago", UPPER, "Úlcera gástrica Forrest Ia (sangrado en chorro)", "K25.4", False),
    ("Estómago", UPPER, "Úlcera gástrica Forrest Ib (sangrado en capa)", "K25.4", False),
    ("Estómago", UPPER, "Úlcera gástrica Forrest IIa (vaso visible)", "K25.4", False),
    ("Estómago", UPPER, "Úlcera gástrica Forrest IIb (coágulo adherido)", "K25.4", False),
    ("Estómago", UPPER, "Úlcera gástrica Forrest IIc (mancha pigmentada)", "K25.4", False),
    ("Estómago", UPPER, "Úlcera gástrica Forrest III (fondo limpio)", "K25.9", False),
    ("Estómago", UPPER, "Pólipo gástrico", "K31.7", False),
    ("Estómago", UPPER, "Pólipos de glándulas fúndicas", "K31.7", False),
    ("Estómago", UPPER, "Divertículo gástrico", "K31.4", False),
    ("Estómago", UPPER, "Lesión subepitelial gástrica", None, False),
    ("Estómago", UPPER, "Lesión gástrica de aspecto neoplásico, pendiente de histología", None, False),
    ("Estómago", UPPER, "Angiectasia gástrica", "K31.8", True),
    ("Estómago", UPPER, "Restos alimentarios en estómago (estudio limitado)", None, False),
    # ---------------------------------------------------------------- duodeno
    ("Duodeno", UPPER, "Duodenitis", "K29.8", False),
    ("Duodeno", UPPER, "Duodenitis erosiva de bulbo", "K29.8", False),
    ("Duodeno", UPPER, "Úlcera duodenal Forrest Ia (sangrado en chorro)", "K26.4", False),
    ("Duodeno", UPPER, "Úlcera duodenal Forrest Ib (sangrado en capa)", "K26.4", False),
    ("Duodeno", UPPER, "Úlcera duodenal Forrest IIa (vaso visible)", "K26.4", False),
    ("Duodeno", UPPER, "Úlcera duodenal Forrest IIb (coágulo adherido)", "K26.4", False),
    ("Duodeno", UPPER, "Úlcera duodenal Forrest IIc (mancha pigmentada)", "K26.4", False),
    ("Duodeno", UPPER, "Úlcera duodenal Forrest III (fondo limpio)", "K26.9", False),
    ("Duodeno", UPPER, "Pólipo duodenal", "K31.7", False),
    ("Duodeno", UPPER, "Atrofia de vellosidades duodenales (descartar enfermedad celíaca), pendiente de histología", None, False),
    ("Duodeno", UPPER, "Angiectasia duodenal", "K31.8", True),
    ("Duodeno", UPPER, "Lesión de papila de aspecto neoplásico, pendiente de histología", None, False),
    # ---------------------------------------------------------------- sangrado
    ("Sangrado", UPPER + LOWER, "Hemorragia digestiva sin causa identificada en este estudio", "K92.2", False),
    # ---------------------------------------------------------------- colon, recto y ano
    ("Colon y recto", LOWER, "Pólipo de colon", "K63.5", False),
    ("Colon y recto", LOWER, "Pólipos de colon múltiples", "K63.5", False),
    ("Colon y recto", LOWER, "Pólipo de colon NICE 1 (aspecto hiperplásico o serrado)", "K63.5", False),
    ("Colon y recto", LOWER, "Pólipo de colon NICE 2 (aspecto adenomatoso)", "K63.5", False),
    ("Colon y recto", LOWER, "Lesión de colon NICE 3 (sospecha de invasión submucosa profunda), pendiente de histología", None, False),
    ("Colon y recto", LOWER, "Pólipo de recto", "K62.1", False),
    ("Colon y recto", LOWER, "Enfermedad diverticular de colon sigmoides", "K57.3", False),
    ("Colon y recto", LOWER, "Enfermedad diverticular de colon (pancolónica)", "K57.3", False),
    ("Colon y recto", LOWER, "Enfermedad diverticular de colon", "K57.3", False),
    ("Colon y recto", LOWER, "Hemorroides internas grado I", "K64.0", False),
    ("Colon y recto", LOWER, "Hemorroides internas grado II", "K64.1", False),
    ("Colon y recto", LOWER, "Hemorroides internas grado III", "K64.2", False),
    ("Colon y recto", LOWER, "Hemorroides internas grado IV", "K64.3", False),
    ("Colon y recto", LOWER, "Fisura anal crónica", "K60.1", False),
    ("Colon y recto", LOWER, "Angiodisplasia de colon", "K55.2", False),
    ("Colon y recto", LOWER, "Colitis ulcerosa: proctitis", "K51.2", False),
    ("Colon y recto", LOWER, "Colitis ulcerosa: rectosigmoiditis", "K51.3", False),
    ("Colon y recto", LOWER, "Colitis ulcerosa izquierda", "K51.5", False),
    ("Colon y recto", LOWER, "Colitis ulcerosa extensa (pancolitis)", "K51.0", False),
    ("Colon y recto", LOWER, "Pseudopólipos inflamatorios", "K51.4", False),
    ("Colon y recto", LOWER, "Enfermedad de Crohn de colon", "K50.1", False),
    ("Colon y recto", LOWER, "Enfermedad de Crohn de íleon terminal", "K50.0", False),
    ("Colon y recto", LOWER, "Colitis inespecífica, pendiente de histología", "K52.9", False),
    ("Colon y recto", LOWER, "Proctitis actínica", "K62.7", False),
    ("Colon y recto", LOWER, "Úlcera rectal", "K62.6", False),
    ("Colon y recto", LOWER, "Prolapso rectal", "K62.3", False),
    ("Colon y recto", LOWER, "Melanosis coli", "K63.8", True),
    ("Colon y recto", LOWER, "Lesión de colon de aspecto neoplásico, pendiente de histología", None, False),
    ("Colon y recto", LOWER, "Lesión de recto de aspecto neoplásico, pendiente de histología", None, False),
    ("Colon y recto", LOWER, "Preparación intestinal inadecuada (estudio limitado)", None, False),
    # ---------------------------------------------------------------- vía biliar y páncreas
    ("Vía biliar y páncreas", BILIO, "Coledocolitiasis", "K80.5", False),
    ("Vía biliar y páncreas", BILIO, "Coledocolitiasis con colangitis", "K80.3", False),
    ("Vía biliar y páncreas", BILIO, "Colelitiasis", "K80.2", False),
    ("Vía biliar y páncreas", BILIO, "Colangitis", "K83.0", False),
    ("Vía biliar y páncreas", BILIO, "Estenosis de la vía biliar", "K83.1", False),
    ("Vía biliar y páncreas", BILIO, "Quiste de colédoco", "K83.5", False),
    ("Vía biliar y páncreas", BILIO, "Pancreatitis crónica", "K86.1", False),
    ("Vía biliar y páncreas", BILIO, "Pseudoquiste de páncreas", "K86.3", False),
    ("Vía biliar y páncreas", BILIO, "Lesión quística de páncreas", "K86.2", False),
    ("Vía biliar y páncreas", BILIO, "Lesión sólida de páncreas, pendiente de histología", None, False),
]

ICD_SOURCE = "CIE-10 de la OMS (5.ª ed.), verificado en classbrowser.nhs.uk el 31-oct-2026"


def for_kind(kind):
    """Lista para el desplegable del tipo de estudio: [{g, t, c, a}]."""
    return [{"g": g, "t": t, "c": c, "a": a} for g, kinds, t, c, a in DIAGNOSES if kind in kinds]
