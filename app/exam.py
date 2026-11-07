"""Exploración física con clics (v0.13.0).

Igual que el asistente de historia: el médico marca «Normal» o los hallazgos de cada sistema y el programa redacta el texto
con EXACTAMENTE lo marcado. Los textos normales son plantillas editables por el médico (Ajustes → Frases y plantillas).
- Sistema con «Normal» y sin hallazgos → texto normal de ese sistema.
- Sistema con hallazgos → solo los hallazgos; si además marcó «Normal» o «Resto sin alteraciones», se agrega
  «Resto de la exploración … sin alteraciones.»
- Sistema sin nada marcado → no se escribe nada.
"""
import json

SIDES = [("derecho", "derecho"), ("izquierdo", "izquierdo"), ("bilateral", "bilateral")]
LIMBS = [("msd", "miembro superior derecho"), ("msi", "miembro superior izquierdo"), ("mid", "miembro inferior derecho"),
         ("mii", "miembro inferior izquierdo")]
N = "exploracion_abdominal"   # en NeuroMed Pro este campo de la nota se llama «Exploración neurológica»

# sistema: (etiqueta, campo SOAP destino, nombre en «Resto de la exploración …», [(clave, etiqueta, tipo, opciones, plantilla)])
SYSTEMS = {
    "general": ("Aspecto general", "exploracion_general", "general", [
        ("hallazgos", "Hallazgos", "multi", [
            ("palidez", "palidez de piel y mucosas"), ("mucosas_secas", "mucosas orales secas"), ("febril", "aspecto febril"),
            ("caquexia", "aspecto caquéctico"), ("edema", "edema de miembros inferiores"), ("lesiones_piel", "lesiones cutáneas"),
            ("manchas_cafe", "manchas café con leche"), ("mordedura", "mordedura lateral de lengua"), ("trauma", "signos de traumatismo craneal")],
         "Presenta {v}."),
    ]),
    "cardiopulmonar": ("Cardiopulmonar y vascular", "exploracion_general", "cardiopulmonar", [
        ("corazon", "Corazón", "multi", [("taquicardia", "taquicardia"), ("arritmia", "ruidos cardiacos arrítmicos"),
                                         ("soplo", "soplo cardiaco")], "Cardiaco: {v}."),
        ("cuello", "Cuello", "multi", [("soplo_der", "soplo carotídeo derecho"), ("soplo_izq", "soplo carotídeo izquierdo")], "Cuello: {v}."),
        ("pulmon", "Pulmones", "multi", [("murmullo", "disminución del murmullo vesicular"), ("estertores", "estertores"),
                                         ("sibilancias", "sibilancias")], "Pulmonar: {v}."),
    ]),
    "mental": ("Estado mental y lenguaje", N, "del estado mental", [
        ("conciencia", "Conciencia", "select", [("somnoliento", "Somnoliento, despierta al llamado."), ("estupor", "Estuporoso."),
                                                ("coma", "En coma."), ("confuso", "Confuso.")], None),
        ("orientacion", "Desorientado en", "multi", [("tiempo", "tiempo"), ("espacio", "espacio"), ("persona", "persona")], "Desorientado en {v}."),
        ("lenguaje", "Lenguaje", "multi", [("afasia_motora", "afasia de expresión"), ("afasia_sensitiva", "afasia de comprensión"),
                                           ("afasia_global", "afasia global"), ("disartria", "disartria"), ("anomia", "anomia")], "Lenguaje: {v}."),
        ("otros", "Otros", "multi", [("negligencia", "heminegligencia"), ("memoria", "alteración de la memoria reciente"),
                                     ("bradipsiquia", "bradipsiquia")], "Presenta {v}."),
    ]),
    "pares": ("Pares craneales", N, "de pares craneales", [
        ("pupilas", "Pupilas", "multi", [("anisocoria", "anisocoria"), ("midriasis_arreactiva", "midriasis arreactiva"),
                                         ("defecto_aferente", "defecto pupilar aferente relativo")], "Pupilas: {v}."),
        ("fondo", "Fondo de ojo", "select", [("papiledema", "Fondo de ojo con papiledema."), ("palidez", "Fondo de ojo con palidez papilar."),
                                             ("no_valorable", "Fondo de ojo no valorable.")], None),
        ("campos", "Campos visuales", "multi", [("hemianopsia_der", "hemianopsia homónima derecha"),
                                                ("hemianopsia_izq", "hemianopsia homónima izquierda"), ("cuadrantanopsia", "cuadrantanopsia")],
         "Campos visuales: {v}."),
        ("oculomotor", "Motilidad ocular", "multi", [("desviacion", "desviación conjugada de la mirada"), ("paresia_iii", "paresia del III par"),
                                                     ("paresia_vi", "paresia del VI par"), ("nistagmo", "nistagmo"), ("diplopia", "diplopía"),
                                                     ("ptosis", "ptosis palpebral")], "Motilidad ocular: {v}."),
        ("facial", "Facial", "multi", [("central_der", "paresia facial central derecha"), ("central_izq", "paresia facial central izquierda"),
                                       ("periferica_der", "parálisis facial periférica derecha"),
                                       ("periferica_izq", "parálisis facial periférica izquierda")], "Presenta {v}."),
        ("bulbares", "Pares bajos", "multi", [("disfagia", "disfagia"), ("disfonia", "disfonía"), ("lengua", "desviación de la lengua"),
                                              ("velo", "paresia del velo del paladar")], "Pares bajos: {v}."),
    ]),
    "motor": ("Fuerza, tono y trofismo", N, "motora", [
        ("debilidad", "Debilidad en", "multi", LIMBS, "Debilidad en {v}."),
        ("grado", "Fuerza del segmento afectado (MRC 0–5)", "number", None, "Fuerza {v}/5 en el segmento afectado."),
        ("patron", "Patrón", "multi", [("hemiparesia_der", "hemiparesia derecha"), ("hemiparesia_izq", "hemiparesia izquierda"),
                                       ("paraparesia", "paraparesia"), ("cuadriparesia", "cuadriparesia"), ("proximal", "debilidad de predominio proximal"),
                                       ("distal", "debilidad de predominio distal"), ("fatigable", "debilidad fatigable")], "Patrón: {v}."),
        ("tono", "Tono", "multi", [("espasticidad", "espasticidad"), ("rigidez", "rigidez"), ("rueda_dentada", "rigidez en rueda dentada"),
                                   ("hipotonia", "hipotonía")], "Tono: {v}."),
        ("trofismo", "Trofismo y movimientos", "multi", [("atrofia", "atrofia muscular"), ("fasciculaciones", "fasciculaciones"),
                                                         ("temblor_reposo", "temblor de reposo"), ("temblor_postural", "temblor postural o de acción"),
                                                         ("bradicinesia", "bradicinesia"), ("mioclonias", "mioclonías")], "Se observa {v}."),
    ]),
    "reflejos": ("Reflejos", N, "de reflejos", [
        ("osteotendinosos", "Osteotendinosos", "select", [("hiper", "Reflejos osteotendinosos aumentados."),
                                                          ("hipo", "Reflejos osteotendinosos disminuidos."),
                                                          ("abolidos", "Reflejos osteotendinosos abolidos."),
                                                          ("asimetricos", "Reflejos osteotendinosos asimétricos.")], None),
        ("babinski", "Babinski", "multi", SIDES, "Signo de Babinski {v}."),
        ("otros", "Otros", "multi", [("clonus", "clonus aquíleo"), ("hoffmann", "signo de Hoffmann"), ("glabelar", "reflejo glabelar inagotable"),
                                     ("prension", "reflejo de prensión")], "Presenta {v}."),
    ]),
    "sensibilidad": ("Sensibilidad", N, "sensitiva", [
        ("hemi", "Hemihipoestesia", "select", [("der", "Hemihipoestesia derecha."), ("izq", "Hemihipoestesia izquierda.")], None),
        ("patron", "Patrón", "multi", [("guante_calcetin", "hipoestesia en guante y calcetín"), ("nivel", "nivel sensitivo"),
                                       ("radicular", "hipoestesia de distribución radicular"), ("mediano", "hipoestesia en territorio del nervio mediano")],
         "Presenta {v}."),
        ("profunda", "Sensibilidad profunda", "multi", [("vibratoria", "disminución de la sensibilidad vibratoria"),
                                                        ("posicional", "alteración de la sensibilidad posicional"), ("romberg", "Romberg positivo")],
         "Presenta {v}."),
        ("nivel_detalle", "Nivel o territorio", "text", None, "Territorio: {v}."),
    ]),
    "coordinacion": ("Coordinación y marcha", N, "de coordinación y marcha", [
        ("dismetria", "Dismetría", "multi", SIDES, "Dismetría {v}."),
        ("otros", "Otros", "multi", [("disdiadococinesia", "disdiadococinesia"), ("ataxia_tronco", "ataxia de tronco")], "Presenta {v}."),
        ("marcha", "Marcha", "select", [("hemiparetica", "Marcha hemiparética."), ("parkinsoniana", "Marcha parkinsoniana, a pasos cortos."),
                                        ("ataxica", "Marcha atáxica, con base de sustentación amplia."), ("estepage", "Marcha en steppage."),
                                        ("no_deambula", "No deambula."), ("con_apoyo", "Deambula con apoyo.")], None),
        ("tandem", "Marcha en tándem", "select", [("alterada", "Marcha en tándem alterada.")], None),
    ]),
    "meninges": ("Signos meníngeos", N, "meníngea", [
        ("signos", "Signos", "multi", [("rigidez_nuca", "rigidez de nuca"), ("kernig", "signo de Kernig"), ("brudzinski", "signo de Brudzinski")],
         "Presenta {v}."),
    ]),
}
ALL_NORMAL = ("general", "cardiopulmonar", "mental", "pares", "motor", "reflejos", "sensibilidad", "coordinacion")

DEFAULT_NORMAL = {
    "general": "Paciente consciente, hidratado, con buena coloración de piel y mucosas, sin lesiones cutáneas ni signos de traumatismo.",
    "cardiopulmonar": "Ruidos cardiacos rítmicos, sin soplos. Sin soplos carotídeos. Campos pulmonares con buena entrada de aire, sin ruidos agregados.",
    "mental": "Alerta, orientado en tiempo, espacio y persona. Lenguaje fluente, con comprensión, repetición y denominación conservadas.",
    "pares": "Pupilas isocóricas y normorreactivas. Campos visuales por confrontación normales. Movimientos oculares completos, sin nistagmo. "
             "Cara simétrica. Pares bajos sin alteraciones.",
    "motor": "Fuerza 5/5 en las cuatro extremidades. Tono y trofismo normales. Sin movimientos anormales.",
    "reflejos": "Reflejos osteotendinosos ++/++++ simétricos. Respuesta plantar flexora bilateral.",
    "sensibilidad": "Sensibilidad superficial y profunda conservadas en las cuatro extremidades. Romberg negativo.",
    "coordinacion": "Pruebas dedo-nariz y talón-rodilla sin dismetría. Marcha normal, tándem conservado.",
    "meninges": "Sin rigidez de nuca ni signos meníngeos.",
}


def normal_texts(settings_json):
    try:
        custom = json.loads(settings_json) if settings_json else {}
    except ValueError:
        custom = {}
    return {k: (custom.get(k) or v) for k, v in DEFAULT_NORMAL.items()}


def _join(items):
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else (", ".join(items[:-1]) + " y " + items[-1] if items else "")


def compose(src, template: str, normals: dict) -> dict:
    """src: MultiDict con claves «sistema-campo», «sistema-normal», «sistema-resto». Devuelve {campo_de_la_nota: texto}."""
    out = {}
    for sysk, (label, target, resto_name, fields) in SYSTEMS.items():
        parts = []
        for key, flabel, kind, options, tpl in fields:
            name = f"{sysk}-{key}"
            if kind == "multi":
                allowed = dict(options)
                vals = [allowed[v] for v in src.getlist(name) if v in allowed]
                if vals:
                    parts.append(tpl.format(v=_join(vals)))
            elif kind == "select":
                v = src.get(name)
                if v in dict(options):
                    parts.append(dict(options)[v])
            elif kind == "number":
                raw = (src.get(name) or "").strip().replace(",", ".")
                try:
                    x = float(raw)
                    if 0 <= x <= 40:
                        parts.append(tpl.format(v=f"{x:g}"))
                except ValueError:
                    pass
            else:
                v = (src.get(name) or "").strip()[:300].rstrip(".")
                if v:
                    parts.append(tpl.format(v=v))
        normal = src.get(f"{sysk}-normal") == "1"
        resto = src.get(f"{sysk}-resto") == "1"
        if parts:
            text = " ".join(parts)
            if normal or resto:
                text += f" Resto de la exploración {resto_name} sin alteraciones."
        elif normal:
            text = normals[sysk]
        else:
            continue
        dest = "narrativa" if template == "narrativa" else target
        out.setdefault(dest, []).append(text)
    result = {k: " ".join(v) for k, v in out.items()}
    if template == "narrativa" and result.get("narrativa"):
        result["narrativa"] = "Exploración física: " + result["narrativa"]
    return result
