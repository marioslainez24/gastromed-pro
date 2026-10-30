"""Formularios de consulta gastroenterológica (Fase 2).

Contenido propio, redactado para GastroMed Pro. No reproduce cuestionarios validados protegidos por licencia
(p. ej., GerdQ, Rome IV, PAC-SYM, IBS-SSS): se registran como «pendientes de licencia».
Cada formulario documenta duración, evolución, síntomas acompañantes, tratamientos previos, antecedentes y signos de alarma.
"""

VERSION = 1

# Escala de Bristol: descripciones propias (la escala original es de Lewis y Heaton, 1997).
BRISTOL = [
    (1, "Trozos duros separados, difíciles de evacuar"),
    (2, "Forma alargada, abultada y dura"),
    (3, "Forma alargada con grietas en la superficie"),
    (4, "Forma alargada, lisa y blanda"),
    (5, "Trozos blandos con bordes definidos, fáciles de evacuar"),
    (6, "Trozos esponjosos con bordes irregulares, pastosa"),
    (7, "Totalmente líquida, sin trozos sólidos"),
]

DURATION = ("duracion", "Duración", "select", [("<1s", "Menos de 1 semana"), ("1-4s", "1 a 4 semanas"), ("1-3m", "1 a 3 meses"),
                                                ("3-6m", "3 a 6 meses"), (">6m", "Más de 6 meses")])
EVOLUTION = ("evolucion", "Evolución", "select", [("continua", "Continua"), ("intermitente", "Intermitente / episódica"),
                                                  ("empeorando", "Empeorando"), ("mejorando", "Mejorando"), ("estable", "Estable")])
PREV_TX = ("tratamientos_previos", "Tratamientos previos y respuesta", "textarea", None)
HISTORY = ("antecedentes_relevantes", "Antecedentes relevantes para este problema", "textarea", None)
NOTES = ("comentarios", "Comentarios", "textarea", None)

COMMON_ALARMS = [("perdida_peso", "Pérdida de peso involuntaria"), ("sangrado", "Sangrado digestivo (hematemesis, melena o hematoquecia)"),
                 ("anemia", "Anemia o ferropenia"), ("disfagia_prog", "Disfagia progresiva"), ("vomitos_persist", "Vómitos persistentes"),
                 ("masa", "Masa abdominal palpable"), ("fiebre", "Fiebre"), ("ictericia", "Ictericia"),
                 ("edad_inicio", "Inicio de síntomas después de los 50 años"), ("antec_cancer", "Antecedente familiar de cáncer digestivo")]


def alarms(*keys, extra=()):
    d = dict(COMMON_ALARMS)
    return ("signos_alarma", "Signos de alarma presentes", "multi", [(k, d[k]) for k in keys] + list(extra))


def F(key, label, kind="text", options=None):
    return (key, label, kind, options)


FORMS = {
    "reflujo_dispepsia": ("Reflujo y dispepsia", [
        DURATION, EVOLUTION,
        F("sintomas", "Síntomas", "multi", [("pirosis", "Pirosis"), ("regurgitacion", "Regurgitación"), ("epigastralgia", "Dolor epigástrico"),
                                             ("ardor_epig", "Ardor epigástrico"), ("plenitud", "Plenitud posprandial"), ("saciedad", "Saciedad precoz"),
                                             ("eructos", "Eructos"), ("nausea", "Náusea"), ("tos", "Tos crónica"), ("disfonia", "Disfonía"),
                                             ("dolor_toracico", "Dolor torácico no cardiaco")]),
        F("frecuencia", "Frecuencia de los síntomas", "select", [("<1", "Menos de 1 día por semana"), ("1-2", "1–2 días por semana"),
                                                                 ("3-6", "3–6 días por semana"), ("diario", "Diario")]),
        F("nocturnos", "Síntomas nocturnos", "select", [("no", "No"), ("si", "Sí")]),
        F("desencadenantes", "Desencadenantes (comidas, decúbito, estrés…)", "text"),
        F("aine", "Uso de AINE o ácido acetilsalicílico", "select", [("no", "No"), ("si", "Sí"), ("ocasional", "Ocasional")]),
        F("ibp", "Respuesta a inhibidores de bomba de protones", "select", [("no_usado", "No ha usado"), ("completa", "Completa"),
                                                                           ("parcial", "Parcial"), ("sin_respuesta", "Sin respuesta")]),
        F("hp_previo", "Estudio previo de H. pylori", "text"),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "anemia", "disfagia_prog", "vomitos_persist", "masa", "edad_inicio", "antec_cancer"),
        NOTES]),
    "disfagia": ("Disfagia y odinofagia", [
        DURATION, EVOLUTION,
        F("tipo", "Tipo", "select", [("orofaringea", "Orofaríngea (al iniciar la deglución)"), ("esofagica", "Esofágica (retroesternal)")]),
        F("consistencia", "Con qué alimentos", "select", [("solidos", "Solo sólidos"), ("ambos", "Sólidos y líquidos desde el inicio"),
                                                          ("progresiva", "Primero sólidos, luego líquidos")]),
        F("odinofagia", "Odinofagia", "select", [("no", "No"), ("si", "Sí")]),
        F("impactacion", "Episodios de impactación alimentaria", "select", [("no", "No"), ("si", "Sí")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("regurgitacion", "Regurgitación de alimento no digerido"), ("tos", "Tos o atoragamiento"),
                                                              ("pirosis", "Pirosis"), ("dolor_toracico", "Dolor torácico"), ("halitosis", "Halitosis")]),
        F("atopia", "Atopia / alergias (asma, rinitis, dermatitis)", "select", [("no", "No"), ("si", "Sí")]),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "anemia", "disfagia_prog", "edad_inicio", "antec_cancer"),
        NOTES]),
    "dolor_abdominal": ("Dolor abdominal", [
        DURATION, EVOLUTION,
        F("localizacion", "Localización", "multi", [("epigastrio", "Epigastrio"), ("hipocondrio_der", "Hipocondrio derecho"),
                                                    ("hipocondrio_izq", "Hipocondrio izquierdo"), ("periumbilical", "Periumbilical"),
                                                    ("fosa_iliaca_der", "Fosa ilíaca derecha"), ("fosa_iliaca_izq", "Fosa ilíaca izquierda"),
                                                    ("hipogastrio", "Hipogastrio"), ("difuso", "Difuso")]),
        F("caracter", "Carácter", "select", [("colico", "Cólico"), ("urente", "Urente"), ("opresivo", "Opresivo"), ("punzante", "Punzante"),
                                             ("sordo", "Sordo")]),
        F("intensidad", "Intensidad (0–10)", "number", None),
        F("irradiacion", "Irradiación", "text"),
        F("relacion_comidas", "Relación con comidas", "select", [("no", "Sin relación"), ("empeora", "Empeora al comer"), ("mejora", "Mejora al comer")]),
        F("relacion_evacuacion", "Relación con la evacuación", "select", [("no", "Sin relación"), ("mejora", "Mejora al evacuar"),
                                                                          ("cambio_habito", "Asociado a cambio en el hábito intestinal")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("nausea", "Náusea"), ("vomito", "Vómito"), ("diarrea", "Diarrea"),
                                                              ("estrenimiento", "Estreñimiento"), ("distension", "Distensión"), ("fiebre", "Fiebre"),
                                                              ("coluria", "Coluria"), ("acolia", "Acolia")]),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "anemia", "fiebre", "ictericia", "masa", "vomitos_persist", "edad_inicio", "antec_cancer",
               extra=[("dolor_nocturno", "Dolor que despierta por la noche")]),
        NOTES]),
    "nausea_vomito": ("Náuseas y vómitos", [
        DURATION, EVOLUTION,
        F("frecuencia", "Episodios de vómito por día", "number", None),
        F("contenido", "Contenido", "multi", [("alimento", "Alimento"), ("bilioso", "Bilioso"), ("fecaloide", "Fecaloide"),
                                              ("sangre", "Sangre o «en pozo de café»")]),
        F("momento", "Momento", "select", [("posprandial_inm", "Posprandial inmediato"), ("posprandial_tardio", "Posprandial tardío"),
                                           ("matutino", "Matutino"), ("ciclico", "Episodios cíclicos")]),
        F("factores", "Factores asociados", "multi", [("medicamentos", "Medicamentos nuevos"), ("cannabis", "Consumo de cannabis"),
                                                      ("embarazo", "Posible embarazo"), ("diabetes", "Diabetes"), ("cirugia", "Cirugía abdominal previa")]),
        F("deshidratacion", "Signos de deshidratación", "select", [("no", "No"), ("si", "Sí")]),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "vomitos_persist", "masa", extra=[("cefalea", "Cefalea o síntomas neurológicos"),
                                                                             ("distension_obst", "Distensión con ausencia de evacuaciones")]),
        NOTES]),
    "diarrea": ("Diarrea aguda y crónica", [
        F("tipo", "Tipo", "select", [("aguda", "Aguda (<14 días)"), ("persistente", "Persistente (14–30 días)"), ("cronica", "Crónica (>4 semanas)")]),
        DURATION, EVOLUTION,
        F("frecuencia", "Evacuaciones por día", "number", None),
        F("bristol", "Consistencia habitual (escala de Bristol)", "bristol", None),
        F("caracteristicas", "Características", "multi", [("sangre", "Sangre"), ("moco", "Moco"), ("grasa", "Esteatorrea / grasosa"),
                                                          ("nocturna", "Nocturna"), ("urgencia", "Urgencia"), ("incontinencia", "Incontinencia"),
                                                          ("tenesmo", "Tenesmo")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("dolor", "Dolor abdominal"), ("fiebre", "Fiebre"), ("vomito", "Vómito"),
                                                              ("distension", "Distensión"), ("artralgias", "Artralgias"), ("lesiones_piel", "Lesiones cutáneas"),
                                                              ("aftas", "Aftas orales")]),
        F("exposiciones", "Exposiciones", "multi", [("antibioticos", "Antibióticos recientes"), ("viaje", "Viaje reciente"),
                                                    ("hospitalizacion", "Hospitalización reciente"), ("contactos", "Contactos con síntomas similares"),
                                                    ("agua", "Agua o alimentos de riesgo"), ("lacteos", "Relación con lácteos")]),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "anemia", "fiebre", "edad_inicio", "antec_cancer",
               extra=[("deshidratacion", "Deshidratación"), ("antec_eii", "Antecedente familiar de enfermedad inflamatoria intestinal")]),
        NOTES]),
    "estrenimiento": ("Estreñimiento", [
        DURATION, EVOLUTION,
        F("frecuencia", "Evacuaciones por semana", "number", None),
        F("bristol", "Consistencia habitual (escala de Bristol)", "bristol", None),
        F("sintomas", "Síntomas", "multi", [("esfuerzo", "Esfuerzo excesivo"), ("incompleta", "Sensación de evacuación incompleta"),
                                            ("bloqueo", "Sensación de bloqueo anorrectal"), ("maniobras", "Maniobras manuales"),
                                            ("dolor", "Dolor abdominal"), ("distension", "Distensión")]),
        F("factores", "Factores", "multi", [("fibra", "Baja ingesta de fibra"), ("liquidos", "Baja ingesta de líquidos"),
                                            ("medicamentos", "Medicamentos (opioides, calcio, hierro, anticolinérgicos…)"),
                                            ("hipotiroidismo", "Hipotiroidismo"), ("diabetes", "Diabetes"), ("sedentarismo", "Sedentarismo")]),
        F("laxantes", "Laxantes usados y respuesta", "textarea", None),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "anemia", "edad_inicio", "antec_cancer",
               extra=[("cambio_reciente", "Cambio reciente del hábito intestinal")]),
        NOTES]),
    "sangrado": ("Sangrado digestivo", [
        F("forma", "Forma de presentación", "multi", [("hematemesis", "Hematemesis"), ("pozo_cafe", "Vómito en pozo de café"), ("melena", "Melena"),
                                                      ("hematoquecia", "Hematoquecia"), ("rectorragia", "Rectorragia"), ("oculto", "Sangrado oculto / anemia")]),
        F("inicio", "Inicio", "text"),
        F("episodios", "Número de episodios", "number", None),
        F("hemodinamia", "Repercusión", "multi", [("mareo", "Mareo"), ("sincope", "Síncope"), ("taquicardia", "Taquicardia"),
                                                  ("hipotension", "Hipotensión")]),
        F("medicamentos", "Medicamentos de riesgo", "multi", [("aine", "AINE"), ("aas", "Ácido acetilsalicílico"),
                                                              ("anticoag", "Anticoagulantes"), ("antiagreg", "Otros antiagregantes"),
                                                              ("isrs", "ISRS")]),
        F("antecedentes_hd", "Antecedentes", "multi", [("hd_previa", "Hemorragia digestiva previa"), ("cirrosis", "Cirrosis / várices"),
                                                       ("ulcera", "Úlcera péptica"), ("diverticulos", "Enfermedad diverticular"),
                                                       ("alcohol", "Consumo de alcohol")]),
        F("escalas", "Escalas calculadas (ver calculadoras)", "text"),
        PREV_TX, HISTORY, NOTES]),
    "anemia_ferropenia": ("Anemia y ferropenia", [
        DURATION,
        F("sintomas", "Síntomas", "multi", [("fatiga", "Fatiga"), ("disnea", "Disnea de esfuerzo"), ("pica", "Pica / pagofagia"),
                                            ("piernas_inquietas", "Piernas inquietas")]),
        F("perdidas", "Posibles pérdidas", "multi", [("menstrual", "Menstruación abundante"), ("digestiva", "Sangrado digestivo visible"),
                                                     ("donacion", "Donación de sangre frecuente"), ("urinaria", "Hematuria")]),
        F("malabsorcion", "Malabsorción posible", "multi", [("celiaca", "Sospecha de enfermedad celíaca"), ("cirugia", "Cirugía gástrica o bariátrica"),
                                                            ("ibp", "Uso crónico de IBP"), ("hp", "H. pylori")]),
        F("dieta", "Dieta (vegetariana, baja en hierro…)", "text"),
        F("hierro", "Tratamiento con hierro (vía, dosis, respuesta)", "textarea", None),
        HISTORY,
        alarms("perdida_peso", "sangrado", "edad_inicio", "antec_cancer"),
        NOTES]),
    "perdida_peso": ("Pérdida de peso", [
        F("peso_habitual", "Peso habitual (kg)", "number", None),
        F("peso_actual", "Peso actual (kg)", "number", None),
        F("tiempo", "En cuánto tiempo", "text"),
        F("intencional", "¿Intencional?", "select", [("no", "No"), ("si", "Sí")]),
        F("ingesta", "Ingesta", "select", [("normal", "Normal"), ("disminuida", "Disminuida"), ("aumentada", "Aumentada")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("hiporexia", "Hiporexia"), ("disfagia", "Disfagia"), ("diarrea", "Diarrea"),
                                                              ("dolor", "Dolor abdominal"), ("fiebre", "Fiebre"), ("sudoracion", "Sudoración nocturna"),
                                                              ("animo", "Ánimo deprimido")]),
        PREV_TX, HISTORY, NOTES]),
    "ictericia_hepaticas": ("Ictericia y alteración de pruebas hepáticas", [
        DURATION, EVOLUTION,
        F("patron", "Patrón bioquímico", "select", [("hepatocelular", "Hepatocelular"), ("colestasico", "Colestásico"), ("mixto", "Mixto"),
                                                     ("bilirrubina_aislada", "Hiperbilirrubinemia aislada")]),
        F("sintomas", "Síntomas", "multi", [("ictericia", "Ictericia"), ("coluria", "Coluria"), ("acolia", "Acolia"), ("prurito", "Prurito"),
                                            ("dolor_hcd", "Dolor en hipocondrio derecho"), ("fiebre", "Fiebre")]),
        F("exposiciones", "Factores de riesgo", "multi", [("alcohol", "Alcohol"), ("medicamentos", "Medicamentos o productos naturales"),
                                                          ("transfusiones", "Transfusiones"), ("tatuajes", "Tatuajes / exposición percutánea"),
                                                          ("sexual", "Riesgo de transmisión sexual"), ("metabolico", "Obesidad / diabetes / dislipidemia"),
                                                          ("viaje", "Viaje a zona endémica")]),
        F("alcohol_detalle", "Consumo de alcohol (cantidad y tiempo)", "text"),
        F("descompensacion", "Datos de descompensación", "multi", [("ascitis", "Ascitis"), ("encefalopatia", "Encefalopatía"),
                                                                   ("hd_variceal", "Hemorragia variceal"), ("coagulopatia", "Coagulopatía")]),
        PREV_TX, HISTORY, NOTES]),
    "distension": ("Distensión abdominal", [
        DURATION, EVOLUTION,
        F("patron", "Patrón", "select", [("progresiva_dia", "Progresiva durante el día"), ("posprandial", "Posprandial"), ("constante", "Constante")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("dolor", "Dolor"), ("flatulencia", "Flatulencia"), ("eructos", "Eructos"),
                                                              ("cambio_habito", "Cambio en el hábito intestinal"), ("saciedad", "Saciedad precoz")]),
        F("dieta", "Relación con alimentos (lácteos, FODMAP, edulcorantes…)", "text"),
        F("ascitis_sospecha", "Datos que sugieren ascitis u otra causa orgánica", "select", [("no", "No"), ("si", "Sí")]),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "sangrado", "anemia", "masa", "edad_inicio", "antec_cancer"),
        NOTES]),
    "eii": ("Enfermedad inflamatoria intestinal", [
        F("diagnostico", "Diagnóstico", "select", [("cu", "Colitis ulcerosa"), ("ec", "Enfermedad de Crohn"), ("no_clasificada", "Colitis no clasificada"),
                                                   ("sospecha", "Sospecha (en estudio)")]),
        F("anio_dx", "Año de diagnóstico", "number", None),
        F("extension", "Extensión / localización", "text"),
        F("comportamiento", "Comportamiento (Crohn)", "select", [("no_aplica", "No aplica"), ("inflamatorio", "Inflamatorio"),
                                                                 ("estenosante", "Estenosante"), ("penetrante", "Penetrante")]),
        F("perianal", "Enfermedad perianal", "select", [("no", "No"), ("si", "Sí")]),
        F("evacuaciones", "Evacuaciones por día", "number", None),
        F("sangre", "Sangre en heces", "select", [("no", "No"), ("ocasional", "Ocasional"), ("frecuente", "Frecuente"), ("siempre", "Siempre")]),
        F("extraintestinales", "Manifestaciones extraintestinales", "multi", [("articular", "Articulares"), ("cutaneas", "Cutáneas"),
                                                                              ("oculares", "Oculares"), ("hepaticas", "Hepatobiliares (CEP)")]),
        F("tratamiento_actual", "Tratamiento actual", "textarea", None),
        F("historial_tx", "Historial de corticoides, inmunomoduladores, biológicos y moléculas pequeñas (respuesta, pérdida de respuesta, efectos adversos)",
          "textarea", None),
        F("cribado", "Cribado previo al tratamiento y vacunas (TB, VHB, VHC, VIH, varicela…)", "textarea", None),
        F("actividad_global", "Valoración global del médico", "select", [("remision", "Remisión"), ("leve", "Leve"), ("moderada", "Moderada"),
                                                                         ("grave", "Grave")]),
        F("indices", "Índices de actividad pendientes de licencia/validación (Mayo, Harvey-Bradshaw…): no habilitados", "text"),
        NOTES]),
    "pancreas_biliar": ("Enfermedades pancreáticas y biliares", [
        F("cuadro", "Cuadro", "select", [("pa", "Pancreatitis aguda"), ("pc", "Pancreatitis crónica"), ("quiste", "Lesión quística pancreática"),
                                         ("litiasis", "Litiasis biliar"), ("coledocolitiasis", "Coledocolitiasis / colangitis"),
                                         ("estenosis", "Estenosis biliar"), ("protesis", "Paciente con prótesis biliar")]),
        DURATION, EVOLUTION,
        F("etiologia", "Etiología sospechada", "multi", [("biliar", "Biliar"), ("alcohol", "Alcohol"), ("trigliceridos", "Hipertrigliceridemia"),
                                                         ("farmacos", "Fármacos"), ("cpre", "Post-CPRE"), ("idiopatica", "Idiopática")]),
        F("insuf_exocrina", "Datos de insuficiencia pancreática exocrina", "multi", [("esteatorrea", "Esteatorrea"), ("perdida_peso", "Pérdida de peso"),
                                                                                    ("deficit_vitaminas", "Déficit de vitaminas liposolubles")]),
        F("diabetes", "Diabetes asociada", "select", [("no", "No"), ("si", "Sí")]),
        F("imagenes", "Imágenes y evolución (tamaño de quistes, conducto, fechas)", "textarea", None),
        F("protesis", "Prótesis: tipo, fecha de colocación y fecha prevista de revisión o retiro", "textarea", None),
        PREV_TX, HISTORY,
        alarms("perdida_peso", "ictericia", "fiebre", "masa"),
        NOTES]),
}

LICENSE_PENDING = ["GerdQ", "Criterios de Roma IV (cuestionarios)", "PAC-SYM / PAC-QOL", "IBS-SSS", "Índice de Mayo", "Harvey-Bradshaw",
                   "CDAI", "MUST / NRS-2002 (nutrición)"]


def clean(form_code: str, src) -> tuple[dict, list]:
    """Valida y normaliza los datos de un formulario (src: request.form)."""
    title, fields = FORMS[form_code]
    data, errors = {}, []
    for key, label, kind, options in fields:
        if kind == "multi":
            allowed = {o[0] for o in options}
            vals = [v for v in src.getlist(key) if v in allowed]
            if vals:
                data[key] = vals
        elif kind == "select":
            v = src.get(key) or ""
            if v and v in {o[0] for o in options}:
                data[key] = v
        elif kind == "bristol":
            v = src.get(key) or ""
            if v:
                if v not in {str(n) for n, _ in BRISTOL}:
                    errors.append(f"{label}: valor no válido.")
                else:
                    data[key] = int(v)
        elif kind == "number":
            v = (src.get(key) or "").strip().replace(",", ".")
            if v:
                try:
                    x = float(v)
                    if x < 0 or x > 100000:
                        raise ValueError
                    data[key] = int(x) if x.is_integer() else x
                except ValueError:
                    errors.append(f"{label}: debe ser un número.")
        else:
            v = (src.get(key) or "").strip()
            if v:
                data[key] = v[:4000]
    return data, errors


def render_summary(form_code: str, data: dict) -> list[tuple[str, str]]:
    title, fields = FORMS[form_code]
    out = []
    for key, label, kind, options in fields:
        if key not in data:
            continue
        v = data[key]
        if kind == "multi":
            d = dict(options)
            out.append((label, ", ".join(d.get(x, x) for x in v)))
        elif kind == "select":
            out.append((label, dict(options).get(v, v)))
        elif kind == "bristol":
            out.append((label, f"Tipo {v}: {dict(BRISTOL)[v]}"))
        else:
            out.append((label, str(v)))
    return out
