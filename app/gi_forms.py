"""Formularios de consulta de neurología (NeuroMed Pro; estructura de la Fase 2 de GastroMed Pro).

Contenido propio, redactado para NeuroMed Pro. No reproduce cuestionarios validados protegidos por licencia
(p. ej., MoCA, MMSE, HIT-6, MDS-UPDRS): se registran como «pendientes de licencia».
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

COMMON_ALARMS = [("inicio_subito", "Inicio súbito, máxima intensidad en menos de 1 minuto"), ("fiebre", "Fiebre"),
                 ("rigidez_nuca", "Rigidez de nuca"), ("deficit_focal", "Déficit neurológico focal"),
                 ("conciencia", "Alteración de la conciencia o confusión"), ("convulsion", "Convulsión"),
                 ("edad_inicio", "Inicio después de los 50 años"), ("inmunosupresion", "Inmunosupresión, VIH o cáncer"),
                 ("embarazo", "Embarazo o posparto"), ("trauma", "Traumatismo craneal reciente"),
                 ("anticoagulado", "Uso de anticoagulantes"), ("progresion_rapida", "Progresión rápida en días"),
                 ("bulbar_resp", "Dificultad para tragar o respirar"), ("esfinteres", "Pérdida de control de esfínteres"),
                 ("perdida_peso", "Pérdida de peso involuntaria")]


def alarms(*keys, extra=()):
    d = dict(COMMON_ALARMS)
    return ("signos_alarma", "Signos de alarma presentes", "multi", [(k, d[k]) for k in keys] + list(extra))


def F(key, label, kind="text", options=None):
    return (key, label, kind, options)


YN = [("no", "No"), ("si", "Sí")]
SIDE = [("derecho", "Derecho"), ("izquierdo", "Izquierdo"), ("bilateral", "Bilateral"), ("alternante", "Alternante")]

# NeuroMed Pro: formularios de consulta de neurología (contenido propio). Las claves se guardan con la nota.
FORMS = {
    "cefalea": ("Cefalea", [
        DURATION, EVOLUTION,
        F("inicio", "Forma de inicio", "select", [("subito", "Súbito"), ("progresivo", "Progresivo en minutos u horas"),
                                                  ("cronico", "Crónico, de larga evolución")]),
        F("localizacion", "Localización", "multi", [("hemicraneal_der", "Hemicraneal derecha"), ("hemicraneal_izq", "Hemicraneal izquierda"),
                                                    ("frontal", "Frontal"), ("temporal", "Temporal"), ("occipital", "Occipital o nuca"),
                                                    ("periorbitaria", "Periorbitaria"), ("holocraneal", "Holocraneal")]),
        F("caracter", "Carácter", "select", [("pulsatil", "Pulsátil"), ("opresivo", "Opresivo"), ("punzante", "Punzante"),
                                             ("lancinante", "Lancinante (como descarga)"), ("sordo", "Sordo")]),
        F("intensidad", "Intensidad (0–10)", "number", None),
        F("dias_mes", "Días con cefalea al mes", "number", None),
        F("duracion_crisis", "Duración de cada episodio", "select", [("seg", "Segundos"), ("min", "15 a 180 minutos"),
                                                                     ("horas", "4 a 72 horas"), ("continua", "Continua")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("nausea", "Náusea"), ("vomito", "Vómito"), ("fotofobia", "Fotofobia"),
                                                              ("fonofobia", "Fonofobia"), ("empeora_actividad", "Empeora con la actividad física"),
                                                              ("autonomicos", "Lagrimeo, rinorrea o ptosis del mismo lado"),
                                                              ("inquietud", "Inquietud o agitación durante el dolor")]),
        F("aura", "Aura", "multi", [("visual", "Visual (luces, zigzag, escotomas)"), ("sensitiva", "Sensitiva (hormigueo que avanza)"),
                                    ("lenguaje", "De lenguaje"), ("motora", "Motora")]),
        F("desencadenantes", "Desencadenantes (desvelo, ayuno, estrés, menstruación, alimentos…)", "text"),
        F("analgesicos", "Días al mes con analgésicos o triptanes", "number", None),
        PREV_TX, HISTORY,
        alarms("inicio_subito", "fiebre", "rigidez_nuca", "deficit_focal", "conciencia", "convulsion", "edad_inicio", "inmunosupresion",
               "embarazo", "trauma", "anticoagulado", extra=[("valsalva", "Empeora con tos, esfuerzo o al acostarse"),
                                                             ("cambio_patron", "Cambio reciente del patrón habitual")]),
        NOTES]),
    "crisis": ("Crisis epilépticas", [
        DURATION, EVOLUTION,
        F("tipo", "Tipo de crisis", "multi", [("tcg", "Tónico-clónica generalizada"), ("focal_conciencia", "Focal sin alteración de la conciencia"),
                                              ("focal_alterada", "Focal con alteración de la conciencia"), ("focal_bilateral", "Focal que evoluciona a bilateral"),
                                              ("ausencias", "Ausencias"), ("mioclonias", "Mioclonías"), ("atonicas", "Atónicas (caídas)")]),
        F("frecuencia", "Frecuencia de las crisis", "text"),
        F("ultima", "Fecha de la última crisis", "text"),
        F("fenomenos", "Fenómenos durante la crisis", "multi", [("aura", "Aura o sensación previa"), ("automatismos", "Automatismos"),
                                                                 ("mordedura", "Mordedura lateral de lengua"), ("esfinteres", "Relajación de esfínteres"),
                                                                 ("cianosis", "Cianosis"), ("ojos_abiertos", "Ojos abiertos durante el evento"),
                                                                 ("desviacion", "Desviación de la cabeza o la mirada")]),
        F("postictal", "Estado después de la crisis", "select", [("confusion", "Confusión"), ("somnolencia", "Somnolencia"),
                                                                 ("paresia", "Debilidad transitoria (Todd)"), ("rapida", "Recuperación inmediata")]),
        F("testigo", "Hubo testigo", "select", YN),
        F("desencadenantes_crisis", "Desencadenantes", "multi", [("desvelo", "Desvelo"), ("alcohol", "Alcohol"), ("olvido", "Olvido de medicación"),
                                                                 ("fiebre", "Fiebre"), ("menstruacion", "Menstruación"), ("luces", "Luces intermitentes"),
                                                                 ("estres", "Estrés")]),
        F("medicacion", "Fármacos anticrisis actuales y adherencia", "text"),
        F("efectos", "Efectos adversos", "text"),
        F("conduce", "Conduce vehículos", "select", YN),
        PREV_TX, HISTORY,
        alarms("fiebre", "rigidez_nuca", "deficit_focal", "conciencia", "trauma", "embarazo", "inmunosupresion",
               extra=[("prolongada", "Crisis de más de 5 minutos o en salvas")]),
        NOTES]),
    "deficit": ("Déficit focal / ACV o AIT", [
        F("inicio", "Forma de inicio", "select", [("subito", "Súbito"), ("progresivo", "Progresivo en horas o días"), ("despertar", "Al despertar")]),
        F("hora", "Hora del último momento visto bien", "text"),
        F("sintomas", "Síntomas", "multi", [("cara", "Desviación de la comisura labial"), ("brazo", "Debilidad de un brazo"), ("pierna", "Debilidad de una pierna"),
                                            ("habla", "Dificultad para hablar"), ("comprension", "Dificultad para comprender"), ("vision", "Pérdida de visión"),
                                            ("diplopia", "Visión doble"), ("vertigo", "Vértigo o desequilibrio"), ("sensibilidad", "Adormecimiento de un lado"),
                                            ("cefalea", "Cefalea")]),
        F("lado", "Lado afectado", "select", SIDE[:3]),
        F("resolucion", "Evolución de los síntomas", "select", [("lt1h", "Resolución completa en menos de 1 hora"),
                                                                ("gt1h", "Resolución completa en más de 1 hora"), ("parcial", "Mejoría parcial"),
                                                                ("persiste", "Persisten igual"), ("empeora", "Empeoran")]),
        F("factores", "Factores de riesgo vascular", "multi", [("hta", "Hipertensión"), ("dm", "Diabetes"), ("fa", "Fibrilación auricular"),
                                                               ("tabaco", "Tabaquismo"), ("dislipidemia", "Dislipidemia"), ("acv_previo", "ACV o AIT previo"),
                                                               ("cardiopatia", "Cardiopatía isquémica")]),
        F("antitromboticos", "Antiagregantes o anticoagulantes que toma", "text"),
        PREV_TX, HISTORY,
        alarms("conciencia", "convulsion", "anticoagulado", "trauma", "progresion_rapida", extra=[("cefalea_intensa", "Cefalea intensa de inicio súbito"),
                                                                                                 ("vomito", "Vómito")]),
        NOTES]),
    "mareo": ("Mareo y vértigo", [
        DURATION, EVOLUTION,
        F("tipo", "Tipo", "select", [("vertigo", "Vértigo (giro de objetos)"), ("inestabilidad", "Inestabilidad o desequilibrio"),
                                     ("presincope", "Sensación de desmayo")]),
        F("episodios", "Duración de cada episodio", "select", [("seg", "Segundos"), ("min", "Minutos"), ("horas", "Horas"), ("continuo", "Continuo, días")]),
        F("desencadenantes_mareo", "Desencadenantes", "multi", [("posicion", "Cambios de posición en la cama"), ("cabeza", "Girar o inclinar la cabeza"),
                                                                ("ponerse_pie", "Ponerse de pie"), ("espontaneo", "Espontáneo")]),
        F("acompanantes", "Síntomas acompañantes", "multi", [("nausea", "Náusea o vómito"), ("hipoacusia", "Disminución de la audición"),
                                                              ("acufenos", "Acúfenos"), ("plenitud", "Plenitud ótica"), ("diplopia", "Visión doble"),
                                                              ("disartria", "Dificultad para articular"), ("ataxia", "No puede caminar"),
                                                              ("cefalea", "Cefalea")]),
        PREV_TX, HISTORY,
        alarms("inicio_subito", "deficit_focal", "conciencia", "anticoagulado", extra=[("factores_vasculares", "Varios factores de riesgo vascular")]),
        NOTES]),
    "periferico": ("Debilidad, adormecimiento o dolor neuropático", [
        DURATION, EVOLUTION,
        F("distribucion", "Distribución", "select", [("distal_simetrica", "Distal y simétrica (guante y calcetín)"), ("proximal", "Proximal"),
                                                      ("un_miembro", "Un miembro"), ("hemicuerpo", "Un lado del cuerpo"),
                                                      ("territorio", "Territorio de un nervio o raíz")]),
        F("sintomas", "Síntomas", "multi", [("adormecimiento", "Adormecimiento"), ("hormigueo", "Hormigueo"), ("dolor_urente", "Dolor urente"),
                                            ("calambres", "Calambres"), ("debilidad", "Debilidad"), ("fatigable", "Debilidad que empeora durante el día"),
                                            ("fasciculaciones", "Fasciculaciones"), ("dolor_lumbar", "Dolor lumbar o cervical irradiado")]),
        F("territorio", "Nervio o raíz sospechada", "text"),
        F("factores", "Factores asociados", "multi", [("diabetes", "Diabetes"), ("alcohol", "Alcohol"), ("quimio", "Quimioterapia"),
                                                      ("b12", "Déficit de vitamina B12 o cirugía bariátrica"), ("infeccion", "Infección reciente"),
                                                      ("vacuna", "Vacunación reciente"), ("familiar", "Familiares con síntomas parecidos")]),
        PREV_TX, HISTORY,
        alarms("progresion_rapida", "bulbar_resp", "esfinteres", "perdida_peso"),
        NOTES]),
    "cognitivo": ("Deterioro cognitivo", [
        DURATION, EVOLUTION,
        F("informante", "Informante y parentesco", "text"),
        F("inicio", "Forma de inicio", "select", [("insidioso", "Insidioso"), ("subagudo", "En semanas"), ("escalonado", "Escalonado")]),
        F("dominios", "Dominios afectados", "multi", [("memoria", "Memoria reciente"), ("lenguaje", "Lenguaje"), ("orientacion", "Orientación"),
                                                      ("ejecutivas", "Planificación y juicio"), ("visuoespacial", "Orientación espacial"),
                                                      ("atencion", "Atención")]),
        F("conducta", "Conducta y sueño", "multi", [("apatia", "Apatía"), ("depresion", "Ánimo deprimido"), ("alucinaciones", "Alucinaciones"),
                                                    ("agitacion", "Agitación o agresividad"), ("rem", "Habla o se mueve mientras sueña"),
                                                    ("fluctuaciones", "Fluctuaciones marcadas")]),
        F("funcionalidad", "Funcionalidad", "select", [("independiente", "Independiente"), ("instrumentales", "Ayuda en actividades instrumentales"),
                                                       ("basicas", "Ayuda en actividades básicas")]),
        F("factores", "Factores asociados", "multi", [("vascular", "Factores de riesgo vascular"), ("alcohol", "Alcohol"),
                                                      ("farmacos", "Fármacos sedantes o anticolinérgicos"), ("auditivo", "Pérdida auditiva"),
                                                      ("familiar", "Familiares con demencia")]),
        PREV_TX, HISTORY,
        alarms("progresion_rapida", "deficit_focal", "convulsion", "trauma", "edad_inicio", extra=[("marcha_esfinteres", "Trastorno de la marcha e incontinencia")]),
        NOTES]),
    "movimiento": ("Temblor y trastornos del movimiento", [
        DURATION, EVOLUTION,
        F("sintomas", "Síntomas", "multi", [("temblor_reposo", "Temblor de reposo"), ("temblor_accion", "Temblor al usar las manos"),
                                            ("lentitud", "Lentitud de movimientos"), ("rigidez", "Rigidez"), ("marcha", "Pasos cortos o arrastra los pies"),
                                            ("caidas", "Caídas"), ("micrografia", "Letra pequeña"), ("hipomimia", "Cara poco expresiva"),
                                            ("involuntarios", "Movimientos involuntarios")]),
        F("lado", "Lado de inicio", "select", SIDE[:3]),
        F("no_motores", "Síntomas no motores", "multi", [("estrenimiento", "Estreñimiento"), ("olfato", "Pérdida del olfato"),
                                                         ("rem", "Habla o se mueve mientras sueña"), ("depresion", "Ánimo deprimido"),
                                                         ("ortostatismo", "Mareo al ponerse de pie")]),
        F("factores", "Fármacos y exposiciones", "multi", [("metoclopramida", "Metoclopramida"), ("antipsicoticos", "Antipsicóticos"),
                                                           ("flunarizina", "Flunarizina o cinarizina"), ("alcohol_mejora", "El temblor mejora con alcohol"),
                                                           ("familiar", "Familiares con temblor")]),
        F("off", "Horas OFF al día (si recibe levodopa)", "number", None),
        PREV_TX, HISTORY,
        alarms("progresion_rapida", "conciencia", extra=[("caidas_tempranas", "Caídas en el primer año"), ("disautonomia", "Disautonomía grave")]),
        NOTES]),
}

LICENSE_PENDING = ["MoCA (Montreal Cognitive Assessment)", "Mini-Mental (MMSE)", "HIT-6", "Escala de Epworth", "MDS-UPDRS",
                   "IRLS (piernas inquietas)"]


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
