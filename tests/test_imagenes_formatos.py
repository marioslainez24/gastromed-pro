"""Subida de imágenes de endoscopia: formatos de torre (BMP/TIFF/WebP) convertidos a JPG, HEIC con mensaje claro, una por una."""
import io

from PIL import Image

from conftest import create_patient, csrf, login
from tests.test_fase3 import new_proc


def img(fmt, color=(200, 80, 80)):
    b = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(b, fmt)
    return b.getvalue()


def test_bmp_tiff_webp_se_convierten_a_jpg(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    for i, (fmt, name) in enumerate((("BMP", "t.bmp"), ("TIFF", "t.tif"), ("WEBP", "t.webp"))):
        r = med.post(f"/procedimientos/{proc}/imagenes", data={"csrf_token": tok, "confirm_patient": pid,
                                                               "imagen": (io.BytesIO(img(fmt, (10 + i * 40, 90, 90))), name)},
                     headers={"X-Requested-With": "fetch"}, content_type="multipart/form-data")
        assert r.status_code == 200 and r.get_json()["agregadas"] == 1, (fmt, r.get_json())
    mimes = [m[0] for m in env["db"].execute("SELECT f.mime FROM procedure_images i JOIN files f ON f.id = i.file_id WHERE i.procedure_id = ?", (proc,))]
    assert mimes == ["image/jpeg"] * 3


def test_heic_pdf_y_basura_dan_mensaje_claro(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64
    for data, name, msg in ((heic, "IMG_1.HEIC", "Más compatible"), (b"%PDF-1.4\n...%%EOF", "x.pdf", "Archivos"),
                            (b"no es imagen", "x.jpg", "formato de imagen no reconocido")):
        r = med.post(f"/procedimientos/{proc}/imagenes", data={"csrf_token": tok, "confirm_patient": pid, "imagen": (io.BytesIO(data), name)},
                     headers={"X-Requested-With": "fetch"}, content_type="multipart/form-data")
        assert r.status_code == 422 and msg in " ".join(r.get_json()["errores"]), (name, r.get_json())


def test_pantalla_sube_una_por_una(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "data-img-upload" in html and 'id="proc-form"' in html and "image/*" in html
