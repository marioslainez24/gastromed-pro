"""v0.25.0: el número de expediente es el DNI (pedido del Dr. Lainez). Sin DNI se usa el número automático GM-…."""
from conftest import create_patient, csrf, login


def _mrn(env, pid):
    return env["db"].execute("SELECT mrn FROM patients WHERE id = ?", (pid,)).fetchone()[0]


def test_nuevo_paciente_con_dni_usa_el_dni(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med, document_number="0801-1975-12345")
    assert _mrn(env, pid) == "0801-1975-12345"
    html = med.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert "0801-1975-12345" in html


def test_sin_dni_numero_automatico(env):
    med = login(env["app"], "propietario")
    a = create_patient(med, document_type="sin_documento", document_number="", first_names="Sin", last_names="Documento")
    b = create_patient(med, document_type="pasaporte", document_number="P1234567", first_names="Con", last_names="Pasaporte")
    assert _mrn(env, a).startswith("GM-") and _mrn(env, b).startswith("GM-")


def test_al_agregar_dni_cambia_el_expediente_y_el_anterior_se_sigue_encontrando(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med, document_type="sin_documento", document_number="", first_names="Luego", last_names="Con Dni")
    old = _mrn(env, pid)
    assert old.startswith("GM-")
    form = {"csrf_token": csrf(med), "first_names": "Luego", "last_names": "Con Dni", "birth_date": "1980-05-10", "sex": "femenino",
            "document_type": "dni", "document_number": "0801-1980-77777", "phone": "+504 9999-0000", "version": "1"}
    assert med.post(f"/pacientes/{pid}/editar", data=form).status_code == 302
    assert _mrn(env, pid) == "0801-1980-77777"
    assert pid in med.get("/pacientes/", query_string={"q": old}).get_data(as_text=True)
    assert env["db"].execute("SELECT COUNT(*) FROM audit_log WHERE action = 'paciente_editado' AND entity_id = ? AND detail LIKE '%mrn%'",
                             (pid,)).fetchone()[0] == 1


def test_pacientes_que_ya_existian_pasan_al_dni(env):
    from app.views_patients import sync_mrn_with_dni
    med = login(env["app"], "propietario")
    pid = create_patient(med, document_number="0801-1966-55555")
    db = env["db"]
    db.execute("UPDATE patients SET mrn = 'GM-000777' WHERE id = ?", (pid,))      # como estaba antes de v0.25
    db.commit()
    with env["app"].app_context():
        from app.db import get_db
        assert sync_mrn_with_dni(get_db()) == 1
        assert sync_mrn_with_dni(get_db()) == 0                                    # una sola vez
    assert _mrn(env, pid) == "0801-1966-55555"
    assert pid in med.get("/pacientes/", query_string={"q": "GM-000777"}).get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'expediente_numero_dni' AND entity_id = ?", (pid,)).fetchone()[0] == 1
