"""v0.20.0: personal de endoscopia en Ajustes y menús de endoscopista y asistentes 1–3 en el informe."""
import io
import json

from pypdf import PdfReader

from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def test_personal_de_endoscopia_y_menus_en_el_informe(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    db = env["db"]
    owner = db.execute("SELECT doctor_display_name FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()[0]
    page = med.get("/ajustes/personal-endoscopia").get_data(as_text=True)
    assert owner in page and "Por defecto" in page                                     # el dueño de la cuenta ya viene como endoscopista
    for name in ("Lic. Ana Ficticia", "Lic. Beto Ficticio", "Lic. Carla Ficticia"):
        med.post("/ajustes/personal-endoscopia", data={"csrf_token": tok, "action": "agregar", "role": "asistente", "name": name})
    r = med.post("/ajustes/personal-endoscopia", data={"csrf_token": tok, "action": "agregar", "role": "asistente", "name": "lic. ana ficticia"},
                 follow_redirects=True)
    assert "ya está en la lista" in r.get_data(as_text=True)
    med.post("/ajustes/personal-endoscopia", data={"csrf_token": tok, "action": "agregar", "role": "medico", "name": "Dra. Otra Ficticia"})
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert 'name="endoscopist"' in html and f'<option value="{owner}" selected>' in html               # dueño elegido por defecto
    assert 'name="assistant_3"' in html and "Lic. Carla Ficticia" in html and 'name="assistants"' not in html
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), endoscopist="Dra. Otra Ficticia",
                                                               assistant_1="Lic. Beto Ficticio", assistant_2="Lic. Ana Ficticia"))
    d = json.loads(db.execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert d["endoscopist"] == "Dra. Otra Ficticia" and d["assistants"] == "Lic. Beto Ficticio, Lic. Ana Ficticia"
    pdf = med.get(f"/procedimientos/{proc}/pdf?papel=carta")
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf.data)).pages)
    assert "Endoscopista: Dra. Otra Ficticia" in text and "Asistentes: Lic. Beto Ficticio, Lic. Ana Ficticia" in text
    # desactivar a alguien no cambia el informe y su nombre sigue elegido en ese borrador
    sid = db.execute("SELECT id FROM endo_staff WHERE name = 'Lic. Beto Ficticio'").fetchone()[0]
    med.post("/ajustes/personal-endoscopia", data={"csrf_token": tok, "action": "desactivar", "id": sid})
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert '<option value="Lic. Beto Ficticio" selected>' in html
    # «↑ Primero» cambia el que aparece por defecto
    did = db.execute("SELECT id FROM endo_staff WHERE name = 'Dra. Otra Ficticia'").fetchone()[0]
    med.post("/ajustes/personal-endoscopia", data={"csrf_token": tok, "action": "subir", "id": did})
    nuevo = new_proc(med, pid, tok, "eda")
    assert '<option value="Dra. Otra Ficticia" selected>' in med.get(f"/procedimientos/{nuevo}").get_data(as_text=True)
    # solo quien administra ajustes
    assert login(env["app"], "recepcion").get("/ajustes/personal-endoscopia").status_code == 403


def test_informe_anterior_con_asistentes_escritos_a_mano_se_conserva(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "eda")
    db = env["db"]
    d = json.loads(db.execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    d["assistants"] = "Enfermera Pérez (texto de una versión anterior)"
    db.execute("UPDATE procedures SET data = ? WHERE id = ?", (json.dumps(d), proc))
    db.commit()
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert '<option value="Enfermera Pérez (texto de una versión anterior)" selected>' in html
