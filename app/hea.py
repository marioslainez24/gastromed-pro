"""Asistente para redactar la historia de la enfermedad actual (v0.12.0).

El médico marca opciones de los formularios gastroenterológicos (gi_forms.FORMS) y este módulo arma un párrafo en español
con EXACTAMENTE lo marcado. Reglas:
- No agrega síntomas, datos ni conclusiones que el médico no marcó.
- Solo escribe negativos («Niega…») si el médico marcó «Interrogados y negados los no marcados»; si no, calla.
- El texto se inserta en el campo de la nota, donde el médico lo revisa y corrige.
"""
from .gi_forms import BRISTOL, FORMS, clean

MOTIVO = {
    "reflujo_dispepsia": "síntomas de reflujo y dispepsia", "disfagia": "disfagia", "dolor_abdominal": "dolor abdominal",
    "nausea_vomito": "náuseas y vómitos", "diarrea": "diarrea", "estrenimiento": "estreñimiento", "sangrado": "sangrado digestivo",
    "anemia_ferropenia": "anemia", "perdida_peso": "pérdida de peso", "ictericia_hepaticas": "ictericia o alteración de pruebas hepáticas",
    "distension": "distensión abdominal", "eii": "seguimiento de enfermedad inflamatoria intestinal",
    "pancreas_biliar": "enfermedad pancreática o biliar",
}
DURATION_TXT = {"<1s": "menos de una semana", "1-4s": "1 a 4 semanas", "1-3m": "1 a 3 meses", "3-6m": "3 a 6 meses",
                ">6m": "más de 6 meses"}
EVOLUTION_TXT = {"continua": "de curso continuo", "intermitente": "de curso intermitente", "empeorando": "con empeoramiento progresivo",
                 "mejorando": "con tendencia a la mejoría", "estable": "de curso estable"}
UNITS = {"dias": ("día", "días"), "semanas": ("semana", "semanas"), "meses": ("mes", "meses"), "anios": ("año", "años")}

# Plantillas por campo. {v} = valor (lista unida con «y», opción en minúscula, número o texto tal cual).
# Para opciones con frase propia se usa un dict {valor: frase}.
YESNO = lambda si, no: {"si": si, "no": no}  # noqa: E731
T = {
    "*": {
        "sintomas": "Refiere {v}.", "acompanantes": "Se acompaña de {v}.", "tratamientos_previos": "Tratamientos previos: {v}.",
        "antecedentes_relevantes": "Antecedentes relevantes: {v}.", "comentarios": "{v}", "desencadenantes": "Desencadenantes: {v}.",
        "exposiciones": "Como antecedentes de exposición refiere {v}.", "factores": "Factores asociados: {v}.",
        "dieta": "Dieta: {v}.", "imagenes": "Imágenes: {v}.", "protesis": "Prótesis: {v}.",
    },
    "reflujo_dispepsia": {
        "frecuencia": {"<1": "Los síntomas se presentan menos de un día por semana.", "1-2": "Los síntomas se presentan 1 a 2 días por semana.",
                       "3-6": "Los síntomas se presentan 3 a 6 días por semana.", "diario": "Los síntomas son diarios."},
        "nocturnos": YESNO("Presenta síntomas nocturnos.", "Sin síntomas nocturnos."),
        "aine": {"si": "Usa AINE o ácido acetilsalicílico.", "no": "No usa AINE ni ácido acetilsalicílico.",
                 "ocasional": "Uso ocasional de AINE o ácido acetilsalicílico."},
        "ibp": {"no_usado": "No ha usado inhibidores de bomba de protones.", "completa": "Respuesta completa a inhibidores de bomba de protones.",
                "parcial": "Respuesta parcial a inhibidores de bomba de protones.", "sin_respuesta": "Sin respuesta a inhibidores de bomba de protones."},
        "hp_previo": "Estudio previo de H. pylori: {v}.",
    },
    "disfagia": {
        "tipo": {"orofaringea": "La disfagia es orofaríngea, al iniciar la deglución.", "esofagica": "La disfagia es esofágica, de localización retroesternal."},
        "consistencia": {"solidos": "Es solo para sólidos.", "ambos": "Es para sólidos y líquidos desde el inicio.",
                         "progresiva": "Inició con sólidos y progresó a líquidos."},
        "odinofagia": YESNO("Refiere odinofagia.", "Sin odinofagia."),
        "impactacion": YESNO("Ha presentado episodios de impactación alimentaria.", "Sin episodios de impactación alimentaria."),
        "atopia": YESNO("Tiene antecedentes de atopia.", "Sin antecedentes de atopia."),
    },
    "dolor_abdominal": {
        "localizacion": "El dolor se localiza en {v}.", "caracter": "Es de carácter {v}.", "intensidad": "Intensidad {v}/10.",
        "irradiacion": "Se irradia a {v}.",
        "relacion_comidas": {"no": "Sin relación con las comidas.", "empeora": "Empeora al comer.", "mejora": "Mejora al comer."},
        "relacion_evacuacion": {"no": "Sin relación con la evacuación.", "mejora": "Mejora al evacuar.",
                                "cambio_habito": "Se asocia a cambio en el hábito intestinal."},
    },
    "nausea_vomito": {
        "frecuencia": "Presenta {v} episodios de vómito al día.", "contenido": "El contenido es {v}.",
        "momento": {"posprandial_inm": "Los vómitos son posprandiales inmediatos.", "posprandial_tardio": "Los vómitos son posprandiales tardíos.",
                    "matutino": "Los vómitos son matutinos.", "ciclico": "Presenta episodios cíclicos."},
        "deshidratacion": YESNO("Con signos de deshidratación.", "Sin signos de deshidratación."),
    },
    "diarrea": {
        "tipo": {"aguda": "Diarrea aguda (menos de 14 días).", "persistente": "Diarrea persistente (14 a 30 días).",
                 "cronica": "Diarrea crónica (más de 4 semanas)."},
        "frecuencia": "Presenta {v} evacuaciones al día.", "caracteristicas": "Las evacuaciones se acompañan de {v}.",
    },
    "estrenimiento": {
        "frecuencia": "Presenta {v} evacuaciones por semana.", "laxantes": "Laxantes usados y respuesta: {v}.",
    },
    "sangrado": {
        "forma": "Se presenta como {v}.", "inicio": "Inicio: {v}.", "episodios": "Número de episodios: {v}.",
        "hemodinamia": "Con repercusión: {v}.", "medicamentos": "Usa {v}.", "antecedentes_hd": "Antecedentes: {v}.",
        "escalas": "Escalas: {v}.",
    },
    "anemia_ferropenia": {
        "perdidas": "Posibles pérdidas: {v}.", "malabsorcion": "Posible malabsorción: {v}.",
        "hierro": "Tratamiento con hierro: {v}.",
    },
    "perdida_peso": {
        "peso_habitual": "Peso habitual {v} kg.", "peso_actual": "Peso actual {v} kg.", "tiempo": "Pérdida ocurrida en {v}.",
        "intencional": YESNO("La pérdida de peso es intencional.", "La pérdida de peso no es intencional."),
        "ingesta": {"normal": "Ingesta normal.", "disminuida": "Ingesta disminuida.", "aumentada": "Ingesta aumentada."},
    },
    "ictericia_hepaticas": {
        "patron": {"hepatocelular": "Patrón bioquímico hepatocelular.", "colestasico": "Patrón bioquímico colestásico.",
                   "mixto": "Patrón bioquímico mixto.", "bilirrubina_aislada": "Hiperbilirrubinemia aislada."},
        "exposiciones": "Factores de riesgo: {v}.", "alcohol_detalle": "Consumo de alcohol: {v}.",
        "descompensacion": "Con datos de descompensación: {v}.",
    },
    "distension": {
        "patron": {"progresiva_dia": "La distensión es progresiva durante el día.", "posprandial": "La distensión es posprandial.",
                   "constante": "La distensión es constante."},
        "dieta": "Relación con alimentos: {v}.",
        "ascitis_sospecha": YESNO("Hay datos que sugieren ascitis u otra causa orgánica.", "Sin datos que sugieran ascitis u otra causa orgánica."),
    },
    "eii": {
        "diagnostico": {"cu": "Con diagnóstico de colitis ulcerosa.", "ec": "Con diagnóstico de enfermedad de Crohn.",
                        "no_clasificada": "Con diagnóstico de colitis no clasificada.",
                        "sospecha": "En estudio por sospecha de enfermedad inflamatoria intestinal."},
        "anio_dx": "Diagnosticada en {v}.", "extension": "Extensión o localización: {v}.",
        "comportamiento": {"inflamatorio": "Comportamiento inflamatorio.", "estenosante": "Comportamiento estenosante.",
                           "penetrante": "Comportamiento penetrante.", "no_aplica": ""},
        "perianal": YESNO("Con enfermedad perianal.", "Sin enfermedad perianal."),
        "evacuaciones": "Presenta {v} evacuaciones al día.",
        "sangre": {"no": "Sin sangre en las heces.", "ocasional": "Sangre ocasional en las heces.", "frecuente": "Sangre frecuente en las heces.",
                   "siempre": "Sangre en todas las evacuaciones."},
        "extraintestinales": "Manifestaciones extraintestinales: {v}.", "tratamiento_actual": "Tratamiento actual: {v}.",
        "historial_tx": "Historial de tratamientos: {v}.", "cribado": "Cribado y vacunas: {v}.",
        "actividad_global": {"remision": "En valoración global, en remisión.", "leve": "En valoración global, actividad leve.",
                             "moderada": "En valoración global, actividad moderada.", "grave": "En valoración global, actividad grave."},
        "indices": "",
    },
    "pancreas_biliar": {
        "cuadro": {"pa": "Cuadro de pancreatitis aguda.", "pc": "Cuadro de pancreatitis crónica.", "quiste": "Lesión quística pancreática.",
                   "litiasis": "Litiasis biliar.", "coledocolitiasis": "Coledocolitiasis o colangitis.", "estenosis": "Estenosis biliar.",
                   "protesis": "Paciente con prótesis biliar."},
        "etiologia": "Etiología sospechada: {v}.", "insuf_exocrina": "Con datos de insuficiencia pancreática exocrina: {v}.",
        "diabetes": YESNO("Con diabetes asociada.", "Sin diabetes asociada."),
    },
}
SKIP = {"duracion", "evolucion", "signos_alarma"}   # se usan en la frase inicial y en el cierre


def _low(label: str) -> str:
    """Primera letra en minúscula salvo siglas (AINE, IBP, CEP…)."""
    if len(label) > 1 and label[1].isupper():
        return label
    return label[:1].lower() + label[1:]


def _join(items):
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def _fmt_num(x):
    return f"{x:g}" if isinstance(x, float) else str(x)


def _opening(form_code, data, patient, exact):
    who = {"femenino": "Paciente femenina", "masculino": "Paciente masculino"}.get(patient.get("sex"), "Paciente")
    age = patient.get("age")
    who += f" de {age}" if age and age != "—" else ""
    parts = [f"{who} que consulta por {MOTIVO[form_code]}"]
    if exact:
        parts.append(f"de {exact} de evolución")
    elif data.get("duracion"):
        parts.append(f"de {DURATION_TXT[data['duracion']]} de evolución")
    text = " ".join(parts)
    if data.get("evolucion"):
        text += ", " + EVOLUTION_TXT[data["evolucion"]]
    return text + "."


def exact_time(src):
    """«3 meses» a partir de número + unidad; None si no se indicó."""
    n = (src.get("hea_tiempo") or "").strip().replace(",", ".")
    unit = src.get("hea_unidad")
    if not n or unit not in UNITS:
        return None
    try:
        x = float(n)
    except ValueError:
        return None
    if not 0 < x <= 100:
        return None
    one, many = UNITS[unit]
    return f"{_fmt_num(int(x) if x.is_integer() else x)} {one if x == 1 else many}"


def compose(form_code: str, src, patient: dict) -> tuple[str, dict, list]:
    """Devuelve (texto, datos limpios del formulario, errores)."""
    if form_code not in FORMS:
        raise KeyError(form_code)
    data, errors = clean(form_code, src)
    title, fields = FORMS[form_code]
    tpl = {**T["*"], **T.get(form_code, {})}
    out = [_opening(form_code, data, patient, exact_time(src))]
    for key, label, kind, options in fields:
        if key in SKIP or key not in data:
            continue
        v = data[key]
        t = tpl.get(key)
        if kind == "bristol":
            out.append(f"Consistencia de las heces tipo {v} de Bristol ({_low(dict(BRISTOL)[v])}).")
            continue
        if isinstance(t, dict):
            phrase = t.get(v)
            if phrase is None:
                phrase = f"{label}: {_low(dict(options).get(v, str(v)))}."
            if phrase:
                out.append(phrase)
            continue
        if kind == "multi":
            val = _join([_low(dict(options)[x]) for x in v])
        elif kind == "select":
            val = _low(dict(options).get(v, v))
        elif kind == "number":
            val = _fmt_num(v)
        else:
            val = v.rstrip(".")
        if t == "":
            continue
        out.append((t or (label + ": {v}.")).format(v=val))
    # Signos de alarma: presentes siempre; ausentes solo si el médico confirma que los interrogó.
    alarm_field = next((f for f in fields if f[0] == "signos_alarma"), None)
    if alarm_field:
        opts = dict(alarm_field[3])
        present = data.get("signos_alarma", [])
        if present:
            out.append("Signos de alarma: " + _join([_low(opts[x]) for x in present]) + ".")
        if src.get("hea_niega") == "1":
            absent = [_low(opts[k]) for k in opts if k not in present]
            if absent:
                out.append(("Niega " if not present else "Niega los demás signos de alarma interrogados: ") + _join(absent) + ".")
    text = " ".join(x.strip() for x in out if x.strip())
    return text, data, errors
