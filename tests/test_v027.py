"""v0.27.0: hasta 3 logos, grandes en el informe."""
import io

from PIL import Image
from pypdf import PdfReader

from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def _png(color, size=(600, 300)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def _upload(c, tok, kind, data):
    return c.post("/ajustes/imagenes", data={"csrf_token": tok, "kind": kind, "imagen": (io.BytesIO(data), f"{kind}.png")},
                  content_type="multipart/form-data")


def _images(pdf_bytes):
    return [im for pg in PdfReader(io.BytesIO(pdf_bytes)).pages for im in pg.images]


def test_tres_logos_en_ajustes_y_en_el_informe(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    html = med.get("/ajustes/").get_data(as_text=True)
    assert "Logo 1" in html and "Logo 2" in html and "Logo 3" in html
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc)))
    assert len(_images(med.get(f"/procedimientos/{proc}/pdf").data)) == 0
    for i, (kind, color) in enumerate((("logo", "red"), ("logo2", "green"), ("logo3", "blue")), 1):
        assert _upload(med, tok, kind, _png(color)).status_code == 302
        for style in ("clasico", "formal", "moderno"):
            med.post("/ajustes/estilo-informe", data={"csrf_token": tok, "report_style": style})
            imgs = _images(med.get(f"/procedimientos/{proc}/pdf").data)
            assert len(imgs) == i, (style, i, len(imgs))
    # también en la receta y otros documentos (los tres)
    assert env["db"].execute("SELECT COUNT(*) FROM clinic_assets WHERE kind IN ('logo','logo2','logo3')").fetchone()[0] == 3
    # quitar el 2: quedan dos
    med.post("/ajustes/imagenes", data={"csrf_token": tok, "kind": "logo2", "remove": "1"})
    assert len(_images(med.get(f"/procedimientos/{proc}/pdf").data)) == 2
    assert _upload(med, tok, "logo9", _png("black")).status_code == 400


def test_logos_grandes():
    from reportlab.lib.units import mm
    from app import pdf
    one = pdf._with_logo(["x"], {"logo": _png("red")}, 180 * mm, big=True)[0]
    img = one._cellvalues[0][0]
    assert img.drawWidth >= 47 * mm or img.drawHeight >= 31 * mm          # antes: 30 × 22 mm
    row = pdf._with_logo(["x"], {"logo": _png("red"), "logo2": _png("green"), "logo3": _png("blue")}, 180 * mm, big=True)[0]
    assert all(im.drawHeight >= 29 * mm or im.drawWidth >= 51 * mm for im in row._cellvalues[0])
