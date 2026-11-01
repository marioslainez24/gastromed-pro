"""v0.17.0: calculadoras de otras especialidades (riñón, cardiología, urgencias, general)."""
from conftest import create_patient, csrf, login
from app import calculators as C

NUEVAS = ["ckd_epi_2021", "cockcroft_gault", "calcio_corregido", "brecha_anionica", "cha2ds2_vasc", "has_bled", "qtc_bazett",
          "curb65", "qsofa", "glasgow_coma", "superficie_corporal"]


def test_nuevas_calculadoras_registradas_con_grupo_y_casos():
    for code in NUEVAS:
        c = C.BY_CODE[code]
        assert c.group not in ("Hepatología", "Hemorragia digestiva", "Páncreas") and len(c.reference_cases) >= 2, code
        assert all(ok for *_, ok in C.self_check(c)), code


def test_ckd_epi_caso_publicado_y_datos_ausentes():
    # Ejemplo resuelto independiente (MetricGate): mujer 55 años, creatinina 1.2 mg/dL → 53.5 mL/min/1.73 m², G3a
    r = C.run(C.BY_CODE["ckd_epi_2021"], {"creat": "1.2", "edad": "55", "sexo": "femenino"})
    assert r["valor"] == 53.5 and r["categoria"] == "G3a"
    try:
        C.run(C.BY_CODE["ckd_epi_2021"], {"creat": "1.2", "edad": "55"})
        raise AssertionError("debía exigir el sexo")
    except C.MissingData:
        pass


def test_pantalla_agrupa_y_calcula_con_datos_del_expediente(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    html = med.get("/calculadoras").get_data(as_text=True)
    for grp in ("Riñón y electrolitos", "Cardiología", "Infección y urgencias", "General"):
        assert grp in html, grp
    pid = create_patient(med, sex="femenino", birth_date="1971-01-01")
    med.post(f"/pacientes/{pid}/laboratorio/registrar", data={"csrf_token": tok, "taken_on": "2026-10-10", "code": ["creat", "na"],
                                                              "v_creat": "1.2", "v_na": "140"})
    page = med.get(f"/calculadoras/ckd_epi_2021?patient_id={pid}").get_data(as_text=True)
    assert 'value="1.2"' in page                                                   # la creatinina se trae del expediente
    r = med.post("/calculadoras/ckd_epi_2021", data={"csrf_token": tok, "patient_id": pid, "creat": "1.2", "edad": "55", "sexo": "femenino"})
    assert "53.5" in r.get_data(as_text=True) and "G3a" in r.get_data(as_text=True)
    ag = med.get(f"/calculadoras/brecha_anionica?patient_id={pid}").get_data(as_text=True)
    assert 'value="140"' in ag                                                     # el sodio se trae del expediente
    r = med.post("/calculadoras/glasgow_coma", data={"csrf_token": tok, "ocular": "3", "verbal": "4", "motora": "5"})
    assert "Glasgow 12/15" in r.get_data(as_text=True)
