"""v0.18.0: descartar informes de endoscopia en borrador (no se borran: se ocultan, quedan en la auditoría y no se pueden modificar)."""
import sqlite3

import pytest

from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def test_descartar_borrador_lo_quita_de_las_listas(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    keep = new_proc(med, pid, tok, "eda")
    gone = new_proc(med, pid, tok, "colonoscopia")
    lista = med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert f"/procedimientos/{gone}/descartar" in lista and "✕ Descartar" in lista
    assert f"/procedimientos/{gone}/descartar" in med.get("/endoscopia").get_data(as_text=True)
    assert "Descartar este borrador" in med.get(f"/procedimientos/{gone}").get_data(as_text=True)
    # otro usuario no puede descartar un borrador ajeno
    otro = login(env["app"], "medico")
    assert otro.post(f"/procedimientos/{gone}/descartar", data={"csrf_token": csrf(otro)}).status_code == 409
    r = med.post(f"/procedimientos/{gone}/descartar", data={"csrf_token": tok})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/pacientes/{pid}/procedimientos")
    lista = med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert gone not in lista and keep in lista
    assert gone not in med.get("/endoscopia").get_data(as_text=True)
    assert med.get(f"/procedimientos/{gone}").status_code == 404
    db = env["db"]
    assert db.execute("SELECT discarded_at IS NOT NULL FROM procedures WHERE id = ?", (gone,)).fetchone()[0] == 1   # no se borró
    assert db.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'procedimiento_descartado' AND entity_id = ?", (gone,)).fetchone()[0] == 1
    with pytest.raises(sqlite3.DatabaseError):                                       # descartado = intocable
        db.execute("UPDATE procedures SET data = '{}' WHERE id = ?", (gone,))


def test_informe_finalizado_no_se_puede_descartar(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    proc = new_proc(med, pid, tok)
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), then="finalizar"))
    med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert env["db"].execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "finalizado"
    assert "Descartar" not in med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert med.post(f"/procedimientos/{proc}/descartar", data={"csrf_token": tok}).status_code == 409
    with pytest.raises(sqlite3.DatabaseError):
        env["db"].execute("UPDATE procedures SET discarded_at = '2026-11-01' WHERE id = ?", (proc,))
