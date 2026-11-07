"""NeuroMed Pro 1.0: escalas neurológicas con fuente y casos de referencia, y pantalla de escalas."""
from app import calculators as C
from app import neuro_calcs as N
from conftest import create_patient, csrf, login


def test_todas_las_escalas_tienen_fuente_y_casos_que_coinciden():
    for calc in N.ALL:
        assert calc.source and calc.verified_against and calc.reference_cases, calc.code
        for inp, expected, res, ok in C.self_check(calc):
            assert ok, (calc.code, inp, expected, res)


def test_nihss_ejemplo_y_datos_faltantes():
    base = {k: "0" for k, _, _ in N.NIH_ITEMS}
    r = C.run(N.NIHSS, {**base, "i5b": "4", "i6b": "4", "i9": "3", "i4": "3"})
    assert r["valor"] == 14 and r["categoria"] == "moderado" and "aviso" in r
    import pytest
    with pytest.raises(C.MissingData):
        C.run(N.NIHSS, {k: v for k, v in base.items() if k != "i9"})
    with pytest.raises(C.MissingData):
        C.run(N.NIHSS, {**base, "i9": "7"})       # opción inexistente


def test_ich_y_wfns_puntos_de_corte():
    assert C.run(N.ICH, {"glasgow": "12", "volumen": "30", "edad": "80"})["valor"] == 3
    assert C.run(N.ICH, {"glasgow": "13", "volumen": "29.9", "edad": "79"})["valor"] == 0
    assert C.run(N.WFNS, {"glasgow": "13"})["valor"] == 2 and C.run(N.WFNS, {"glasgow": "7"})["valor"] == 4


def test_lista_de_escalas_sin_calculadoras_digestivas(env):
    med = login(env["app"], "propietario")
    html = med.get("/calculadoras").get_data(as_text=True)
    assert "Escalas neurológicas" in html and "NIHSS" in html and "Glasgow" in html and "Barthel" in html
    assert "MELD" not in html and "Child-Pugh" not in html and "Glasgow-Blatchford" not in html
    pid = create_patient(med)
    tok = csrf(med)
    r = med.post("/calculadoras/abcd2", data={"csrf_token": tok, "patient_id": pid, "edad": "70", "pa": "1", "clinica": "2", "duracion": "2"})
    assert "ABCD² 6" in r.get_data(as_text=True)
