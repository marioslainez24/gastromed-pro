"""v0.11.0: desplegable de diagnósticos endoscópicos frecuentes con código CIE-10 (OMS, 5.ª ed.)."""
import html as H
import json
import re

from app import endo_diagnoses as DX
from conftest import create_patient, csrf, login
from tests.test_fase3 import new_proc

# Códigos comprobados en classbrowser.nhs.uk (CIE-10 OMS 5.ª ed.) — si alguien cambia la lista, esta prueba obliga a revisarla.
VERIFIED = {"K20", "K21.0", "K22.0", "K22.1", "K22.2", "K22.5", "K22.6", "K22.7", "K25.4", "K25.9", "K26.4", "K26.9", "K29.0", "K29.4",
            "K29.7", "K29.8", "K31.4", "K31.7", "K31.8", "K44.9", "I85.0", "I85.9", "I86.4", "K92.2", "K63.5", "K62.1", "K57.3",
            "K64.0", "K64.1", "K64.2", "K64.3", "K60.1", "K55.2", "K51.0", "K51.2", "K51.3", "K51.4", "K51.5", "K50.0", "K50.1",
            "K52.9", "K62.7", "K62.6", "K62.3", "K63.8", "K80.2", "K80.3", "K80.5", "K83.0", "K83.1", "K83.5", "K86.1", "K86.2", "K86.3",
            # v0.19.0, verificados el 1-nov-2026 en classbrowser.nhs.uk (bloques K20-K31, K50-K52, K90-K93)
            "K21.9", "K29.6", "K50.8", "K51.9", "K91.8"}


def test_catalogo_codigos_verificados_y_ejemplos_del_doctor():
    codes = {c for _, _, _, c, _ in DX.DIAGNOSES if c}
    assert codes <= VERIFIED, codes - VERIFIED
    texts = [t for _, _, t, _, _ in DX.DIAGNOSES]
    assert len(texts) == len(set(texts))
    assert "Esofagitis erosiva grado A de Los Ángeles" in texts
    assert any(t.startswith("Gastropatía hipertensiva portal") for t in texts)
    # sin código propio -> marcado como aproximado; neoplasias sin código hasta tener histología
    for g, k, t, c, a in DX.DIAGNOSES:
        if "neoplásico" in t:
            assert c is None
        if a:   # categorías «otras…»: .8, o K29.6 («Otras gastritis», v0.19.0)
            assert c and (c.endswith(".8") or c == "K29.6")
    eda = {d["t"] for d in DX.for_kind("eda")}
    colo = {d["t"] for d in DX.for_kind("colonoscopia")}
    assert "Hemorroides internas grado II" in colo and "Hemorroides internas grado II" not in eda
    assert "Varices" not in " ".join(colo)


def test_desplegable_en_la_conclusion_segun_el_estudio(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    html = med.get(f"/procedimientos/{new_proc(med, pid, tok, 'eda')}").get_data(as_text=True)
    assert "data-dx-open" in html and "classbrowser.nhs.uk" in html
    data = json.loads(H.unescape(re.search(r'data-dx="([^"]*)"', html).group(1)))
    assert {"g": "Esófago", "t": "Esofagitis erosiva grado A de Los Ángeles", "c": "K21.0", "a": False} in data
    html = med.get(f"/procedimientos/{new_proc(med, pid, tok, 'colonoscopia')}").get_data(as_text=True)
    data = json.loads(H.unescape(re.search(r'data-dx="([^"]*)"', html).group(1)))
    assert all(d["g"] in ("Normal", "Colon y recto", "Sangrado") for d in data)
