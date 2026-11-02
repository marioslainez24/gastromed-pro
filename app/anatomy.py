"""Esquema anatómico del informe de endoscopia (v0.19.0).

Dibujo propio y esquemático (no anatómicamente exacto) del tubo digestivo alto y del colon. El médico hace clic en el dibujo para
marcar dónde está una lesión o una biopsia; cada marca guarda el segmento, el tipo, una nota corta y el frasco. La misma geometría
se usa para la pantalla (SVG) y para el PDF (ReportLab), así lo marcado se ve igual en los dos.
"""
from xml.sax.saxutils import escape

# Región: (clave, segmento del informe, tipo, geometría, grosor)
#   tipo "line": tubo dibujado como línea gruesa por los puntos dados
#   tipo "path": figura rellena con comandos M/L/C/Z
#   tipo "ellipse": (cx, cy, rx, ry)
UPPER = {
    "viewbox": (300, 345),
    "regions": [
        ("eso_p", "Esófago proximal", "line", [(118, 8), (119, 50)], 22),
        ("eso_m", "Esófago medio", "line", [(119, 50), (121, 92)], 22),
        ("eso_d", "Esófago distal", "line", [(121, 92), (125, 128)], 22),
        ("fondo", "Fondo gástrico", "path", [("M", 133, 156), ("C", 128, 116, 168, 98, 200, 106), ("C", 226, 113, 233, 140, 226, 162),
                                             ("L", 150, 162), ("Z",)], 0),
        ("cuerpo", "Cuerpo gástrico", "path", [("M", 150, 162), ("L", 226, 162), ("C", 238, 196, 238, 228, 226, 252), ("L", 166, 252),
                                               ("C", 158, 222, 152, 192, 150, 162), ("Z",)], 0),
        ("antro", "Antro", "path", [("M", 166, 252), ("L", 226, 252), ("C", 214, 288, 168, 302, 118, 292), ("L", 110, 268),
                                    ("C", 134, 272, 156, 264, 166, 252), ("Z",)], 0),
        ("angulo", "Ángulo gástrico", "ellipse", (164, 254, 11, 8), 0),
        ("cardias", "Cardias", "ellipse", (139, 156, 13, 10), 0),
        ("ueg", "Unión esofagogástrica", "line", [(125, 128), (130, 146)], 24),
        ("piloro", "Píloro", "ellipse", (106, 281, 8, 12), 0),
        ("bulbo", "Bulbo duodenal", "ellipse", (86, 277, 15, 13), 0),
        ("d2", "Segunda porción duodenal", "line", [(74, 288), (66, 318), (80, 334), (112, 336)], 18),
    ],
    "labels": [("Esófago", 150, 50), ("Fondo", 196, 128), ("Cuerpo", 176, 212), ("Antro", 160, 282), ("Bulbo", 70, 258), ("Duodeno", 18, 312)],
}

COLON = {
    "viewbox": (300, 345),
    "regions": [
        ("ileon", "Íleon terminal", "line", [(14, 238), (58, 246)], 13),
        ("ciego", "Ciego", "line", [(76, 262), (76, 292)], 32),
        ("asc", "Colon ascendente", "line", [(76, 262), (76, 112)], 28),
        ("hep", "Ángulo hepático", "line", [(76, 112), (78, 82), (104, 66)], 28),
        ("trans", "Colon transverso", "line", [(104, 66), (150, 96), (196, 66)], 28),
        ("esp", "Ángulo esplénico", "line", [(196, 66), (226, 58), (234, 90)], 28),
        ("desc", "Colon descendente", "line", [(234, 90), (234, 228)], 26),
        ("sigma", "Sigmoides", "line", [(234, 228), (230, 262), (192, 250), (164, 268), (152, 290)], 24),
        ("recto", "Recto", "line", [(152, 290), (152, 322)], 26),
        ("anal", "Canal anal", "line", [(152, 322), (152, 340)], 12),
        ("valvula", "Válvula ileocecal", "ellipse", (62, 247, 7, 7), 0),
    ],
    "labels": [("Ascendente", 96, 190), ("Transverso", 124, 120), ("Descendente", 158, 160), ("Sigmoides", 170, 236), ("Ciego", 96, 300),
               ("Íleon", 6, 228), ("Recto", 168, 318)],
}

# En la rectosigmoidoscopia el tramo descendente se llama «Colon descendente distal»
ALIASES = {"rectosigmoidoscopia": {"Colon descendente": "Colon descendente distal"}}
DIAGRAMS = {"eda": UPPER, "colonoscopia": COLON, "rectosigmoidoscopia": COLON}
KINDS_OF_MARK = {"lesion": ("Lesión", "#c62828"), "biopsia": ("Biopsia", "#1565c0"), "reseccion": ("Resección / pólipo", "#2e7d32"),
                 "otro": ("Otro", "#6d4c41")}
MAX_MARKS = 30


def diagram_for(kind):
    return DIAGRAMS.get(kind)


def segment_name(kind, seg):
    return ALIASES.get(kind, {}).get(seg, seg)


def valid_segments(kind):
    d = DIAGRAMS.get(kind)
    return {segment_name(kind, r[1]) for r in d["regions"]} if d else set()


def _path_d(cmds):
    out = []
    for c in cmds:
        out.append(c[0] + (" " + " ".join(f"{v:g}" for v in c[1:]) if len(c) > 1 else ""))
    return " ".join(out)


def svg(kind, marks=(), interactive=False):
    """SVG del esquema con las marcas numeradas. Interactivo: cada región lleva data-seg para el clic."""
    d = DIAGRAMS.get(kind)
    if not d:
        return ""
    w, h = d["viewbox"]
    parts = [f'<svg class="anat" viewBox="0 0 {w} {h}" role="img" aria-label="Esquema anatómico'
             + (f' con {len(marks)} marca(s)' if marks else "") + '"' + (' data-anat' if interactive else "") + ">"]
    for key, seg, typ, geo, width in d["regions"]:
        name = escape(segment_name(kind, seg))
        attr = f' class="anat-reg anat-{typ}" data-seg="{name}"'
        if typ == "line":
            pts = " ".join(f"{x:g},{y:g}" for x, y in geo)
            parts.append(f'<polyline{attr} points="{pts}" stroke-width="{width}"><title>{name}</title></polyline>')
        elif typ == "path":
            parts.append(f'<path{attr} d="{_path_d(geo)}"><title>{name}</title></path>')
        else:
            cx, cy, rx, ry = geo
            parts.append(f'<ellipse{attr} cx="{cx:g}" cy="{cy:g}" rx="{rx:g}" ry="{ry:g}"><title>{name}</title></ellipse>')
    for t, x, y in d["labels"]:
        parts.append(f'<text class="anat-label" x="{x}" y="{y}">{escape(t)}</text>')
    parts.append('<g class="anat-marks">')
    for i, m in enumerate(marks, 1):
        color = KINDS_OF_MARK.get(m.get("kind"), KINDS_OF_MARK["otro"])[1]
        parts.append(f'<g class="anat-mark"><circle cx="{m["x"]:g}" cy="{m["y"]:g}" r="8" fill="{color}"/>'
                     f'<text x="{m["x"]:g}" y="{m["y"] + 3.5:g}" text-anchor="middle">{i}</text></g>')
    parts.append("</g></svg>")
    return "".join(parts)


def drawing(kind, marks, max_width):
    """Dibujo de ReportLab (para el PDF) con la misma geometría y las marcas numeradas."""
    from reportlab.graphics.shapes import Circle, Drawing, Ellipse, Group, Path, PolyLine, String
    from reportlab.lib import colors
    d = DIAGRAMS.get(kind)
    if not d:
        return None
    w, h = d["viewbox"]
    scale = min(1.0, max_width / w) * 0.62
    dr = Drawing(w * scale, h * scale)
    g = Group()
    fill, edge, tube = colors.HexColor("#f3d9d4"), colors.HexColor("#b07c76"), colors.HexColor("#e9bfb8")

    def Y(y):
        return h - y

    for key, seg, typ, geo, width in d["regions"]:
        if typ == "line":
            pts = []
            for x, y in geo:
                pts += [x, Y(y)]
            g.add(PolyLine(pts, strokeColor=edge, strokeWidth=width + 2, strokeLineCap=1, strokeLineJoin=1))
            g.add(PolyLine(pts, strokeColor=tube, strokeWidth=width, strokeLineCap=1, strokeLineJoin=1))
        elif typ == "path":
            p = Path(fillColor=fill, strokeColor=edge, strokeWidth=1.2)
            for c in geo:
                if c[0] == "M":
                    p.moveTo(c[1], Y(c[2]))
                elif c[0] == "L":
                    p.lineTo(c[1], Y(c[2]))
                elif c[0] == "C":
                    p.curveTo(c[1], Y(c[2]), c[3], Y(c[4]), c[5], Y(c[6]))
                elif c[0] == "Z":
                    p.closePath()
            g.add(p)
        else:
            cx, cy, rx, ry = geo
            g.add(Ellipse(cx, Y(cy), rx, ry, fillColor=fill, strokeColor=edge, strokeWidth=1.2))
    for t, x, y in d["labels"]:
        g.add(String(x, Y(y), t, fontName="Helvetica", fontSize=11, fillColor=colors.HexColor("#5b6b73")))
    for i, m in enumerate(marks, 1):
        color = colors.HexColor(KINDS_OF_MARK.get(m.get("kind"), KINDS_OF_MARK["otro"])[1])
        g.add(Circle(m["x"], Y(m["y"]), 10, fillColor=color, strokeColor=colors.white, strokeWidth=1))
        g.add(String(m["x"], Y(m["y"]) - 4, str(i), fontName="Helvetica-Bold", fontSize=11, fillColor=colors.white, textAnchor="middle"))
    g.scale(scale, scale)
    dr.add(g)
    return dr


def parse_marks(kind, form):
    """Lee las marcas del formulario (mark-N-x, -y, -seg, -kind, -label, -jar). Devuelve (marcas, errores)."""
    import re
    d = DIAGRAMS.get(kind)
    if not d:
        return [], []
    w, h = d["viewbox"]
    segs = valid_segments(kind)
    out, errors = [], []
    idx = sorted({int(m.group(1)) for k in form.keys() if (m := re.fullmatch(r"mark-(\d{1,3})-x", k))})
    for i in idx:
        try:
            x, y = float(form.get(f"mark-{i}-x")), float(form.get(f"mark-{i}-y"))
        except (TypeError, ValueError):
            continue
        if not (0 <= x <= w and 0 <= y <= h):
            continue
        seg = form.get(f"mark-{i}-seg")
        if seg not in segs:
            continue
        kd = form.get(f"mark-{i}-kind") if form.get(f"mark-{i}-kind") in KINDS_OF_MARK else "lesion"
        jar = (form.get(f"mark-{i}-jar") or "").strip()
        jar = int(jar) if jar.isdigit() and 1 <= int(jar) <= 99 else None
        out.append({"x": round(x, 1), "y": round(y, 1), "seg": seg, "kind": kd,
                    "label": (form.get(f"mark-{i}-label") or "").strip()[:80], "jar": jar})
        if len(out) >= MAX_MARKS:
            errors.append(f"Máximo {MAX_MARKS} marcas en el esquema.")
            break
    return out, errors
