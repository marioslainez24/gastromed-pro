"""Escalas neurológicas de NeuroMed Pro (1.0).

Mismas reglas que app/calculators.py: cada escala declara fuente, fórmula, población, manejo de datos ausentes, interpretación
prudente y limitaciones; si falta un dato obligatorio no se calcula; el resultado nunca es una orden terapéutica. Los casos de
referencia se comprueban en tests/test_neuro_escalas.py y se muestran al médico en la pantalla de revisión antes de aprobar
la escala. Las descripciones de cada opción están redactadas en español para NeuroMed Pro a partir de la publicación original.
"""
from .calculators import Calculator, Field


def _opts(labels, start=0):
    return [(str(i), f"{i} · {l}") for i, l in enumerate(labels, start)]


def _sum(v, keys):
    return sum(int(v[k]) for k in keys)


# ------------------------------------------------------------------------------------------------ NIHSS
NIH_ITEMS = [
    ("i1a", "1a. Nivel de conciencia", ["Alerta", "Somnoliento, despierta con estímulo menor", "Estuporoso, requiere estímulos repetidos o dolorosos",
                                        "Coma o sin respuesta"]),
    ("i1b", "1b. Preguntas (mes y edad)", ["Responde ambas correctamente", "Responde una", "Ninguna correcta"]),
    ("i1c", "1c. Órdenes (abrir y cerrar ojos, apretar la mano)", ["Realiza ambas", "Realiza una", "Ninguna"]),
    ("i2", "2. Mirada conjugada", ["Normal", "Parálisis parcial de la mirada", "Desviación forzada"]),
    ("i3", "3. Campos visuales", ["Sin pérdida", "Hemianopsia parcial", "Hemianopsia completa", "Hemianopsia bilateral (ceguera)"]),
    ("i4", "4. Parálisis facial", ["Normal", "Menor", "Parcial", "Completa"]),
    ("i5a", "5a. Motor brazo izquierdo", ["Sin caída en 10 s", "Cae antes de 10 s sin tocar la cama", "Algún esfuerzo contra la gravedad",
                                         "Sin esfuerzo contra la gravedad", "Sin movimiento"]),
    ("i5b", "5b. Motor brazo derecho", ["Sin caída en 10 s", "Cae antes de 10 s sin tocar la cama", "Algún esfuerzo contra la gravedad",
                                        "Sin esfuerzo contra la gravedad", "Sin movimiento"]),
    ("i6a", "6a. Motor pierna izquierda", ["Sin caída en 5 s", "Cae antes de 5 s sin tocar la cama", "Algún esfuerzo contra la gravedad",
                                           "Sin esfuerzo contra la gravedad", "Sin movimiento"]),
    ("i6b", "6b. Motor pierna derecha", ["Sin caída en 5 s", "Cae antes de 5 s sin tocar la cama", "Algún esfuerzo contra la gravedad",
                                          "Sin esfuerzo contra la gravedad", "Sin movimiento"]),
    ("i7", "7. Ataxia de extremidades", ["Ausente", "En una extremidad", "En dos extremidades"]),
    ("i8", "8. Sensibilidad", ["Normal", "Pérdida leve a moderada", "Pérdida grave o total"]),
    ("i9", "9. Lenguaje", ["Normal", "Afasia leve a moderada", "Afasia grave", "Mutismo o afasia global"]),
    ("i10", "10. Disartria", ["Normal", "Leve a moderada", "Grave o anartria"]),
    ("i11", "11. Extinción e inatención", ["Ninguna", "En una modalidad", "Profunda o en más de una modalidad"]),
]


def _nihss(v):
    t = _sum(v, [k for k, _, _ in NIH_ITEMS])
    cat = "sin déficit" if t == 0 else "leve" if t <= 4 else "moderado" if t <= 15 else "moderado a grave" if t <= 20 else "grave"
    return {"valor": t, "categoria": cat, "texto": f"NIHSS {t} · {cat}",
            "interpretacion": "Gravedad del déficit neurológico del ACV (0–42). Un NIHSS ≥6 aumenta la probabilidad de oclusión de gran "
                              "vaso. Un puntaje bajo no descarta discapacidad (afasia aislada, hemianopsia o déficit de la mano)."}


NIHSS = Calculator(
    code="nihss", name="NIHSS (escala de ictus del NIH)", version="Brott-1989", group="ACV",
    source="Brott T et al. Measurements of acute cerebral infarction: a clinical examination scale. Stroke 1989;20:864-70. "
           "Versión en español: Montaner J, Álvarez-Sabín J. Med Clin (Barc) 2006;126:241-5.",
    verified_against=["Ítems y puntajes de la escala oficial del NIH (stroke.nih.gov); casos sumados a mano"],
    population="Adultos con sospecha o diagnóstico de ACV.",
    formula="Suma de 15 ítems: 1a (0–3), 1b (0–2), 1c (0–2), mirada (0–2), campos (0–3), facial (0–3), cada brazo (0–4), "
            "cada pierna (0–4), ataxia (0–2), sensibilidad (0–2), lenguaje (0–3), disartria (0–2), extinción (0–2). Rango 0–42.",
    rounding="Puntos enteros.", missing="Todos los ítems son obligatorios.",
    limitations="Valora menos el territorio posterior. Un miembro amputado o una articulación fija se registra como no evaluable (anótelo y "
                "puntúe 0 en ese ítem).",
    fields=[Field(k, l, kind="select", options=_opts(o)) for k, l, o in NIH_ITEMS],
    compute=_nihss,
    reference_cases=[({k: "0" for k, _, _ in NIH_ITEMS}, {"valor": 0, "categoria": "sin déficit"}),
                     ({**{k: "0" for k, _, _ in NIH_ITEMS}, "i1b": "1", "i2": "1", "i4": "2", "i5b": "2", "i6b": "1", "i9": "1", "i10": "1"},
                      {"valor": 9, "categoria": "moderado"}),
                     ({k: str(len(o) - 1) for k, _, o in NIH_ITEMS}, {"valor": 42, "categoria": "grave"})])


# ------------------------------------------------------------------------------------------------ ABCD2
def _abcd2(v):
    p = {"Edad ≥60": 1 if v["edad"] >= 60 else 0, "PA ≥140/90": 1 if v["pa"] else 0, "Clínica": int(v["clinica"]),
         "Duración": int(v["duracion"]), "Diabetes": 1 if v["dm"] else 0}
    t = sum(p.values())
    cat, r = ("bajo", "1.0") if t <= 3 else ("moderado", "4.1") if t <= 5 else ("alto", "8.1")
    return {"valor": t, "categoria": cat, "texto": f"ABCD² {t} · riesgo {cat}", "detalle": p,
            "interpretacion": f"Riesgo de ACV a 2 días en la cohorte de validación: {r} %. Todo AIT requiere estudio urgente "
                              "(imagen cerebral y vascular, ECG) independientemente del puntaje."}


ABCD2 = Calculator(
    code="abcd2", name="ABCD² (ataque isquémico transitorio)", version="Johnston-2007", group="ACV",
    source="Johnston SC et al. Validation and refinement of scores to predict very early stroke risk after transient ischaemic attack. "
           "Lancet 2007;369:283-92.",
    verified_against=["Tabla de puntos y riesgos a 2 días publicados (Lancet 2007)"],
    population="Adultos con AIT en las primeras horas o días.",
    formula="Edad ≥60 1; PA ≥140/90 en la primera evaluación 1; debilidad unilateral 2 o trastorno del habla sin debilidad 1; "
            "duración ≥60 min 2 o 10–59 min 1; diabetes 1. Rango 0–7.",
    rounding="Puntos enteros.", missing="Edad, clínica y duración obligatorias; PA y diabetes se toman como «no» si no se marcan.",
    limitations="No sustituye la imagen vascular: una estenosis carotídea o una FA cambian el manejo con cualquier puntaje.",
    fields=[Field("edad", "Edad", "años", min=18, max=120), Field("pa", "PA ≥140/90 mmHg en la primera evaluación", kind="bool", required=False),
            Field("clinica", "Clínica", kind="select", options=[("0", "0 · Otros síntomas"), ("1", "1 · Trastorno del habla sin debilidad"),
                                                                ("2", "2 · Debilidad unilateral")]),
            Field("duracion", "Duración", kind="select", options=[("0", "0 · Menos de 10 minutos"), ("1", "1 · 10 a 59 minutos"),
                                                                  ("2", "2 · 60 minutos o más")]),
            Field("dm", "Diabetes", kind="bool", required=False)],
    compute=_abcd2,
    reference_cases=[({"edad": "45", "clinica": "0", "duracion": "0"}, {"valor": 0, "categoria": "bajo"}),
                     ({"edad": "70", "pa": "1", "clinica": "2", "duracion": "1"}, {"valor": 5, "categoria": "moderado"}),
                     ({"edad": "70", "pa": "1", "clinica": "2", "duracion": "2", "dm": "1"}, {"valor": 7, "categoria": "alto"})])


# ------------------------------------------------------------------------------------------------ Rankin
MRS_TXT = ["Sin síntomas", "Sin discapacidad significativa: realiza sus actividades habituales pese a síntomas",
           "Discapacidad leve: no realiza todas sus actividades previas, pero se vale por sí mismo",
           "Discapacidad moderada: necesita alguna ayuda, camina sin ayuda",
           "Discapacidad moderadamente grave: no camina ni atiende sus necesidades sin ayuda",
           "Discapacidad grave: encamado, incontinente, requiere cuidado constante", "Muerte"]


def _mrs(v):
    r = int(v["grado"])
    cat = "independiente" if r <= 2 else "dependiente" if r <= 5 else "muerte"
    return {"valor": r, "categoria": cat, "texto": f"Rankin modificada {r} · {MRS_TXT[r].split(':')[0].lower()}",
            "interpretacion": "mRS 0–2 se considera buen resultado funcional en los ensayos de ACV. El mRS previo al evento orienta la "
                              "indicación de los tratamientos de reperfusión."}


MRS = Calculator(
    code="rankin", name="Escala de Rankin modificada (mRS)", version="vanSwieten-1988", group="ACV",
    source="van Swieten JC et al. Interobserver agreement for the assessment of handicap in stroke patients. Stroke 1988;19:604-7.",
    verified_against=["Grados publicados (Stroke 1988)"],
    population="Adultos después de un ACV u otra lesión neurológica.", formula="Un solo grado de 0 a 6.",
    rounding="Entero.", missing="Obligatorio.", limitations="Escala global: no describe qué déficit causa la discapacidad.",
    fields=[Field("grado", "Situación funcional", kind="select", options=_opts(MRS_TXT))],
    compute=_mrs,
    reference_cases=[({"grado": "0"}, {"valor": 0, "categoria": "independiente"}), ({"grado": "3"}, {"valor": 3, "categoria": "dependiente"}),
                     ({"grado": "6"}, {"valor": 6, "categoria": "muerte"})])


# ------------------------------------------------------------------------------------------------ ASPECTS
ASPECTS_REG = [("c", "Núcleo caudado"), ("l", "Núcleo lenticular"), ("ic", "Cápsula interna"), ("i", "Ínsula"),
               ("m1", "M1 · corteza anterior de la ACM"), ("m2", "M2 · corteza lateral al ribete insular"), ("m3", "M3 · corteza posterior de la ACM"),
               ("m4", "M4 · anterior, nivel supraganglionar"), ("m5", "M5 · lateral, nivel supraganglionar"), ("m6", "M6 · posterior, nivel supraganglionar")]


def _aspects(v):
    t = 10 - sum(1 for k, _ in ASPECTS_REG if v[k])
    cat = "6 a 10" if t >= 6 else "3 a 5" if t >= 3 else "0 a 2"
    return {"valor": t, "categoria": cat, "texto": f"ASPECTS {t}",
            "interpretacion": "Cada región con cambios isquémicos tempranos resta 1 punto de 10. 6–10 es el perfil habitual de los ensayos de "
                              "trombectomía en ventana temprana; con 3–5, ensayos de 2023 mostraron beneficio en pacientes seleccionados. "
                              "La decisión se toma con neurointervención."}


ASPECTS = Calculator(
    code="aspects", name="ASPECTS (TAC en ACV de la ACM)", version="Barber-2000", group="ACV",
    source="Barber PA et al. Validity and reliability of a quantitative computed tomography score in predicting outcome of hyperacute stroke "
           "before thrombolytic therapy. Lancet 2000;355:1670-4. Núcleo extenso: Sarraj A et al. N Engl J Med 2023;388:1259-71.",
    verified_against=["Regiones y regla de resta publicadas (Lancet 2000)"],
    population="Adultos con ACV agudo del territorio de la arteria cerebral media.",
    formula="10 menos 1 punto por cada una de las 10 regiones con cambios isquémicos tempranos.",
    rounding="Entero.", missing="Las regiones no marcadas se toman como normales.",
    limitations="Depende de la calidad de la TAC y de la experiencia del lector. No aplica al territorio posterior.",
    fields=[Field(k, l, kind="bool", required=False) for k, l in ASPECTS_REG],
    compute=_aspects,
    reference_cases=[({}, {"valor": 10, "categoria": "6 a 10"}), ({"i": "1", "m2": "1"}, {"valor": 8, "categoria": "6 a 10"}),
                     ({"c": "1", "l": "1", "ic": "1", "i": "1", "m1": "1", "m2": "1"}, {"valor": 4, "categoria": "3 a 5"})])


# ------------------------------------------------------------------------------------------------ hemorragia
def _ich(v):
    g = int(v["glasgow"])
    p = {"Glasgow": 2 if g <= 4 else 1 if g <= 12 else 0, "Volumen ≥30 mL": 1 if v["volumen"] >= 30 else 0,
         "Hemorragia intraventricular": 1 if v["hiv"] else 0, "Origen infratentorial": 1 if v["infra"] else 0,
         "Edad ≥80": 1 if v["edad"] >= 80 else 0}
    t = sum(p.values())
    mort = {0: "0", 1: "13", 2: "26", 3: "72", 4: "97", 5: "100", 6: "100"}[t]
    return {"valor": t, "texto": f"ICH score {t}", "detalle": p,
            "interpretacion": f"Mortalidad a 30 días en la cohorte de derivación: {mort} %. Es una escala pronóstica: no debe usarse sola para "
                              "limitar el tratamiento en las primeras 24 horas."}


ICH = Calculator(
    code="ich_score", name="ICH score (hemorragia intracerebral)", version="Hemphill-2001", group="Hemorragia cerebral",
    source="Hemphill JC et al. The ICH score: a simple, reliable grading scale for intracerebral hemorrhage. Stroke 2001;32:891-7.",
    verified_against=["Tabla de puntos y mortalidad por puntaje publicadas (Stroke 2001)"],
    population="Adultos con hemorragia intracerebral espontánea.",
    formula="Glasgow 3–4: 2, 5–12: 1, 13–15: 0; volumen ≥30 mL 1; hemorragia intraventricular 1; infratentorial 1; edad ≥80 1. Rango 0–6.",
    rounding="Puntos enteros.", missing="Glasgow, volumen y edad obligatorios.",
    limitations="Volumen estimado por ABC/2 en la TAC inicial. No aplica a hemorragias por trauma, tumor o malformación.",
    fields=[Field("glasgow", "Glasgow", min=3, max=15), Field("volumen", "Volumen del hematoma (ABC/2)", "mL", min=0, max=300),
            Field("hiv", "Extensión intraventricular", kind="bool", required=False),
            Field("infra", "Origen infratentorial", kind="bool", required=False), Field("edad", "Edad", "años", min=18, max=120)],
    compute=_ich,
    reference_cases=[({"glasgow": "15", "volumen": "10", "edad": "60"}, {"valor": 0}),
                     ({"glasgow": "10", "volumen": "35", "hiv": "1", "edad": "70"}, {"valor": 3}),
                     ({"glasgow": "4", "volumen": "40", "hiv": "1", "infra": "1", "edad": "85"}, {"valor": 6})])


def _hh(v):
    g = int(v["grado"])
    return {"valor": g, "categoria": "buen grado" if g <= 2 else "intermedio" if g == 3 else "mal grado",
            "texto": f"Hunt y Hess grado {['', 'I', 'II', 'III', 'IV', 'V'][g]}",
            "interpretacion": "Grado clínico de la hemorragia subaracnoidea aneurismática; los grados IV–V se asocian a peor pronóstico."}


HUNT_HESS = Calculator(
    code="hunt_hess", name="Hunt y Hess (hemorragia subaracnoidea)", version="Hunt-1968", group="Hemorragia cerebral",
    source="Hunt WE, Hess RM. Surgical risk as related to time of intervention in the repair of intracranial aneurysms. J Neurosurg 1968;28:14-20.",
    verified_against=["Grados publicados (J Neurosurg 1968)"],
    population="Adultos con hemorragia subaracnoidea aneurismática.", formula="Un grado de I a V según el cuadro clínico.",
    rounding="Entero.", missing="Obligatorio.", limitations="Subjetiva; se complementa con WFNS, que usa el Glasgow.",
    fields=[Field("grado", "Grado clínico", kind="select", options=[
        ("1", "I · Asintomático o cefalea leve y rigidez de nuca leve"), ("2", "II · Cefalea moderada a grave, rigidez de nuca, sin déficit salvo par craneal"),
        ("3", "III · Somnolencia, confusión o déficit focal leve"), ("4", "IV · Estupor, hemiparesia moderada a grave"),
        ("5", "V · Coma profundo, rigidez de descerebración")])],
    compute=_hh,
    reference_cases=[({"grado": "1"}, {"valor": 1, "categoria": "buen grado"}), ({"grado": "4"}, {"valor": 4, "categoria": "mal grado"})])


def _wfns(v):
    g = v["glasgow"]
    r = 1 if g == 15 else (3 if v["deficit"] else 2) if g >= 13 else 4 if g >= 7 else 5
    return {"valor": r, "categoria": "buen grado" if r <= 3 else "mal grado", "texto": f"WFNS grado {['', 'I', 'II', 'III', 'IV', 'V'][r]}",
            "interpretacion": "Grados I–III: buen grado clínico; IV–V: mal grado, con mayor riesgo de mala evolución."}


WFNS = Calculator(
    code="wfns", name="WFNS (hemorragia subaracnoidea)", version="Teasdale-1988", group="Hemorragia cerebral",
    source="Teasdale GM et al. A universal subarachnoid hemorrhage scale: report of a committee of the World Federation of Neurosurgical "
           "Societies. J Neurol Neurosurg Psychiatry 1988;51:1457.",
    verified_against=["Tabla publicada (JNNP 1988)"],
    population="Adultos con hemorragia subaracnoidea aneurismática.",
    formula="Glasgow 15: I; 13–14 sin déficit motor: II; 13–14 con déficit: III; 7–12: IV; 3–6: V.",
    rounding="Entero.", missing="Glasgow obligatorio; el déficit se toma como «no» si no se marca.",
    limitations="Usar el Glasgow después de la reanimación inicial.",
    fields=[Field("glasgow", "Glasgow", min=3, max=15), Field("deficit", "Déficit motor focal", kind="bool", required=False)],
    compute=_wfns,
    reference_cases=[({"glasgow": "15"}, {"valor": 1}), ({"glasgow": "14", "deficit": "1"}, {"valor": 3}), ({"glasgow": "6"}, {"valor": 5})])


def _fisher(v):
    g = int(v["grado"])
    r = {0: "bajo", 1: "24", 2: "33", 3: "33", 4: "40"}[g]
    return {"valor": g, "texto": f"Fisher modificada {g}",
            "interpretacion": ("Riesgo bajo de vasoespasmo sintomático." if g == 0 else
                               f"Vasoespasmo sintomático en la cohorte original ≈ {r} %. Vigilar entre los días 3 y 14.")}


FISHER = Calculator(
    code="fisher_mod", name="Fisher modificada (hemorragia subaracnoidea)", version="Frontera-2006", group="Hemorragia cerebral",
    source="Frontera JA et al. Prediction of symptomatic vasospasm after subarachnoid hemorrhage: the modified Fisher scale. "
           "Neurosurgery 2006;59:21-7.",
    verified_against=["Grados y frecuencias publicados (Neurosurgery 2006)"],
    population="Adultos con hemorragia subaracnoidea aneurismática.", formula="Grado 0–4 según grosor de la hemorragia y sangre intraventricular.",
    rounding="Entero.", missing="Obligatorio.", limitations="Se basa en la TAC inicial.",
    fields=[Field("grado", "Hallazgo en la TAC", kind="select", options=[
        ("0", "0 · Sin HSA ni hemorragia intraventricular"), ("1", "1 · HSA fina o focal, sin hemorragia intraventricular"),
        ("2", "2 · HSA fina, con hemorragia intraventricular"), ("3", "3 · HSA gruesa, sin hemorragia intraventricular"),
        ("4", "4 · HSA gruesa, con hemorragia intraventricular")])],
    compute=_fisher,
    reference_cases=[({"grado": "0"}, {"valor": 0}), ({"grado": "4"}, {"valor": 4})])


# ------------------------------------------------------------------------------------------------ coma y epilepsia
def _four(v):
    t = _sum(v, ["ojos", "motor", "tronco", "resp"])
    return {"valor": t, "texto": f"FOUR {t}/16 (O{v['ojos']} M{v['motor']} T{v['tronco']} R{v['resp']})",
            "interpretacion": "A menor puntaje, mayor compromiso. Útil en pacientes intubados, donde el Glasgow verbal no es valorable. "
                              "Un FOUR de 0 obliga a evaluar los criterios formales de muerte encefálica, no los reemplaza."}


FOUR = Calculator(
    code="four", name="FOUR (respuesta global sin respuesta verbal)", version="Wijdicks-2005", group="Urgencias neurológicas",
    source="Wijdicks EF et al. Validation of a new coma scale: the FOUR score. Ann Neurol 2005;58:585-93.",
    verified_against=["Componentes y puntajes publicados (Ann Neurol 2005)"],
    population="Adultos con alteración de la conciencia, incluidos intubados.",
    formula="Ojos (0–4) + motor (0–4) + reflejos de tronco (0–4) + respiración (0–4). Rango 0–16.",
    rounding="Puntos enteros.", missing="Los cuatro componentes son obligatorios.", limitations="La sedación altera los componentes.",
    fields=[Field("ojos", "Respuesta ocular", kind="select", options=_opts(["Cerrados aun con dolor", "Cerrados, abre al dolor", "Cerrados, abre a la voz fuerte",
                                                                           "Abiertos, no sigue", "Abre, sigue o parpadea a la orden"])),
            Field("motor", "Respuesta motora", kind="select", options=_opts(["Sin respuesta o estado mioclónico", "Extensión al dolor", "Flexión al dolor",
                                                                            "Localiza el dolor", "Pulgar arriba, puño o signo de paz"])),
            Field("tronco", "Reflejos de tronco", kind="select", options=_opts(["Pupilar, corneal y tusígeno ausentes", "Pupilar y corneal ausentes",
                                                                               "Pupilar o corneal ausente", "Una pupila dilatada y fija",
                                                                               "Pupilar y corneal presentes"])),
            Field("resp", "Respiración", kind="select", options=_opts(["A la frecuencia del ventilador o apnea", "Respira por encima del ventilador",
                                                                      "No intubado, respiración irregular", "No intubado, Cheyne-Stokes",
                                                                      "No intubado, patrón regular"]))],
    compute=_four,
    reference_cases=[({"ojos": "4", "motor": "4", "tronco": "4", "resp": "4"}, {"valor": 16}),
                     ({"ojos": "0", "motor": "0", "tronco": "0", "resp": "0"}, {"valor": 0})])


def _stess(v):
    t = _sum(v, ["conciencia", "tipo", "edad", "previas"])
    cat = "desfavorable" if t >= 3 else "favorable"
    return {"valor": t, "categoria": cat, "texto": f"STESS {t} · pronóstico {cat}",
            "interpretacion": "STESS ≥3 se asocia a mayor mortalidad intrahospitalaria; 0–2 tiene alto valor predictivo negativo para muerte."}


STESS = Calculator(
    code="stess", name="STESS (estado epiléptico)", version="Rossetti-2008", group="Epilepsia",
    source="Rossetti AO et al. Status Epilepticus Severity Score (STESS): a tool to orient early treatment strategy. J Neurol 2008;255:1561-6.",
    verified_against=["Componentes y punto de corte publicados (J Neurol 2008)"],
    population="Adultos con estado epiléptico.", formula="Conciencia (0–1) + peor tipo de crisis (0–2) + edad (0 o 2) + crisis previas (0–1). Rango 0–6.",
    rounding="Puntos enteros.", missing="Todos obligatorios.", limitations="No incluye la causa del estado epiléptico, que pesa mucho en el pronóstico.",
    fields=[Field("conciencia", "Conciencia al inicio", kind="select", options=[("0", "0 · Alerta, somnoliento o confuso"), ("1", "1 · Estupor o coma")]),
            Field("tipo", "Peor tipo de crisis", kind="select", options=[("0", "0 · Focal, ausencias o mioclónicas"), ("1", "1 · Tónico-clónica generalizada"),
                                                                         ("2", "2 · No convulsivo en coma")]),
            Field("edad", "Edad", kind="select", options=[("0", "0 · Menor de 65 años"), ("2", "2 · 65 años o más")]),
            Field("previas", "Crisis previas", kind="select", options=[("0", "0 · Sí"), ("1", "1 · No o se desconoce")])],
    compute=_stess,
    reference_cases=[({"conciencia": "0", "tipo": "0", "edad": "0", "previas": "0"}, {"valor": 0, "categoria": "favorable"}),
                     ({"conciencia": "1", "tipo": "2", "edad": "2", "previas": "1"}, {"valor": 6, "categoria": "desfavorable"})])


def _helps(v):
    t = sum(1 for k in ("frec", "esporadicas", "periodicas", "plus", "crisis") if v[k]) + (2 if v["birds"] else 0)
    r = ["5", "12", "27", "50", "73", "88", ">95"][min(t, 6)]
    return {"valor": t, "texto": f"2HELPS2B {t}",
            "interpretacion": f"Riesgo de crisis en el EEG continuo ≈ {r} %. Con 0 puntos puede bastar 1 hora de monitoreo; con 1 o más se "
                              "recomienda prolongarlo a 24 horas o más."}


HELPS2B = Calculator(
    code="2helps2b", name="2HELPS2B (riesgo de crisis en EEG continuo)", version="Struck-2017", group="Epilepsia",
    source="Struck AF et al. Association of an electroencephalography-based risk score with seizure probability in hospitalized patients. "
           "JAMA Neurol 2017;74:1419-24.",
    verified_against=["Componentes y riesgos por puntaje publicados (JAMA Neurol 2017)"],
    population="Adultos hospitalizados en monitoreo con EEG continuo.",
    formula="1 punto cada uno: frecuencia >2 Hz, descargas esporádicas, LPD/LRDA/BIPD, características «plus», crisis previas; BIRDs 2 puntos.",
    rounding="Puntos enteros.", missing="Los elementos no marcados se toman como «no».", limitations="Requiere interpretación experta del EEG.",
    fields=[Field("frec", "Patrón periódico o rítmico con frecuencia >2 Hz", kind="bool", required=False),
            Field("esporadicas", "Descargas epileptiformes esporádicas", kind="bool", required=False),
            Field("periodicas", "LPD, LRDA o BIPD", kind="bool", required=False),
            Field("plus", "Patrón con características «plus»", kind="bool", required=False),
            Field("crisis", "Crisis previas (remotas o recientes)", kind="bool", required=False),
            Field("birds", "BIRDs (descargas rítmicas breves)", kind="bool", required=False)],
    compute=_helps,
    reference_cases=[({}, {"valor": 0}), ({"esporadicas": "1", "crisis": "1"}, {"valor": 2}),
                     ({k: "1" for k in ("frec", "esporadicas", "periodicas", "plus", "crisis", "birds")}, {"valor": 7})])


# ------------------------------------------------------------------------------------------------ movimiento y neuromuscular
def _hy(v):
    s = float(v["estadio"])
    cat = "leve" if s < 3 else "moderado" if s < 4 else "avanzado"
    return {"valor": s, "categoria": cat, "texto": f"Hoehn y Yahr {v['estadio']} · {cat}",
            "interpretacion": "Estadio motor de la enfermedad de Parkinson. Desde el estadio 3 hay inestabilidad postural: prevenir caídas."}


HOEHN_YAHR = Calculator(
    code="hoehn_yahr", name="Hoehn y Yahr modificada (Parkinson)", version="Goetz-2004", group="Movimientos anormales",
    source="Hoehn MM, Yahr MD. Parkinsonism: onset, progression and mortality. Neurology 1967;17:427-42. Goetz CG et al. Movement Disorder "
           "Society Task Force report on the Hoehn and Yahr staging scale. Mov Disord 2004;19:1020-8.",
    verified_against=["Estadios publicados (Mov Disord 2004)"],
    population="Pacientes con enfermedad de Parkinson.", formula="Un estadio de 1 a 5 (incluye 1.5 y 2.5 de la versión modificada).",
    rounding="Medio punto.", missing="Obligatorio.", limitations="Solo valora lo motor; no refleja síntomas no motores ni fluctuaciones.",
    fields=[Field("estadio", "Estadio", kind="select", options=[
        ("1", "1 · Afectación unilateral"), ("1.5", "1.5 · Unilateral con afectación axial"), ("2", "2 · Bilateral sin alteración del equilibrio"),
        ("2.5", "2.5 · Bilateral leve, se recupera en la prueba del empujón"), ("3", "3 · Bilateral leve a moderada, inestabilidad postural, independiente"),
        ("4", "4 · Discapacidad grave, aún camina o se mantiene de pie sin ayuda"), ("5", "5 · En silla de ruedas o encamado si no tiene ayuda")])],
    compute=_hy,
    reference_cases=[({"estadio": "2.5"}, {"valor": 2.5, "categoria": "leve"}), ({"estadio": "4"}, {"valor": 4.0, "categoria": "avanzado"})])


MGADL_ITEMS = [
    ("habla", "Habla", ["Normal", "Disartria o voz nasal intermitente", "Disartria constante, pero se entiende", "Difícil de entender"]),
    ("mastica", "Masticación", ["Normal", "Fatiga con alimentos sólidos", "Fatiga con alimentos blandos", "Sonda de alimentación"]),
    ("deglute", "Deglución", ["Normal", "Atragantamiento ocasional", "Atragantamiento frecuente, cambió la dieta", "Sonda de alimentación"]),
    ("respira", "Respiración", ["Normal", "Disnea con esfuerzo", "Disnea en reposo", "Dependencia de ventilador"]),
    ("dientes", "Cepillarse los dientes o peinarse", ["Sin dificultad", "Esfuerzo extra, sin pausas", "Necesita pausas", "No puede"]),
    ("silla", "Levantarse de una silla", ["Sin dificultad", "Leve, a veces usa los brazos", "Moderada, siempre usa los brazos", "Grave, requiere ayuda"]),
    ("diplopia", "Visión doble", ["Ninguna", "Ocurre, pero no a diario", "Diaria, pero no constante", "Constante"]),
    ("ptosis", "Párpado caído", ["Ninguno", "Ocurre, pero no a diario", "Diario, pero no constante", "Constante"]),
]


def _mgadl(v):
    t = _sum(v, [k for k, _, _ in MGADL_ITEMS])
    bulbar = int(v["deglute"]) >= 2 or int(v["respira"]) >= 2
    return {"valor": t, "categoria": "síntomas bulbares o respiratorios" if bulbar else "sin síntomas bulbares graves",
            "texto": f"MG-ADL {t}/24",
            "interpretacion": ("Disfagia o disnea importantes: valore crisis miasténica (capacidad vital, fuerza cervical). " if bulbar else "")
                              + "Un cambio de 2 puntos o más se considera clínicamente significativo."}


MGADL = Calculator(
    code="mg_adl", name="MG-ADL (miastenia gravis)", version="Wolfe-1999", group="Neuromuscular",
    source="Wolfe GI et al. Myasthenia gravis activities of daily living profile. Neurology 1999;52:1487-9. "
           "Diferencia mínima importante: Muppidi S et al. Muscle Nerve 2011;44:727-31.",
    verified_against=["Ítems y puntajes publicados (Neurology 1999)"],
    population="Pacientes con miastenia gravis.", formula="Suma de 8 ítems de 0 a 3. Rango 0–24.",
    rounding="Puntos enteros.", missing="Todos obligatorios.", limitations="Lo informa el paciente sobre la última semana.",
    fields=[Field(k, l, kind="select", options=_opts(o)) for k, l, o in MGADL_ITEMS],
    compute=_mgadl,
    reference_cases=[({k: "0" for k, _, _ in MGADL_ITEMS}, {"valor": 0, "categoria": "sin síntomas bulbares graves"}),
                     ({**{k: "1" for k, _, _ in MGADL_ITEMS}, "deglute": "2"}, {"valor": 9, "categoria": "síntomas bulbares o respiratorios"})])


MRC_GROUPS = [("hombro", "Abducción del hombro"), ("codo", "Flexión del codo"), ("muneca", "Extensión de la muñeca"), ("cadera", "Flexión de la cadera"),
              ("rodilla", "Extensión de la rodilla"), ("tobillo", "Dorsiflexión del tobillo")]
MRC_KEYS = [(f"{g}_{s}", f"{l} {sl}") for g, l in MRC_GROUPS for s, sl in (("d", "derecha"), ("i", "izquierda"))]
MRC_OPTS = [(str(x), f"{x} · {t}") for x, t in ((5, "Fuerza normal"), (4, "Contra resistencia"), (3, "Contra la gravedad"),
                                                (2, "Movimiento sin gravedad"), (1, "Contracción visible"), (0, "Sin contracción"))]


def _mrc(v):
    t = _sum(v, [k for k, _ in MRC_KEYS])
    cat = "sin debilidad significativa" if t >= 48 else "debilidad significativa" if t >= 36 else "debilidad grave"
    return {"valor": t, "categoria": cat, "texto": f"MRC suma {t}/60 · {cat}",
            "interpretacion": "Menos de 48 define debilidad adquirida en la UCI; útil también para seguir Guillain-Barré y polineuropatías."}


MRC = Calculator(
    code="mrc_sum", name="MRC suma (fuerza muscular)", version="Kleyweg-1991", group="Neuromuscular",
    source="Kleyweg RP et al. Interobserver agreement in the assessment of muscle strength and functional abilities in Guillain-Barré "
           "syndrome. Muscle Nerve 1991;14:1103-9. Umbral <48: De Jonghe B et al. JAMA 2002;288:2859-67.",
    verified_against=["Grupos musculares y umbral publicados"],
    population="Adultos con debilidad generalizada.", formula="6 grupos musculares de cada lado, de 0 a 5. Rango 0–60.",
    rounding="Puntos enteros.", missing="Todos obligatorios.", limitations="Requiere un paciente despierto y colaborador.",
    fields=[Field(k, l, kind="select", options=MRC_OPTS) for k, l in MRC_KEYS],
    compute=_mrc,
    reference_cases=[({k: "5" for k, _ in MRC_KEYS}, {"valor": 60, "categoria": "sin debilidad significativa"}),
                     ({k: "3" for k, _ in MRC_KEYS}, {"valor": 36, "categoria": "debilidad significativa"})])


# ------------------------------------------------------------------------------------------------ funcionalidad, cognición, sueño, cefalea
BARTHEL_ITEMS = [
    ("comer", "Comer", [("10", "Independiente"), ("5", "Necesita ayuda para cortar o untar"), ("0", "Dependiente")]),
    ("banarse", "Bañarse", [("5", "Independiente"), ("0", "Dependiente")]),
    ("arreglarse", "Arreglarse (cara, pelo, dientes, afeitado)", [("5", "Independiente"), ("0", "Dependiente")]),
    ("vestirse", "Vestirse", [("10", "Independiente"), ("5", "Necesita ayuda, hace la mitad solo"), ("0", "Dependiente")]),
    ("deposiciones", "Deposiciones", [("10", "Continente"), ("5", "Accidente ocasional"), ("0", "Incontinente")]),
    ("miccion", "Micción", [("10", "Continente"), ("5", "Accidente ocasional"), ("0", "Incontinente o sondado")]),
    ("retrete", "Uso del retrete", [("10", "Independiente"), ("5", "Necesita alguna ayuda"), ("0", "Dependiente")]),
    ("traslado", "Traslado cama–sillón", [("15", "Independiente"), ("10", "Mínima ayuda"), ("5", "Gran ayuda, se sienta solo"), ("0", "Dependiente")]),
    ("deambular", "Deambulación", [("15", "Camina 50 m solo"), ("10", "Camina 50 m con ayuda"), ("5", "Independiente en silla de ruedas"), ("0", "Inmóvil")]),
    ("escaleras", "Subir escaleras", [("10", "Independiente"), ("5", "Necesita ayuda"), ("0", "Incapaz")]),
]


def _barthel(v):
    t = _sum(v, [k for k, _, _ in BARTHEL_ITEMS])
    cat = ("independiente" if t == 100 else "dependencia leve" if t >= 60 else "dependencia moderada" if t >= 40
           else "dependencia grave" if t >= 20 else "dependencia total")
    return {"valor": t, "categoria": cat, "texto": f"Barthel {t}/100 · {cat}",
            "interpretacion": "Independencia en actividades básicas de la vida diaria; orienta rehabilitación y apoyo del cuidador."}


BARTHEL = Calculator(
    code="barthel", name="Índice de Barthel", version="Mahoney-1965", group="Funcionalidad y cognición",
    source="Mahoney FI, Barthel DW. Functional evaluation: the Barthel Index. Md State Med J 1965;14:61-5. Cortes de gravedad: Shah S et al. "
           "J Clin Epidemiol 1989;42:703-9.",
    verified_against=["Ítems y puntajes publicados (1965)"],
    population="Adultos con discapacidad física (ACV, neurodegenerativas).", formula="Suma de 10 actividades. Rango 0–100.",
    rounding="Múltiplos de 5.", missing="Todos obligatorios.", limitations="Efecto techo: no detecta problemas en actividades instrumentales.",
    fields=[Field(k, l, kind="select", options=[(x, f"{x} · {t}") for x, t in o]) for k, l, o in BARTHEL_ITEMS],
    compute=_barthel,
    reference_cases=[({k: o[0][0] for k, _, o in BARTHEL_ITEMS}, {"valor": 100, "categoria": "independiente"}),
                     ({k: "0" for k, _, _ in BARTHEL_ITEMS}, {"valor": 0, "categoria": "dependencia total"})])


PFEFFER_ITEMS = ["Manejar su dinero y pagar cuentas", "Hacer trámites o llenar formularios", "Hacer compras solo",
                 "Jugar juegos de habilidad o practicar un pasatiempo", "Calentar agua, preparar café y apagar la estufa",
                 "Preparar una comida completa", "Estar al tanto de las noticias", "Entender un programa de televisión, libro o revista",
                 "Recordar citas, fechas y medicamentos", "Salir del barrio, manejar o usar transporte"]
PFEFFER_OPTS = [("0", "0 · Normal (o nunca lo hizo, pero podría)"), ("1", "1 · Con dificultad, pero lo hace solo"),
                ("2", "2 · Requiere ayuda"), ("3", "3 · Dependiente")]


def _pfeffer(v):
    t = _sum(v, [f"q{i}" for i in range(10)])
    cat = "deterioro funcional" if t >= 9 else "funcionalidad conservada"
    return {"valor": t, "categoria": cat, "texto": f"Pfeffer {t}/30 · {cat}",
            "interpretacion": "Lo responde el familiar o cuidador. Un puntaje ≥9 indica deterioro en actividades instrumentales y apoya demencia "
                              "frente a deterioro cognitivo leve cuando las pruebas cognitivas están alteradas."}


PFEFFER = Calculator(
    code="pfeffer", name="Cuestionario de actividades funcionales de Pfeffer", version="Pfeffer-1982", group="Funcionalidad y cognición",
    source="Pfeffer RI et al. Measurement of functional activities in older adults in the community. J Gerontol 1982;37:323-9.",
    verified_against=["10 actividades, puntaje 0–3 y punto de corte ≥9 publicados"],
    population="Adultos mayores con sospecha de deterioro cognitivo.", formula="Suma de 10 actividades de 0 a 3. Rango 0–30.",
    rounding="Puntos enteros.", missing="Todos obligatorios.", limitations="Influido por la escolaridad, la cultura y el estado físico.",
    fields=[Field(f"q{i}", l, kind="select", options=PFEFFER_OPTS) for i, l in enumerate(PFEFFER_ITEMS)],
    compute=_pfeffer,
    reference_cases=[({f"q{i}": "0" for i in range(10)}, {"valor": 0, "categoria": "funcionalidad conservada"}),
                     ({f"q{i}": ("1" if i < 9 else "0") for i in range(10)}, {"valor": 9, "categoria": "deterioro funcional"})])


def _midas(v):
    t = round(sum(v[k] for k in ("a", "b", "c", "d", "e")))
    g = "I" if t <= 5 else "II" if t <= 10 else "III" if t <= 20 else "IV"
    txt = {"I": "discapacidad mínima", "II": "leve", "III": "moderada", "IV": "grave"}[g]
    return {"valor": t, "categoria": g, "texto": f"MIDAS {t} días · grado {g} ({txt})",
            "interpretacion": "Grados III–IV suelen justificar tratamiento preventivo además del de las crisis. Vigilar el uso excesivo de analgésicos."}


MIDAS = Calculator(
    code="midas", name="MIDAS (discapacidad por migraña)", version="Stewart-2001", group="Cefalea y sueño",
    source="Stewart WF et al. Development and testing of the Migraine Disability Assessment (MIDAS) Questionnaire to assess headache-related "
           "disability. Neurology 2001;56(6 Suppl 1):S20-8.",
    verified_against=["Cinco preguntas y grados publicados"],
    population="Adultos con migraña.", formula="Suma de días perdidos o con productividad reducida en 3 meses. Grado I 0–5, II 6–10, III 11–20, IV ≥21.",
    rounding="Días enteros.", missing="Las cinco preguntas son obligatorias (escriba 0 si no hubo días).",
    limitations="Preguntas redactadas para NeuroMed Pro con el sentido del cuestionario original.",
    fields=[Field("a", "Días que faltó al trabajo o a clases por la cefalea (3 meses)", "días", min=0, max=92),
            Field("b", "Días con productividad en el trabajo o estudio reducida a la mitad o menos", "días", min=0, max=92),
            Field("c", "Días que no hizo tareas del hogar", "días", min=0, max=92),
            Field("d", "Días con productividad en el hogar reducida a la mitad o menos", "días", min=0, max=92),
            Field("e", "Días que se perdió actividades familiares, sociales o de ocio", "días", min=0, max=92)],
    compute=_midas,
    reference_cases=[({"a": "0", "b": "0", "c": "0", "d": "0", "e": "0"}, {"valor": 0, "categoria": "I"}),
                     ({"a": "2", "b": "5", "c": "3", "d": "4", "e": "2"}, {"valor": 16, "categoria": "III"}),
                     ({"a": "5", "b": "5", "c": "5", "d": "5", "e": "1"}, {"valor": 21, "categoria": "IV"})])


SB_ITEMS = [("ronca", "Ronca fuerte"), ("cansancio", "Cansancio o somnolencia durante el día"), ("apneas", "Alguien lo ha visto dejar de respirar al dormir"),
            ("hta", "Hipertensión arterial"), ("imc", "IMC mayor de 35 kg/m²"), ("edad", "Edad mayor de 50 años"),
            ("cuello", "Circunferencia del cuello mayor de 40 cm"), ("hombre", "Sexo masculino")]


def _stopbang(v):
    t = sum(1 for k, _ in SB_ITEMS if v[k])
    cat = "alto" if t >= 5 else "intermedio" if t >= 3 else "bajo"
    return {"valor": t, "categoria": cat, "texto": f"STOP-Bang {t}/8 · riesgo {cat}",
            "interpretacion": "Probabilidad de apnea obstructiva del sueño moderada a grave. Con riesgo intermedio o alto, considerar "
                              "polisomnografía o poligrafía respiratoria."}


STOPBANG = Calculator(
    code="stop_bang", name="STOP-Bang (apnea del sueño)", version="Chung-2008", group="Cefalea y sueño",
    source="Chung F et al. STOP questionnaire: a tool to screen patients for obstructive sleep apnea. Anesthesiology 2008;108:812-21. "
           "Chung F et al. Chest 2016;149:631-8.",
    verified_against=["Ocho preguntas y categorías de riesgo publicadas"],
    population="Adultos con sospecha de apnea obstructiva del sueño.", formula="1 punto por cada respuesta afirmativa. Rango 0–8.",
    rounding="Puntos enteros.", missing="Los elementos no marcados se toman como «no».", limitations="Es tamizaje: no diagnostica apnea.",
    fields=[Field(k, l, kind="bool", required=False) for k, l in SB_ITEMS],
    compute=_stopbang,
    reference_cases=[({}, {"valor": 0, "categoria": "bajo"}), ({"ronca": "1", "hta": "1", "edad": "1"}, {"valor": 3, "categoria": "intermedio"}),
                     ({k: "1" for k, _ in SB_ITEMS}, {"valor": 8, "categoria": "alto"})])


ALL = [NIHSS, ASPECTS, ABCD2, MRS, ICH, HUNT_HESS, WFNS, FISHER, FOUR, STESS, HELPS2B, HOEHN_YAHR, MGADL, MRC, BARTHEL, PFEFFER,
       MIDAS, STOPBANG]
