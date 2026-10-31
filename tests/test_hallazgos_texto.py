"""v0.8.0: descripción de hallazgos por segmento con texto libre, línea Z y botón «Normal»."""
import io

from pypdf import PdfReader

from app import endoscopy_defs as D
from tests.test_fase3 import create_patient, csrf, login, new_proc, version


def base(tok, v, **over):
    f = {"csrf_token": tok, "version": v, "performed_on": "2026-10-29", "indication_category": "diagnostica",
         "indication": "Dispepsia (ficticio)", "consent_obtained": "1", "sedation_type": "moderada", "extent": "segunda_porcion",
         "complete": "1", "conclusion": "Gastritis eritematosa de antro.", "then": "guardar"}
    f.update(over)
    return f


def test_secciones_por_tipo_de_estudio():
    assert [k for k, _ in D.NARRATIVE["eda"]] == ["esofago", "ueg", "estomago", "duodeno"]
    assert [k for k, _ in D.NARRATIVE["colonoscopia"]] == ["colon"]
    for kind in D.KINDS:
        secs, concl = D.normal_texts(None)
        assert all(secs[k] for k, _ in D.NARRATIVE[kind]) and concl[kind]
    assert D.zline_text({"zline": "coincide"}) == "Coincide con la línea Z."
    t = D.zline_text({"zline": "no_coincide", "zline_cm": 36, "hiatus_cm": 39})
    assert "No coincide" in t and "36 cm" in t and "39 cm" in t
    assert D.zline_text({}) == ""


def test_eda_con_texto_por_segmento_y_linea_z_en_pantalla_y_pdf(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    for lab in ("Esófago", "Unión esofagogástrica", "Estómago", "Duodeno", "Todo normal", "Línea Z"):
        assert lab in html
    assert D.DEFAULT_NORMAL_TEXTS["estomago"][:40] in html          # texto del botón Normal disponible
    f = base(tok, version(env, proc), **{"nar-esofago": "Mucosa normal.", "zline": "no_coincide", "zline_cm": "36", "hiatus_cm": "39",
                                        "nar-ueg": "Hernia hiatal por deslizamiento de 3 cm.", "nar-estomago": "Eritema en antro.",
                                        "nar-duodeno": "Normal."})
    med.post(f"/procedimientos/{proc}/guardar", data=f)
    import json
    d = json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert d["narrative"]["estomago"] == "Eritema en antro." and d["zline"] == "no_coincide" and d["zline_cm"] == 36
    r = med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert env["db"].execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "finalizado"
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Descripción de hallazgos" in html and "Eritema en antro." in html and "línea Z a 36 cm" in html
    pdf = med.get(f"/procedimientos/{proc}/pdf?papel=carta")
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf.data)).pages)
    assert "Descripción de hallazgos" in text and "Eritema en antro." in text and "No coincide con la línea Z" in text
    assert "Hernia hiatal por deslizamiento" in text


def test_colonoscopia_un_solo_apartado_y_medidas_ignoradas_si_coincide(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "colonoscopia")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert 'name="nar-colon"' in html and 'name="nar-esofago"' not in html and 'name="zline"' not in html
    med.post(f"/procedimientos/{proc}/guardar", data=base(tok, version(env, proc), extent="ciego", **{"nar-colon": D.DEFAULT_NORMAL_TEXTS["colon"],
                                                                                                       "zline": "coincide", "zline_cm": "30"}))
    import json
    d = json.loads(env["db"].execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    assert d["narrative"] == {"colon": D.DEFAULT_NORMAL_TEXTS["colon"]} and "zline" not in d


def test_finalizar_exige_descripcion_de_hallazgos(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    proc = new_proc(med, pid, tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data=base(tok, version(env, proc)))
    med.post(f"/procedimientos/{proc}/finalizar", data={"csrf_token": tok, "version": version(env, proc)})
    assert env["db"].execute("SELECT status FROM procedures WHERE id = ?", (proc,)).fetchone()[0] == "borrador"
    assert "descripción de hallazgos" in med.get(f"/procedimientos/{proc}").get_data(as_text=True)


def test_textos_normales_personalizables_y_restaurar(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    assert "Textos de estudio normal" in med.get("/endoscopia/textos-normales").get_data(as_text=True)
    form = {"csrf_token": tok}
    for k, v in D.DEFAULT_NORMAL_TEXTS.items():
        form[f"sec-{k}"] = v
    for k, v in D.DEFAULT_NORMAL_CONCLUSION.items():
        form[f"concl-{k}"] = v
    form["sec-estomago"] = "Estómago normal a mi manera (ficticio)."
    med.post("/endoscopia/textos-normales", data=form)
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "eda")
    html = med.get(f"/procedimientos/{proc}").get_data(as_text=True)
    assert "Estómago normal a mi manera (ficticio)." in html
    med.post("/endoscopia/textos-normales", data={"csrf_token": tok, "action": "restaurar"})
    assert env["db"].execute("SELECT endo_normal_texts FROM clinic_settings").fetchone()[0] is None
    # recepción no puede cambiarlos
    rec = login(env["app"], "recepcion")
    assert rec.get("/endoscopia/textos-normales").status_code == 403
