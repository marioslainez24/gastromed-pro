"""Generación de PDF (ReportLab). Tamaños carta (216×279 mm) y A4 (210×297 mm)."""
import io
import json
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .util import age, fmt_birth, label, parse_utc
from zoneinfo import ZoneInfo

INK = colors.HexColor("#1d2b36")
MUTED = colors.HexColor("#5b6b77")
ACCENT = colors.HexColor("#0f6e66")

_base = dict(fontName="Helvetica", fontSize=12, leading=16, textColor=INK)   # v0.22: letra 12 a pedido del Dr. Lainez (antes 10)
ST = {
    "doctor": ParagraphStyle("doctor", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 17, "leading": 21}),
    "sub": ParagraphStyle("sub", **{**_base, "fontSize": 11, "leading": 14, "textColor": MUTED}),
    "title": ParagraphStyle("title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 13.5, "leading": 17.5, "textColor": ACCENT}),
    "body": ParagraphStyle("body", **_base),
    "med": ParagraphStyle("med", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 13, "leading": 16.5}),
    "subr": ParagraphStyle("subr", **{**_base, "fontSize": 11, "leading": 14, "textColor": MUTED, "alignment": 2}),
    "item9": ParagraphStyle("item9", **{**_base, "fontSize": 11, "leading": 14}),
    "small": ParagraphStyle("small", **{**_base, "fontSize": 10, "leading": 12.5, "textColor": MUTED}),
}


def _img_flowable(data: bytes, max_w, max_h):
    from PIL import Image as PILImage
    from reportlab.platypus import Image as RLImage
    w, h = PILImage.open(io.BytesIO(data)).size
    k = min(max_w / w, max_h / h)
    return RLImage(io.BytesIO(data), width=w * k, height=h * k)


def _with_logo(story, assets, width):
    """Coloca el logo de la clínica a la izquierda del encabezado (si fue cargado en Ajustes)."""
    if not assets or not assets.get("logo"):
        return story
    logo = _img_flowable(assets["logo"], 30 * mm, 22 * mm)
    t = Table([[logo, story]], colWidths=[34 * mm, width - 34 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [t]


def _sig_img(assets):
    """Imagen de firma escaneada (no es una firma electrónica verificable)."""
    if not assets or not assets.get("firma"):
        return ""
    return _img_flowable(assets["firma"], 60 * mm, 15 * mm)


# v0.24.1: los documentos NO llevan pie con «Generado con GastroMed Pro» ni el titular de la licencia (pedido del Dr. Lainez).


def _e(s) -> str:
    return escape(str(s or ""))


def prescription_pdf(r, items, p, s, size: str, allergies, assets=None) -> bytes:
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=22 * mm, title="Receta médica", author=s["doctor_display_name"],
                            subject="Receta", creator="GastroMed Pro")
    tz = ZoneInfo(s["timezone"])
    issued = parse_utc(r["issued_at"]).astimezone(tz)
    width = pagesize[0] - 36 * mm

    story = [Paragraph(_e(s["doctor_display_name"]), ST["doctor"])]
    sub = [x for x in [s["specialty"], f"Colegiación: {s['license_number']}" if s["license_number"] else None] if x]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), ST["sub"]))
    contact = [x for x in [s["address"], f"Tel.: {s['phones']}" if s["phones"] else None, s["contact_email"]] if x]
    if contact:
        story.append(Paragraph(_e(" · ".join(contact)), ST["sub"]))
    story = _with_logo(story, assets, width)
    story.append(Spacer(1, 4 * mm))

    head = Table([[Paragraph("RECETA MÉDICA", ST["title"]),
                   Paragraph(f"Fecha: {issued:%d/%m/%Y}", ST["subr"])]],
                 colWidths=[width * 0.6, width * 0.4])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(head)

    if p["allergy_status"] == "con_alergias" and allergies:
        alg = "; ".join(f"{a['substance']} ({label('severity', a['severity']).lower()})" for a in allergies)
    else:
        alg = label("allergy_status", p["allergy_status"])
    doc_line = "" if p["document_type"] == "sin_documento" else f" · {label('document_type', p['document_type'])}: {_e(p['document_number'])}"
    pt = Table([[Paragraph(f"<b>Paciente:</b> {_e(p['first_names'])} {_e(p['last_names'])}", ST["body"]),
                 Paragraph(f"<b>Edad:</b> {_e(age(p['birth_date'], issued.date()))}", ST["body"])],
                [Paragraph(f"<b>Expediente:</b> {_e(p['mrn'])}{doc_line}", ST["sub"]),
                 Paragraph(f"<b>Nac.:</b> {_e(fmt_birth(p['birth_date']))}", ST["sub"])],
                [Paragraph(f"<b>Alergias:</b> {_e(alg)}", ST["body"]), ""]],
               colWidths=[width * 0.7, width * 0.3])
    pt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4f3")), ("SPAN", (0, 2), (1, 2)),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [Spacer(1, 3 * mm), pt, Spacer(1, 5 * mm)]

    for i, it in enumerate(items, 1):
        name = _e(it["active_ingredient"]) + (f" — {_e(it['presentation'])}" if it["presentation"] else "")
        detail = (f"<b>Dosis:</b> {_e(it['dose'])} {_e(it['dose_unit'])} &nbsp;·&nbsp; <b>Vía:</b> {_e(it['route'])} &nbsp;·&nbsp; "
                  f"<b>Frecuencia:</b> {_e(it['frequency'])} &nbsp;·&nbsp; <b>Duración:</b> {_e(it['duration'])} &nbsp;·&nbsp; "
                  f"<b>Cantidad:</b> {_e(it['quantity'])}")
        block = [Paragraph(f"{i}. {name}", ST["med"]), Paragraph(detail, ST["body"])]
        if it["instructions"]:
            block.append(Paragraph(f"<i>Indicaciones:</i> {_e(it['instructions'])}".replace("\n", "<br/>"), ST["body"]))
        block.append(Spacer(1, 3.5 * mm))
        story.append(KeepTogether(block))

    if r["general_instructions"]:
        story += [Spacer(1, 2 * mm), Paragraph("Indicaciones generales", ST["title"]),
                  Paragraph(_e(r["general_instructions"]).replace("\n", "<br/>"), ST["body"])]

    sig = Table([[_sig_img(assets)], [Paragraph(f"<b>{_e(s['doctor_display_name'])}</b><br/>Firma y sello", ST["sub"])]],
                colWidths=[70 * mm], rowHeights=[18 * mm, None])
    sig.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, INK), ("ALIGN", (0, 1), (0, 1), "CENTER"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    outer = Table([[sig]], colWidths=[width])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    story += [Spacer(1, 10 * mm), KeepTogether([outer])]

    voided = r["status"] == "anulada"

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(pagesize[0] - 18 * mm, 12 * mm, f"Página {d.page}")
        if voided:
            canvas.setFont("Helvetica-Bold", 64)
            canvas.setFillColor(colors.Color(0.75, 0.1, 0.1, alpha=0.25))
            canvas.translate(pagesize[0] / 2, pagesize[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "ANULADA")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _g(it):
    try:
        return it["grp"]
    except (KeyError, IndexError):
        return None


def order_pdf(o, items, p, s, size: str, type_label: str, priority_label: str, assets=None) -> bytes:
    """Solicitud de laboratorio, imagen o endoscopia."""
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=22 * mm, title=f"Solicitud de {type_label}", author=s["doctor_display_name"],
                            creator="GastroMed Pro")
    tz = ZoneInfo(s["timezone"])
    issued = parse_utc(o["created_at"]).astimezone(tz)
    width = pagesize[0] - 36 * mm
    story = [Paragraph(_e(s["doctor_display_name"]), ST["doctor"])]
    sub = [x for x in [s["specialty"], f"Colegiación: {s['license_number']}" if s["license_number"] else None] if x]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), ST["sub"]))
    contact = [x for x in [s["address"], f"Tel.: {s['phones']}" if s["phones"] else None] if x]
    if contact:
        story.append(Paragraph(_e(" · ".join(contact)), ST["sub"]))
    story = _with_logo(story, assets, width)
    story.append(Spacer(1, 4 * mm))
    head = Table([[Paragraph(f"SOLICITUD DE {_e(type_label.upper())}", ST["title"]),
                   Paragraph(f"Fecha: {issued:%d/%m/%Y}<br/>Prioridad: {_e(priority_label)}", ST["subr"])]],
                 colWidths=[width * 0.6, width * 0.4])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(head)
    doc_line = "" if p["document_type"] == "sin_documento" else f" · {_e(p['document_number'])}"
    pt = Table([[Paragraph(f"<b>Paciente:</b> {_e(p['first_names'])} {_e(p['last_names'])}", ST["body"]),
                 Paragraph(f"<b>Edad:</b> {_e(age(p['birth_date'], issued.date()))}", ST["body"])],
                [Paragraph(f"<b>Expediente:</b> {_e(p['mrn'])}{doc_line}", ST["sub"]),
                 Paragraph(f"<b>Sexo:</b> {_e(label('sex', p['sex']))}", ST["sub"])]], colWidths=[width * 0.7, width * 0.3])
    pt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4f3")), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [Spacer(1, 3 * mm), pt, Spacer(1, 5 * mm), Paragraph("Estudios solicitados", ST["title"])]
    if any(_g(it) for it in items):
        # Agrupado por sección, como la hoja de solicitud
        groups = {}
        for it in items:
            groups.setdefault(_g(it) or "Otras pruebas", []).append(it["description"])
        for gname, descs in groups.items():
            story.append(Paragraph(f"<b>{_e(gname)}</b>", ST["body"]))
            if gname == "Perfiles":
                for d_ in descs:
                    name, _, comps = d_.partition(": ")
                    story.append(Paragraph(f"• <b>{_e(name)}</b>" + (f" <font size=8>({_e(comps)})</font>" if comps else ""), ST["body"]))
            else:
                cells = [Paragraph("• " + _e(d_), ST["item9"]) for d_ in descs]
                rows = [cells[i:i + 2] + [""] * (2 - len(cells[i:i + 2])) for i in range(0, len(cells), 2)]
                t = Table(rows, colWidths=[width / 2] * 2)
                t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 1),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(t)
            story.append(Spacer(1, 2 * mm))
    else:
        for i, it in enumerate(items, 1):
            story.append(Paragraph(f"{i}. {_e(it['description'])}", ST["body"]))
    if o["indication"]:
        story += [Spacer(1, 4 * mm), Paragraph("Indicación clínica / datos relevantes", ST["title"]),
                  Paragraph(_e(o["indication"]).replace("\n", "<br/>"), ST["body"])]
    sig = Table([[_sig_img(assets)], [Paragraph(f"<b>{_e(s['doctor_display_name'])}</b><br/>Firma y sello", ST["sub"])]],
                colWidths=[70 * mm], rowHeights=[18 * mm, None])
    sig.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, INK), ("ALIGN", (0, 1), (0, 1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    outer = Table([[sig]], colWidths=[width])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    story += [Spacer(1, 10 * mm), KeepTogether([outer])]
    voided = o["status"] == "anulada"

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(pagesize[0] - 18 * mm, 12 * mm, f"Página {d.page}")
        if voided:
            canvas.setFont("Helvetica-Bold", 64)
            canvas.setFillColor(colors.Color(0.75, 0.1, 0.1, alpha=0.25))
            canvas.translate(pagesize[0] / 2, pagesize[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "ANULADA")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _annotated_jpeg(raw: bytes, annotations: list, max_px=900) -> bytes:
    """Copia de la imagen con las anotaciones dibujadas (el original no se modifica)."""
    from PIL import Image as PILImage, ImageDraw
    im = PILImage.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((max_px, max_px))
    if annotations:
        dr = ImageDraw.Draw(im)
        r = max(9, im.width // 45)
        for n, a in enumerate(annotations, 1):
            x, y = a["x"] * im.width, a["y"] * im.height
            dr.ellipse([x - r, y - r, x + r, y + r], fill=(255, 210, 0), outline=(0, 0, 0), width=2)
            dr.text((x - r / 3, y - r / 1.6), str(n), fill=(0, 0, 0))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


# ---- Estilos del informe de endoscopia (v0.22.0, a pedido del Dr. Lainez) ----------------------------------------------------
REPORT_STYLES = {"clasico": "Clásico (verde, con recuadro de color)", "formal": "Formal (blanco y negro, letra tipo libro)",
                 "moderno": "Moderno (franja de color arriba)"}


def _report_styles(style):
    if style == "formal":
        b = dict(fontName="Times-Roman", fontSize=12.5, leading=16, textColor=colors.black)
        return {"doctor": ParagraphStyle("f-doc", **{**b, "fontName": "Times-Bold", "fontSize": 18, "leading": 22, "alignment": 1}),
                "sub": ParagraphStyle("f-sub", **{**b, "fontSize": 11, "leading": 14, "alignment": 1}),
                "subr": ParagraphStyle("f-subr", **{**b, "fontSize": 11, "leading": 14, "alignment": 2}),
                "title": ParagraphStyle("f-title", **{**b, "fontName": "Times-Bold", "fontSize": 13, "leading": 16}),
                "body": ParagraphStyle("f-body", **b), "small": ParagraphStyle("f-small", **{**b, "fontSize": 10.5, "leading": 13}),
                "head": ParagraphStyle("f-head", **{**b, "fontName": "Times-Bold", "fontSize": 14, "leading": 18, "alignment": 1})}
    if style == "moderno":
        white = colors.white
        return {**ST, "doctor": ParagraphStyle("m-doc", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 18, "leading": 22, "textColor": white}),
                "sub": ParagraphStyle("m-sub", **{**_base, "fontSize": 10.5, "leading": 13.5, "textColor": colors.HexColor("#d7ece9")}),
                "sigsub": ST["sub"],
                "title": ParagraphStyle("m-title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 13, "leading": 16, "textColor": ACCENT}),
                "head": ParagraphStyle("m-head", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 15, "leading": 19, "textColor": ACCENT}),
                "subr": ParagraphStyle("m-subr", **{**_base, "fontSize": 11, "leading": 14, "textColor": MUTED, "alignment": 2})}
    return ST


def _report_header(style, X, name, sub, title, date_txt, assets, width):
    """Encabezado del informe según el estilo elegido en Ajustes."""
    if style == "formal":
        out = []
        if assets and assets.get("logo"):
            logo = _img_flowable(assets["logo"], 30 * mm, 20 * mm)
            logo.hAlign = "CENTER"
            out.append(logo)
        out.append(Paragraph(_e(name), X["doctor"]))
        if sub:
            out.append(Paragraph(_e(" · ".join(sub)), X["sub"]))
        t = Table([[Paragraph(_e(title), X["head"])]], colWidths=[width])
        t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.5, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        return out + [Spacer(1, 2 * mm), t, Spacer(1, 1 * mm), Paragraph(date_txt, X["subr"])]
    if style == "moderno":
        txt = [Paragraph(_e(name), X["doctor"])] + ([Paragraph(_e(" · ".join(sub)), X["sub"])] if sub else [])
        if assets and assets.get("logo"):
            logo = _img_flowable(assets["logo"], 26 * mm, 18 * mm)
            band = Table([[txt, logo]], colWidths=[width - 34 * mm, 34 * mm])
        else:
            band = Table([[txt]], colWidths=[width])
        band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                  ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                                  ("ALIGN", (-1, 0), (-1, 0), "RIGHT")]))
        head = Table([[Paragraph(_e(title), X["head"]), Paragraph(date_txt, X["subr"])]], colWidths=[width * 0.65, width * 0.35])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 6)]))
        return [band, Spacer(1, 1 * mm), head]
    story = [Paragraph(_e(name), X["doctor"])]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), X["sub"]))
    story = _with_logo(story, assets, width)
    head = Table([[Paragraph(_e(title), X["title"]), Paragraph(date_txt, X["subr"])]], colWidths=[width * 0.6, width * 0.4])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return story + [Spacer(1, 2 * mm), head]


def _patient_box_style(style):
    pad = [("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
           ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if style == "formal":
        return pad + [("BOX", (0, 0), (-1, -1), 0.8, colors.black), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#8a8a8a")),
                      ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if style == "moderno":
        return pad + [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f7f6")), ("LINEBEFORE", (0, 0), (0, -1), 4, ACCENT),
                      ("LEFTPADDING", (0, 0), (0, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    return pad + [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4f3"))]


def _report_heading(style, X, text, width):
    """Título de cada sección del informe según el estilo."""
    if style == "formal":
        t = Table([[Paragraph(_e(text.upper()), X["title"])]], colWidths=[width])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        return t
    if style == "moderno":
        t = Table([[Paragraph(_e(text), X["title"])]], colWidths=[width])
        t.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, 0), 3, ACCENT), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        return t
    return Paragraph(_e(text), X["title"])


def procedure_pdf(pr, d, p, s, size, images, scope, addenda, D, assets=None, endo=None, allergies=(), endo2=None, style="clasico") -> bytes:
    from reportlab.platypus import Image as RLImage
    style = style if style in REPORT_STYLES else "clasico"
    X = _report_styles(style)
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    title = D.KINDS[pr["kind"]]
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=20 * mm,
                            title=f"Informe de {title}", author=(endo or {}).get("name") or s["doctor_display_name"], creator="GastroMed Pro")
    width = pagesize[0] - 32 * mm
    # Encabezado y firma con el ENDOSCOPISTA elegido en el informe (v0.22.0); si es otro médico, sin la firma escaneada del dueño
    endo = endo or {"name": s["doctor_display_name"], "owner": True, "detail": None}
    signer = endo["name"] or s["doctor_display_name"]
    all_assets = assets or {}
    if not endo["owner"]:
        assets = {k: v for k, v in all_assets.items() if k != "firma"}
    sub = [x for x in ([s["specialty"], f"Colegiación: {s['license_number']}" if s["license_number"] else None] if endo["owner"] else [endo.get("detail")])
           + [s["address"], f"Tel.: {s['phones']}" if s["phones"] else None] if x]
    date_txt = f"Fecha: {fmt_birth(pr['performed_on'])}" + ("" if pr["status"] == "finalizado" else "<br/><b>BORRADOR</b>")   # sin folio
    story = _report_header(style, X, signer, sub, f"INFORME DE {title.upper()}", date_txt, assets, width)
    # Datos del paciente (v0.22.0, pedido del Dr. Lainez): DNI, fecha de nacimiento, edad el día del estudio y más
    from datetime import date as _date
    try:
        on = _date.fromisoformat(pr["performed_on"])
    except (TypeError, ValueError):
        on = None
    doc_cell = "<b>Identidad:</b> sin documento" if p["document_type"] in (None, "", "sin_documento") else \
        f"<b>{_e(label('document_type', p['document_type']))}:</b> {_e(p['document_number'] or '—')}"
    if p["allergy_status"] == "con_alergias" and allergies:
        alg = "; ".join(f"{a['substance']}" for a in allergies)
    else:
        alg = label("allergy_status", p["allergy_status"]) if p["allergy_status"] else ""
    cells = [(f"<b>Paciente:</b> {_e(p['first_names'])} {_e(p['last_names'])}", f"<b>Expediente:</b> {_e(p['mrn'])}"),
             (doc_cell, f"<b>Fecha de nacimiento:</b> {_e(fmt_birth(p['birth_date'])) if p['birth_date'] else 'no registrada'}"),
             (f"<b>Edad:</b> {_e(age(p['birth_date'], on))}", f"<b>Sexo:</b> {_e(label('sex', p['sex']))}")]
    care = D.care_text(d)
    extra = [x for x in [f"<b>Atención:</b> {_e(care)}" if care else None,
                         f"<b>Lugar:</b> {_e(d['facility'])}" if d.get("facility") else None,
                         f"<b>Exp. del hospital:</b> {_e(d['facility_record'])}" if d.get("facility_record") else None,
                         f"<b>Teléfono:</b> {_e(p['phone'])}" if p["phone"] else None,
                         f"<b>Procedencia:</b> {_e(p['origin'])}" if p["origin"] else None,
                         f"<b>Médico que refiere:</b> {_e(p['referring_physician'])}" if p["referring_physician"] else None,
                         f"<b>Aseguradora:</b> {_e(p['payer'])}" if p["payer"] else None] if x]
    while extra:
        cells.append((extra.pop(0), extra.pop(0) if extra else ""))
    rows = [[Paragraph(a, X["body"]), Paragraph(b, X["body"])] for a, b in cells]
    if alg:
        rows.append([Paragraph(f"<b>Alergias:</b> {_e(alg)}", X["body"]), ""])
    pt = Table(rows, colWidths=[width * 0.55, width * 0.45])
    pt.setStyle(TableStyle(_patient_box_style(style) + ([("SPAN", (0, len(rows) - 1), (1, len(rows) - 1))] if alg else [])))
    story += [Spacer(1, 2 * mm), pt, Spacer(1, 3 * mm)]

    def H(t):
        return _report_heading(style, X, t, width)

    def sec(t, body):
        if body:
            # el título nunca queda solo al final de una página
            story.append(KeepTogether([H(t), Paragraph(_e(body).replace("\n", "<br/>"), X["body"])]))
            story.append(Spacer(1, 2 * mm))

    sec("Indicación", (D.INDICATION_CATEGORIES.get(pr["indication_category"] or "", "") + ". " if pr["indication_category"] else "") + (d.get("indication") or ""))
    pre = []
    pre.append("Consentimiento informado: " + ("obtenido" if d.get("consent_obtained") else "NO registrado") +
               (f" ({d['consent_version']})" if d.get("consent_version") else ""))
    if d.get("asa"):
        pre.append(f"Clasificación ASA: {d['asa']}")
    if d.get("comorbidities"):
        pre.append(f"Comorbilidades: {d['comorbidities']}")
    if d.get("anticoagulation"):
        pre.append(f"Anticoagulación/antiagregación: {d['anticoagulation']}")
    if d.get("prep_product"):
        pre.append(f"Preparación: {d['prep_product']}" + (f" ({d['prep_regimen']})" if d.get("prep_regimen") else ""))
    sed = D.SEDATION.get(d.get("sedation_type") or "", "No registrada")
    pre.append(f"Sedación: {sed}" + (f" · {d['sedation_agents']}" if d.get("sedation_agents") else "") +
               (f" · administrada por {d['sedation_by']}" if d.get("sedation_by") else ""))
    if d.get("monitoring"):
        pre.append(f"Monitorización: {d['monitoring']}")
    eq = [x for x in [f"Endoscopista{' 1' if d.get('endoscopist_2') else ''}: {d['endoscopist']}" if d.get("endoscopist") else None,
                      f"Endoscopista 2: {d['endoscopist_2']}" if d.get("endoscopist_2") else None,
                      f"Equipo: {scope['name']}" + (f" (serie {scope['serial']})" if scope and scope['serial'] else "") if scope else None,
                      f"Asistentes: {d['assistants']}" if d.get("assistants") else None,
                      f"Horario: {d.get('start_time') or '?'}–{d.get('end_time') or '?'}" if d.get("start_time") else None] if x]
    # Endoscopistas y asistentes en NEGRITA (pedido del Dr. Lainez, 3-nov-2026); el resto del bloque igual
    staff_prefixes = ("Endoscopista", "Asistentes:")
    lines = [f"<b>{_e(x)}</b>" if x.startswith(staff_prefixes) else _e(x) for x in pre + eq]
    story.append(H("Evaluación previa, preparación y sedación"))
    story.append(Paragraph("<br/>".join(l.replace("\n", "<br/>") for l in lines), X["body"]))
    story.append(Spacer(1, 2 * mm))
    ext = dict(D.EXTENT[pr["kind"]]).get(pr["extent"] or "", "")
    tech = [f"Extensión: {ext}" if ext else None,
            ("Estudio completo" if pr["complete"] == 1 else ("Estudio incompleto" + (f": {d['incomplete_reason']}" if d.get("incomplete_reason") else "")))
            if pr["complete"] is not None else None,
            f"Tiempo de retirada: {pr['withdrawal_minutes']:g} min" if pr["withdrawal_minutes"] is not None else None]
    if pr["bbps_right"] is not None:
        tot = (pr["bbps_right"] or 0) + (pr["bbps_transverse"] or 0) + (pr["bbps_left"] or 0)
        tech.append(f"Preparación (escala de Boston): derecho {pr['bbps_right']}, transverso {pr['bbps_transverse']}, izquierdo {pr['bbps_left']} · total {tot}/9")
    sec("Técnica", "\n".join(x for x in tech if x))
    nar = d.get("narrative") or {}
    if any(nar.values()) or d.get("zline"):
        story.append(H("Descripción de hallazgos"))
        for key, lab in D.NARRATIVE[pr["kind"]]:
            txt = nar.get(key) or ""
            if key == "ueg" and d.get("zline"):
                txt = (D.zline_text(d) + " " + txt).strip()
            if txt:
                story.append(Paragraph(f"<b>{_e(lab)}:</b> " + _e(txt).replace("\n", "<br/>"), X["body"]))
                story.append(Spacer(1, 1.2 * mm))
        story.append(Spacer(1, 1 * mm))
    if d.get("findings"):
        story.append(H("Hallazgos detallados" if any(nar.values()) else "Hallazgos"))
        rows = [[Paragraph("<b>Segmento</b>", X["small"]), Paragraph("<b>Hallazgo</b>", X["small"]), Paragraph("<b>Clasificación / tamaño</b>", X["small"]),
                 Paragraph("<b>Frasco</b>", X["small"])]]
        for f in d["findings"]:
            cl = []
            if f.get("classification"):
                grp, short, desc = D.CLASS_LOOKUP[f["classification"]]
                cl.append(f"{D.CLASSIFICATIONS[grp][0]} {short}")
            if f.get("prague_c") is not None or f.get("prague_m") is not None:
                cl.append(f"Praga C{f.get('prague_c') or 0:g} M{f.get('prague_m') or 0:g}")
            if f.get("size_mm"):
                cl.append(f"{f['size_mm']:g} mm")
            if f.get("removed"):
                cl.append(f"Resección: {f['removed']}")
            rows.append([Paragraph(_e(f["segment"]), X["small"]),
                         Paragraph(_e(" · ".join(x for x in [f.get("type"), f.get("desc")] if x)), X["body"]),
                         Paragraph(_e(" · ".join(cl)), X["small"]), Paragraph(str(f.get("jar") or ""), X["small"])])
        t = Table(rows, colWidths=[width * 0.2, width * 0.45, width * 0.27, width * 0.08], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d4d3")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f3"))]))
        story += [t, Spacer(1, 2 * mm)]
    if d.get("marks"):
        from . import anatomy as A
        dr = A.drawing(pr["kind"], d["marks"], width * 0.5)
        if dr:
            legend = [Paragraph(f"<b>{i}.</b> <font color='{A.KINDS_OF_MARK[m['kind']][1]}'>●</font> <b>{_e(m['seg'])}</b> · "
                                f"{_e(A.KINDS_OF_MARK[m['kind']][0])}" + (f": {_e(m['label'])}" if m.get("label") else "")
                                + (f" · frasco {m['jar']}" if m.get("jar") else ""), X["small"]) for i, m in enumerate(d["marks"], 1)]
            t = Table([[dr, legend]], colWidths=[dr.width + 4 * mm, width - dr.width - 4 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            story += [KeepTogether([H("Esquema anatómico"), t]), Spacer(1, 2 * mm)]
    if d.get("jars"):
        sec("Muestras enviadas a patología", "\n".join(f"Frasco {j['jar']}: {j['site']}" + (f" — {j['desc']}" if j.get("desc") else "")
                                                      + (f" ({j['pieces']} fragmentos)" if j.get("pieces") else "") for j in d["jars"]))
    sec("Intervenciones", d.get("interventions"))
    sec("Material utilizado", d.get("materials"))
    comps = ", ".join(D.COMPLICATIONS[c] for c in d.get("complications", []))
    sec("Complicaciones", (comps + (f". {d['complication_detail']}" if d.get("complication_detail") else "")) if comps else "Ninguna registrada.")
    if d.get("stents"):
        sec("Prótesis colocadas", "\n".join(f"{x['kind']}" + (f" — {x['desc']}" if x.get("desc") else "") +
                                             (f" · revisión/retiro previsto: {fmt_birth(x['review_due'])}" if x.get("review_due") else "") for x in d["stents"]))
    sec("Conclusión", d.get("conclusion"))
    sec("Recomendaciones", d.get("recommendations"))
    sec("Seguimiento", "\n".join(x for x in [d.get("follow_up") or "", f"Control / vigilancia indicada para: {fmt_birth(pr['surveillance_due'])}"
                                              if pr["surveillance_due"] else ""] if x))
    if images:
        story.append(H("Imágenes"))
        cells, row = [], []
        cw = (width - 4 * mm) / 3
        for im, raw in images:
            ann = json.loads(im["annotations"] or "[]")
            jpg = _annotated_jpeg(raw, ann)
            from PIL import Image as PILImage
            w, h = PILImage.open(io.BytesIO(jpg)).size
            img = RLImage(io.BytesIO(jpg), width=cw - 2 * mm, height=(cw - 2 * mm) * h / w)
            cap = " · ".join(x for x in [im["location"], im["caption"]] if x)
            if ann:
                cap += (" · " if cap else "") + "; ".join(f"{i}: {a['text']}" for i, a in enumerate(ann, 1) if a.get("text"))
            row.append([img, Paragraph(_e(cap), X["small"])])
            if len(row) == 3:
                cells.append(row)
                row = []
        if row:
            cells.append(row + [""] * (3 - len(row)))
        t = Table(cells, colWidths=[cw] * 3)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm)]))
        story += [t, Spacer(1, 2 * mm)]
    for a in addenda:
        sec(f"Adenda · {a['full_name']} · {a['created_at'][:10]}", a["text"])
    signed = pr["status"] == "finalizado"
    def sig_block(name, role, own_assets):
        img = _sig_img(own_assets)
        t = Table([[img], [Paragraph(f"<b>{_e(name)}</b><br/><b>{role}</b> · Nombre, firma y sello", X.get("sigsub", X["sub"]))]],
                  colWidths=[78 * mm], rowHeights=[16 * mm if img else 13 * mm, None])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, INK), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return t

    if endo2:
        # Dos endoscopistas: dos firmas lado a lado; la firma escaneada solo en la del médico de Ajustes
        a2 = all_assets if endo2["owner"] else {k: v for k, v in all_assets.items() if k != "firma"}
        outer = Table([[sig_block(signer, "Endoscopista 1", assets), sig_block(endo2["name"], "Endoscopista 2", a2)]],
                      colWidths=[width / 2, width / 2])
        outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    else:
        outer = Table([[sig_block(signer, "Endoscopista", assets)]], colWidths=[width])
        outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    # la firma nunca queda sola en una página: va junto con la última sección del informe
    tail = []
    if len(story) >= 2 and isinstance(story[-1], Spacer):
        tail = story[-2:]
        del story[-2:]
    story.append(KeepTogether(tail + [Spacer(1, 3 * mm), outer]))

    def on_page(canvas, dd):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(pagesize[0] - 16 * mm, 11 * mm, f"Página {dd.page}")
        if not signed:
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0.6, 0.6, 0.6, alpha=0.2))
            canvas.translate(pagesize[0] / 2, pagesize[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "BORRADOR")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def document_pdf(d, p, s, size, assets=None) -> bytes:
    """Documento clínico (incapacidad, constancia, referencia, libre). Texto tal como lo emitió el médico."""
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=16 * mm, bottomMargin=22 * mm,
                            title=d["title"], author=s["doctor_display_name"], creator="GastroMed Pro")
    width = pagesize[0] - 44 * mm
    story = [Paragraph(_e(s["doctor_display_name"]), ST["doctor"])]
    sub = [x for x in [s["specialty"], f"Colegiación: {s['license_number']}" if s["license_number"] else None] if x]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), ST["sub"]))
    contact = [x for x in [s["address"], f"Tel.: {s['phones']}" if s["phones"] else None] if x]
    if contact:
        story.append(Paragraph(_e(" · ".join(contact)), ST["sub"]))
    story = _with_logo(story, assets, width)
    tz = ZoneInfo(s["timezone"])
    issued = parse_utc(d["issued_at"]).astimezone(tz)
    head = Table([[Paragraph(_e(d["title"]), ST["title"]), Paragraph(f"Fecha: {issued:%d/%m/%Y}", ST["subr"])]],
                 colWidths=[width * 0.65, width * 0.35])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    body_style = ParagraphStyle("docbody", **{**_base, "fontSize": 12.5, "leading": 18.5, "alignment": 4})
    story += [Spacer(1, 6 * mm), head, Spacer(1, 10 * mm)]
    for para in d["body"].split("\n\n"):
        story.append(Paragraph(_e(para).replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 4 * mm))
    sig = Table([[_sig_img(assets)], [Paragraph(f"<b>{_e(s['doctor_display_name'])}</b>" +
                                                (f"<br/>Colegiación {_e(s['license_number'])}" if s["license_number"] else "") +
                                                "<br/>Firma y sello", ST["sub"])]],
                colWidths=[75 * mm], rowHeights=[20 * mm, None])
    sig.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, INK), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    outer = Table([[sig]], colWidths=[width])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER")]))
    story += [Spacer(1, 16 * mm), KeepTogether([outer])]
    voided = d["status"] == "anulado"

    def on_page(canvas, _d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        if voided:
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0.7, 0.1, 0.1, alpha=0.25))
            canvas.translate(pagesize[0] / 2, pagesize[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "ANULADO")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def jar_labels_pdf(pr, d, p, s, size, kind_label) -> bytes:
    """Etiquetas para frascos de biopsia: una por frasco, en hoja carta/A4 para recortar (2 columnas × 6 filas)."""
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    c = rl_canvas.Canvas(buf, pagesize=pagesize)
    c.setTitle("Etiquetas de frascos")
    c.setAuthor(s["doctor_display_name"])
    margin, cols, rows = 10 * mm, 2, 6
    w = (pagesize[0] - 2 * margin) / cols
    h = (pagesize[1] - 2 * margin) / rows
    jars = d.get("jars") or []
    for i, j in enumerate(jars):
        if i and i % (cols * rows) == 0:
            c.showPage()
        k = i % (cols * rows)
        x = margin + (k % cols) * w
        y = pagesize[1] - margin - (k // cols + 1) * h
        c.setDash(2, 2)
        c.setStrokeColor(MUTED)
        c.rect(x + 1.5 * mm, y + 1.5 * mm, w - 3 * mm, h - 3 * mm)
        c.setDash()
        tx, ty = x + 5 * mm, y + h - 9 * mm
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(tx, ty, f"FRASCO {j['jar']}")
        c.setFont("Helvetica-Bold", 10.5)
        name = f"{p['last_names']}, {p['first_names']}"
        c.drawString(tx, ty - 5.5 * mm, name[:46])
        c.setFont("Helvetica", 9)
        c.drawString(tx, ty - 10 * mm, f"Exp. {p['mrn']}" + (f"   Nac. {fmt_birth(p['birth_date'])}" if p["birth_date"] else ""))
        c.drawString(tx, ty - 14.5 * mm, f"{kind_label} · {fmt_birth(pr['performed_on'])}"[:60])
        c.setFont("Helvetica-Bold", 9.5)
        from reportlab.lib.utils import simpleSplit
        for li, line in enumerate(simpleSplit(f"Sitio: {j['site']}", "Helvetica-Bold", 9.5, w - 10 * mm)[:2]):
            c.drawString(tx, ty - (19.5 + 4 * li) * mm, line)
        c.setFont("Helvetica", 8.5)
        extra = " · ".join(x for x in [f"{j['pieces']} fragmento(s)" if j.get("pieces") else None,
                                       (j.get("desc") or "")[:60] or None] if x)
        if extra:
            c.drawString(tx, y + 6 * mm, extra[:70])
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawRightString(x + w - 5 * mm, y + 6 * mm, s["doctor_display_name"][:40])
    if not jars:
        c.setFont("Helvetica", 11)
        c.drawString(20 * mm, pagesize[1] - 30 * mm, "El informe no tiene frascos registrados.")
    c.save()
    return buf.getvalue()


def sheet_pdf(title, body, s, size, assets=None) -> bytes:
    """Hoja de preparación o consentimiento con el encabezado del consultorio."""
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=11 * mm, bottomMargin=11 * mm,
                            title=title, author=s["doctor_display_name"], creator="GastroMed Pro")
    width = pagesize[0] - 30 * mm
    story = [Paragraph(_e(s["doctor_display_name"]), ST["doctor"])]
    sub = [x for x in [s["specialty"], s["address"], f"Tel.: {s['phones']}" if s["phones"] else None] if x]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), ST["sub"]))
    story = _with_logo(story, assets, width)
    story += [Spacer(1, 3 * mm), Paragraph(_e(title), ST["title"]), Spacer(1, 2 * mm)]
    style = ParagraphStyle("sheet", **{**_base, "fontSize": 12, "leading": 14.6})
    for block in body.split("\n\n"):
        lines = block.split("\n")
        first = lines[0].strip()
        if first and any(c.isalpha() for c in first) and first == first.upper() and len(first) <= 80:   # título de sección
            lines[0] = f"<b>{_e(first)}</b>"
            html = "<br/>".join([lines[0]] + [_e(x) for x in lines[1:]])
        else:
            html = _e(block).replace("\n", "<br/>")
        story.append(Paragraph(html, style))
        story.append(Spacer(1, 1.6 * mm))
    def on_page(canvas, _d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
