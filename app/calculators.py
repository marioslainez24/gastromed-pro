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


# =============================================================================================== v0.17: otras especialidades
SEXO = Field("sexo", "Sexo", kind="select", options=[("femenino", "Femenino"), ("masculino", "Masculino")])
EDAD = Field("edad", "Edad", "años", min=18, max=120)


def _kdigo(e):
    return "G1" if e >= 90 else "G2" if e >= 60 else "G3a" if e >= 45 else "G3b" if e >= 30 else "G4" if e >= 15 else "G5"


def _ckd_epi(v):
    fem = v["sexo"] == "femenino"
    k, a = (0.7, -0.241) if fem else (0.9, -0.302)
    r = v["creat"] / k
    e = 142 * min(r, 1) ** a * max(r, 1) ** -1.200 * 0.9938 ** v["edad"] * (1.012 if fem else 1)
    cat = _kdigo(e)
    return {"valor": round(e, 1), "categoria": cat, "texto": f"TFGe {e:.1f} mL/min/1.73 m² · categoría {cat} (KDIGO)",
            "interpretacion": "Categorías KDIGO de filtrado: G1 ≥90, G2 60–89, G3a 45–59, G3b 30–44, G4 15–29, G5 <15 mL/min/1.73 m². "
                              "Una sola medición no establece enfermedad renal crónica (requiere >3 meses)."}


CKD_EPI = Calculator(
    code="ckd_epi_2021", name="Filtrado glomerular CKD-EPI 2021", version="CKD-EPI-2021", group="Riñón y electrolitos",
    source="Inker LA et al. New creatinine- and cystatin C-based equations to estimate GFR without race. N Engl J Med 2021;385:1737-49.",
    verified_against=["Ecuación publicada (NEJM 2021) y ejemplo resuelto de MetricGate: mujer 55 años, creatinina 1.2 mg/dL → 53.5 "
                      "(consultado 1-nov-2026)"],
    population="Adultos ≥18 años con creatinina estable. No válido en lesión renal aguda, embarazo, amputados o masa muscular extrema.",
    formula="142 × min(Cr/κ, 1)^α × max(Cr/κ, 1)^−1.200 × 0.9938^edad × 1.012 [mujer]; κ = 0.7 (mujer) o 0.9 (hombre); "
            "α = −0.241 (mujer) o −0.302 (hombre). Sin coeficiente de raza.",
    rounding="Un decimal.", missing="Creatinina, edad y sexo obligatorios.",
    limitations="En cirrosis la creatinina sobreestima el filtrado (poca masa muscular). Para dosificar fármacos algunas fichas usan Cockcroft-Gault.",
    fields=[Field("creat", "Creatinina sérica", "mg/dL", lab="creat", min=0.1, max=25), EDAD, SEXO],
    compute=_ckd_epi,
    reference_cases=[({"creat": "1.2", "edad": "55", "sexo": "femenino"}, {"valor": 53.5, "categoria": "G3a"}),
                     ({"creat": "1.0", "edad": "50", "sexo": "masculino"}, {"valor": 91.7, "categoria": "G1"}),
                     ({"creat": "0.6", "edad": "40", "sexo": "femenino"}, {"valor": 116.3, "categoria": "G1"})])


def _cockcroft(v):
    c = (140 - v["edad"]) * v["peso"] / (72 * v["creat"]) * (0.85 if v["sexo"] == "femenino" else 1)
    return {"valor": round(c, 1), "texto": f"Depuración de creatinina estimada {c:.1f} mL/min",
            "interpretacion": "Estimación de la depuración de creatinina (mL/min, no ajustada a superficie corporal), usada en muchas fichas "
                              "técnicas para ajustar dosis. Verifique la recomendación de la ficha de cada fármaco."}


COCKCROFT = Calculator(
    code="cockcroft_gault", name="Cockcroft-Gault (depuración de creatinina)", version="CG-1976", group="Riñón y electrolitos",
    source="Cockcroft DW, Gault MH. Prediction of creatinine clearance from serum creatinine. Nephron 1976;16:31-41.",
    verified_against=["Fórmula publicada (Nephron 1976); casos calculados a mano: hombre 60 años, 72 kg, Cr 1.0 → 80.0"],
    population="Adultos con creatinina estable.",
    formula="[(140 − edad) × peso (kg)] / (72 × creatinina mg/dL) × 0.85 si es mujer.",
    rounding="Un decimal.", missing="Edad, peso, creatinina y sexo obligatorios.",
    limitations="Se usa el peso real; en obesidad, ascitis o edemas sobreestima la depuración. No válido en lesión renal aguda.",
    fields=[EDAD, Field("peso", "Peso", "kg", min=20, max=300), Field("creat", "Creatinina sérica", "mg/dL", lab="creat", min=0.1, max=25), SEXO],
    compute=_cockcroft,
    reference_cases=[({"edad": "60", "peso": "72", "creat": "1.0", "sexo": "masculino"}, {"valor": 80.0}),
                     ({"edad": "60", "peso": "72", "creat": "1.0", "sexo": "femenino"}, {"valor": 68.0})])


def _ca_corr(v):
    c = v["ca"] + 0.8 * (4.0 - v["alb"])
    return {"valor": round(c, 1), "texto": f"Calcio corregido {c:.1f} mg/dL",
            "interpretacion": "Estimación del calcio total ajustado a una albúmina de 4 g/dL. Compare con el rango de referencia de su "
                              "laboratorio; si hay duda (acidosis, insuficiencia renal, hipoalbuminemia grave) mida calcio iónico."}


CA_CORR = Calculator(
    code="calcio_corregido", name="Calcio corregido por albúmina", version="Payne-1973", group="Riñón y electrolitos",
    source="Payne RB et al. Interpretation of serum calcium in patients with abnormal serum proteins. BMJ 1973;4:643-6.",
    verified_against=["Fórmula de uso habitual: calcio + 0.8 × (4 − albúmina); casos calculados a mano"],
    population="Adultos con hipoalbuminemia o hiperalbuminemia.",
    formula="Calcio total (mg/dL) + 0.8 × (4.0 − albúmina g/dL).",
    rounding="Un decimal.", missing="Calcio y albúmina obligatorios.",
    limitations="Aproximación con exactitud limitada; el calcio iónico es la medida de referencia.",
    fields=[Field("ca", "Calcio total", "mg/dL", min=2, max=20), Field("alb", "Albúmina", "g/dL", lab="alb", min=0.5, max=7)],
    compute=_ca_corr,
    reference_cases=[({"ca": "8.0", "alb": "2.0"}, {"valor": 9.6}), ({"ca": "10.0", "alb": "4.5"}, {"valor": 9.6})])


def _anion_gap(v):
    ag = v["na"] - (v["cl"] + v["hco3"])
    return {"valor": round(ag, 1), "texto": f"Brecha aniónica {ag:g} mEq/L",
            "interpretacion": "El rango normal depende del método de cada laboratorio (con electrodos selectivos suele ser más bajo que "
                              "el clásico 12 ± 4). La hipoalbuminemia reduce la brecha y puede ocultar una acidosis con brecha elevada."}


ANION_GAP = Calculator(
    code="brecha_anionica", name="Brecha aniónica (anion gap)", version="AG-clasica", group="Riñón y electrolitos",
    source="Kraut JA, Madias NE. Serum anion gap: its uses and limitations in clinical medicine. Clin J Am Soc Nephrol 2007;2:162-74.",
    verified_against=["Fórmula publicada Na − (Cl + HCO3); caso calculado a mano 140 − (104 + 24) = 12"],
    population="Adultos con trastorno ácido-base.", formula="Na − (Cl + HCO3), en mmol/L (equivale a mEq/L), sin potasio.",
    rounding="Un decimal.", missing="Sodio, cloro y bicarbonato obligatorios.",
    limitations="No corrige por albúmina. Use los valores de una misma muestra.",
    fields=[Field("na", "Sodio", "mmol/L", lab="na", min=90, max=200), Field("cl", "Cloro", "mmol/L", min=50, max=160),
            Field("hco3", "Bicarbonato", "mmol/L", min=1, max=60)],
    compute=_anion_gap,
    reference_cases=[({"na": "140", "cl": "104", "hco3": "24"}, {"valor": 12.0}), ({"na": "135", "cl": "100", "hco3": "10"}, {"valor": 25.0})])


def _cha2ds2(v):
    p = {"Insuficiencia cardiaca": 1 if v["icc"] else 0, "Hipertensión": 1 if v["hta"] else 0,
         "Edad": 2 if v["edad"] >= 75 else 1 if v["edad"] >= 65 else 0, "Diabetes": 1 if v["dm"] else 0,
         "Ictus/AIT/tromboembolia": 2 if v["ictus"] else 0, "Enfermedad vascular": 1 if v["vascular"] else 0,
         "Sexo femenino": 1 if v["sexo"] == "femenino" else 0}
    t = sum(p.values())
    return {"valor": t, "texto": f"CHA₂DS₂-VASc {t} puntos", "detalle": p,
            "interpretacion": "A mayor puntaje, mayor riesgo anual de ictus en fibrilación auricular no valvular. La decisión de "
                              "anticoagular se toma según la guía vigente y el riesgo de sangrado (HAS-BLED), no solo con este puntaje."}


CHA2DS2 = Calculator(
    code="cha2ds2_vasc", name="CHA₂DS₂-VASc", version="Lip-2010", group="Cardiología",
    source="Lip GYH et al. Refining clinical risk stratification for predicting stroke and thromboembolism in atrial fibrillation. "
           "Chest 2010;137:263-72.",
    verified_against=["Tabla de puntos publicada (Chest 2010) y MDCalc, consultado 1-nov-2026"],
    population="Adultos con fibrilación auricular no valvular.",
    formula="Insuficiencia cardiaca 1, hipertensión 1, edad ≥75 2, diabetes 1, ictus/AIT/tromboembolia 2, enfermedad vascular 1, "
            "edad 65–74 1, sexo femenino 1 (máximo 9).",
    rounding="Puntos enteros.", missing="Edad y sexo obligatorios; los demás se toman como «no» si no se marcan.",
    limitations="No aplica a estenosis mitral moderada-grave ni prótesis mecánicas. La guía europea 2024 usa CHA₂DS₂-VA (sin el punto por sexo).",
    fields=[EDAD, SEXO, Field("icc", "Insuficiencia cardiaca o disfunción del ventrículo izquierdo", kind="bool", required=False),
            Field("hta", "Hipertensión", kind="bool", required=False), Field("dm", "Diabetes", kind="bool", required=False),
            Field("ictus", "Ictus, AIT o tromboembolia previa", kind="bool", required=False),
            Field("vascular", "Enfermedad vascular (infarto previo, enfermedad arterial periférica, placa aórtica)", kind="bool", required=False)],
    compute=_cha2ds2,
    reference_cases=[({"edad": "50", "sexo": "masculino"}, {"valor": 0}),
                     ({"edad": "76", "sexo": "femenino", "hta": "1"}, {"valor": 4}),
                     ({"edad": "80", "sexo": "femenino", "icc": "1", "hta": "1", "dm": "1", "ictus": "1", "vascular": "1"}, {"valor": 9})])


def _hasbled(v):
    keys = [("hta", "Hipertensión (sistólica >160)"), ("renal", "Función renal alterada"), ("hepatica", "Función hepática alterada"),
            ("ictus", "Ictus previo"), ("sangrado", "Sangrado previo o predisposición"), ("inr", "INR lábil"),
            ("mayor65", "Edad >65 años"), ("farmacos", "Antiagregantes o AINE"), ("alcohol", "Alcohol ≥8 bebidas/semana")]
    p = {lab: 1 if v[k] else 0 for k, lab in keys}
    t = sum(p.values())
    cat = "alto" if t >= 3 else "no alto"
    return {"valor": t, "categoria": cat, "texto": f"HAS-BLED {t} puntos" + (" · riesgo alto de sangrado" if t >= 3 else ""), "detalle": p,
            "interpretacion": "≥3 indica riesgo alto de sangrado: obliga a vigilar y corregir los factores modificables, "
                              "no contraindica por sí solo la anticoagulación."}


HASBLED = Calculator(
    code="has_bled", name="HAS-BLED (riesgo de sangrado)", version="Pisters-2010", group="Cardiología",
    source="Pisters R et al. A novel user-friendly score (HAS-BLED) to assess 1-year risk of major bleeding in patients with atrial "
           "fibrillation. Chest 2010;138:1093-100.",
    verified_against=["Tabla de puntos publicada (Chest 2010), consultado 1-nov-2026"],
    population="Adultos con fibrilación auricular en evaluación o tratamiento anticoagulante.",
    formula="1 punto cada uno: hipertensión (sistólica >160), función renal alterada (diálisis, trasplante o Cr >2.26 mg/dL), función "
            "hepática alterada (cirrosis o bilirrubina >2× y AST/ALT/FA >3× normal), ictus, sangrado, INR lábil (<60% en rango), "
            "edad >65, fármacos (antiagregantes/AINE), alcohol (≥8 bebidas/semana). Máximo 9.",
    rounding="Puntos enteros.", missing="Los elementos no marcados se toman como «no».",
    limitations="«INR lábil» solo aplica a pacientes con warfarina/acenocumarol.",
    fields=[Field("hta", "Hipertensión no controlada (sistólica >160 mmHg)", kind="bool", required=False),
            Field("renal", "Función renal alterada (diálisis, trasplante o creatinina >2.26 mg/dL)", kind="bool", required=False),
            Field("hepatica", "Función hepática alterada (cirrosis, o bilirrubina >2× y transaminasas/FA >3× lo normal)", kind="bool", required=False),
            Field("ictus", "Ictus previo", kind="bool", required=False),
            Field("sangrado", "Sangrado mayor previo o predisposición (anemia, trombocitopenia)", kind="bool", required=False),
            Field("inr", "INR lábil (tiempo en rango <60%)", kind="bool", required=False),
            Field("mayor65", "Edad >65 años", kind="bool", required=False),
            Field("farmacos", "Antiagregantes o AINE", kind="bool", required=False),
            Field("alcohol", "Alcohol ≥8 bebidas por semana", kind="bool", required=False)],
    compute=_hasbled,
    reference_cases=[({}, {"valor": 0, "categoria": "no alto"}),
                     ({"hta": "1", "mayor65": "1", "farmacos": "1"}, {"valor": 3, "categoria": "alto"}),
                     ({k: "1" for k in ("hta", "renal", "hepatica", "ictus", "sangrado", "inr", "mayor65", "farmacos", "alcohol")},
                      {"valor": 9, "categoria": "alto"})])


CURB_MORT = {0: "0.7", 1: "3.2", 2: "13", 3: "17", 4: "41.5", 5: "57"}


def _curb65(v):
    p = {"Confusión": 1 if v["confusion"] else 0, "BUN >19 mg/dL": 1 if v["bun"] > 19 else 0,
         "Frecuencia respiratoria ≥30": 1 if v["fr"] >= 30 else 0,
         "Sistólica <90 o diastólica ≤60": 1 if (v["pas"] < 90 or v["pad"] <= 60) else 0, "Edad ≥65": 1 if v["edad"] >= 65 else 0}
    t = sum(p.values())
    grupo = "bajo" if t <= 1 else "intermedio" if t == 2 else "alto"
    return {"valor": t, "categoria": grupo, "texto": f"CURB-65 {t} puntos · riesgo {grupo}", "detalle": p,
            "interpretacion": f"Mortalidad a 30 días en la cohorte de derivación: {CURB_MORT[t]} %. Orientativo: 0–1 suele manejarse "
                              "en casa, 2 valorar ingreso corto o vigilancia estrecha, 3–5 hospitalización (considerar UCI con 4–5)."}


CURB65 = Calculator(
    code="curb65", name="CURB-65 (neumonía)", version="Lim-2003", group="Infección y urgencias",
    source="Lim WS et al. Defining community acquired pneumonia severity on presentation to hospital. Thorax 2003;58:377-82.",
    verified_against=["Criterios y mortalidad por puntaje publicados (Thorax 2003), consultado 1-nov-2026"],
    population="Adultos con neumonía adquirida en la comunidad.",
    formula="1 punto cada uno: confusión, urea >7 mmol/L (BUN >19 mg/dL), frecuencia respiratoria ≥30, sistólica <90 o diastólica ≤60, edad ≥65.",
    rounding="Puntos enteros.", missing="BUN, frecuencia respiratoria, presión y edad obligatorios; la confusión se toma como «no» si no se marca.",
    limitations="No considera hipoxemia, comorbilidades ni contexto social; complemente con el juicio clínico.",
    fields=[Field("confusion", "Confusión de nueva aparición", kind="bool", required=False),
            Field("bun", "BUN (nitrógeno ureico)", "mg/dL", lab="bun", min=1, max=300),
            Field("fr", "Frecuencia respiratoria", "rpm", min=4, max=80),
            Field("pas", "Presión sistólica", "mmHg", min=30, max=300), Field("pad", "Presión diastólica", "mmHg", min=10, max=200), EDAD],
    compute=_curb65,
    reference_cases=[({"bun": "10", "fr": "18", "pas": "120", "pad": "80", "edad": "40"}, {"valor": 0, "categoria": "bajo"}),
                     ({"bun": "25", "fr": "32", "pas": "120", "pad": "70", "edad": "70"}, {"valor": 3, "categoria": "alto"}),
                     ({"bun": "19", "fr": "29", "pas": "90", "pad": "61", "edad": "64"}, {"valor": 0, "categoria": "bajo"}),
                     ({"confusion": "1", "bun": "30", "fr": "30", "pas": "85", "pad": "50", "edad": "80"}, {"valor": 5, "categoria": "alto"})])


def _qsofa(v):
    p = {"Sistólica ≤100": 1 if v["pas"] <= 100 else 0, "Frecuencia respiratoria ≥22": 1 if v["fr"] >= 22 else 0,
         "Alteración del estado mental": 1 if v["mental"] else 0}
    t = sum(p.values())
    cat = "positivo" if t >= 2 else "negativo"
    return {"valor": t, "categoria": cat, "texto": f"qSOFA {t} · {cat}", "detalle": p,
            "interpretacion": "≥2 en sospecha de infección identifica mayor riesgo de mala evolución. No es un criterio diagnóstico de "
                              "sepsis ni sirve para descartarla."}


QSOFA = Calculator(
    code="qsofa", name="qSOFA", version="Sepsis-3", group="Infección y urgencias",
    source="Seymour CW et al. Assessment of clinical criteria for sepsis (Sepsis-3). JAMA 2016;315:762-74.",
    verified_against=["Criterios publicados (JAMA 2016), consultado 1-nov-2026"],
    population="Adultos con sospecha de infección fuera de la UCI.",
    formula="1 punto cada uno: sistólica ≤100 mmHg, frecuencia respiratoria ≥22, alteración del estado mental (Glasgow <15).",
    rounding="Puntos enteros.", missing="Presión y frecuencia obligatorias; el estado mental se toma como «normal» si no se marca.",
    limitations="Baja sensibilidad: un qSOFA negativo no descarta sepsis.",
    fields=[Field("pas", "Presión sistólica", "mmHg", min=30, max=300), Field("fr", "Frecuencia respiratoria", "rpm", min=4, max=80),
            Field("mental", "Alteración del estado mental (Glasgow <15)", kind="bool", required=False)],
    compute=_qsofa,
    reference_cases=[({"pas": "120", "fr": "18"}, {"valor": 0, "categoria": "negativo"}),
                     ({"pas": "100", "fr": "22"}, {"valor": 2, "categoria": "positivo"}),
                     ({"pas": "101", "fr": "21", "mental": "1"}, {"valor": 1, "categoria": "negativo"})])


def _gcs(v):
    e, vb, m = int(v["ocular"]), int(v["verbal"]), int(v["motora"])
    t = e + vb + m
    cat = "grave" if t <= 8 else "moderado" if t <= 12 else "leve"
    return {"valor": t, "categoria": cat, "texto": f"Glasgow {t}/15 (O{e} V{vb} M{m}) · {cat}",
            "interpretacion": "Gravedad del deterioro de conciencia: 13–15 leve, 9–12 moderado, ≤8 grave. Registre los tres componentes."}


GCS = Calculator(
    code="glasgow_coma", name="Escala de coma de Glasgow", version="Teasdale-1974", group="Infección y urgencias",
    source="Teasdale G, Jennett B. Assessment of coma and impaired consciousness. Lancet 1974;2:81-4.",
    verified_against=["Escala publicada (Lancet 1974) con las descripciones de la versión actual (glasgowcomascale.org)"],
    population="Adultos con alteración de la conciencia.",
    formula="Apertura ocular (1–4) + respuesta verbal (1–5) + respuesta motora (1–6). Rango 3–15.",
    rounding="Puntos enteros.", missing="Los tres componentes son obligatorios.",
    limitations="La intubación, la sedación o la afasia impiden valorar la respuesta verbal; en ese caso anótelo en vez de puntuar.",
    fields=[Field("ocular", "Apertura ocular", kind="select", options=[("4", "4 · Espontánea"), ("3", "3 · Al sonido/a la voz"),
                                                                      ("2", "2 · A la presión/al dolor"), ("1", "1 · Ninguna")]),
            Field("verbal", "Respuesta verbal", kind="select", options=[("5", "5 · Orientada"), ("4", "4 · Confusa"), ("3", "3 · Palabras"),
                                                                       ("2", "2 · Sonidos"), ("1", "1 · Ninguna")]),
            Field("motora", "Respuesta motora", kind="select", options=[("6", "6 · Obedece órdenes"), ("5", "5 · Localiza el dolor"),
                                                                       ("4", "4 · Flexión normal (retirada)"), ("3", "3 · Flexión anormal"),
                                                                       ("2", "2 · Extensión"), ("1", "1 · Ninguna")])],
    compute=_gcs,
    reference_cases=[({"ocular": "4", "verbal": "5", "motora": "6"}, {"valor": 15, "categoria": "leve"}),
                     ({"ocular": "3", "verbal": "4", "motora": "5"}, {"valor": 12, "categoria": "moderado"}),
                     ({"ocular": "2", "verbal": "2", "motora": "4"}, {"valor": 8, "categoria": "grave"}),
                     ({"ocular": "1", "verbal": "1", "motora": "1"}, {"valor": 3, "categoria": "grave"})])


def _qtc(v):
    rr = 60 / v["fc"]
    q = v["qt"] / math.sqrt(rr)
    largo = q > (460 if v["sexo"] == "femenino" else 450)
    return {"valor": round(q), "categoria": "prolongado" if largo else "no prolongado",
            "texto": f"QTc (Bazett) {round(q)} ms" + (" · prolongado" if largo else ""),
            "interpretacion": "Se considera prolongado >450 ms en hombres y >460 ms en mujeres; >500 ms se asocia a riesgo alto de "
                              "arritmias. Revise fármacos que prolongan el QT (p. ej., algunos procinéticos y antieméticos)."}


QTC = Calculator(
    code="qtc_bazett", name="QT corregido (Bazett)", version="Bazett-1920", group="Cardiología",
    source="Bazett HC. An analysis of the time-relations of electrocardiograms. Heart 1920;7:353-70. Umbrales: Rautaharju PM et al., "
           "AHA/ACCF/HRS. J Am Coll Cardiol 2009;53:982-91.",
    verified_against=["Fórmula publicada QT/√RR; casos calculados a mano (QT 400 ms a 60 lpm → 400)"],
    population="Adultos con ECG en ritmo regular.",
    formula="QTc = QT (ms) / √RR (s), con RR = 60 / frecuencia cardiaca.",
    rounding="Milisegundos enteros.", missing="QT, frecuencia y sexo obligatorios.",
    limitations="Bazett sobrecorrige con frecuencias altas (>90–100 lpm) y subcorrige con bajas. No válido con bloqueo de rama o ritmo irregular.",
    fields=[Field("qt", "Intervalo QT medido", "ms", min=200, max=800), Field("fc", "Frecuencia cardiaca", "lpm", min=30, max=200), SEXO],
    compute=_qtc,
    reference_cases=[({"qt": "400", "fc": "60", "sexo": "masculino"}, {"valor": 400, "categoria": "no prolongado"}),
                     ({"qt": "360", "fc": "100", "sexo": "masculino"}, {"valor": 465, "categoria": "prolongado"}),
                     ({"qt": "360", "fc": "100", "sexo": "femenino"}, {"valor": 465, "categoria": "prolongado"})])


def _bsa(v):
    s = math.sqrt(v["talla"] * v["peso"] / 3600)
    return {"valor": round(s, 2), "texto": f"Superficie corporal {s:.2f} m²",
            "interpretacion": "Superficie corporal estimada (Mosteller), usada para dosis por m² y para índices ajustados."}


BSA = Calculator(
    code="superficie_corporal", name="Superficie corporal (Mosteller)", version="Mosteller-1987", group="General",
    source="Mosteller RD. Simplified calculation of body-surface area. N Engl J Med 1987;317:1098.",
    verified_against=["Fórmula publicada √(talla cm × peso kg / 3600); caso calculado a mano 170 cm y 70 kg → 1.82"],
    population="Adultos y niños.", formula="√(talla (cm) × peso (kg) / 3600).",
    rounding="Dos decimales.", missing="Peso y talla obligatorios.",
    limitations="Con ascitis o edemas el peso real sobreestima la superficie.",
    fields=[Field("peso", "Peso", "kg", min=1, max=400), Field("talla", "Talla", "cm", min=30, max=250)],
    compute=_bsa,
    reference_cases=[({"peso": "70", "talla": "170"}, {"valor": 1.82}), ({"peso": "100", "talla": "180"}, {"valor": 2.24})])


ALL = [CHILD, MELD_NA, MELD3, FIB4, APRI, MADDREY, LILLE, GBS, ROCKALL, BISAP, BMI,
       CKD_EPI, COCKCROFT, CA_CORR, ANION_GAP, CHA2DS2, HASBLED, QTC, CURB65, QSOFA, GCS, BSA]

BY_CODE = {c.code: c for c in ALL}


def self_check(calc: Calculator) -> list[tuple[dict, dict, dict, bool]]:
    """Ejecuta los casos de referencia; se muestra al médico en la pantalla de revisión."""
    out = []
    for inp, expected in calc.reference_cases:
        res = run(calc, inp)
        ok = all((abs(res.get(k) - v) < 1e-9 if isinstance(v, float) else res.get(k) == v) for k, v in expected.items())
        out.append((inp, expected, res, ok))
    return out
