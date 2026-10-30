"""Permisos, aislamiento entre organizaciones, auditoría, cabeceras y secretos."""
import re
import sqlite3
from pathlib import Path

import pytest

from conftest import create_patient, csrf, login
from app.security import verify_audit_chain


def _note_and_rx(env, pid):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    with env["db"]:
        env["db"].execute("UPDATE patients SET allergy_status = 'sin_alergias_conocidas', clinical_alerts = 'ALERTA-SECRETA' WHERE id = ?", (pid,))
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                   ).headers["Location"].split("/")[-1]
    med.post(f"/notas/{nid}/guardar", json={"version": 1, "motivo": "MOTIVO-CONFIDENCIAL"}, headers={"X-CSRF-Token": tok})
    r = med.post("/recetas/nueva", data={"csrf_token": tok, "patient_id": pid, "item-0-active_ingredient": "Mesalazina",
                                         "item-0-dose": "1", "item-0-dose_unit": "g", "item-0-route": "oral", "item-0-frequency": "cada 12 h",
                                         "item-0-duration": "30 días", "item-0-quantity": "60"})
    return nid, r.headers["Location"].split("/")[-1]


def test_recepcion_no_accede_a_informacion_clinica(env):
    rec = login(env["app"], "recepcion")
    pid = create_patient(rec)
    nid, rx = _note_and_rx(env, pid)
    html = rec.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert rec.get(f"/pacientes/{pid}").status_code == 200
    assert "ALERTA-SECRETA" not in html and "MOTIVO-CONFIDENCIAL" not in html and "Mesalazina" not in html
    assert "no está disponible para su rol" in html
    for url in [f"/notas/{nid}", f"/recetas/{rx}", f"/recetas/{rx}/pdf", f"/notas/nueva?patient_id={pid}", f"/recetas/nueva?patient_id={pid}"]:
        assert rec.get(url).status_code == 403, url
    tok = csrf(rec)
    assert rec.post(f"/notas/{nid}/adenda", data={"csrf_token": tok, "text": "x"}).status_code == 403
    assert rec.post(f"/pacientes/{pid}/alergias", data={"csrf_token": tok, "substance": "x"}).status_code == 403
    assert rec.get("/ajustes/").status_code == 403
    # El intento queda auditado
    assert env["db"].execute("SELECT COUNT(*) c FROM audit_log WHERE action = 'acceso_denegado'").fetchone()["c"] >= 1


def test_caja_y_enfermeria(env):
    caja = login(env["app"], "caja")
    pid = create_patient(login(env["app"], "propietario"))
    nid, rx = _note_and_rx(env, pid)
    assert caja.get(f"/notas/{nid}").status_code == 403
    assert caja.get("/pacientes/nuevo").status_code == 403
    enf = login(env["app"], "enfermeria")
    assert enf.get(f"/notas/{nid}").status_code == 200  # enfermería puede leer
    tok = csrf(enf)
    assert enf.post(f"/notas/{nid}/guardar", json={"version": 2}, headers={"X-CSRF-Token": tok}).status_code == 403
    assert enf.get(f"/recetas/nueva?patient_id={pid}").status_code == 403


def test_cambiar_identificador_no_expone_otra_organizacion(env):
    mine = login(env["app"], "propietario")
    pid = create_patient(mine)
    nid, rx = _note_and_rx(env, pid)
    otra = login(env["app"], "otra", email="otra@prueba.hn")
    for url in [f"/pacientes/{pid}", f"/pacientes/{pid}/editar", f"/notas/{nid}", f"/recetas/{rx}", f"/recetas/{rx}/pdf",
                f"/agenda/nueva?patient_id={pid}", "/pacientes/../pacientes/abc", "/pacientes/1"]:
        assert otra.get(url).status_code == 404, url
    assert pid not in otra.get("/pacientes/", query_string={"q": "Paciente"}).get_data(as_text=True)
    # Otro médico de la misma clínica no puede editar el borrador ajeno
    col = login(env["app"], "medico")
    assert col.post(f"/notas/{nid}/guardar", json={"version": 2, "motivo": "x"}, headers={"X-CSRF-Token": csrf(col)}).status_code == 403


def test_auditoria_inmutable_y_encadenada(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    med.get(f"/pacientes/{pid}")
    db = env["db"]
    actions = {r["action"] for r in db.execute("SELECT action FROM audit_log")}
    assert {"inicio_sesion_exitoso", "paciente_creado", "expediente_consultado"} <= actions
    assert verify_audit_chain(db) == (True, None)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE audit_log SET action = 'x' WHERE seq = 1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM audit_log")
    # Simulación de manipulación a bajo nivel: se quitan los triggers y se altera un registro → la cadena lo detecta
    db.execute("DROP TRIGGER audit_log_immutable_u")
    db.execute("UPDATE audit_log SET action = 'manipulado' WHERE seq = 2")
    assert verify_audit_chain(db)[0] is False


def test_cabeceras_de_seguridad_y_cookies(env):
    c = env["app"].test_client()
    r = c.get("/ingresar")
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["Cache-Control"] == "no-store"
    med = login(env["app"], "propietario")
    cookie = med.get_cookie("gm_sesion")
    assert cookie is not None and cookie.http_only and cookie.same_site == "Lax"


def test_sesion_revocada_al_salir(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    cookie = med.get_cookie("gm_sesion").value
    med.post("/salir", data={"csrf_token": tok})
    other = env["app"].test_client()
    other.set_cookie("gm_sesion", cookie)  # reutilizar la cookie robada no sirve
    assert other.get("/agenda/").status_code == 302


def test_sin_secretos_en_codigo_ni_frontend():
    root = Path(__file__).resolve().parent.parent
    pattern = re.compile(r"(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|GASTROMED_SECRET_KEY\s*=\s*['\"]?[A-Za-z0-9]{16,})")
    hits = []
    for f in list(root.glob("app/**/*")) + list(root.glob("scripts/*")) + list(root.glob("*.py")) + list(root.glob(".env.example")):
        if f.is_file() and f.suffix in {".py", ".js", ".html", ".css", ".sql", ".example", ".webmanifest", ".md", ""}:
            if pattern.search(f.read_text(encoding="utf-8", errors="ignore")):
                hits.append(str(f))
    assert hits == []
    gi = (root / ".gitignore").read_text()
    for must in [".env", "instance/"]:
        assert must in gi


def test_produccion_exige_clave_y_https(tmp_path):
    from app.config import Config
    with pytest.raises(RuntimeError):
        Config(ENV="produccion", SECRET_KEY="corta", DATABASE_PATH=str(tmp_path / "x.db"))
    with pytest.raises(RuntimeError):
        Config(ENV="produccion", SECRET_KEY="y" * 40, COOKIE_SECURE=False, DATABASE_PATH=str(tmp_path / "x.db"))
