"""v0.19.0: clasificaciones del consenso que aportó el Dr. Lainez, en los hallazgos con clics y en los diagnósticos de la conclusión."""
import pytest
from werkzeug.datastructures import MultiDict

from conftest import create_patient, csrf, login
from tests.test_fase3 import new_proc
from app import endo_diagnoses as DX
from app import endo_findings as EF


def md(**kw):
    m = MultiDict()
    for k, v in kw.items():
        m.setlist(k, v if isinstance(v, list) else [v])
    return m


@pytest.mark.parametrize("sec,key,data,texto,dx,code", [
    ("esofago", "candida", {"kodsi": "III"}, "grado III de Kodsi", "Esofagitis candidiásica grado III de Kodsi", "K20"),
    ("esofago", "estenosis", {"cm": "30", "paso": "si", "bernal": "II"}, "tipo II de Bernal", "Estenosis esofágica tipo II de Bernal", "K22.2"),
    ("esofago", "acalasia", {"grado": "III"}, "acalasia grado III (avanzado)", "Hallazgos compatibles con acalasia, grado endoscópico III", "K22.0"),
    ("esofago", "nerd_m", {}, "grado M", "Enfermedad por reflujo no erosiva con cambios mínimos (grado M)", "K21.9"),
    ("ueg", "hill", {"grado": "IV"}, "grado IV de Hill", "Válvula gastroesofágica grado IV de Hill", None),
    ("ueg", "paraesofagica", {"tipo": "II"}, "tipo II (paraesofágica)", "Hernia hiatal tipo II (paraesofágica)", "K44.9"),
    ("estomago", "sydney", {"cat": "erosiva_plana", "topo": "antro"}, "erosiva plana del antro",
     "Gastritis endoscópica erosiva plana del antro (Sistema Sídney)", "K29.7"),
    ("estomago", "lanza", {"grado": "4"}, "más de 25 petequias", "Gastropatía por AINE grado 4 de Lanza", "K29.7"),
    ("estomago", "paniagua", {"grado": "I"}, "grado I (ligero)", "Gastritis por reflujo duodenogástrico grado I (Paniagua)", "K29.6"),
    ("estomago", "neoplasia_g", {"loc": "cuerpo", "borrmann": "IV"}, "linitis plástica",
     "Lesión gástrica de aspecto neoplásico Borrmann IV, pendiente de histología", None),
    ("estomago", "goitein", {"grado": "III"}, "solo permite el paso de una guía", "Estenosis de anastomosis gastroyeyunal grado III de Goitein", "K91.8"),
    ("colon", "cu_mayo", {"mayo": "3", "ext": "extensa"}, "Mayo endoscópico 3", "Colitis ulcerosa: colitis extensa (pancolitis), Mayo endoscópico 3", "K51.0"),
    ("colon", "rutgeerts", {"i": "i0"}, "Rutgeerts i0", "Enfermedad de Crohn posquirúrgica, Rutgeerts i0 (sin recurrencia endoscópica)", "K50.8"),
])
def test_clasificaciones_redactan_frase_y_diagnostico(sec, key, data, texto, dx, code):
    t, out = EF.compose(sec, key, md(**data))
    assert texto in t, t
    assert out[0]["t"] == dx and out[0]["c"] == code


def test_puntajes_dica_baveno_y_actinica():
    # DICA (Tursi 2015): izquierdo 2 + >15 divertículos 1 + erosiones 2 = 5 → DICA 2; con estenosis +4 y derecho +1 y SCAD → 11 → DICA 3
    t, out = EF.compose("colon", "dica", md(extension=["izquierdo"], numero="mas15", inflamacion="erosiones"))
    assert "DICA 2 (5 puntos)" in t and out[0]["c"] == "K57.3"
    t, _ = EF.compose("colon", "dica", md(extension=["izquierdo", "derecho"], numero="mas15", inflamacion="scad", complicaciones=["estenosis"]))
    assert "DICA 3 (11 puntos)" in t
    t, _ = EF.compose("colon", "dica", md(extension=["derecho"], numero="hasta15", inflamacion="no"))
    assert "DICA 1 (1 punto)" in t
    # Baveno: mosaico severo 2 + rojas aisladas 1 + GAVE 2 = 5 → severa; leve 1 + aisladas 1 = 2 → leve (corte ≤3 / ≥4)
    _, out = EF.compose("estomago", "hipertensiva_pts", md(mosaico="severo", rojas="aisladas", gave="si"))
    assert out[0]["t"] == "Gastropatía hipertensiva portal severa"
    t, out = EF.compose("estomago", "hipertensiva_pts", md(mosaico="severo", rojas="aisladas", gave="no"))
    assert "puntaje de Baveno 3" in t and out[0]["t"] == "Gastropatía hipertensiva portal leve"
    # Colitis actínica: 1 + 1 + 0 = 2 → A; 2 + 2 + 1 = 5 → C
    _, out = EF.compose("colon", "actinica", md(distribucion="distal", superficie="menos50", sangre="no"))
    assert out[0]["t"] == "Proctitis actínica grado A (2 puntos)"
    _, out = EF.compose("colon", "actinica", md(distribucion="todo", superficie="mas50", sangre="si"))
    assert out[0]["t"] == "Proctitis actínica grado C (5 puntos)"


def test_grados_normales_no_sugieren_diagnostico_y_falta_dato():
    assert EF.compose("ueg", "hill", md(grado="I"))[1] == []
    assert EF.compose("estomago", "lanza", md(grado="0"))[1] == []
    with pytest.raises(EF.Invalid):
        EF.compose("colon", "dica", md(numero="mas15", inflamacion="no"))           # falta la extensión


def test_catalogo_conclusion_incluye_las_nuevas():
    eda = {d["t"]: d["c"] for d in DX.for_kind("eda")}
    colon = {d["t"]: d["c"] for d in DX.for_kind("colonoscopia")}
    assert eda["Esofagitis candidiásica grado II de Kodsi"] == "K20" and eda["Hernia hiatal tipo III (mixta)"] == "K44.9"
    assert eda["Gastropatía por AINE grado 2 de Lanza"] == "K29.7" and "Válvula gastroesofágica grado III de Hill" in eda
    assert colon["Enfermedad diverticular de colon DICA 2"] == "K57.3" and colon["Proctitis actínica grado B"] == "K62.7"
    assert "Colitis ulcerosa, Mayo endoscópico 0 (remisión endoscópica)" in colon
    # todo diagnóstico que sugiere un hallazgo de grado fijo debe existir también en el desplegable
    for g in ("I", "II", "III", "IV"):
        assert EF.compose("estomago", "goitein", md(grado=g))[1][0]["t"] in eda


def test_pantalla_muestra_guia_de_grados_y_fuente(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    eda = new_proc(med, pid, tok, "eda")
    html = med.get(f"/procedimientos/{eda}").get_data(as_text=True)
    assert "Válvula gastroesofágica (Hill)" in html and "Grado III: casi no hay pliegue" in html
    assert "Fuente: Kodsi BE et al. Gastroenterology 1976" in html and "Gastritis endoscópica (Sídney)" in html
    r = med.post(f"/procedimientos/{eda}/hallazgo", data={"csrf_token": tok, "section": "estomago", "finding": "lanza",
                                                        "ef-estomago-lanza-grado": "2"})
    assert r.status_code == 200 and r.get_json()["dx"][0] == {"t": "Gastropatía por AINE grado 2 de Lanza", "c": "K29.7", "a": False}
    col = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{col}").get_data(as_text=True)
    assert "Enfermedad diverticular (DICA)" in html and "Colitis ulcerosa (Mayo endoscópico)" in html and "0-IIa+IIc" in html
