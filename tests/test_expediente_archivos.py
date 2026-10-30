"""Antecedentes, medicamentos, problemas y archivos privados."""
import hashlib
import io
from pathlib import Path

import pytest

from conftest import create_patient, csrf, login

PDF_OK = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PDF_JS = b"%PDF-1.4\n1 0 obj<</OpenAction<</S/JavaScript/JS(app.alert(1))>>>>endobj\n%%EOF\n"
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def upload(c, pid, data, name="estudio.pdf", **over):
    form = {"csrf_token": csrf(c), "patient_id": pid, "category": "laboratorio", "title": "Pruebas hepáticas",
            "study_date": "2026-10-01", "institution": "Laboratorio Demo", "archivo": (io.BytesIO(data), name)}
    form.update(over)
    return c.post("/archivos/subir", data=form, content_type="multipart/form-data")


def test_antecedentes_medicamentos_problemas(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    base = f"/pacientes/{pid}/expediente"
    assert med.post(f"{base}/antecedentes", data={"csrf_token": tok, "category": "quirurgico", "description": "Colecistectomía",
                                                   "when_text": "2018"}).status_code == 302
    assert med.post(f"{base}/medicamentos", data={"csrf_token": tok, "name": "Propranolol", "dose": "20 mg", "frequency": "cada 12 h",
                                                   "source": "otro_medico"}).status_code == 302
    assert med.post(f"{base}/problemas", data={"csrf_token": tok, "description": "Cirrosis hepática compensada"}).status_code == 302
    assert med.post(f"{base}/medicamentos/conciliar", data={"csrf_token": tok, "confirm": "1"}).status_code == 302
    html = med.get(f"/pacientes/{pid}").get_data(as_text=True)
    for t in ["Colecistectomía", "Propranolol", "Cirrosis hepática compensada", "Lista conciliada"]:
        assert t in html, t
    db = env["db"]
    mid = db.execute("SELECT id FROM patient_medications").fetchone()["id"]
    assert med.post(f"{base}/medicamentos/{mid}/suspender", data={"csrf_token": tok, "stop_reason": "Bradicardia"}).status_code == 302
    row = db.execute("SELECT status, stop_reason FROM patient_medications WHERE id = ?", (mid,)).fetchone()
    assert row["status"] == "suspendido" and row["stop_reason"] == "Bradicardia"
    with pytest.raises(Exception):
        db.execute("DELETE FROM patient_medications")
    # Recepción no puede ni ver ni registrar
    rec = login(env["app"], "recepcion")
    assert "Propranolol" not in rec.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert rec.post(f"{base}/problemas", data={"csrf_token": csrf(rec), "description": "x"}).status_code == 403


def test_subida_y_descarga_cifrada(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    r = upload(med, pid, PDF_OK)
    assert r.status_code == 302
    f = env["db"].execute("SELECT * FROM files").fetchone()
    assert f["mime"] == "application/pdf" and f["sha256"] == hashlib.sha256(PDF_OK).hexdigest()
    stored = (Path(env["cfg"].FILES_DIR) / f["storage_name"]).read_bytes()
    assert PDF_OK not in stored and b"%PDF" not in stored  # cifrado en reposo
    r = med.get(f"/archivos/{f['id']}")
    assert r.status_code == 200 and r.data == PDF_OK and r.mimetype == "application/pdf"
    assert "sandbox" in r.headers["Content-Security-Policy"] and r.headers["Cache-Control"] == "no-store"
    assert "Pruebas" not in r.headers["Content-Disposition"]
    # Imagen desde la cámara del celular
    assert upload(med, pid, JPG, name="IMG_0001.JPG", category="endoscopia", title="Foto informe").status_code == 302
    assert upload(med, pid, PNG, name="captura.png", title="Captura").status_code == 302


@pytest.mark.parametrize("data,name,msg", [
    (b"MZ\x90\x00malware", "estudio.pdf", "no permitido"),          # ejecutable renombrado
    (b"<html><script>alert(1)</script>", "x.png", "no permitido"),   # HTML disfrazado
    (PDF_JS, "a.pdf", "contenido activo"),                            # PDF con JavaScript
    (b"", "vacio.pdf", "vacío"),
])
def test_rechaza_archivos_peligrosos(env, data, name, msg):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    r = upload(med, pid, data, name=name)
    assert r.status_code == 422 and msg in r.get_data(as_text=True)
    assert env["db"].execute("SELECT COUNT(*) c FROM files").fetchone()["c"] == 0
    assert not any(Path(env["cfg"].FILES_DIR).glob("*.bin")) if Path(env["cfg"].FILES_DIR).exists() else True


def test_limite_de_tamano(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    big = PDF_OK[:-6] + b"0" * (20 * 1024 * 1024) + b"%%EOF\n"
    r = upload(med, pid, big)
    assert r.status_code in (413, 422)


def test_archivos_solo_con_autorizacion(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    upload(med, pid, PDF_OK)
    fid = env["db"].execute("SELECT id FROM files").fetchone()["id"]
    assert login(env["app"], "recepcion").get(f"/archivos/{fid}").status_code == 403
    assert login(env["app"], "caja").get(f"/archivos/{fid}").status_code == 403
    assert login(env["app"], "otra", email="otra@prueba.hn").get(f"/archivos/{fid}").status_code == 404
    assert env["app"].test_client().get(f"/archivos/{fid}").status_code == 302  # sin sesión
    assert login(env["app"], "enfermeria").get(f"/archivos/{fid}").status_code == 200
    # Retirar conserva el registro y el contenido
    assert med.post(f"/archivos/{fid}/archivar", data={"csrf_token": csrf(med), "reason": "Pertenece a otro paciente"}).status_code == 302
    row = env["db"].execute("SELECT archived_at, archive_reason FROM files WHERE id = ?", (fid,)).fetchone()
    assert row["archived_at"] and row["archive_reason"] == "Pertenece a otro paciente"
    assert "Pruebas hepáticas" not in med.get(f"/pacientes/{pid}").get_data(as_text=True)
    with pytest.raises(Exception):
        env["db"].execute("UPDATE files SET sha256 = 'x' WHERE id = ?", (fid,))
