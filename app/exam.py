"""Exploración física con clics (v0.13.0).

Igual que el asistente de historia: el médico marca «Normal» o los hallazgos de cada sistema y el programa redacta el texto
con EXACTAMENTE lo marcado. Los textos normales son plantillas editables por el médico (Ajustes → Frases y plantillas).
- Sistema con «Normal» y sin hallazgos → texto normal de ese sistema.
- Sistema con hallazgos → solo los hallazgos; si además marcó «Normal» o «Resto sin alteraciones», se agrega
  «Resto de la exploración … sin alteraciones.»
- Sistema sin nada marcado → no se escribe nada.
"""
import json

LOCS = [("epigastrio", "epigastrio"), ("hipocondrio_der", "hipocondrio derecho"), ("hipocondrio_izq", "hipocondrio izquierdo"),
        ("mesogastrio", "mesogastrio"), ("flanco_der", "flanco derecho"), ("flanco_izq", "flanco izquierdo"),
        ("fosa_iliaca_der", "fosa ilíaca derecha"), ("fosa_iliaca_izq", "fosa ilíaca izquierda"), ("hipogastrio", "hipogastrio"),
        ("difuso", "forma difusa")]

# sistema: (etiqueta, campo SOAP destino, nombre en «Resto de la exploración …», [(clave, etiqueta, tipo, opciones, plantilla)])
SYSTEMS = {
    "general": ("Aspecto general", "exploracion_general", "general", [
        ("hallazgos", "Hallazgos", "multi", [
            ("palidez", "palidez de piel y mucosas"), ("ictericia_escleras", "ictericia de escleras"), ("ictericia", "ictericia generalizada"),
            ("mucosas_secas", "mucosas orales secas"), ("caquexia", "aspecto caquéctico"), ("edema", "edema de miembros inferiores"),
            ("estigmas", "estigmas de hepatopatía crónica (arañas vasculares, eritema palmar)"), ("ginecomastia", "ginecomastia"),
            ("asterixis", "asterixis"), ("desorientacion", "desorientación"), ("adenopatia", "adenopatía supraclavicular izquierda"),
            ("febril", "aspecto febril")], "Presenta {v}."),
    ]),
    "cardiopulmonar": ("Cardiopulmonar", "exploracion_general", "cardiopulmonar", [
        ("corazon", "Corazón", "multi", [("taquicardia", "taquicardia"), ("arritmia", "ruidos cardiacos arrítmicos"),
                                         ("soplo", "soplo cardiaco")], "Cardiaco: {v}."),
        ("pulmon", "Pulmones", "multi", [("murmullo", "disminución del murmullo vesicular"), ("estertores", "estertores"),
                                         ("sibilancias", "sibilancias"), ("matidez", "matidez a la percusión")], "Pulmonar: {v}."),
    ]),
    "abdomen": ("Abdomen", "exploracion_abdominal", "abdominal", [
        ("inspeccion", "Inspección", "multi", [("distendido", "distendido"), ("globoso", "globoso"), ("cicatrices", "con cicatrices quirúrgicas"),
                                               ("red_venosa", "con red venosa colateral"), ("hernia_umbilical", "con hernia umbilical"),
                                               ("hernia_ventral", "con hernia ventral"), ("ostomia", "con ostomía")], "Abdomen {v}."),
        ("dolor", "Doloroso a la palpación en", "multi", LOCS, "Doloroso a la palpación en {v}."),
        ("signos", "Signos", "multi", [("murphy", "signo de Murphy positivo"), ("mcburney", "punto de McBurney doloroso"),
                                       ("rebote", "rebote positivo (Blumberg)"), ("defensa", "defensa muscular"),
                                       ("rovsing", "signo de Rovsing positivo")], "Con {v}."),
        ("visceras", "Visceromegalias y masas", "multi", [("hepatomegalia", "hepatomegalia"), ("esplenomegalia", "esplenomegalia"),
                                                          ("masa", "masa palpable")], "Se palpa {v}."),
        ("higado_cm", "Borde hepático (cm bajo el reborde costal)", "number", None, "Borde hepático a {v} cm por debajo del reborde costal."),
        ("masa_detalle", "Masa: localización y características", "text", None, "Masa: {v}."),
        ("ascitis", "Ascitis", "multi", [("matidez_cambiante", "matidez cambiante"), ("onda", "onda ascítica"),
                                         ("tension", "ascitis a tensión")], "Datos de ascitis: {v}."),
        ("peristalsis", "Peristalsis", "select", [("aumentada", "Peristalsis aumentada."), ("disminuida", "Peristalsis disminuida."),
                                                  ("ausente", "Peristalsis ausente."), ("lucha", "Peristalsis de lucha.")], None),
    ]),
    "rectal": ("Tacto rectal", "exploracion_abdominal", "rectal", [
        ("hallazgos", "Hallazgos", "multi", [("hemorroides_ext", "hemorroides externas"), ("fisura", "fisura anal"),
                                             ("fistula", "orificio fistuloso perianal"), ("hipotonico", "esfínter hipotónico"),
                                             ("hipertonico", "esfínter hipertónico"), ("masa", "masa palpable en recto"),
                                             ("ampolla_heces", "ampolla rectal con heces"), ("ampolla_vacia", "ampolla rectal vacía")],
         "Tacto rectal: {v}."),
        ("guante", "Guante", "select", [("limpio", "Guante sin sangre ni melena."), ("sangre", "Guante con sangre roja."),
                                        ("melena", "Guante con melena."), ("heces", "Guante con heces de aspecto normal.")], None),
    ]),
}
ALL_NORMAL = ("general", "cardiopulmonar", "abdomen")   # «Todo normal» no incluye el tacto rectal (se marca solo si se realizó)

DEFAULT_NORMAL = {
    "general": "Paciente consciente, orientado, hidratado, con buena coloración de piel y mucosas, sin ictericia ni edema.",
    "cardiopulmonar": "Ruidos cardiacos rítmicos, sin soplos. Campos pulmonares con buena entrada de aire, sin ruidos agregados.",
    "abdomen": "Abdomen plano, blando, depresible, no doloroso a la palpación superficial ni profunda, sin masas ni visceromegalias, "
               "peristalsis presente, sin signos de irritación peritoneal.",
    "rectal": "Tacto rectal: esfínter de tono normal, ampolla rectal sin masas, guante sin sangre ni melena.",
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
                    if 0 < x <= 40:
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
