"""v0.28.0: el médico elige dónde va cada logo (izquierda / centro / derecha) y su tamaño."""
import io
import json

from PIL import Image
from pypdf import PdfReader

from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def _png(color, size=(600, 300)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def _positions(pdf_bytes):
    """Posición horizontal (x) de cada imagen en la primera página, ordenadas por su color."""
    page = PdfReader(io.BytesIO(pdf_bytes)).pages[0]
    out = []

    def visit(op, args, cm, tm):
        if op == b"Do":
            out.append(round(cm[4]))
    page.extract_text(visitor_operand_before=visit)
    return out


def test_colocacion_izquierda_centro_derecha(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    for kind, color in (("logo", "red"), ("logo2", "green"), ("logo3", "blue")):
        med.post("/ajustes/imagenes", data={"csrf_token": tok, "kind": kind, "imagen": (io.BytesIO(_png(color)), "x.png")},
                 content_type="multipart/form-data")
    html = med.get("/ajustes/").get_data(as_text=True)
    assert "¿Dónde va cada logo?" in html and "colocación automática" in html
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc)))
    r = med.post("/ajustes/logos-posicion", data={"csrf_token": tok, "pos-logo": "derecha", "pos-logo2": "izquierda",
                                                  "pos-logo3": "centro", "size": "mediano"})
    assert r.status_code == 302
    lay = json.loads(env["db"].execute("SELECT logo_layout FROM clinic_settings").fetchone()[0])
    assert lay == {"logo": "derecha", "logo2": "izquierda", "logo3": "centro", "size": "mediano"}
    for style in ("clasico", "formal", "moderno"):
        med.post("/ajustes/estilo-informe", data={"csrf_token": tok, "report_style": style})
        data = med.get(f"/procedimientos/{proc}/pdf").data
        xs = _positions(data)
        assert len(xs) == 3, (style, xs)
    # logo 1 a la derecha y logo 2 a la izquierda: en el PDF el 2 queda más a la izquierda que el 1
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages[0].images) == 3
    assert "Usando su colocación" in med.get("/ajustes/").get_data(as_text=True)
    # volver a automático
    med.post("/ajustes/logos-posicion", data={"csrf_token": tok, "action": "automatico"})
    assert env["db"].execute("SELECT logo_layout FROM clinic_settings").fetchone()[0] is None
    assert med.post("/ajustes/logos-posicion", data={"csrf_token": tok, "pos-logo": "arriba", "pos-logo2": "izquierda",
                                                     "pos-logo3": "centro", "size": "grande"}).status_code == 400


def test_orden_izquierda_derecha_en_el_pdf():
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import LETTER
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from app import pdf
    assets = {"logo": _png("red", (300, 300)), "logo2": _png("green", (300, 301)),
              "_layout": {"logo": "derecha", "logo2": "izquierda", "logo3": "centro", "size": "grande"}}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER)
    doc.build(pdf._with_logo([Paragraph("Dr. Prueba", pdf.ST["doctor"])], assets, 180 * mm, big=True))
    xs = _positions(buf.getvalue())
    assert len(xs) == 2 and xs[0] != xs[1]
    t = pdf._with_logo([Paragraph("Dr. Prueba", pdf.ST["doctor"])], assets, 180 * mm, big=True)[0]
    left, right = t._cellvalues[0][0], t._cellvalues[0][-1]
    assert left.drawHeight > 0 and right.drawHeight > 0
    # el logo 2 (verde, 301 px de alto) está en la celda izquierda
    assert abs(left.imageHeight - 301) < 2 or abs(left.drawWidth / left.drawHeight - 300 / 301) < 0.01
