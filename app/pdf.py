"""Generación de PDF (ReportLab). Tamaños carta (216×279 mm) y A4 (210×297 mm)."""
import io
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

_base = dict(fontName="Helvetica", fontSize=10, leading=13.5, textColor=INK)
ST = {
    "doctor": ParagraphStyle("doctor", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 15, "leading": 18}),
    "sub": ParagraphStyle("sub", **{**_base, "fontSize": 9, "leading": 12, "textColor": MUTED}),
    "title": ParagraphStyle("title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 11, "textColor": ACCENT}),
    "body": ParagraphStyle("body", **_base),
    "med": ParagraphStyle("med", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 11}),
    "subr": ParagraphStyle("subr", **{**_base, "fontSize": 9, "leading": 12, "textColor": MUTED, "alignment": 2}),
    "small": ParagraphStyle("small", **{**_base, "fontSize": 8, "leading": 10, "textColor": MUTED}),
}


def _e(s) -> str:
    return escape(str(s or ""))


def prescription_pdf(r, items, p, s, size: str, allergies) -> bytes:
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
    story.append(Spacer(1, 4 * mm))

    head = Table([[Paragraph("RECETA MÉDICA", ST["title"]),
                   Paragraph(f"Fecha: {issued:%d/%m/%Y}<br/>Folio: {r['id'][:8].upper()}", ST["subr"])]],
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

    sig = Table([[""], [Paragraph(f"<b>{_e(s['doctor_display_name'])}</b><br/>Firma y sello", ST["sub"])]],
                colWidths=[70 * mm], rowHeights=[18 * mm, None])
    sig.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, INK), ("ALIGN", (0, 1), (0, 1), "CENTER"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    outer = Table([[sig]], colWidths=[width])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    story += [Spacer(1, 10 * mm), KeepTogether([outer])]

    voided = r["status"] == "anulada"

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 12 * mm, "Generado con GastroMed Pro. Requiere firma manuscrita del médico; "
                                           "este documento no contiene firma electrónica verificable.")
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
