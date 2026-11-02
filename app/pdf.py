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

_base = dict(fontName="Helvetica", fontSize=10, leading=13.5, textColor=INK)
ST = {
    "doctor": ParagraphStyle("doctor", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 15, "leading": 18}),
    "sub": ParagraphStyle("sub", **{**_base, "fontSize": 9, "leading": 12, "textColor": MUTED}),
    "title": ParagraphStyle("title", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 11, "textColor": ACCENT}),
    "body": ParagraphStyle("body", **_base),
    "med": ParagraphStyle("med", **{**_base, "fontName": "Helvetica-Bold", "fontSize": 11}),
    "subr": ParagraphStyle("subr", **{**_base, "fontSize": 9, "leading": 12, "textColor": MUTED, "alignment": 2}),
    "item9": ParagraphStyle("item9", **{**_base, "fontSize": 9, "leading": 11.5}),
    "small": ParagraphStyle("small", **{**_base, "fontSize": 8, "leading": 10, "textColor": MUTED}),
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
                   Paragraph(f"Fecha: {issued:%d/%m/%Y}<br/>Folio: {o['id'][:8].upper()}<br/>Prioridad: {_e(priority_label)}", ST["subr"])]],
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
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 12 * mm, "Generado con GastroMed Pro. Requiere firma manuscrita del médico.")
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


def procedure_pdf(pr, d, p, s, size, images, scope, addenda, D, assets=None) -> bytes:
    from reportlab.platypus import Image as RLImage
    buf = io.BytesIO()
    pagesize = LETTER if size == "carta" else A4
    title = D.KINDS[pr["kind"]]
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=20 * mm,
                            title=f"Informe de {title}", author=s["doctor_display_name"], creator="GastroMed Pro")
    width = pagesize[0] - 32 * mm
    story = [Paragraph(_e(s["doctor_display_name"]), ST["doctor"])]
    sub = [x for x in [s["specialty"], f"Colegiación: {s['license_number']}" if s["license_number"] else None,
                       s["address"], f"Tel.: {s['phones']}" if s["phones"] else None] if x]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), ST["sub"]))
    story = _with_logo(story, assets, width)
    head = Table([[Paragraph(f"INFORME DE {_e(title.upper())}", ST["title"]),
                   Paragraph(f"Fecha: {fmt_birth(pr['performed_on'])}<br/>Folio: {pr['id'][:8].upper()}"
                             + ("" if pr["status"] == "finalizado" else "<br/><b>BORRADOR</b>"), ST["subr"])]],
                 colWidths=[width * 0.6, width * 0.4])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [Spacer(1, 2 * mm), head]
    pt = Table([[Paragraph(f"<b>Paciente:</b> {_e(p['first_names'])} {_e(p['last_names'])} · {_e(p['mrn'])}", ST["body"]),
                 Paragraph(f"<b>Edad:</b> {_e(age(p['birth_date']))} · {_e(label('sex', p['sex']))}", ST["body"])]],
               colWidths=[width * 0.62, width * 0.38])
    pt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4f3")), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    story += [Spacer(1, 2 * mm), pt, Spacer(1, 3 * mm)]

    def sec(t, body):
        if body:
            story.append(Paragraph(_e(t), ST["title"]))
            story.append(Paragraph(_e(body).replace("\n", "<br/>"), ST["body"]))
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
    eq = [x for x in [f"Endoscopista: {d['endoscopist']}" if d.get("endoscopist") else None,
                      f"Equipo: {scope['name']}" + (f" (serie {scope['serial']})" if scope and scope['serial'] else "") if scope else None,
                      f"Asistentes: {d['assistants']}" if d.get("assistants") else None,
                      f"Horario: {d.get('start_time') or '?'}–{d.get('end_time') or '?'}" if d.get("start_time") else None] if x]
    sec("Evaluación previa, preparación y sedación", "\n".join(pre + eq))
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
        story.append(Paragraph("Descripción de hallazgos", ST["title"]))
        for key, lab in D.NARRATIVE[pr["kind"]]:
            txt = nar.get(key) or ""
            if key == "ueg" and d.get("zline"):
                txt = (D.zline_text(d) + " " + txt).strip()
            if txt:
                story.append(Paragraph(f"<b>{_e(lab)}:</b> " + _e(txt).replace("\n", "<br/>"), ST["body"]))
                story.append(Spacer(1, 1.2 * mm))
        story.append(Spacer(1, 1 * mm))
    if d.get("findings"):
        story.append(Paragraph("Hallazgos detallados" if any(nar.values()) else "Hallazgos", ST["title"]))
        rows = [[Paragraph("<b>Segmento</b>", ST["small"]), Paragraph("<b>Hallazgo</b>", ST["small"]), Paragraph("<b>Clasificación / tamaño</b>", ST["small"]),
                 Paragraph("<b>Frasco</b>", ST["small"])]]
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
            rows.append([Paragraph(_e(f["segment"]), ST["small"]),
                         Paragraph(_e(" · ".join(x for x in [f.get("type"), f.get("desc")] if x)), ST["body"]),
                         Paragraph(_e(" · ".join(cl)), ST["small"]), Paragraph(str(f.get("jar") or ""), ST["small"])])
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
                                + (f" · frasco {m['jar']}" if m.get("jar") else ""), ST["small"]) for i, m in enumerate(d["marks"], 1)]
            t = Table([[dr, legend]], colWidths=[dr.width + 4 * mm, width - dr.width - 4 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            story += [KeepTogether([Paragraph("Esquema anatómico", ST["title"]), t]), Spacer(1, 2 * mm)]
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
    sec("Seguimiento", (d.get("follow_up") or "") + (f"\nControl / vigilancia indicada para: {fmt_birth(pr['surveillance_due'])}"
                                                     if pr["surveillance_due"] else ""))
    if images:
        story.append(Paragraph("Imágenes", ST["title"]))
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
            row.append([img, Paragraph(_e(cap), ST["small"])])
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
    sig = Table([[_sig_img(assets)], [Paragraph(f"<b>{_e(s['doctor_display_name'])}</b><br/>Firma y sello", ST["sub"])]], colWidths=[70 * mm], rowHeights=[16 * mm, None])
    sig.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, INK), ("ALIGN", (0, 1), (0, 1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    outer = Table([[sig]], colWidths=[width])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    story += [Spacer(1, 6 * mm), KeepTogether([outer])]

    def on_page(canvas, dd):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 11 * mm, "Generado con GastroMed Pro. " + ("Informe finalizado; requiere firma manuscrita." if signed
                                                                            else "BORRADOR: no válido como informe definitivo."))
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
    head = Table([[Paragraph(_e(d["title"]), ST["title"]), Paragraph(f"Fecha: {issued:%d/%m/%Y}<br/>Folio: {d['id'][:8].upper()}", ST["subr"])]],
                 colWidths=[width * 0.65, width * 0.35])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    body_style = ParagraphStyle("docbody", **{**_base, "fontSize": 11, "leading": 17, "alignment": 4})
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
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(22 * mm, 12 * mm, "Generado con GastroMed Pro. Válido solo con firma manuscrita y sello del médico.")
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
        c.setFont("Helvetica", 8)
        c.drawRightString(x + w - 5 * mm, ty, f"Folio {pr['id'][:8].upper()}")
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
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=title, author=s["doctor_display_name"], creator="GastroMed Pro")
    width = pagesize[0] - 40 * mm
    story = [Paragraph(_e(s["doctor_display_name"]), ST["doctor"])]
    sub = [x for x in [s["specialty"], s["address"], f"Tel.: {s['phones']}" if s["phones"] else None] if x]
    if sub:
        story.append(Paragraph(_e(" · ".join(sub)), ST["sub"]))
    story = _with_logo(story, assets, width)
    story += [Spacer(1, 5 * mm), Paragraph(_e(title), ST["title"]), Spacer(1, 4 * mm)]
    style = ParagraphStyle("sheet", **{**_base, "fontSize": 10, "leading": 13.2})
    for block in body.split("\n\n"):
        lines = block.split("\n")
        first = lines[0].strip()
        if first and any(c.isalpha() for c in first) and first == first.upper() and len(first) <= 80:   # título de sección
            lines[0] = f"<b>{_e(first)}</b>"
            html = "<br/>".join([lines[0]] + [_e(x) for x in lines[1:]])
        else:
            html = _e(block).replace("\n", "<br/>")
        story.append(Paragraph(html, style))
        story.append(Spacer(1, 2.2 * mm))
    doc.build(story)
    return buf.getvalue()
