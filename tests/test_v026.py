"""v0.26.0: plantillas de hallazgos por patología (del Word del Dr. Lainez), con menú en cada segmento del informe."""
import json
import re

from conftest import create_patient, csrf, login
from tests.test_fase3 import new_proc
from app import endo_templates as ET


def test_textos_del_word_cargados_y_ubicados():
    titles = {(k, s, t) for k, s, t, *_ in ET.SEED}
    assert ("eda", "esofago", "Várices esofágicas F3") in titles and ("eda", "estomago", "Gastropatía hipertensiva") in titles
    assert ("eda", "duodeno", "Linfangiectasia duodenal") in titles and ("colonoscopia", "colon", "Colitis ulcerosa") in titles
    assert ("eda", "recomendaciones", "Cuidados post ligadura de várices") in titles
    assert ("rectosigmoidoscopia", "rectosigmoides", "Hemorroides y fisura") in titles
    secs = {k: {s for s, _ in v} for k, v in ET.SECTIONS.items()}
    assert all(s in secs[k] for k, s, *_ in ET.SEED) and len({(k, t) for k, s, t, *_ in ET.SEED}) == len(ET.SEED)
    gist = next(x for x in ET.SEED if x[2].startswith("GIST"))
    assert gist[4] == "GIST de …"


def test_menu_en_cada_segmento_del_informe(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    eda = new_proc(med, pid, tok, "eda")
    html = med.get(f"/procedimientos/{eda}").get_data(as_text=True)
    for target in ("nar-esofago", "nar-ueg", "nar-estomago", "nar-duodeno", "recommendations"):
        assert f'data-tpl-target="{target}"' in html, target
    data = json.loads(re.search(r'data-tpl="([^"]*)"', html).group(1).replace("&#34;", '"').replace("&quot;", '"'))
    assert any(v["t"] == "Acalasia" and "caída al vacío" in v["b"] for v in data.values())
    col = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{col}").get_data(as_text=True)
    assert 'data-tpl-target="nar-colon"' in html and "Colitis ulcerosa" in html and "Acalasia" not in html


def test_editar_agregar_y_quitar_del_menu(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    html = med.get("/endoscopia/plantillas?tipo=eda").get_data(as_text=True)
    assert "Mis plantillas de hallazgos" in html and "Gastropatía hipertensiva" in html
    db = env["db"]
    org = env["org"]["org_id"]
    tid = db.execute("SELECT id FROM endo_templates WHERE org_id = ? AND title = 'Acalasia'", (org,)).fetchone()[0]
    r = med.post("/endoscopia/plantillas", data={"csrf_token": tok, "tipo": "eda", "id": tid, "action": "guardar", "section": "esofago",
                                                  "title": "Acalasia tipo II", "body": "Texto corregido.", "conclusion": "Acalasia"})
    assert r.status_code == 302
    assert db.execute("SELECT title, body, conclusion FROM endo_templates WHERE id = ?", (tid,)).fetchone()[:] == ("Acalasia tipo II", "Texto corregido.", "Acalasia")
    med.post("/endoscopia/plantillas", data={"csrf_token": tok, "tipo": "eda", "id": tid, "action": "desactivar"})
    pid = create_patient(med)
    eda = new_proc(med, pid, tok, "eda")
    assert "Acalasia tipo II" not in med.get(f"/procedimientos/{eda}").get_data(as_text=True)
    med.post("/endoscopia/plantillas", data={"csrf_token": tok, "tipo": "eda", "action": "agregar", "section": "duodeno",
                                              "title": "Mi plantilla nueva", "body": "Texto nuevo de duodeno."})
    assert "Mi plantilla nueva" in med.get(f"/procedimientos/{eda}").get_data(as_text=True)
    # sección que no corresponde al tipo de estudio → no se guarda
    med.post("/endoscopia/plantillas", data={"csrf_token": tok, "tipo": "eda", "action": "agregar", "section": "colon", "title": "X", "body": "Y"})
    assert db.execute("SELECT COUNT(*) FROM endo_templates WHERE title = 'X'").fetchone()[0] == 0
    assert login(env["app"], "recepcion").get("/endoscopia/plantillas").status_code == 403


def test_carga_una_sola_vez(env):
    with env["app"].app_context():
        from app.db import get_db
        db = get_db()
        org = env["org"]["org_id"]
        assert ET.ensure_seed(db, org) == len(ET.SEED)
        assert ET.ensure_seed(db, org) == 0
