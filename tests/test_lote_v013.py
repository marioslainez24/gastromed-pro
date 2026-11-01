"""v0.13.0 (lote 2): clasificaciones, etiquetas de frascos, cálculos rápidos, hallazgos con clics, recomendaciones, hojas, sala de espera,
preconsulta, imprimir todo y resumen del paciente."""
import io
import json

from pypdf import PdfReader

from app import endoscopy_defs as D
from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def pdf_text(data):
    return "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(data)).pages)


def test_clasificaciones_nuevas_verificadas():
    for grp in ("sarin", "zargar", "nice", "kudo"):
        assert grp in D.CLASSIFICATIONS
    assert [s for _, s, _ in D.CLASSIFICATIONS["zargar"][1]] == ["0", "1", "2a", "2b", "3a", "3b"]
    assert [s for _, s, _ in D.CLASSIFICATIONS["sarin"][1]] == ["GOV1", "GOV2", "IGV1", "IGV2"]
    assert "adenoma" in D.CLASS_LOOKUP["N-2"][2]
    assert "Hewett" in D.__doc__ and "Zargar" in D.__doc__ and "Sarin" in D.__doc__


def test_etiquetas_de_frascos(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok)
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), **{
        "jar-1-number": "2", "jar-1-site": "Recto, biopsias aleatorias", "jar-1-pieces": "4"}))
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Etiquetas de frascos (2)" in html
    r = med.get(f"/procedimientos/{proc}/etiquetas?papel=carta")
    t = pdf_text(r.data)
    assert r.status_code == 200 and "FRASCO 1" in t and "FRASCO 2" in t and "Recto, biopsias aleatorias" in t and "4 fragmento(s)" in t
    assert "Exp. GM-" in t
