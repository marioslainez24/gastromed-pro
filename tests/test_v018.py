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
    lista = med.get(f"/pacientes/{pid}/procedimientos").get_data(as_text=True)
    # v0.23.0: el finalizado ya no usa el descarte de borradores; tiene su propio «Descartar» con motivo (/anular)
    assert f"/procedimientos/{proc}/descartar" not in lista and f"/procedimientos/{proc}/anular" in lista
    assert med.post(f"/procedimientos/{proc}/descartar", data={"csrf_token": tok}).status_code == 409
    with pytest.raises(sqlite3.DatabaseError):
        env["db"].execute("UPDATE procedures SET discarded_at = '2026-11-01' WHERE id = ?", (proc,))


def test_descartar_nota_en_borrador(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                   ).headers["Location"].rsplit("/", 1)[-1]
    exp = med.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert f"/notas/{nid}/descartar" in exp and "1 nota(s) de consulta en borrador" in exp
    assert "Descartar esta nota" in med.get(f"/notas/{nid}").get_data(as_text=True)
    otro = login(env["app"], "medico")
    assert otro.post(f"/notas/{nid}/descartar", data={"csrf_token": csrf(otro)}).status_code == 409
    r = med.post(f"/notas/{nid}/descartar", data={"csrf_token": tok})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/pacientes/{pid}")
    exp = med.get(f"/pacientes/{pid}").get_data(as_text=True)
    assert nid not in exp and "en borrador</a>" not in exp
    assert med.get(f"/notas/{nid}").status_code == 404
    assert med.post(f"/notas/{nid}/guardar", data={"csrf_token": tok, "motivo": "x"}).status_code == 404
    db = env["db"]
    assert db.execute("SELECT discarded_at IS NOT NULL FROM clinical_notes WHERE id = ?", (nid,)).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'nota_descartada' AND entity_id = ?", (nid,)).fetchone()[0] == 1
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE clinical_notes SET fields = '{}' WHERE id = ?", (nid,))


def test_nota_finalizada_no_se_descarta(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                   ).headers["Location"].rsplit("/", 1)[-1]
    env["db"].execute("UPDATE clinical_notes SET status = 'finalizada', finalized_at = '2026-11-01T00:00:00Z' WHERE id = ?", (nid,))
    env["db"].commit()
    assert med.post(f"/notas/{nid}/descartar", data={"csrf_token": tok}).status_code == 409
    with pytest.raises(sqlite3.DatabaseError):
        env["db"].execute("UPDATE clinical_notes SET discarded_at = '2026-11-01' WHERE id = ?", (nid,))


def test_hojas_de_preparacion_colonoscopia_y_eda(env):
    import io
    from pypdf import PdfReader
    med = login(env["app"], "propietario")
    tok = csrf(med)
    html = med.get("/endoscopia/hojas?tipo=colonoscopia").get_data(as_text=True)
    assert "Debe comprar 4 sobres de Fortrans." in html and "Texto tomado de su hoja de Word" in html and "Borrador sin revisar" in html
    eda = med.get("/endoscopia/hojas?tipo=eda").get_data(as_text=True)
    assert "PREPARACIÓN PARA ENDOSCOPÍA DIGESTIVA ALTA" in eda and "ayuno completo de al menos 8 horas" in eda
    pid = create_patient(med)
    assert med.get(f"/pacientes/{pid}/hoja/prep/colonoscopia").status_code == 409        # sin aprobar no se imprime
    # aprobar SOLO la preparación de colonoscopía tal cual: el consentimiento sigue sin aprobar
    from app.proc_sheets import PREP_COLONOSCOPIA, DRAFT_CONSENT
    r = med.post("/endoscopia/hojas", data={"csrf_token": tok, "tipo": "colonoscopia", "solo": "prep",
                                            "prep": PREP_COLONOSCOPIA, "consent": DRAFT_CONSENT})
    assert r.status_code == 302
    pdf = med.get(f"/pacientes/{pid}/hoja/prep/colonoscopia")
    assert pdf.status_code == 200
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf.data)).pages)
    assert "Fortrans" in text and "Gelatina sin color rojo" in text and "{telefono}" not in text
    assert med.get(f"/pacientes/{pid}/hoja/consent/colonoscopia").status_code == 409
