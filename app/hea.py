"""Asistente para redactar la historia de la enfermedad actual (v0.12.0).

El médico marca opciones de los formularios de neurología (gi_forms.FORMS) y este módulo arma un párrafo en español
con EXACTAMENTE lo marcado. Reglas:
- No agrega síntomas, datos ni conclusiones que el médico no marcó.
- Solo escribe negativos («Niega…») si el médico marcó «Interrogados y negados los no marcados»; si no, calla.
- El texto se inserta en el campo de la nota, donde el médico lo revisa y corrige.
"""
from .gi_forms import BRISTOL, FORMS, clean

MOTIVO = {
    "cefalea": "cefalea", "crisis": "crisis epilépticas", "deficit": "déficit neurológico focal", "mareo": "mareo",
    "periferico": "debilidad, adormecimiento o dolor en las extremidades", "cognitivo": "deterioro cognitivo",
    "movimiento": "temblor o trastorno del movimiento",
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
        "factores": "Factores asociados: {v}.",
    },
    "cefalea": {
        "inicio": {"subito": "De inicio súbito.", "progresivo": "De inicio progresivo en minutos u horas.", "cronico": "De larga evolución."},
        "localizacion": "Localización: {v}.", "caracter": "De carácter {v}.", "intensidad": "Intensidad {v}/10.",
        "dias_mes": "Presenta cefalea {v} días al mes.",
        "duracion_crisis": {"seg": "Cada episodio dura segundos.", "min": "Cada episodio dura de 15 a 180 minutos.",
                            "horas": "Cada episodio dura de 4 a 72 horas.", "continua": "El dolor es continuo."},
        "aura": "Con aura {v}.", "analgesicos": "Usa analgésicos o triptanes {v} días al mes.",
    },
    "crisis": {
        "tipo": "Tipo de crisis: {v}.", "frecuencia": "Frecuencia: {v}.", "ultima": "Última crisis: {v}.",
        "fenomenos": "Durante la crisis: {v}.",
        "postictal": {"confusion": "Después de la crisis queda confuso.", "somnolencia": "Después de la crisis queda somnoliento.",
                      "paresia": "Presenta debilidad transitoria después de la crisis.", "rapida": "Se recupera de inmediato."},
        "testigo": YESNO("Los eventos fueron presenciados por un testigo.", "Sin testigo de los eventos."),
        "desencadenantes_crisis": "Desencadenantes: {v}.", "medicacion": "Fármacos anticrisis y adherencia: {v}.",
        "efectos": "Efectos adversos: {v}.", "conduce": YESNO("Conduce vehículos.", "No conduce vehículos."),
    },
    "deficit": {
        "inicio": {"subito": "De inicio súbito.", "progresivo": "De instalación progresiva en horas o días.", "despertar": "Lo notó al despertar."},
        "hora": "Último momento visto bien: {v}.", "lado": {"derecho": "Afecta el lado derecho.", "izquierdo": "Afecta el lado izquierdo.",
                                                            "bilateral": "Afecta ambos lados."},
        "resolucion": {"lt1h": "Los síntomas se resolvieron por completo en menos de 1 hora.", "gt1h": "Los síntomas se resolvieron por completo en más de 1 hora.",
                       "parcial": "Los síntomas mejoraron parcialmente.", "persiste": "Los síntomas persisten.", "empeora": "Los síntomas empeoran."},
        "factores": "Factores de riesgo vascular: {v}.", "antitromboticos": "Antitrombóticos: {v}.",
    },
    "mareo": {
        "tipo": {"vertigo": "Describe vértigo, con sensación de giro de objetos.", "inestabilidad": "Describe inestabilidad o desequilibrio.",
                 "presincope": "Describe sensación de desmayo."},
        "episodios": {"seg": "Los episodios duran segundos.", "min": "Los episodios duran minutos.", "horas": "Los episodios duran horas.",
                      "continuo": "Es continuo, por días."},
        "desencadenantes_mareo": "Se desencadena con {v}.",
    },
    "periferico": {
        "distribucion": {"distal_simetrica": "De distribución distal y simétrica.", "proximal": "De predominio proximal.",
                         "un_miembro": "Afecta un miembro.", "hemicuerpo": "Afecta un lado del cuerpo.", "territorio": "En el territorio de un nervio o raíz."},
        "territorio": "Nervio o raíz sospechada: {v}.",
    },
    "cognitivo": {
        "informante": "Informa: {v}.", "inicio": {"insidioso": "De inicio insidioso.", "subagudo": "De instalación en semanas.",
                                                    "escalonado": "De evolución escalonada."},
        "dominios": "Afecta {v}.", "conducta": "En conducta y sueño: {v}.",
        "funcionalidad": {"independiente": "Es independiente en sus actividades.", "instrumentales": "Necesita ayuda en actividades instrumentales.",
                          "basicas": "Necesita ayuda en actividades básicas."},
    },
    "movimiento": {
        "lado": {"derecho": "Inició en el lado derecho.", "izquierdo": "Inició en el lado izquierdo.", "bilateral": "De inicio bilateral."},
        "no_motores": "Síntomas no motores: {v}.", "factores": "Fármacos y exposiciones: {v}.", "off": "Refiere {v} horas OFF al día.",
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
