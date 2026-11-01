"""Todas las pantallas cargan sin error para el propietario; ajustes se guardan."""
import re

from conftest import create_patient, csrf, login


def test_todas_las_pantallas_cargan(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    med.post("/agenda/nueva", data={"csrf_token": tok, "patient_id": pid, "practitioner_id": env["users"]["propietario"],
                                    "appt_type": "primera_vez", "starts_local": "2026-11-03T09:00", "duration": "40"})
    aid = env["db"].execute("SELECT id FROM appointments").fetchone()["id"]
    med.post(f"/agenda/cita/{aid}/reprogramar", data={"csrf_token": tok, "version": 1, "starts_local": "2026-11-03T10:00",
                                                       "duration": "40", "detail": "Pidió cambio"})
    n1 = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}).headers["Location"].split("/")[-1]
    med.post(f"/notas/{n1}/guardar", json={"version": 1, "motivo": "Dispepsia", "diagnosticos": "Dispepsia funcional"}, headers={"X-CSRF-Token": tok})
    med.post(f"/notas/{n1}/finalizar", data={"csrf_token": tok, "version": 2})
    n2 = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "subsecuente", "template": "soap"}).headers["Location"].split("/")[-1]
    urls = ["/agenda/", "/agenda/?fecha=2026-11-03", "/agenda/semana?fecha=2026-11-03", "/agenda/mes?fecha=2026-11-03",
            "/agenda/nueva", f"/agenda/nueva?patient_id={pid}", f"/agenda/cita/{aid}", "/pacientes/", "/pacientes/nuevo",
            f"/pacientes/{pid}", f"/pacientes/{pid}/editar", f"/notas/nueva?patient_id={pid}", f"/notas/{n1}", f"/notas/{n2}",
            f"/notas/{n2}?confirmar=1", f"/recetas/nueva?patient_id={pid}", "/ajustes/", "/ajustes/usuarios", "/ajustes/auditoria",
            "/manifest.webmanifest", "/sw.js", "/no-existe"]
    for u in urls:
        r = med.get(u)
        assert r.status_code == (404 if u == "/no-existe" else 200), u
    html = med.get(f"/notas/{n2}").get_data(as_text=True)
    assert "Nota anterior (" in html and "Dispepsia funcional" in html  # se muestra con fecha, no se copia sola
    assert "Dispepsia funcional" not in re.search(r'<textarea name="diagnosticos".*?</textarea>', html, re.S).group(0)
    ev = med.get(f"/agenda/cita/{aid}").get_data(as_text=True)
    assert "reprogramó" in ev and "Pidió cambio" in ev


def test_guardar_ajustes(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    data = {"csrf_token": tok, "version": 1, "doctor_display_name": "Dr. Mario Lainez", "specialty": "Gastroenterología",
            "license_number": "CMH-0000 (prueba)", "address": "Consultorio de prueba", "phones": "+504 0000-0000", "contact_email": "",
            "currency": "HNL", "locale": "es-HN", "phone_prefix": "+504", "timezone": "America/Tegucigalpa", "paper_size": "a4",
            "dur_primera_vez": "45", "dur_seguimiento": "20", "dur_procedimiento": "60", "dur_teleconsulta": "20"}
    assert med.post("/ajustes/", data=data).status_code == 302
    s = env["db"].execute("SELECT * FROM clinic_settings WHERE org_id = ?", (env["org"]["org_id"],)).fetchone()
    assert s["paper_size"] == "a4" and s["license_number"] == "CMH-0000 (prueba)" and '"primera_vez": 45' in s["appointment_durations"]
    assert med.post("/ajustes/", data=dict(data, csrf_token=tok)).status_code == 409  # versión vieja
