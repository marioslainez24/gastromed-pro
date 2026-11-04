"""v0.23.0: descartar (anular) un informe de endoscopia FINALIZADO, con motivo; no se borra ni cambia su contenido."""
import sqlite3

import pytest

from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version


def _finalized(env, med, tok, pid, kind="colonoscopia", **over):
    proc = new_proc(med, pid, tok, kind)
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc), then="finalizar", **over))
    med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert env["db"].execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "finalizado"
    return proc


def test_descartar_informe_finalizado_con_motivo(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    keep = _finalized(env, med, tok, pid)
    gone = _finalized(env, med, tok, pid)
    db = env["db"]
    sha, data = db.execute("SELECT content_sha256, data FROM procedures WHERE id = ?", (gone,)).fetchone()
    lista = med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert f"/procedimientos/{gone}/anular" in lista and "Motivo (ej.: duplicado" in lista
    assert "Descartar este informe" in med.get(f"/procedimientos/{gone}").get_data(as_text=True)
    # sin motivo no se descarta
    med.post(f"/procedimientos/{gone}/anular", data={"csrf_token": tok, "reason": " "})
    assert db.execute("SELECT discarded_at FROM procedures WHERE id = ?", (gone,)).fetchone()[0] is None
    r = med.post(f"/procedimientos/{gone}/anular", data={"csrf_token": tok, "reason": "Duplicado"})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/pacientes/{pid}/procedimientos")
    lista = med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert gone not in lista and keep in lista
    assert gone not in med.get("/endoscopia").get_data(as_text=True)
    assert med.get(f"/procedimientos/{gone}").status_code == 404
    assert med.get(f"/procedimientos/{gone}/pdf").status_code == 404
    # contenido intacto, motivo y auditoría guardados
    row = db.execute("SELECT status, content_sha256, data, discarded_at FROM procedures WHERE id = ?", (gone,)).fetchone()
    assert row[0] == "finalizado" and row[1] == sha and row[2] == data and row[3]
    assert db.execute("SELECT reason FROM procedure_voids WHERE procedure_id = ?", (gone,)).fetchone()[0] == "Duplicado"
    assert db.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'procedimiento_finalizado_descartado' AND entity_id = ?",
                      (gone,)).fetchone()[0] == 1
    # sigue siendo intocable
    for sql in ("UPDATE procedures SET data = '{}' WHERE id = ?", "UPDATE procedures SET discarded_at = NULL WHERE id = ?",
                "DELETE FROM procedures WHERE id = ?", "UPDATE procedure_voids SET reason = 'x' WHERE procedure_id = ?",
                "DELETE FROM procedure_voids WHERE procedure_id = ?"):
        with pytest.raises(sqlite3.DatabaseError):
            db.execute(sql, (gone,))
    # no se puede descartar dos veces
    assert med.post(f"/procedimientos/{gone}/anular", data={"csrf_token": tok, "reason": "otra vez"}).status_code == 404


def test_reglas_de_la_base_para_descartar(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    fin = _finalized(env, med, tok, pid)
    draft = new_proc(med, pid, tok, "eda")
    db = env["db"]
    # un finalizado no se puede marcar como descartado sin registrar la anulación
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE procedures SET discarded_at = '2026-11-03', discarded_by = author_id WHERE id = ?", (fin,))
    # la anulación solo es para finalizados
    uid = db.execute("SELECT author_id FROM procedures WHERE id = ?", (draft,)).fetchone()[0]
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("INSERT INTO procedure_voids(id, org_id, procedure_id, reason, voided_by, voided_at) VALUES ('v1', ?, ?, 'xxx', ?, 'x')",
                   (env["org"]["org_id"], draft, uid))
    # con la anulación registrada, solo se puede cambiar la marca de descartado; nada más
    db.execute("INSERT INTO procedure_voids(id, org_id, procedure_id, reason, voided_by, voided_at) VALUES ('v2', ?, ?, 'Duplicado', ?, 'x')",
               (env["org"]["org_id"], fin, uid))
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE procedures SET discarded_at = 'x', discarded_by = ?, data = '{}' WHERE id = ?", (uid, fin))
    db.execute("UPDATE procedures SET discarded_at = 'x', discarded_by = ? WHERE id = ?", (uid, fin))
    db.rollback()


def test_quien_puede_descartar(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    proc = _finalized(env, med, tok, pid)
    otro = login(env["app"], "medico")
    assert f"/procedimientos/{proc}/anular" not in otro.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    assert otro.post(f"/procedimientos/{proc}/anular", data={"csrf_token": csrf(otro), "reason": "Duplicado"}).status_code == 409
    assert login(env["app"], "recepcion").post(f"/procedimientos/{proc}/anular", data={"csrf_token": tok, "reason": "x"}).status_code in (403, 400)


def test_descartado_no_cuenta_en_estadisticas_ni_busqueda(env):
    from datetime import date
    from app.views_stats import compute
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    a = _finalized(env, med, tok, pid, conclusion="Hallazgo único ficticio XYZ.")
    _finalized(env, med, tok, pid)
    with env["app"].test_request_context():
        from app.db import get_db
        before = compute(get_db(), env["org"]["org_id"], date(2026, 1, 1), date(2026, 12, 31))["totals"]["colonoscopia"]
    assert "Hallazgo único ficticio" in med.get("/buscar-expedientes?q=XYZ").get_data(as_text=True)
    med.post(f"/procedimientos/{a}/anular", data={"csrf_token": tok, "reason": "Error de paciente"})
    with env["app"].test_request_context():
        from app.db import get_db
        after = compute(get_db(), env["org"]["org_id"], date(2026, 1, 1), date(2026, 12, 31))["totals"]["colonoscopia"]
    assert after == before - 1
    assert "Hallazgo único ficticio" not in med.get("/buscar-expedientes?q=XYZ").get_data(as_text=True)
