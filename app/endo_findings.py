"""Hallazgos de endoscopia con clics (v0.13.0).

El médico elige un hallazgo en un segmento, completa sus datos (grado, tamaño, localización…) y el programa redacta la frase
para ese segmento y SUGIERE el diagnóstico correspondiente del catálogo (endo_diagnoses) para la conclusión; el médico decide
si lo agrega. La frase contiene solo lo marcado. Cada clic en «Agregar» suma una frase (para varios pólipos, agregar uno por vez).
Clasificaciones: las verificadas en endoscopy_defs (Los Ángeles, Forrest, París, Praga, Sarin, Zargar, NICE).

v0.19.0 · Pedido del Dr. Lainez: incorporar las clasificaciones de su presentación «Taller: Consenso de Clasificaciones en Endoscopia
Digestiva» (curso poscongreso GASTRO 2019, Cuba). Cada grado lleva su descripción (se muestra debajo de las opciones) y la fuente
está en SOURCES. Verificadas contra la publicación original o una revisión que la reproduce (1-nov-2026):
- Kodsi BE et al. Gastroenterology 1976;71:715-9 (reproducida en Jiménez Sánchez J et al. Gastroenterol Hepatol 2024;47:194-8).
- Hill LD et al. Gastrointest Endosc 1996;44:541-7.  Tipos de hernia hiatal: Kahrilas PJ et al. Best Pract Res Clin Gastroenterol 2008;22:601-16.
- Sistema Sídney, división endoscópica: Tytgat GN. J Gastroenterol Hepatol 1991;6:223-34.
- Borrmann R, 1926 (tipos avanzados en la clasificación de París, Gastrointest Endosc 2003;58:S3-43).
- Goitein D et al. Surg Endosc 2005;19:628-32 (reproducida en Espinel J, Pinedo E. World J Gastrointest Endosc 2012;4:290).
- Mayo endoscópico: Schroeder KW et al. N Engl J Med 1987;317:1625-9.
- Rutgeerts P et al. Gastroenterology 1990;99:956-63 (i2a/i2b: modificación de uso habitual, según el consenso).
- DICA: Tursi A et al. J Gastrointestin Liver Dis 2015;24:85-93 y 2019;28:23-7 (puntos y cortes 1–3, 4–7, >7).
Tomadas del consenso (sin publicación original disponible para cotejar): esofagitis no erosiva grado M (Los Ángeles modificada,
Hoshihara), herpes por estadios, estenosis de Bernal, acalasia por grados, cáncer avanzado de esófago, várices F1–F3, Lanza,
Paniagua (reflujo duodenogástrico), puntaje de Baveno de la gastropatía hipertensiva y colitis actínica. Se indica en SOURCES.
"""
from . import endo_diagnoses as DX

CATALOG = {t: (c, a) for _, _, t, c, a in DX.DIAGNOSES}


def P(name, label, kind="select", options=None, required=True, unit="", help=None):
    return {"name": name, "label": label, "kind": kind, "options": options or [], "required": required, "unit": unit, "help": help or []}


def G(name, label, grades, required=True):
    """Parámetro de grado: grades = [(valor, nombre corto, descripción)]. La descripción se muestra como guía."""
    return P(name, label, options=[(v, s) for v, s, _ in grades], required=required, help=[f"{s}: {d}" for _, s, d in grades])


def DXD(t, c, a=False):
    """Diagnóstico armado al momento (con el grado elegido) y su código CIE-10."""
    return {"t": t, "c": c, "a": a}


CONSENSO = "Consenso de Clasificaciones en Endoscopia Digestiva (GASTRO 2019, Cuba), presentación del Dr. Lainez"
KODSI = [("I", "I", "placas de 2 mm o menos, hiperemia leve, sin edema ni úlceras"),
         ("II", "II", "placas de más de 2 mm, hiperemia intensa, puede haber edema, sin úlceras"),
         ("III", "III", "placas confluentes, lineales o nodulares sobreelevadas, hiperemia intensa y/o úlceras"),
         ("IV", "IV", "lo del grado III más friabilidad de la mucosa y estrechamiento de la luz")]
HERPES = [("1", "Estadio 1", "vesículas de menos de 5 mm de diámetro"),
          ("2", "Estadio 2", "las vesículas se rompen: úlceras de 0.5 a 2 cm, bordes sobreelevados bien delimitados, fibrina y halo eritematoso"),
          ("3", "Estadio 3", "las úlceras crecen y se fusionan en úlceras grandes orientadas a lo largo del eje del esófago")]
BERNAL = [("I", "Tipo I", "central, única, corta y elástica, sin deformidad, bordes regulares y delgados"),
          ("II", "Tipo II", "central, única, corta, con deformidad por seudodivertículos o angulación; puede ser excéntrica, la fibrosis le da dureza"),
          ("III", "Tipo III", "excéntrica, múltiple, larga y rígida, alternando estrechez y dilatación, con gran deformidad"),
          ("IV", "Tipo IV", "firme, excéntrica, de bordes irregulares que sangran con facilidad al contacto; desvía el eje del esófago por efecto de masa")]
ACALASIA = [("I", "Grado I (temprano)", "ligera dilatación del cuerpo esofágico, con escasos restos de alimentos o sin ellos"),
            ("II", "Grado II (tardío)", "dilatación moderada, restos de alimentos y esofagitis por estasis o micótica grado I–II"),
            ("III", "Grado III (avanzado)", "dilatación marcada, esófago tortuoso y sigmoideo, abundantes restos y esofagitis por estasis o micótica III–IV")]
CA_ESO = [("vegetante", "Vegetante o polipoide", "masa intraluminal de superficie irregular con excrecencias polipoideas, friable"),
          ("ulcerado", "Ulcerado localizado", "poco prominente hacia la luz, excavado en su porción central (úlcera de profundidad variable)"),
          ("ulcero_infiltrante", "Ulcerativo e infiltrante", "forma mixta"),
          ("infiltrante", "Infiltrante", "crece por la submucosa; puede alcanzar gran extensión sin ocluir la luz"),
          ("inclasificable", "Inclasificable", "combina los tipos anteriores")]
VARF = [("F1", "F1", "pequeñas y rectas, desaparecen con la insuflación"),
        ("F2", "F2", "tortuosas, ocupan menos de un tercio de la luz y no desaparecen con la insuflación"),
        ("F3", "F3", "grandes, ocupan más de un tercio de la luz y no desaparecen con la insuflación")]
HILL = [("I", "Grado I", "pliegue de tejido prominente que abraza estrechamente el endoscopio, 3–4 cm a lo largo de la curvatura menor (válvula normal)"),
        ("II", "Grado II", "pliegue menos prominente; con la respiración se abre un espacio entre el endoscopio y el pliegue, que se cierra pronto"),
        ("III", "Grado III", "casi no hay pliegue; el hiato está ensanchado y queda un espacio constante alrededor del endoscopio"),
        ("IV", "Grado IV", "sin pliegue; unión abierta con hernia hiatal y espacio amplio entre el endoscopio y el hiato")]
HERNIA_T = [("II", "Tipo II (paraesofágica)", "parte del estómago (habitualmente el fondo) se hernia junto al esófago; la unión esofagogástrica queda en su lugar"),
            ("III", "Tipo III (mixta)", "elementos de los tipos I y II: la unión y parte del estómago están por encima del diafragma"),
            ("IV", "Tipo IV", "defecto amplio por el que, además del estómago, pasan otros órganos (colon, bazo, páncreas o intestino delgado)")]
SYDNEY_CAT = [("eritematosa", "Eritematosa/exudativa", "eritema, edema y exudado", "K29.7", False),
              ("erosiva_plana", "Erosiva plana", "erosiones planas", "K29.7", False),
              ("erosiva_elevada", "Erosiva elevada (rugosa)", "erosiones sobre elevaciones de la mucosa", "K29.7", False),
              ("atrofica", "Atrófica", "atrofia, patrón vascular visible", "K29.4", False),
              ("hemorragica", "Hemorrágica", "punteado o manchas hemorrágicas", "K29.0", False),
              ("reflujo", "Por reflujo enterogástrico", "bilis en la cámara, eritema y edema", "K29.6", True),
              ("hiperplasia", "Hiperplasia de pliegues", "pliegues engrosados que no se aplanan con la insuflación", "K29.6", True)]
SYDNEY_TOPO = [("antro", "del antro"), ("cuerpo", "del cuerpo (fúndica)"), ("pangastritis", "de todo el estómago (pangastritis)")]
LANZA = [("0", "Grado 0", "sin lesiones visibles"), ("1", "Grado 1", "1 petequia o erosión"), ("2", "Grado 2", "de 2 a 10 petequias o erosiones"),
         ("3", "Grado 3", "de 11 a 25 petequias o erosiones"), ("4", "Grado 4", "más de 25 petequias o erosiones, o una úlcera de cualquier tamaño")]
PANIAGUA = [("I", "Grado I (ligero)", "escaso líquido amarillo claro en el lago gástrico; lesiones eritematosas en el antro"),
            ("II", "Grado II (moderado)", "moderada cantidad de líquido amarillo verdoso en antro y cuerpo; pliegues engrosados y eritematosos"),
            ("III", "Grado III (severo)", "abundante líquido amarillo verdoso espeso con grumos que baña toda la pared; lesiones eritematosas y "
                                           "petequiales en cuerpo y fondo, pliegues engrosados, edematosos y vascularizados")]
BORRMANN = [("I", "Borrmann I", "polipoide: circunscrito, solitario, sin ulceración"),
            ("II", "Borrmann II", "ulcerado con elevación marginal y contornos bien definidos"),
            ("III", "Borrmann III", "ulcerado con infiltración periférica, bordes mal definidos"),
            ("IV", "Borrmann IV", "infiltrante difuso (linitis plástica)")]
GOITEIN = [("I", "Grado I", "estenosis leve: permite el paso de un endoscopio de 10.5 mm"),
           ("II", "Grado II", "estenosis moderada: permite el paso de un endoscopio pediátrico de 8.5 mm"),
           ("III", "Grado III", "estenosis severa: solo permite el paso de una guía"),
           ("IV", "Grado IV", "obstrucción completa o casi completa, no franqueable")]
MAYO = [("0", "Mayo 0", "normal o enfermedad inactiva"),
        ("1", "Mayo 1", "leve: eritema, disminución del patrón vascular, friabilidad leve"),
        ("2", "Mayo 2", "moderada: eritema marcado, ausencia de patrón vascular, friabilidad, erosiones"),
        ("3", "Mayo 3", "grave: sangrado espontáneo, ulceraciones")]
UC_EXT = [("proctitis", "proctitis", "K51.2"), ("rectosigmoiditis", "rectosigmoiditis", "K51.3"),
          ("izquierda", "colitis izquierda (hasta el ángulo esplénico)", "K51.5"), ("extensa", "colitis extensa (pancolitis)", "K51.0")]
RUTGEERTS = [("i0", "i0", "sin lesiones"), ("i1", "i1", "5 o menos lesiones aftosas"),
             ("i2a", "i2a", "lesiones confinadas a la anastomosis"),
             ("i2b", "i2b", "más de 5 lesiones aftosas con mucosa normal entre ellas, o áreas salteadas de lesiones más grandes"),
             ("i3", "i3", "ileítis aftosa difusa con mucosa difusamente inflamada"),
             ("i4", "i4", "inflamación difusa con úlceras grandes, nódulos y/o estenosis")]
PARIS_ADV = [("1", "Tipo 1", "polipoide, generalmente de base ancha"), ("2", "Tipo 2", "ulcerado con márgenes demarcados y elevados"),
             ("3", "Tipo 3", "ulcerado e infiltrante, sin límites definidos"), ("4", "Tipo 4", "no ulcerado, infiltrante difuso"),
             ("5", "Tipo 5", "avanzado inclasificable")]


def _pts(n):
    return f"{n} punto" + ("" if n == 1 else "s")


def _lc(s):
    """Minúscula solo en la primera letra (conserva los números romanos: «Tipo II» → «tipo II»)."""
    return s[:1].lower() + s[1:]


def _phg(v, r):
    pts = {"leve": 1, "severo": 2}[r["mosaico"]] + {"no": 0, "aisladas": 1, "confluentes": 2}[r["rojas"]] + {"no": 0, "si": 2}[r["gave"]]
    return pts, ("leve" if pts <= 3 else "severa")


def _dica(r):
    pts = sum({"izquierdo": 2, "derecho": 1}[x] for x in r["extension"]) + (1 if r["numero"] == "mas15" else 0)
    pts += {"no": 0, "edema": 1, "erosiones": 2, "scad": 3}[r["inflamacion"]] + 4 * len(r.get("complicaciones") or [])
    return pts, (1 if pts <= 3 else 2 if pts <= 7 else 3)


def _dica_sentence(r):
    ext = {"izquierdo": "colon izquierdo", "derecho": "colon derecho"}
    where = " y ".join(ext[x] for x in ("izquierdo", "derecho") if x in r["extension"])
    num = "15 o menos" if r["numero"] == "hasta15" else "más de 15"
    infl = {"no": "sin signos inflamatorios", "edema": "con edema o hiperemia", "erosiones": "con erosiones",
            "scad": "con colitis segmentaria asociada a divertículos (SCAD)"}[r["inflamacion"]]
    comp = r.get("complicaciones") or []
    pts, dica = _dica(r)
    return (f"Enfermedad diverticular de {where}, {num} divertículos por segmento, {infl}"
            + (", con " + ", ".join({"rigidez": "rigidez", "estenosis": "estenosis", "pus": "pus", "sangrado": "sangrado"}[c] for c in comp)
               if comp else ", sin complicaciones") + f". Clasificación DICA {dica} ({_pts(pts)}).")


def _saunders(r):
    pts = {"distal": 1, "todo": 2}[r["distribucion"]] + {"menos50": 1, "mas50": 2}[r["superficie"]] + {"no": 0, "si": 1}[r["sangre"]]
    return pts, ("A (ligera)" if pts <= 2 else "B (moderada)" if pts == 3 else "C (severa)")


LA = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]
FORREST = [("Ia", "Ia (sangrado en chorro)"), ("Ib", "Ib (sangrado en capa)"), ("IIa", "IIa (vaso visible)"), ("IIb", "IIb (coágulo adherido)"),
           ("IIc", "IIc (mancha pigmentada)"), ("III", "III (fondo limpio)")]
GASTRIC_LOC = [("fondo", "fondo"), ("cuerpo", "cuerpo"), ("angulo", "ángulo"), ("antro", "antro"), ("prepilorica", "región prepilórica")]
DUO_LOC = [("bulbo_ant", "cara anterior del bulbo"), ("bulbo_post", "cara posterior del bulbo"), ("bulbo", "bulbo"),
           ("segunda", "segunda porción")]
COLON_LOC = [("ileon", "íleon terminal"), ("ciego", "ciego"), ("ascendente", "colon ascendente"), ("hepatico", "ángulo hepático"),
             ("transverso", "colon transverso"), ("esplenico", "ángulo esplénico"), ("descendente", "colon descendente"),
             ("sigmoides", "sigmoides"), ("recto", "recto")]
PARIS = [("0-Ip", "0-Ip pediculado"), ("0-Isp", "0-Isp semipediculado"), ("0-Is", "0-Is sésil"), ("0-IIa", "0-IIa ligeramente elevado"),
         ("0-IIa+IIc", "0-IIa+IIc elevado con depresión central"), ("0-IIb", "0-IIb plano"), ("0-IIc", "0-IIc ligeramente deprimido"),
         ("0-IIc+IIa", "0-IIc+IIa deprimido con bordes elevados")]
NICE = [("1", "NICE 1"), ("2", "NICE 2"), ("3", "NICE 3")]
RESECTION = [("asa_fria", "asa fría"), ("asa_caliente", "asa caliente"), ("pinza", "pinza de biopsia"), ("mucosectomia", "mucosectomía"),
             ("no", "no resecado")]


def _forrest_dx(organ, f):
    label = dict(FORREST)[f]
    return f"Úlcera {organ} Forrest {label}"


def _polyp_sentence(v, r):
    s = (f"{v['cantidad']} pólipos" if r.get("cantidad") not in (None, "", "1") else "Pólipo") + f" de {v['mm']} mm en {v['loc']}"
    extra = [x for x in [f"París {r['paris']}" if r.get("paris") else None, v.get("nice")] if x]
    if extra:
        s += ", " + ", ".join(extra)
    if r.get("reseccion") == "no":
        s += ", no resecado"
    elif r.get("reseccion"):
        s += f", resecado con {v['reseccion']}"
        if r.get("recuperado") == "si":
            s += " y recuperado"
        elif r.get("recuperado") == "no":
            s += ", no recuperado"
    return s + "."


def _polyp_dx(v, r):
    if r.get("nice") == "3":
        return "Lesión de colon NICE 3 (sospecha de invasión submucosa profunda), pendiente de histología"
    if r.get("loc") == "recto":
        return "Pólipo de recto"
    if r.get("cantidad") not in (None, "", "1"):
        return "Pólipos de colon múltiples"
    return {"1": "Pólipo de colon NICE 1 (aspecto hiperplásico o serrado)", "2": "Pólipo de colon NICE 2 (aspecto adenomatoso)"}.get(
        r.get("nice"), "Pólipo de colon")


def _divert_dx(v, r):
    locs = r.get("loc") or []
    if locs == ["sigmoides"]:
        return "Enfermedad diverticular de colon sigmoides"
    if len(locs) >= 4:
        return "Enfermedad diverticular de colon (pancolónica)"
    return "Enfermedad diverticular de colon"


FINDINGS = {
    "esofago": [
        ("esofagitis", "Esofagitis erosiva (Los Ángeles)", [P("grado", "Grado de Los Ángeles", options=LA)],
         lambda v, r: f"Erosiones de la mucosa del esófago distal compatibles con esofagitis grado {r['grado']} de Los Ángeles.",
         lambda v, r: f"Esofagitis erosiva grado {r['grado']} de Los Ángeles"),
        ("barrett", "Esófago de Barrett (Praga)", [P("c", "Praga C", "number", unit="cm"), P("m", "Praga M", "number", unit="cm")],
         lambda v, r: f"Mucosa de aspecto columnar que asciende por el esófago distal, Praga C{v['c']} M{v['m']}.",
         lambda v, r: ("Esófago de Barrett (Praga C__ M__), pendiente de histología",
                       f"Esófago de Barrett (Praga C{v['c']} M{v['m']}), pendiente de histología")),
        ("varices", "Várices esofágicas", [P("tam", "Tamaño", options=[("pequenas", "pequeñas (< 5 mm)"), ("grandes", "grandes (> 5 mm)")]),
                                           P("rojos", "Signos rojos", options=[("no", "sin signos rojos"), ("si", "con signos rojos")]),
                                           P("sangrado", "Sangrado", required=False,
                                             options=[("activo", "con sangrado activo"), ("estigmas", "con estigmas de sangrado reciente")]),
                                           G("forma", "Forma (F1–F3)", VARF, required=False)],
         lambda v, r: f"Várices esofágicas {v['tam']}" + (f" {r['forma']} ({dict((a, c) for a, _, c in VARF)[r['forma']]})" if r.get("forma") else "")
         + f", {v['rojos']}" + (f", {v['sangrado']}" if r.get("sangrado") else "") + ".",
         lambda v, r: "Várices esofágicas con sangrado activo o estigmas de sangrado reciente" if r.get("sangrado") else
         f"Várices esofágicas {'pequeñas (< 5 mm)' if r['tam'] == 'pequenas' else 'grandes (> 5 mm)'}, {'con' if r['rojos'] == 'si' else 'sin'} signos rojos"),
        ("nerd_m", "Cambios mínimos (no erosiva, grado M)", [],
         lambda v, r: "Eritema y/o blanquecimiento de la mucosa del esófago distal sin solución de continuidad (grado M de la "
                      "clasificación de Los Ángeles modificada).",
         lambda v, r: "Enfermedad por reflujo no erosiva con cambios mínimos (grado M)"),
        ("candida", "Placas de aspecto candidiásico (Kodsi)", [G("kodsi", "Grado de Kodsi", KODSI, required=False)],
         lambda v, r: "Placas blanquecinas adheridas a la mucosa, de aspecto candidiásico" + (f", grado {r['kodsi']} de Kodsi" if r.get("kodsi") else "") + ".",
         lambda v, r: f"Esofagitis candidiásica grado {r['kodsi']} de Kodsi" if r.get("kodsi") else "Esofagitis de aspecto candidiásico"),
        ("herpes", "Lesiones de aspecto herpético", [G("estadio", "Estadio", HERPES)],
         lambda v, r: f"Lesiones de aspecto herpético, {_lc(v['estadio'])}: {dict((a, c) for a, _, c in HERPES)[r['estadio']]}.",
         lambda v, r: DXD(f"Esofagitis de aspecto herpético, estadio {r['estadio']}, pendiente de histología", None)),
        ("eosinofilica", "Signos de esofagitis eosinofílica", [P("signos", "Signos", "multi", [("anillos", "anillos"), ("surcos", "surcos longitudinales"),
                                                                                             ("exudados", "exudados blanquecinos"), ("edema", "edema"),
                                                                                             ("crepe", "mucosa en papel crepé"),
                                                                                             ("estrechez", "estrechez de la luz")])],
         lambda v, r: f"Mucosa con {v['signos']}, sugestivos de esofagitis eosinofílica.",
         lambda v, r: "Hallazgos sugestivos de esofagitis eosinofílica (anillos, surcos, exudados), pendiente de histología"),
        ("ulcera", "Úlcera esofágica", [P("mm", "Tamaño", "number", unit="mm"), P("cm", "Distancia de la arcada dentaria", "number", unit="cm", required=False)],
         lambda v, r: f"Úlcera esofágica de {v['mm']} mm" + (f" a {v['cm']} cm de la arcada dentaria" if r.get("cm") else "") + ".",
         lambda v, r: "Úlcera esofágica"),
        ("estenosis", "Estenosis (Bernal)", [P("cm", "Distancia de la arcada dentaria", "number", unit="cm"),
                                             P("paso", "Paso del endoscopio", options=[("si", "que permite el paso del endoscopio"),
                                                                                       ("no", "que no permite el paso del endoscopio")]),
                                             G("bernal", "Tipo de Bernal", BERNAL, required=False)],
         lambda v, r: f"Estenosis a {v['cm']} cm de la arcada dentaria, {v['paso']}" + (f", {_lc(v['bernal'])} de Bernal" if r.get("bernal") else "") + ".",
         lambda v, r: DXD(f"Estenosis esofágica tipo {r['bernal']} de Bernal", "K22.2") if r.get("bernal") else "Estenosis esofágica"),
        ("acalasia", "Hallazgos de acalasia (grado)", [G("grado", "Grado endoscópico", ACALASIA)],
         lambda v, r: f"Esófago con {dict((a, c) for a, _, c in ACALASIA)[r['grado']]}; unión esofagogástrica que ofrece resistencia y se "
                      f"vence con presión suave. Hallazgos compatibles con acalasia {_lc(v['grado'])}.",
         lambda v, r: DXD(f"Hallazgos compatibles con acalasia, grado endoscópico {r['grado']}", "K22.0")),
        ("caustico", "Lesión por cáusticos (Zargar)", [P("grado", "Grado de Zargar", options=[(x, x) for x in ("0", "1", "2a", "2b", "3a", "3b")])],
         lambda v, r: f"Lesión de la mucosa esofágica por cáusticos, grado {r['grado']} de Zargar.",
         lambda v, r: ("Lesión esofágica por cáusticos, grado __ de Zargar", f"Lesión esofágica por cáusticos, grado {r['grado']} de Zargar")),
        ("neoplasia", "Lesión de aspecto neoplásico", [P("cm", "Distancia de la arcada dentaria", "number", unit="cm"),
                                                       G("tipo", "Tipo macroscópico (cáncer avanzado)", CA_ESO, required=False)],
         lambda v, r: f"Lesión de aspecto neoplásico" + (f", tipo {_lc(v['tipo'])}," if r.get("tipo") else "") + f" a {v['cm']} cm de la arcada dentaria.",
         lambda v, r: "Lesión esofágica de aspecto neoplásico, pendiente de histología"),
    ],
    "ueg": [
        ("hill", "Válvula gastroesofágica (Hill)", [G("grado", "Grado de Hill (en retroflexión)", HILL)],
         lambda v, r: f"En retroflexión, válvula gastroesofágica {_lc(v['grado'])} de Hill: {dict((a, c) for a, _, c in HILL)[r['grado']]}.",
         lambda v, r: DXD(f"Válvula gastroesofágica grado {r['grado']} de Hill", None) if r["grado"] in ("III", "IV") else None),
        ("hernia", "Hernia hiatal por deslizamiento (tipo I)", [P("cm", "Tamaño", "number", unit="cm")],
         lambda v, r: f"Hernia hiatal por deslizamiento (tipo I) de {v['cm']} cm.",
         lambda v, r: ("Hernia hiatal por deslizamiento de __ cm", f"Hernia hiatal por deslizamiento de {v['cm']} cm")),
        ("paraesofagica", "Hernia paraesofágica o mixta (tipos II–IV)", [G("tipo", "Tipo de hernia", HERNIA_T)],
         lambda v, r: f"Hernia hiatal {_lc(v['tipo'])}: {dict((a, c) for a, _, c in HERNIA_T)[r['tipo']]}.",
         lambda v, r: DXD(f"Hernia hiatal {_lc(dict((a, s) for a, s, _ in HERNIA_T)[r['tipo']])}", "K44.9")),
        ("mallory", "Desgarro de Mallory-Weiss", [], lambda v, r: "Desgarro longitudinal de la mucosa en la unión esofagogástrica.",
         lambda v, r: "Desgarro de Mallory-Weiss"),
        ("cardias", "Cardias que no abraza el endoscopio", [], lambda v, r: "En retroflexión, cardias que no abraza adecuadamente el endoscopio.",
         lambda v, r: None),
    ],
    "estomago": [
        ("eritema", "Eritema", [P("loc", "Localización", "multi", GASTRIC_LOC)],
         lambda v, r: f"Eritema de la mucosa en {v['loc']}.",
         lambda v, r: "Gastropatía eritematosa de antro" if r["loc"] == ["antro"] else "Gastropatía eritematosa"),
        ("erosiones", "Erosiones", [P("loc", "Localización", "multi", GASTRIC_LOC)],
         lambda v, r: f"Erosiones planas en {v['loc']}.", lambda v, r: "Gastropatía erosiva"),
        ("atrofia", "Aspecto atrófico", [P("loc", "Localización", "multi", GASTRIC_LOC)],
         lambda v, r: f"Mucosa de aspecto atrófico, con patrón vascular visible, en {v['loc']}.",
         lambda v, r: "Gastropatía de aspecto atrófico, pendiente de histología"),
        ("sydney", "Gastritis endoscópica (Sídney)", [G("cat", "Categoría", [(a, s, d) for a, s, d, _, _ in SYDNEY_CAT]),
                                                       P("topo", "Topografía", options=SYDNEY_TOPO),
                                                       P("int", "Intensidad", options=[("leve", "leve"), ("moderada", "moderada"), ("severa", "severa")],
                                                         required=False)],
         lambda v, r: f"Gastritis endoscópica {v['cat'].lower()} {v['topo']}" + (f", de intensidad {v['int']}" if r.get("int") else "")
         + " (Sistema Sídney).",
         lambda v, r: DXD(f"Gastritis endoscópica {v['cat'].lower()} {v['topo']} (Sistema Sídney)"
                          + (", pendiente de histología" if r["cat"] == "atrofica" else ""),
                          *[(c, a) for k, _, _, c, a in SYDNEY_CAT if k == r["cat"]][0])),
        ("lanza", "Lesiones por AINE (Lanza)", [G("grado", "Grado de Lanza", LANZA)],
         lambda v, r: f"Lesiones de la mucosa gástrica {_lc(v['grado'])} de Lanza: {dict((a, c) for a, _, c in LANZA)[r['grado']]}.",
         lambda v, r: DXD(f"Gastropatía por AINE grado {r['grado']} de Lanza", "K29.7") if r["grado"] != "0" else None),
        ("paniagua", "Reflujo duodenogástrico (Paniagua)", [G("grado", "Grado", PANIAGUA)],
         lambda v, r: f"{dict((a, c) for a, _, c in PANIAGUA)[r['grado']][0].upper()}{dict((a, c) for a, _, c in PANIAGUA)[r['grado']][1:]}; "
                      f"gastritis por reflujo duodenogástrico {_lc(v['grado'])} (Paniagua).",
         lambda v, r: DXD(f"Gastritis por reflujo duodenogástrico grado {r['grado']} (Paniagua)", "K29.6", True)),
        ("hipertensiva", "Gastropatía hipertensiva portal", [P("grado", "Grado", options=[("leve", "leve"), ("severa", "severa")])],
         lambda v, r: f"Patrón en mosaico de la mucosa compatible con gastropatía hipertensiva portal {v['grado']}.",
         lambda v, r: f"Gastropatía hipertensiva portal {r['grado']}"),
        ("hipertensiva_pts", "Gastropatía hipertensiva (puntaje de Baveno)",
         [P("mosaico", "Patrón en mosaico", options=[("leve", "leve (1 punto)"), ("severo", "severo (2 puntos)")]),
          P("rojas", "Marcas rojas", options=[("no", "ausentes (0)"), ("aisladas", "aisladas (1)"), ("confluentes", "confluentes (2)")]),
          P("gave", "Ectasia vascular antral (GAVE)", options=[("no", "ausente (0)"), ("si", "presente (2)")],
            help=["Leve: 3 puntos o menos. Severa: 4 puntos o más."])],
         lambda v, r: f"Patrón en mosaico {r['mosaico']}, marcas rojas {v['rojas'].split(' (')[0]}, GAVE {v['gave'].split(' (')[0]}: "
                      f"gastropatía hipertensiva portal {_phg(v, r)[1]} (puntaje de Baveno {_phg(v, r)[0]}).",
         lambda v, r: f"Gastropatía hipertensiva portal {'leve' if _phg(v, r)[1] == 'leve' else 'severa'}"),
        ("varices_g", "Várices gástricas (Sarin)", [P("tipo", "Tipo de Sarin", options=[("GOV1", "GOV1"), ("GOV2", "GOV2"), ("IGV1", "IGV1"), ("IGV2", "IGV2")])],
         lambda v, r: f"Várices gástricas tipo {r['tipo']} de Sarin.", lambda v, r: f"Várices gástricas {r['tipo']} (Sarin)"),
        ("gave", "Ectasia vascular antral (GAVE)", [], lambda v, r: "Ectasias vasculares en el antro (GAVE).",
         lambda v, r: "Ectasia vascular antral (GAVE)"),
        ("ulcera_g", "Úlcera gástrica (Forrest)", [P("loc", "Localización", options=GASTRIC_LOC), P("mm", "Tamaño", "number", unit="mm"),
                                                   P("forrest", "Forrest", options=FORREST)],
         lambda v, r: f"Úlcera de {v['mm']} mm en {v['loc']}, Forrest {v['forrest']}.", lambda v, r: _forrest_dx("gástrica", r["forrest"])),
        ("polipo_g", "Pólipo gástrico", [P("cantidad", "Cantidad", "number", required=False), P("mm", "Tamaño", "number", unit="mm"),
                                         P("loc", "Localización", options=GASTRIC_LOC)],
         lambda v, r: (f"{v['cantidad']} pólipos" if r.get("cantidad") not in (None, "", "1") else "Pólipo") + f" de {v['mm']} mm en {v['loc']}.",
         lambda v, r: "Pólipo gástrico"),
        ("subepitelial", "Lesión subepitelial", [P("mm", "Tamaño", "number", unit="mm"), P("loc", "Localización", options=GASTRIC_LOC)],
         lambda v, r: f"Lesión subepitelial de {v['mm']} mm en {v['loc']}, con mucosa de superficie de aspecto normal.",
         lambda v, r: "Lesión subepitelial gástrica"),
        ("neoplasia_g", "Lesión de aspecto neoplásico (Borrmann)", [P("loc", "Localización", options=GASTRIC_LOC),
                                                                    G("borrmann", "Borrmann (cáncer avanzado)", BORRMANN, required=False)],
         lambda v, r: f"Lesión de aspecto neoplásico en {v['loc']}"
         + (f", {v['borrmann']} ({dict((a, c) for a, _, c in BORRMANN)[r['borrmann']]})" if r.get("borrmann") else "") + ".",
         lambda v, r: DXD(f"Lesión gástrica de aspecto neoplásico Borrmann {r['borrmann']}, pendiente de histología", None)
         if r.get("borrmann") else "Lesión gástrica de aspecto neoplásico, pendiente de histología"),
        ("goitein", "Estenosis de anastomosis posbypass (Goitein)", [G("grado", "Grado de Goitein", GOITEIN)],
         lambda v, r: f"Estenosis de la anastomosis gastroyeyunal {_lc(v['grado'])} de Goitein: {dict((a, c) for a, _, c in GOITEIN)[r['grado']]}.",
         lambda v, r: DXD(f"Estenosis de anastomosis gastroyeyunal grado {r['grado']} de Goitein", "K91.8", True)),
        ("restos", "Restos alimentarios", [], lambda v, r: "Restos alimentarios en la cámara gástrica que limitan la evaluación.",
         lambda v, r: "Restos alimentarios en estómago (estudio limitado)"),
    ],
    "duodeno": [
        ("duodenitis", "Duodenitis erosiva de bulbo", [], lambda v, r: "Eritema y erosiones en el bulbo duodenal.",
         lambda v, r: "Duodenitis erosiva de bulbo"),
        ("ulcera_d", "Úlcera duodenal (Forrest)", [P("loc", "Localización", options=DUO_LOC), P("mm", "Tamaño", "number", unit="mm"),
                                                   P("forrest", "Forrest", options=FORREST)],
         lambda v, r: f"Úlcera de {v['mm']} mm en {v['loc']}, Forrest {v['forrest']}.", lambda v, r: _forrest_dx("duodenal", r["forrest"])),
        ("atrofia_d", "Pliegues disminuidos o festoneados", [],
         lambda v, r: "Disminución y festoneado de los pliegues en la segunda porción duodenal.",
         lambda v, r: "Atrofia de vellosidades duodenales (descartar enfermedad celíaca), pendiente de histología"),
        ("polipo_d", "Pólipo duodenal", [P("mm", "Tamaño", "number", unit="mm"), P("loc", "Localización", options=DUO_LOC)],
         lambda v, r: f"Pólipo de {v['mm']} mm en {v['loc']}.", lambda v, r: "Pólipo duodenal"),
        ("papila", "Papila de aspecto neoplásico", [], lambda v, r: "Papila mayor aumentada de tamaño, de aspecto neoplásico.",
         lambda v, r: "Lesión de papila de aspecto neoplásico, pendiente de histología"),
    ],
}
COLON = [
    ("polipo", "Pólipo", [P("cantidad", "Cantidad", "number", required=False), P("mm", "Tamaño", "number", unit="mm"),
                          P("loc", "Localización", options=COLON_LOC), P("paris", "París", options=PARIS, required=False),
                          P("nice", "NICE", options=NICE, required=False), P("reseccion", "Resección", options=RESECTION, required=False),
                          P("recuperado", "Recuperado para patología", options=[("si", "sí"), ("no", "no")], required=False)],
     _polyp_sentence, _polyp_dx),
    ("diverticulos", "Divertículos", [P("loc", "Localización", "multi", COLON_LOC[1:])],
     lambda v, r: f"Divertículos de boca amplia en {v['loc']}, sin signos de complicación.", _divert_dx),
    ("dica", "Enfermedad diverticular (DICA)",
     [P("extension", "Extensión", "multi", [("izquierdo", "colon izquierdo, hasta el ángulo esplénico (2)"), ("derecho", "colon derecho (1)")]),
      P("numero", "Número de divertículos por segmento", options=[("hasta15", "15 o menos (0)"), ("mas15", "más de 15 (1)")]),
      P("inflamacion", "Signos inflamatorios", options=[("no", "ninguno (0)"), ("edema", "edema o hiperemia (1)"), ("erosiones", "erosiones (2)"),
                                                         ("scad", "colitis segmentaria asociada a divertículos, SCAD (3)")]),
      P("complicaciones", "Complicaciones", "multi", [("rigidez", "rigidez (4)"), ("estenosis", "estenosis (4)"), ("pus", "pus (4)"),
                                                        ("sangrado", "sangrado (4)")], required=False,
        help=["DICA 1: 1 a 3 puntos (sin riesgo de complicaciones) · DICA 2: 4 a 7 (bajo riesgo) · DICA 3: más de 7 (riesgo alto)."])],
     lambda v, r: _dica_sentence(r),
     lambda v, r: DXD(f"Enfermedad diverticular de colon DICA {_dica(r)[1]} ({_pts(_dica(r)[0])})",
                      "K57.3")),
    ("cu_mayo", "Colitis ulcerosa (Mayo endoscópico)", [G("mayo", "Mayo endoscópico", MAYO),
                                                         P("ext", "Extensión", options=[(a, s) for a, s, _ in UC_EXT])],
     lambda v, r: ("Mucosa de aspecto normal (enfermedad inactiva)" if r["mayo"] == "0" else
                   f"Mucosa con {dict((a, c) for a, _, c in MAYO)[r['mayo']].split(': ', 1)[-1]}")
     + f", en relación con colitis ulcerosa: {v['ext']}. Mayo endoscópico {r['mayo']}.",
     lambda v, r: DXD(f"Colitis ulcerosa: {v['ext']}, Mayo endoscópico {r['mayo']}" + (" (remisión endoscópica)" if r["mayo"] == "0" else ""),
                      dict((a, c) for a, _, c in UC_EXT)[r["ext"]])),
    ("rutgeerts", "Crohn posquirúrgico (Rutgeerts)", [G("i", "Puntaje de Rutgeerts (neoíleon y anastomosis)", RUTGEERTS)],
     lambda v, r: f"Exploración de la anastomosis ileocólica y del neoíleon terminal: {dict((a, c) for a, _, c in RUTGEERTS)[r['i']]} "
                  f"(Rutgeerts {r['i']}).",
     lambda v, r: DXD(f"Enfermedad de Crohn posquirúrgica, Rutgeerts {r['i']}"
                      + (" (sin recurrencia endoscópica)" if r["i"] == "i0" else ""), "K50.8", True)),
    ("actinica", "Proctitis actínica (puntaje del consenso)",
     [P("distribucion", "Distribución de las telangiectasias", options=[("distal", "recto distal, < 10 cm del margen anal (1)"),
                                                                        ("todo", "todo el recto, > 10 cm (2)")]),
      P("superficie", "Superficie con telangiectasias", options=[("menos50", "menos del 50 % (1)"), ("mas50", "más del 50 % (2)")]),
      P("sangre", "Sangre fresca", options=[("no", "no (0)"), ("si", "sí (1)")],
        help=["Grado A (ligera): 2 puntos · Grado B (moderada): 3 puntos · Grado C (severa): 4–5 puntos."])],
     lambda v, r: f"Telangiectasias en {'el recto distal (a menos de 10 cm del margen anal)' if r['distribucion'] == 'distal' else 'todo el recto'}, "
                  f"que cubren {'menos' if r['superficie'] == 'menos50' else 'más'} del 50 % de la superficie, "
                  f"{'con' if r['sangre'] == 'si' else 'sin'} sangre fresca: proctitis actínica grado {_saunders(r)[1]} ({_saunders(r)[0]} puntos).",
     lambda v, r: DXD(f"Proctitis actínica grado {_saunders(r)[1].split(' ')[0]} ({_saunders(r)[0]} puntos)", "K62.7")),
    ("hemorroides", "Hemorroides internas", [P("grado", "Grado", options=[("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV")])],
     lambda v, r: f"Hemorroides internas grado {r['grado']} en la retroflexión rectal.", lambda v, r: f"Hemorroides internas grado {r['grado']}"),
    ("inflamacion", "Inflamación de la mucosa", [P("signos", "Signos", "multi", [("eritema", "eritema"), ("patron", "pérdida del patrón vascular"),
                                                                               ("friabilidad", "friabilidad"), ("erosiones", "erosiones"),
                                                                               ("ulceras", "úlceras"), ("sangrado", "sangrado espontáneo")]),
                                                 P("forma", "Distribución", options=[("continua", "de forma continua"), ("parches", "en parches")]),
                                                 P("hasta", "Extensión", options=[("recto", "limitada al recto"), ("sigmoides", "desde el recto hasta el sigmoides"),
                                                                                  ("esplenico", "desde el recto hasta el ángulo esplénico"),
                                                                                  ("todo", "desde el recto hasta el ciego"),
                                                                                  ("ileon", "en íleon terminal")])],
     lambda v, r: f"Mucosa con {v['signos']}, {v['forma']}, {v['hasta']}.", lambda v, r: "Colitis inespecífica, pendiente de histología"),
    ("angiodisplasia", "Angiodisplasia", [P("loc", "Localización", "multi", COLON_LOC[1:])],
     lambda v, r: f"Angiodisplasia en {v['loc']}.", lambda v, r: "Angiodisplasia de colon"),
    ("neoplasia_c", "Lesión de aspecto neoplásico", [P("loc", "Localización", options=COLON_LOC[1:]),
                                                     P("mm", "Tamaño", "number", unit="mm", required=False),
                                                     P("circ", "Circunferencia", options=[("parcial", "que ocupa parte de la circunferencia"),
                                                                                          ("total", "circunferencial")], required=False),
                                                     P("paso", "Paso del endoscopio", options=[("si", "que permite el paso del endoscopio"),
                                                                                               ("no", "que no permite el paso del endoscopio")], required=False),
                                                     G("paris_av", "Tipo macroscópico avanzado (París 1–5)", PARIS_ADV, required=False)],
     lambda v, r: "Lesión de aspecto neoplásico" + (f" de {v['mm']} mm" if r.get("mm") else "") + f" en {v['loc']}"
     + "".join(f", {v[k]}" for k in ("circ", "paso") if r.get(k))
     + (f", {_lc(v['paris_av'])} de París ({dict((a, c) for a, _, c in PARIS_ADV)[r['paris_av']]})" if r.get("paris_av") else "") + ".",
     lambda v, r: "Lesión de recto de aspecto neoplásico, pendiente de histología" if r["loc"] == "recto"
     else "Lesión de colon de aspecto neoplásico, pendiente de histología"),
    ("melanosis", "Melanosis coli", [], lambda v, r: "Pigmentación oscura difusa de la mucosa colónica (melanosis coli).",
     lambda v, r: "Melanosis coli"),
    ("ileon", "Íleon terminal explorado", [P("cm", "Centímetros explorados", "number", unit="cm", required=False),
                                           P("aspecto", "Aspecto", options=[("normal", "de aspecto normal"), ("aftas", "con úlceras aftosas"),
                                                                            ("ulceras", "con úlceras")])],
     lambda v, r: "Se intuba el íleon terminal" + (f" en {v['cm']} cm" if r.get("cm") else "") + f", {v['aspecto']}.", lambda v, r: None),
    ("preparacion", "Preparación inadecuada", [],
     lambda v, r: "Restos fecales que impiden la evaluación adecuada de la mucosa.", lambda v, r: "Preparación intestinal inadecuada (estudio limitado)"),
]
FINDINGS["colon"] = COLON
FINDINGS["rectosigmoides"] = COLON


# Fuente que se muestra debajo de cada hallazgo con clasificación
SOURCES = {
    "nerd_m": "Los Ángeles modificada (Hoshihara, Japón), según el " + CONSENSO,
    "candida": "Kodsi BE et al. Gastroenterology 1976;71:715-9",
    "herpes": CONSENSO,
    "estenosis": "Bernal, según el " + CONSENSO,
    "acalasia": CONSENSO,
    "neoplasia": "Tipos macroscópicos según el " + CONSENSO,
    "varices": "Tamaño: Baveno (de Franchis R et al. J Hepatol 1992). F1–F3 según el " + CONSENSO,
    "hill": "Hill LD et al. Gastrointest Endosc 1996;44:541-7",
    "paraesofagica": "Kahrilas PJ et al. Best Pract Res Clin Gastroenterol 2008;22:601-16",
    "sydney": "Sistema Sídney, división endoscópica: Tytgat GN. J Gastroenterol Hepatol 1991;6:223-34",
    "lanza": "Escala de Lanza (0–4), según el " + CONSENSO + ". Existen versiones modificadas de 6 grados.",
    "paniagua": "Paniagua Estévez y colaboradores, según el " + CONSENSO,
    "hipertensiva_pts": "Puntaje de Baveno/NIEC (de Franchis R. J Hepatol 1996), según el " + CONSENSO,
    "neoplasia_g": "Borrmann R, 1926 (tipos avanzados en la clasificación de París, Gastrointest Endosc 2003;58:S3-43)",
    "goitein": "Goitein D et al. Surg Endosc 2005;19:628-32",
    "dica": "Tursi A et al. J Gastrointestin Liver Dis 2015;24:85-93",
    "cu_mayo": "Schroeder KW et al. N Engl J Med 1987;317:1625-9. Extensión según Montreal.",
    "rutgeerts": "Rutgeerts P et al. Gastroenterology 1990;99:956-63; i2a/i2b: puntaje modificado",
    "actinica": "Puntaje de colitis actínica según el " + CONSENSO + " (no se encontró la publicación original para cotejar)",
    "neoplasia_c": "París: Gastrointest Endosc 2003;58:S3-43",
}


def by_key(section):
    return {f[0]: f for f in FINDINGS.get(section, [])}


class Invalid(ValueError):
    pass


def compose(section, finding, src):
    """src: MultiDict con los parámetros (sin prefijo). Devuelve (frase, [sugerencias {t, c, a}])."""
    f = by_key(section).get(finding)
    if not f:
        raise Invalid("Hallazgo no reconocido.")
    key, label, params, sentence, dx = f
    v, r = {}, {}
    for p in params:
        n = p["name"]
        if p["kind"] == "multi":
            opts = dict(p["options"])
            vals = [x for x in src.getlist(n) if x in opts]
            if vals:
                r[n] = vals
                items = [opts[x] for x in vals]
                v[n] = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]
        elif p["kind"] == "number":
            raw = (src.get(n) or "").strip().replace(",", ".")
            if raw:
                try:
                    x = float(raw)
                    if not 0 <= x <= 500:
                        raise ValueError
                except ValueError:
                    raise Invalid(f"«{p['label']}» debe ser un número.") from None
                r[n] = f"{x:g}"
                v[n] = f"{x:g}"
        else:
            x = src.get(n)
            if x in dict(p["options"]):
                r[n] = x
                v[n] = dict(p["options"])[x]
        if p["required"] and n not in r:
            raise Invalid(f"Falta «{p['label']}» para «{label}».")
    text = sentence(v, r)
    out = []
    d = dx(v, r)
    if isinstance(d, dict):
        out.append(d)
    elif d:
        cat, shown = (d, d) if isinstance(d, str) else d
        if cat in CATALOG:
            c, a = CATALOG[cat]
            out.append({"t": shown, "c": c, "a": a})
    return text, out
