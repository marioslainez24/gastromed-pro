"""Biblioteca de calculadoras clínicas.

Reglas (documento de requisitos §12):
- Cada calculadora declara fuente, fórmula, versión, población, variables con unidades, manejo de datos ausentes,
  límites/topes y redondeo, interpretación prudente y limitaciones.
- Si falta un dato obligatorio NO se calcula (MissingData).
- El resultado nunca es una orden terapéutica.
- Cada una tiene casos de referencia en tests/test_calculadoras.py y requiere aprobación clínica en la clínica antes
  de poder guardarse en un expediente.

Verificación de fórmulas (30-oct-2026): ver el campo `verified_against` de cada calculadora.
"""
import math
from dataclasses import dataclass, field


class MissingData(ValueError):
    pass


@dataclass
class Field:
    key: str
    label: str
    unit: str = ""
    kind: str = "number"          # number | select | bool
    options: list = field(default_factory=list)   # [(valor, etiqueta)]
    lab: str | None = None        # código de lab_tests para importar del expediente
    min: float | None = None
    max: float | None = None
    required: bool = True
    help: str = ""


@dataclass
class Calculator:
    code: str
    name: str
    version: str
    group: str
    source: str
    verified_against: list
    population: str
    formula: str
    rounding: str
    missing: str
    limitations: str
    fields: list
    compute: callable = None
    reference_cases: list = field(default_factory=list)   # [(entradas, resultado_esperado_dict)]


def _num(inp, key, f: Field):
    v = inp.get(key)
    if v in (None, ""):
        if f.required:
            raise MissingData(f"Falta «{f.label}»: no se puede calcular.")
        return None
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        raise MissingData(f"«{f.label}» no es un número válido.") from None
    if not math.isfinite(x):
        raise MissingData(f"«{f.label}» no es un número válido.")
    if (f.min is not None and x < f.min) or (f.max is not None and x > f.max):
        raise MissingData(f"«{f.label}» fuera de rango plausible ({f.min}–{f.max} {f.unit}). Verifique el valor y la unidad.")
    return x


def _sel(inp, key, f: Field):
    v = inp.get(key)
    allowed = [str(o[0]) for o in f.options]
    if v in (None, "") or str(v) not in allowed:
        if f.required:
            raise MissingData(f"Falta «{f.label}»: no se puede calcular.")
        return None
    return str(v)


def _bool(inp, key):
    return str(inp.get(key, "")).lower() in ("1", "true", "si", "sí", "on")


def parse(calc: Calculator, inp: dict) -> dict:
    out = {}
    for f in calc.fields:
        if f.kind == "number":
            out[f.key] = _num(inp, f.key, f)
        elif f.kind == "select":
            out[f.key] = _sel(inp, f.key, f)
        else:
            out[f.key] = _bool(inp, f.key)
    return out


def run(calc: Calculator, inp: dict) -> dict:
    v = parse(calc, inp)
    res = calc.compute(v)
    res.setdefault("aviso", "Resultado de apoyo. No sustituye el juicio clínico ni constituye una indicación terapéutica.")
    return res


# ----------------------------------------------------------------------------------------------- Child-Pugh
def _child_pugh(v):
    bili, alb, inr = v["bt"], v["alb"], v["inr"]
    pts = {
        "Bilirrubina": 1 if bili < 2 else (2 if bili <= 3 else 3),
        "Albúmina": 1 if alb > 3.5 else (2 if alb >= 2.8 else 3),
        "INR": 1 if inr < 1.7 else (2 if inr <= 2.3 else 3),
        "Ascitis": {"ausente": 1, "leve": 2, "moderada": 3}[v["ascitis"]],
        "Encefalopatía": {"ausente": 1, "g12": 2, "g34": 3}[v["encefalopatia"]],
    }
    total = sum(pts.values())
    clase = "A" if total <= 6 else ("B" if total <= 9 else "C")
    return {"valor": total, "texto": f"{total} puntos · Clase {clase}", "clase": clase, "detalle": pts,
            "interpretacion": f"Clase {clase} de Child-Pugh (A: 5–6, B: 7–9, C: 10–15)."}


CHILD = Calculator(
    code="child_pugh", name="Child-Pugh", version="CTP-2026.1", group="Hepatología",
    source="Pugh RN et al. Br J Surg 1973;60:646-9 (modificación de Child-Turcotte). Umbrales con INR según uso actual.",
    verified_against=["MSD/Merck Manual Professional: Child-Turcotte-Pugh Scoring System (consultado 30-oct-2026)"],
    population="Adultos con cirrosis hepática. No validado en colestasis primaria (CBP/CEP usan otros umbrales de bilirrubina).",
    formula="Suma de 5 parámetros (1–3 puntos cada uno): bilirrubina (<2, 2–3, >3 mg/dL), albúmina (>3.5, 2.8–3.5, <2.8 g/dL), "
            "INR (<1.7, 1.7–2.3, >2.3), ascitis (ausente, leve/controlada con diuréticos, al menos moderada pese a diuréticos), "
            "encefalopatía (ausente, grado 1–2, grado 3–4).",
    rounding="Puntos enteros; sin redondeo.",
    missing="Todos los parámetros son obligatorios; si falta alguno no se calcula.",
    limitations="Ascitis y encefalopatía son subjetivas. En CBP/CEP los umbrales de bilirrubina difieren y esta versión no los aplica.",
    fields=[Field("bt", "Bilirrubina total", "mg/dL", lab="bt", min=0.1, max=60),
            Field("alb", "Albúmina", "g/dL", lab="alb", min=0.5, max=7),
            Field("inr", "INR", "", lab="inr", min=0.5, max=15),
            Field("ascitis", "Ascitis", kind="select", options=[("ausente", "Ausente"), ("leve", "Leve o controlada con diuréticos"),
                                                                ("moderada", "Al menos moderada pese a diuréticos")]),
            Field("encefalopatia", "Encefalopatía hepática", kind="select",
                  options=[("ausente", "Ausente"), ("g12", "Grado 1–2"), ("g34", "Grado 3–4")])],
    compute=_child_pugh,
    reference_cases=[
        ({"bt": "1.0", "alb": "4.0", "inr": "1.0", "ascitis": "ausente", "encefalopatia": "ausente"}, {"valor": 5, "clase": "A"}),
        ({"bt": "2.5", "alb": "3.0", "inr": "1.8", "ascitis": "leve", "encefalopatia": "ausente"}, {"valor": 9, "clase": "B"}),
        ({"bt": "3.1", "alb": "2.7", "inr": "2.4", "ascitis": "moderada", "encefalopatia": "g34"}, {"valor": 15, "clase": "C"}),
        # Límites exactos: bilirrubina 2.0 y 3.0 → 2 puntos; albúmina 3.5 y 2.8 → 2; INR 1.7 y 2.3 → 2
        ({"bt": "2.0", "alb": "3.5", "inr": "1.7", "ascitis": "ausente", "encefalopatia": "ausente"}, {"valor": 8, "clase": "B"}),
        ({"bt": "3.0", "alb": "2.8", "inr": "2.3", "ascitis": "ausente", "encefalopatia": "ausente"}, {"valor": 8, "clase": "B"}),
    ])


# ----------------------------------------------------------------------------------------------- MELD-Na (OPTN 2016)
def _meld_base(cr, bili, inr, dialysis):
    cr = 4.0 if dialysis else min(max(cr, 1.0), 4.0)
    bili, inr = max(bili, 1.0), max(inr, 1.0)
    return 9.57 * math.log(cr) + 3.78 * math.log(bili) + 11.20 * math.log(inr) + 6.43, cr, bili, inr


def _meld_na(v):
    raw, cr, bili, inr = _meld_base(v["creat"], v["bt"], v["inr"], v["dialisis"])
    meld = round(raw)
    na = min(max(v["na"], 125.0), 137.0)
    score = meld + 1.32 * (137 - na) - 0.033 * meld * (137 - na) if meld > 11 else meld
    score = int(round(min(max(score, 6), 40)))
    return {"valor": score, "texto": f"MELD-Na {score} (MELD {meld})", "meld": meld,
            "detalle": {"Creatinina usada": cr, "Bilirrubina usada": bili, "INR usado": inr, "Sodio usado": na},
            "interpretacion": "Estimación de mortalidad a 90 días en hepatopatía crónica. Rango 6–40."}


MELD_NA = Calculator(
    code="meld_na", name="MELD-Na", version="OPTN-2016", group="Hepatología",
    source="Kim WR et al. N Engl J Med 2008;359:1018-26; adoptado por OPTN/UNOS (2016).",
    verified_against=["MetricGate, documentación MELD-Na (fórmula y límites OPTN), consultado 30-oct-2026"],
    population="Adultos (≥12 años) con hepatopatía crónica terminal. No usar en insuficiencia hepática aguda.",
    formula="MELD = 9.57·ln(Cr) + 3.78·ln(Bili) + 11.20·ln(INR) + 6.43, redondeado. "
            "Si MELD > 11: MELD-Na = MELD + 1.32·(137−Na) − 0.033·MELD·(137−Na).",
    rounding="MELD redondeado al entero antes de la corrección por sodio; resultado final entero entre 6 y 40.",
    missing="Creatinina, bilirrubina, INR y sodio son obligatorios.",
    limitations="Valores <1 se llevan a 1; creatinina máx. 4 (o 4 si diálisis ≥2 veces en 7 días); sodio acotado a 125–137. "
                "Distinto de MELD 3.0: no mezclar.",
    fields=[Field("creat", "Creatinina", "mg/dL", lab="creat", min=0.1, max=25),
            Field("bt", "Bilirrubina total", "mg/dL", lab="bt", min=0.1, max=60),
            Field("inr", "INR", "", lab="inr", min=0.5, max=15),
            Field("na", "Sodio", "mmol/L", lab="na", min=100, max=180),
            Field("dialisis", "Diálisis ≥2 veces en la última semana (o 24 h de hemodiálisis continua)", kind="bool", required=False)],
    compute=_meld_na,
    reference_cases=[
        ({"creat": "1", "bt": "1", "inr": "1", "na": "137"}, {"valor": 6, "meld": 6}),                 # mínimo
        # MELD = 9.57·ln2 + 3.78·ln3 + 11.20·ln1.5 + 6.43 = 6.6334+4.1528+4.5412+6.43 = 21.758 → 22;
        # Na 130: 22 + 1.32·7 − 0.033·22·7 = 22 + 9.24 − 5.082 = 26.158 → 26
        ({"creat": "2", "bt": "3", "inr": "1.5", "na": "130"}, {"valor": 26, "meld": 22}),
        # Sodio acotado a 125 aunque sea 115; diálisis fuerza creatinina 4
        ({"creat": "1", "bt": "1", "inr": "1", "na": "115", "dialisis": "1"}, {"meld": 20}),
        ({"creat": "10", "bt": "40", "inr": "8", "na": "120"}, {"valor": 40}),                         # tope 40
    ])


# ----------------------------------------------------------------------------------------------- MELD 3.0 (Kim 2021)
def _meld3(v):
    female = 1.33 if v["sexo"] == "femenino" else 0.0
    bili = max(v["bt"], 1.0)
    inr = max(v["inr"], 1.0)
    cr = 3.0 if v["dialisis"] else min(max(v["creat"], 1.0), 3.0)
    na = min(max(v["na"], 125.0), 137.0)
    alb = min(max(v["alb"], 1.5), 3.5)
    raw = (female + 4.56 * math.log(bili) + 0.82 * (137 - na) - 0.24 * (137 - na) * math.log(bili)
           + 9.09 * math.log(inr) + 11.14 * math.log(cr) + 1.85 * (3.5 - alb) - 1.83 * (3.5 - alb) * math.log(cr) + 6)
    score = int(round(min(max(raw, 6), 40)))
    return {"valor": score, "texto": f"MELD 3.0: {score}", "crudo": round(raw, 2),
            "detalle": {"Sexo (término)": female, "Bilirrubina usada": bili, "INR usado": inr, "Creatinina usada": cr,
                        "Sodio usado": na, "Albúmina usada": alb},
            "interpretacion": "Estimación de mortalidad a 90 días en hepatopatía crónica (versión 2021, incluye sexo y albúmina)."}


MELD3 = Calculator(
    code="meld3", name="MELD 3.0", version="Kim-2021", group="Hepatología",
    source="Kim WR et al. MELD 3.0: The Model for End-Stage Liver Disease Updated for the Modern Era. Gastroenterology 2021;161:1887.",
    verified_against=["MSD/Merck Manual, calculadora MELD 3.0 (ecuación, límites y referencia), consultado 30-oct-2026"],
    population="Adultos con hepatopatía crónica. Derivado en candidatos a trasplante de EE. UU.",
    formula="1.33·(mujer) + 4.56·ln(Bili) + 0.82·(137−Na) − 0.24·(137−Na)·ln(Bili) + 9.09·ln(INR) + 11.14·ln(Cr) "
            "+ 1.85·(3.5−Alb) − 1.83·(3.5−Alb)·ln(Cr) + 6",
    rounding="Entero más cercano; acotado a 6–40.",
    missing="Sexo, bilirrubina, sodio, INR, creatinina y albúmina obligatorios.",
    limitations="Bilirrubina, INR y creatinina <1 → 1; creatinina máx. 3.0 (3.0 con diálisis: regla de OPTN, PENDIENTE de "
                "verificar contra la política vigente); sodio 125–137; albúmina 1.5–3.5 g/dL. Requiere sexo biológico registrado.",
    fields=[Field("sexo", "Sexo", kind="select", options=[("femenino", "Femenino"), ("masculino", "Masculino")]),
            Field("bt", "Bilirrubina total", "mg/dL", lab="bt", min=0.1, max=60),
            Field("na", "Sodio", "mmol/L", lab="na", min=100, max=180),
            Field("inr", "INR", "", lab="inr", min=0.5, max=15),
            Field("creat", "Creatinina", "mg/dL", lab="creat", min=0.1, max=25),
            Field("alb", "Albúmina", "g/dL", lab="alb", min=0.5, max=7),
            Field("dialisis", "Diálisis ≥2 veces en la última semana", kind="bool", required=False)],
    compute=_meld3,
    reference_cases=[
        # Todos en valores «normales» acotados: 0 + 0 + 0 + 0 + 0 + 0 + 0 + 0 + 6 = 6
        ({"sexo": "masculino", "bt": "1", "na": "137", "inr": "1", "creat": "1", "alb": "3.5"}, {"valor": 6}),
        # Mujer: 6 + 1.33 = 7.33 → 7
        ({"sexo": "femenino", "bt": "1", "na": "137", "inr": "1", "creat": "1", "alb": "3.5"}, {"valor": 7}),
        # Caso calculado a mano: hombre, Bili 2, Na 130, INR 1.5, Cr 1.5, Alb 3.0
        # 4.56·0.6931=3.1607; 0.82·7=5.74; −0.24·7·0.6931=−1.1645; 9.09·0.4055=3.6857; 11.14·0.4055=4.5169;
        # 1.85·0.5=0.925; −1.83·0.5·0.4055=−0.3710; +6 → 22.493 → 22
        ({"sexo": "masculino", "bt": "2", "na": "130", "inr": "1.5", "creat": "1.5", "alb": "3.0"}, {"valor": 22}),
    ])


# ----------------------------------------------------------------------------------------------- FIB-4
def _fib4(v):
    age, ast, alt, plt = v["edad"], v["ast"], v["alt"], v["plt"]
    val = (age * ast) / (plt * math.sqrt(alt))
    low = 2.0 if age >= 65 else 1.30
    cat = "bajo" if val < low else ("alto" if val > 2.67 else "indeterminado")
    warn = []
    if age < 35:
        warn.append("Menores de 35 años: el índice tiene menor exactitud; interpretar con cautela.")
    return {"valor": round(val, 2), "texto": f"FIB-4 {val:.2f} · riesgo {cat} de fibrosis avanzada", "categoria": cat,
            "advertencias": warn,
            "interpretacion": f"<{low:.2f} riesgo bajo; {low:.2f}–2.67 indeterminado; >2.67 riesgo alto"
                              f"{' (umbral inferior 2.0 por edad ≥65)' if age >= 65 else ''}."}


FIB4 = Calculator(
    code="fib4", name="FIB-4", version="Sterling-2006", group="Hepatología",
    source="Sterling RK et al. Hepatology 2006;43:1317-25.",
    verified_against=["Ahmed M. World J Hepatol 2015;7:1450 (tabla 3: fórmula y puntos de corte)",
                      "MetricGate, documentación FIB-4 (umbral 2.0 en ≥65 años), consultado 30-oct-2026"],
    population="Adultos con hepatopatía crónica (derivado en coinfección VIH/VHC; ampliamente usado en MASLD y hepatitis virales).",
    formula="(Edad × AST) / (Plaquetas[10^9/L] × √ALT)",
    rounding="Dos decimales.",
    missing="Edad, AST, ALT y plaquetas obligatorios.",
    limitations="Menor exactitud <35 y ≥65 años (en ≥65 se usa 2.0 como umbral inferior). Puede alterarse en hepatitis aguda o "
                "trombocitopenia de otra causa.",
    fields=[Field("edad", "Edad", "años", min=1, max=120),
            Field("ast", "AST", "U/L", lab="ast", min=1, max=20000),
            Field("alt", "ALT", "U/L", lab="alt", min=1, max=20000),
            Field("plt", "Plaquetas", "10^3/µL (=10^9/L)", lab="plt", min=1, max=2000)],
    compute=_fib4,
    reference_cases=[
        # 50·40/(200·√25) = 2000/1000 = 2.00 → indeterminado
        ({"edad": "50", "ast": "40", "alt": "25", "plt": "200"}, {"valor": 2.0, "categoria": "indeterminado"}),
        # 40·20/(250·√16) = 800/1000 = 0.80 → bajo
        ({"edad": "40", "ast": "20", "alt": "16", "plt": "250"}, {"valor": 0.8, "categoria": "bajo"}),
        # 60·90/(100·√36) = 5400/600 = 9.0 → alto
        ({"edad": "60", "ast": "90", "alt": "36", "plt": "100"}, {"valor": 9.0, "categoria": "alto"}),
        # 70 años: 70·25/(200·√25)=1750/1000=1.75 → bajo (umbral 2.0)
        ({"edad": "70", "ast": "25", "alt": "25", "plt": "200"}, {"valor": 1.75, "categoria": "bajo"}),
    ])


# ----------------------------------------------------------------------------------------------- APRI
def _apri(v):
    val = (v["ast"] / v["ast_lsn"]) / v["plt"] * 100
    cat = "baja" if val <= 0.5 else ("alta" if val > 1.5 else "indeterminada")
    return {"valor": round(val, 2), "texto": f"APRI {val:.2f} · probabilidad {cat} de fibrosis significativa", "categoria": cat,
            "interpretacion": "≤0.5 probabilidad baja; >1.5 probabilidad alta; intermedio indeterminado."}


APRI = Calculator(
    code="apri", name="APRI", version="Wai-2003", group="Hepatología",
    source="Wai CT et al. Hepatology 2003;38:518-26.",
    verified_against=["Ahmed M. World J Hepatol 2015;7:1450 (tabla 3: fórmula y puntos de corte)"],
    population="Adultos con hepatitis C crónica (población de derivación). Uso en otras etiologías: menor validación.",
    formula="[(AST / límite superior normal de AST) / Plaquetas(10^9/L)] × 100",
    rounding="Dos decimales.",
    missing="AST, límite superior normal de AST del laboratorio y plaquetas obligatorios.",
    limitations="Requiere el límite superior normal del propio laboratorio. Afectado por hepatitis aguda o trombocitopenia de otra causa.",
    fields=[Field("ast", "AST", "U/L", lab="ast", min=1, max=20000),
            Field("ast_lsn", "Límite superior normal de AST (del laboratorio)", "U/L", min=10, max=200),
            Field("plt", "Plaquetas", "10^3/µL (=10^9/L)", lab="plt", min=1, max=2000)],
    compute=_apri,
    reference_cases=[
        ({"ast": "40", "ast_lsn": "40", "plt": "200"}, {"valor": 0.5, "categoria": "baja"}),         # (1/200)·100 = 0.5
        ({"ast": "120", "ast_lsn": "40", "plt": "150"}, {"valor": 2.0, "categoria": "alta"}),       # (3/150)·100 = 2.0
        ({"ast": "80", "ast_lsn": "40", "plt": "200"}, {"valor": 1.0, "categoria": "indeterminada"}),
    ])


# ----------------------------------------------------------------------------------------------- Maddrey
def _maddrey(v):
    val = 4.6 * (v["tp"] - v["tp_control"]) + v["bt"]
    return {"valor": round(val, 1), "texto": f"Función discriminante {val:.1f}" + (" (≥32)" if val >= 32 else " (<32)"),
            "interpretacion": "Un valor ≥32 identifica hepatitis alcohólica grave en la que los estudios evaluaron corticoides; "
                              "la decisión terapéutica es del médico."}


MADDREY = Calculator(
    code="maddrey", name="Función discriminante de Maddrey", version="Maddrey-1978", group="Hepatología",
    source="Maddrey WC et al. Gastroenterology 1978;75:193-9.",
    verified_against=["MSD/Merck Manual, Hepatitis Discriminant Function (fórmula, corte ≥32), consultado 30-oct-2026"],
    population="Adultos con hepatitis alcohólica.",
    formula="4.6 × (TP del paciente − TP control, en segundos) + bilirrubina total (mg/dL)",
    rounding="Un decimal.",
    missing="TP del paciente, TP control y bilirrubina obligatorios. No usar INR en lugar del TP.",
    limitations="Depende del reactivo de TP (variabilidad entre laboratorios). Solo en hepatitis alcohólica.",
    fields=[Field("tp", "Tiempo de protrombina del paciente", "s", lab="tp", min=5, max=200),
            Field("tp_control", "TP control del laboratorio", "s", lab="tp_control", min=5, max=60),
            Field("bt", "Bilirrubina total", "mg/dL", lab="bt", min=0.1, max=60)],
    compute=_maddrey,
    reference_cases=[
        ({"tp": "18", "tp_control": "12", "bt": "8"}, {"valor": 35.6}),     # 4.6·6 + 8 = 35.6
        ({"tp": "13", "tp_control": "12", "bt": "5"}, {"valor": 9.6}),
    ])


# ----------------------------------------------------------------------------------------------- Lille
def _lille(v):
    bili0 = v["bt0"] * 17.1      # mg/dL → µmol/L
    bili7 = v["bt7"] * 17.1
    alb = v["alb0"] * 10         # g/dL → g/L
    renal = 1 if v["creat0"] > 1.3 else 0
    r = 3.19 - 0.101 * v["edad"] + 0.147 * alb + 0.0165 * (bili0 - bili7) - 0.206 * renal - 0.0065 * bili0 - 0.0096 * v["tp0"]
    score = math.exp(-r) / (1 + math.exp(-r))
    return {"valor": round(score, 3), "texto": f"Lille {score:.3f} · " + ("≥0.45: sin respuesta" if score >= 0.45 else "<0.45: respuesta"),
            "detalle": {"R": round(r, 4), "Insuficiencia renal (Cr >1.3 mg/dL)": renal},
            "interpretacion": "<0.45 sugiere respuesta a corticoides al día 7; ≥0.45 sugiere ausencia de respuesta."}


LILLE = Calculator(
    code="lille", name="Modelo de Lille", version="Louvet-2007", group="Hepatología",
    source="Louvet A et al. Hepatology 2007;45:1348-54.",
    verified_against=["Wikipedia «Lille Model» (fórmula, definición de insuficiencia renal y corte 0.45), consultado 30-oct-2026"],
    population="Adultos con hepatitis alcohólica grave tratados con corticoides, evaluados al día 7.",
    formula="R = 3.19 − 0.101·edad + 0.147·albúmina día 0 (g/L) + 0.0165·(bilirrubina día 0 − día 7, µmol/L) − 0.206·IR "
            "− 0.0065·bilirrubina día 0 (µmol/L) − 0.0096·TP (s). Lille = e^(−R)/(1+e^(−R)).",
    rounding="Tres decimales.",
    missing="Todos los valores obligatorios; el TP debe estar en segundos (no INR).",
    limitations="Conversión usada: bilirrubina mg/dL × 17.1 = µmol/L; albúmina g/dL × 10 = g/L. "
                "PENDIENTE de verificar contra el artículo original: el término de bilirrubina usa la diferencia día 0 − día 7.",
    fields=[Field("edad", "Edad", "años", min=18, max=110),
            Field("alb0", "Albúmina día 0", "g/dL", lab="alb", min=0.5, max=7),
            Field("bt0", "Bilirrubina día 0", "mg/dL", min=0.1, max=60),
            Field("bt7", "Bilirrubina día 7", "mg/dL", min=0.1, max=60),
            Field("creat0", "Creatinina día 0", "mg/dL", lab="creat", min=0.1, max=25),
            Field("tp0", "Tiempo de protrombina día 0", "s", lab="tp", min=5, max=200)],
    compute=_lille,
    reference_cases=[
        # Calculado a mano: edad 50, alb 2.5 g/dL (25 g/L), bili0 20 mg/dL (342 µmol/L), bili7 15 (256.5), Cr 1.0, TP 20 s
        # R = 3.19 − 5.05 + 3.675 + 0.0165·85.5 − 0 − 0.0065·342 − 0.0096·20 = 3.19−5.05+3.675+1.41075−2.223−0.192 = 0.81075
        # Lille = e^−0.81075/(1+e^−0.81075) = 0.4445/1.4445 = 0.3077
        ({"edad": "50", "alb0": "2.5", "bt0": "20", "bt7": "15", "creat0": "1.0", "tp0": "20"}, {"valor": 0.308}),
        # Sin respuesta: edad 60, alb 2.0 (20 g/L), bili0 10 (171), bili7 12 (205.2), Cr 1.5 (IR=1), TP 25 s
        # R = 3.19 − 6.06 + 2.94 + 0.0165·(−34.2) − 0.206 − 0.0065·171 − 0.0096·25 = −2.0518 → Lille = 0.886
        ({"edad": "60", "alb0": "2.0", "bt0": "10", "bt7": "12", "creat0": "1.5", "tp0": "25"}, {"valor": 0.886}),
    ])


# ----------------------------------------------------------------------------------------------- Glasgow-Blatchford
def _gbs(v):
    urea = v["urea_valor"] * (0.357 if v["urea_unidad"] == "bun_mgdl" else 1.0)   # BUN mg/dL → urea mmol/L
    p = {}
    p["Urea"] = 6 if urea >= 25 else 4 if urea >= 10 else 3 if urea >= 8 else 2 if urea >= 6.5 else 0
    hb = v["hb"]
    if v["sexo"] == "masculino":
        p["Hemoglobina"] = 6 if hb < 10 else 3 if hb < 12 else 1 if hb < 13 else 0
    else:
        p["Hemoglobina"] = 6 if hb < 10 else 1 if hb < 12 else 0
    sbp = v["pas"]
    p["Presión sistólica"] = 3 if sbp < 90 else 2 if sbp < 100 else 1 if sbp < 110 else 0
    p["Pulso ≥100"] = 1 if v["fc"] >= 100 else 0
    p["Melena"] = 1 if v["melena"] else 0
    p["Síncope"] = 2 if v["sincope"] else 0
    p["Hepatopatía"] = 2 if v["hepatopatia"] else 0
    p["Insuficiencia cardiaca"] = 2 if v["icc"] else 0
    total = sum(p.values())
    return {"valor": total, "texto": f"Glasgow-Blatchford {total}", "detalle": p, "urea_mmol_l": round(urea, 1),
            "interpretacion": "0 identifica muy bajo riesgo de necesitar intervención; valores más altos, mayor riesgo. "
                              "Los umbrales de manejo ambulatorio dependen de la guía utilizada."}


GBS = Calculator(
    code="glasgow_blatchford", name="Glasgow-Blatchford", version="Blatchford-2000", group="Hemorragia digestiva",
    source="Blatchford O et al. Lancet 2000;356:1318-21.",
    verified_against=["Wikipedia «Glasgow-Blatchford score» (tabla de puntos, urea en mmol/L), consultado 30-oct-2026"],
    population="Adultos con hemorragia digestiva alta, evaluación previa a la endoscopia.",
    formula="Suma de puntos: urea, hemoglobina (según sexo), presión sistólica, pulso, melena, síncope, hepatopatía, insuficiencia cardiaca.",
    rounding="Puntos enteros.",
    missing="Urea/BUN, hemoglobina, presión sistólica, pulso y sexo obligatorios; las variables sí/no se toman como «no» si no se marcan.",
    limitations="Tabla original en urea mmol/L. Si se ingresa BUN en mg/dL se convierte con ×0.357. Límites: los rangos se aplican "
                "como «desde X hasta menos de Y» (p. ej., urea 6.5–<8 = 2).",
    fields=[Field("urea_unidad", "Tipo de valor", kind="select", options=[("bun_mgdl", "BUN (mg/dL)"), ("urea_mmol", "Urea (mmol/L)")]),
            Field("urea_valor", "Valor de BUN o urea", "", lab="bun", min=0.5, max=300),
            Field("sexo", "Sexo", kind="select", options=[("femenino", "Femenino"), ("masculino", "Masculino")]),
            Field("hb", "Hemoglobina", "g/dL", lab="hb", min=1, max=25),
            Field("pas", "Presión sistólica", "mmHg", min=30, max=300),
            Field("fc", "Pulso", "lpm", min=20, max=250),
            Field("melena", "Melena", kind="bool", required=False), Field("sincope", "Síncope", kind="bool", required=False),
            Field("hepatopatia", "Hepatopatía", kind="bool", required=False),
            Field("icc", "Insuficiencia cardiaca", kind="bool", required=False)],
    compute=_gbs,
    reference_cases=[
        ({"urea_unidad": "urea_mmol", "urea_valor": "5", "sexo": "masculino", "hb": "14", "pas": "120", "fc": "80"}, {"valor": 0}),
        # urea 9 (3) + Hb hombre 11 (3) + PAS 95 (2) + FC 110 (1) + melena (1) + síncope (2) = 12
        ({"urea_unidad": "urea_mmol", "urea_valor": "9", "sexo": "masculino", "hb": "11", "pas": "95", "fc": "110",
          "melena": "1", "sincope": "1"}, {"valor": 12}),
        # Mujer Hb 11 → 1; BUN 30 mg/dL → urea 10.71 → 4; total 5
        ({"urea_unidad": "bun_mgdl", "urea_valor": "30", "sexo": "femenino", "hb": "11", "pas": "120", "fc": "80"}, {"valor": 5}),
        # Máximo: urea 30 (6) + Hb 8 (6) + PAS 80 (3) + 1 + 1 + 2 + 2 + 2 = 23
        ({"urea_unidad": "urea_mmol", "urea_valor": "30", "sexo": "masculino", "hb": "8", "pas": "80", "fc": "120", "melena": "1",
          "sincope": "1", "hepatopatia": "1", "icc": "1"}, {"valor": 23}),
    ])


# ----------------------------------------------------------------------------------------------- Rockall
def _rockall(v):
    p = {"Edad": 0 if v["edad"] < 60 else (1 if v["edad"] < 80 else 2),
         "Choque": {"no": 0, "taquicardia": 1, "hipotension": 2}[v["choque"]],
         "Comorbilidad": {"ninguna": 0, "mayor": 2, "renal_hepatica_cancer": 3}[v["comorbilidad"]]}
    clinical = sum(p.values())
    if v["diagnostico"] is None or v["estigmas"] is None:
        return {"valor": clinical, "texto": f"Rockall pre-endoscópico (clínico) {clinical} / 7", "tipo": "clinico", "detalle": p,
                "interpretacion": "Puntuación clínica previa a la endoscopia (0–7). Complete diagnóstico y estigmas para el Rockall completo."}
    p["Diagnóstico"] = {"mallory_sin_lesion": 0, "otros": 1, "malignidad": 2}[v["diagnostico"]]
    p["Estigmas de sangrado reciente"] = {"ninguno": 0, "mayores": 2}[v["estigmas"]]
    total = sum(p.values())
    return {"valor": total, "texto": f"Rockall completo {total} / 11", "tipo": "completo", "detalle": p,
            "interpretacion": "Puntuación completa (0–11), predice resangrado y mortalidad. <3 buen pronóstico; >8 alto riesgo de mortalidad."}


ROCKALL = Calculator(
    code="rockall", name="Rockall (pre-endoscópico y completo)", version="Rockall-1996", group="Hemorragia digestiva",
    source="Rockall TA et al. Gut 1996;38:316-21.",
    verified_against=["Wikipedia «Rockall score» (tabla de puntos e interpretación), consultado 30-oct-2026"],
    population="Adultos con hemorragia digestiva alta.",
    formula="Clínico: edad + choque + comorbilidad (0–7). Completo: + diagnóstico endoscópico + estigmas (0–11).",
    rounding="Puntos enteros.",
    missing="Edad, choque y comorbilidad obligatorios. Si faltan diagnóstico o estigmas se informa solo el Rockall clínico.",
    limitations="Las dos versiones se muestran claramente diferenciadas. El Rockall clínico no sustituye al Glasgow-Blatchford "
                "para decidir manejo ambulatorio.",
    fields=[Field("edad", "Edad", "años", min=1, max=120),
            Field("choque", "Choque", kind="select", options=[("no", "Sin choque (pulso <100 y PAS ≥100)"),
                                                              ("taquicardia", "Taquicardia (pulso ≥100) con PAS ≥100"),
                                                              ("hipotension", "Hipotensión (PAS <100)")]),
            Field("comorbilidad", "Comorbilidad", kind="select",
                  options=[("ninguna", "Ninguna mayor"), ("mayor", "Insuficiencia cardiaca, cardiopatía isquémica u otra mayor"),
                           ("renal_hepatica_cancer", "Insuficiencia renal, insuficiencia hepática o cáncer diseminado")]),
            Field("diagnostico", "Diagnóstico endoscópico (para el completo)", kind="select", required=False,
                  options=[("mallory_sin_lesion", "Mallory-Weiss o sin lesión y sin estigmas"), ("otros", "Otros diagnósticos"),
                           ("malignidad", "Neoplasia del tubo digestivo alto")]),
            Field("estigmas", "Estigmas de sangrado reciente (para el completo)", kind="select", required=False,
                  options=[("ninguno", "Ninguno o solo mancha oscura"),
                           ("mayores", "Sangre en el tubo digestivo alto, coágulo adherido, vaso visible o sangrado activo")])],
    compute=_rockall,
    reference_cases=[
        ({"edad": "45", "choque": "no", "comorbilidad": "ninguna"}, {"valor": 0, "tipo": "clinico"}),
        ({"edad": "85", "choque": "hipotension", "comorbilidad": "renal_hepatica_cancer"}, {"valor": 7, "tipo": "clinico"}),
        ({"edad": "70", "choque": "taquicardia", "comorbilidad": "mayor", "diagnostico": "otros", "estigmas": "mayores"},
         {"valor": 7, "tipo": "completo"}),
        ({"edad": "85", "choque": "hipotension", "comorbilidad": "renal_hepatica_cancer", "diagnostico": "malignidad",
          "estigmas": "mayores"}, {"valor": 11, "tipo": "completo"}),
    ])


# ----------------------------------------------------------------------------------------------- BISAP
def _bisap(v):
    p = {"BUN >25 mg/dL": 1 if v["bun"] > 25 else 0, "Alteración del estado mental": 1 if v["mental"] else 0,
         "SIRS (≥2 criterios)": 1 if v["sirs"] else 0, "Edad >60": 1 if v["edad"] > 60 else 0,
         "Derrame pleural": 1 if v["derrame"] else 0}
    total = sum(p.values())
    return {"valor": total, "texto": f"BISAP {total} / 5", "detalle": p,
            "interpretacion": "Evaluado en las primeras 24 h. Mayor puntuación se asocia a mayor mortalidad hospitalaria; "
                              "≥3 se ha asociado a mayor riesgo."}


BISAP = Calculator(
    code="bisap", name="BISAP", version="Wu-2008", group="Páncreas",
    source="Wu BU et al. Gut 2008;57:1698-703.",
    verified_against=["Wu BU et al. Gut 2008;57:1698 (definiciones de cada criterio y ventana de 24 h), consultado 30-oct-2026"],
    population="Adultos con pancreatitis aguda, primeras 24 horas de ingreso (incluye valores de urgencias).",
    formula="1 punto por cada uno: BUN >25 mg/dL; alteración del estado mental; SIRS (≥2 de: FC >90, FR >20 o PaCO2 <32, "
            "T >38 o <36 °C, leucocitos >12 000 o <4 000 o >10 % bandas); edad >60; derrame pleural en imagen.",
    rounding="Puntos enteros.",
    missing="BUN y edad obligatorios; los demás criterios se toman como ausentes si no se marcan (confirme que fueron evaluados).",
    limitations="Usar el valor más extremo de las primeras 24 h.",
    fields=[Field("bun", "BUN (peor valor en 24 h)", "mg/dL", lab="bun", min=1, max=300),
            Field("edad", "Edad", "años", min=1, max=120),
            Field("mental", "Alteración del estado mental (desorientación, letargo, somnolencia, estupor o coma)", kind="bool", required=False),
            Field("sirs", "SIRS: ≥2 criterios", kind="bool", required=False),
            Field("derrame", "Derrame pleural en radiografía o TC", kind="bool", required=False)],
    compute=_bisap,
    reference_cases=[
        ({"bun": "15", "edad": "40"}, {"valor": 0}),
        ({"bun": "25", "edad": "60"}, {"valor": 0}),     # límites: >25 y >60 son estrictos
        ({"bun": "26", "edad": "61", "mental": "1", "sirs": "1", "derrame": "1"}, {"valor": 5}),
    ])


# ----------------------------------------------------------------------------------------------- IMC
def _bmi(v):
    val = v["peso"] / ((v["talla"] / 100) ** 2)
    cat = ("bajo peso" if val < 18.5 else "normal" if val < 25 else "sobrepeso" if val < 30 else "obesidad")
    return {"valor": round(val, 1), "texto": f"IMC {val:.1f} kg/m² · {cat} (clasificación OMS adultos)", "categoria": cat,
            "interpretacion": "Clasificación de la OMS para adultos: <18.5 bajo peso; 18.5–24.9 normal; 25–29.9 sobrepeso; ≥30 obesidad."}


BMI = Calculator(
    code="imc", name="Índice de masa corporal", version="OMS", group="Nutrición",
    source="Organización Mundial de la Salud: clasificación del IMC en adultos.",
    verified_against=["Definición estándar OMS (peso/talla²)"],
    population="Adultos ≥18 años. No usar en niños ni embarazo; menos útil con ascitis o edemas.",
    formula="Peso (kg) / talla (m)²", rounding="Un decimal.", missing="Peso y talla obligatorios.",
    limitations="La ascitis y los edemas sobreestiman el peso real.",
    fields=[Field("peso", "Peso", "kg", min=1, max=400), Field("talla", "Talla", "cm", min=30, max=250)],
    compute=_bmi,
    reference_cases=[({"peso": "70", "talla": "170"}, {"valor": 24.2, "categoria": "normal"}),
                     ({"peso": "90", "talla": "170"}, {"valor": 31.1, "categoria": "obesidad"})])


ALL = [CHILD, MELD_NA, MELD3, FIB4, APRI, MADDREY, LILLE, GBS, ROCKALL, BISAP, BMI]
BY_CODE = {c.code: c for c in ALL}


def self_check(calc: Calculator) -> list[tuple[dict, dict, dict, bool]]:
    """Ejecuta los casos de referencia; se muestra al médico en la pantalla de revisión."""
    out = []
    for inp, expected in calc.reference_cases:
        res = run(calc, inp)
        ok = all((abs(res.get(k) - v) < 1e-9 if isinstance(v, float) else res.get(k) == v) for k, v in expected.items())
        out.append((inp, expected, res, ok))
    return out
