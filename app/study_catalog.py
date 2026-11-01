"""Catálogo de estudios para las solicitudes de imagen, endoscopia y colonoscopia (v0.15.0).

Pedido del Dr. Lainez: marcar los estudios con un clic en vez de escribirlos. Son solo NOMBRES de estudios de uso habitual en
gastroenterología (sin indicaciones, dosis ni precios). Lo que no esté se escribe en «Otros».
"""

IMAGING = [
    ("Ultrasonido", [
        "Ultrasonido abdominal completo", "Ultrasonido de abdomen superior (hígado, vías biliares, páncreas y bazo)",
        "Ultrasonido hepático y de vías biliares", "Ultrasonido Doppler del eje esplenoportal", "Ultrasonido Doppler hepático (venas suprahepáticas)",
        "Ultrasonido renal y de vías urinarias", "Ultrasonido pélvico", "Ultrasonido de pared abdominal (hernias)",
        "Elastografía hepática transitoria (FibroScan)", "Elastografía hepática por ondas de corte (2D-SWE)"]),
    ("Tomografía (TAC)", [
        "TAC de abdomen y pelvis simple", "TAC de abdomen y pelvis con contraste intravenoso", "TAC trifásica de hígado",
        "TAC de páncreas (protocolo pancreático)", "Angio-TAC abdominal (arterias mesentéricas)", "Entero-TAC",
        "Colonografía por TAC (colonoscopia virtual)", "TAC de tórax", "TAC de tórax, abdomen y pelvis con contraste (estadificación)"]),
    ("Resonancia magnética", [
        "Resonancia magnética de abdomen con contraste", "Resonancia magnética hepática con contraste hepatoespecífico",
        "Colangiorresonancia (CPRM)", "Resonancia magnética de páncreas", "Entero-resonancia",
        "Resonancia magnética de pelvis (fístulas perianales)"]),
    ("Radiología con contraste y simple", [
        "Radiografía de abdomen simple (de pie y en decúbito)", "Radiografía de tórax PA", "Esofagograma con bario",
        "Serie esofagogastroduodenal (SEGD)", "Tránsito intestinal", "Colon por enema", "Defecografía",
        "Tránsito colónico con marcadores radiopacos"]),
    ("Medicina nuclear", [
        "Gammagrafía con eritrocitos marcados (sangrado digestivo)", "Gammagrafía de vaciamiento gástrico",
        "Gammagrafía hepatobiliar (HIDA)", "PET-CT"]),
]

ENDOSCOPY = [
    ("Endoscopia alta", [
        "Endoscopia digestiva alta diagnóstica", "Endoscopia digestiva alta con toma de biopsias",
        "Endoscopia digestiva alta con biopsias y prueba de ureasa (H. pylori)", "Endoscopia digestiva alta con biopsias gástricas (protocolo de Sydney)",
        "Endoscopia digestiva alta con biopsias de duodeno", "Endoscopia digestiva alta de control"]),
    ("Endoscopia terapéutica", [
        "Ligadura de várices esofágicas", "Hemostasia endoscópica", "Dilatación esofágica", "Polipectomía gástrica o duodenal",
        "Extracción de cuerpo extraño", "Gastrostomía endoscópica percutánea (PEG)", "Colocación de prótesis esofágica o duodenal"]),
    ("Vía biliar, páncreas e intestino delgado", [
        "CPRE (colangiopancreatografía retrógrada endoscópica)", "Ultrasonido endoscópico (USE) alto",
        "Ultrasonido endoscópico con punción (PAAF/BAAF)", "Cápsula endoscópica", "Enteroscopia"]),
    ("Pruebas funcionales", [
        "pH-metría esofágica de 24 horas", "pH-impedanciometría esofágica de 24 horas", "Manometría esofágica de alta resolución"]),
]

COLONOSCOPY = [
    ("Colonoscopia", [
        "Colonoscopia diagnóstica", "Colonoscopia de tamizaje", "Colonoscopia de vigilancia", "Colonoscopia con toma de biopsias",
        "Colonoscopia con ileoscopia", "Colonoscopia con cromoendoscopia"]),
    ("Colonoscopia terapéutica", [
        "Colonoscopia con polipectomía", "Colonoscopia con mucosectomía", "Dilatación de estenosis colónica", "Descompresión colónica"]),
    ("Recto y ano", [
        "Rectosigmoidoscopia flexible", "Rectosigmoidoscopia con toma de biopsias", "Anoscopia", "Ligadura de hemorroides con bandas",
        "Ultrasonido endoscópico rectal", "Manometría anorrectal"]),
]

# tipo de la pantalla → (tipo guardado en la base, título impreso, catálogo, ejemplo para «Otros»)
KINDS = {
    "imagen": ("imagen", None, IMAGING, "Ej.: Ultrasonido de tiroides"),
    "endoscopia": ("endoscopia", "Endoscopia", ENDOSCOPY, "Ej.: Endoscopia con dilatación neumática"),
    "colonoscopia": ("endoscopia", "Colonoscopia", COLONOSCOPY, "Ej.: Colonoscopia con tatuaje de lesión"),
}


def lookup(kind):
    """{nombre del estudio: grupo} para validar lo marcado."""
    return {name: grp for grp, names in KINDS[kind][2] for name in names}
