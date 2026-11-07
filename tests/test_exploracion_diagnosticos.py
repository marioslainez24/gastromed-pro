"""v0.13.0: exploración física con clics y diagnósticos de consulta con CIE-10 verificado."""
import html as H
import json
import re

from werkzeug.datastructures import MultiDict

from app import consult_diagnoses as CDX, exam
from conftest import create_patient, csrf, login

N = exam.DEFAULT_NORMAL

# NeuroMed Pro: códigos de la CIE-10 OMS (5.ª ed.) de la lista de neurología. Si se agrega uno nuevo hay que verificarlo y añadirlo aquí.
VERIFIED = {"R51", "R42", "R55", "R56.8", "R25.1", "R26.8", "R20.2", "R47.0", "R47.1", "R41.0", "R41.3", "R40.2", "M62.8",
            "G43.0", "G43.1", "G43.2", "G43.3", "G43.9", "G44.0", "G44.2", "G44.4", "G44.3", "G50.0", "G93.2",
            "G40.1", "G40.2", "G40.3", "G40.6", "G40.9", "G41.9", "G45.9", "I63.3", "I63.4", "I63.5", "I63.9", "I61.9", "I60.9",
            "I67.1", "I65.2", "I69.3", "I48", "G20", "G21.1", "G25.0", "G25.8", "G24.3", "G24.5", "G51.3", "F06.7", "G30.1", "G30.9",
            "F01.9", "G31.8", "F03", "G35", "G36.0", "H46", "G37.3", "G03.9", "G04.9", "B69.0", "G61.0", "G62.9", "E11.4", "G63.2",
            "G56.0", "G57.3", "G51.0", "M54.1", "G70.0", "G71.0", "G12.2", "G47.0", "G47.3", "G47.4", "H81.1", "G91.9", "C71.9",
            "D32.0", "S06.0", "Z82.3"}
NEURO = ("mental", "pares", "motor", "reflejos", "sensibilidad", "coordinacion")


def test_todo_normal_y_sin_marcar():
    src = MultiDict([("general-normal", "1"), ("cardiopulmonar-normal", "1")] + [(f"{k}-normal", "1") for k in NEURO])
    r = exam.compose(src, "soap", N)
    assert r == {"exploracion_general": N["general"] + " " + N["cardiopulmonar"],
                 "exploracion_abdominal": " ".join(N[k] for k in NEURO)}
    assert exam.compose(MultiDict(), "soap", N) == {}                      # nada marcado: no escribe nada


def test_hallazgos_solo_lo_marcado_y_resto_normal():
    src = MultiDict([("motor-debilidad", "msd"), ("motor-debilidad", "mid"), ("motor-grado", "3"), ("motor-patron", "hemiparesia_der"),
                     ("reflejos-babinski", "derecho"), ("pares-facial", "central_der"), ("motor-resto", "1"),
                     ("motor-debilidad", "inventado"), ("general-hallazgos", "mordedura"), ("meninges-signos", "rigidez_nuca")])
    r = exam.compose(src, "soap", N)
    assert r["exploracion_general"] == "Presenta mordedura lateral de lengua."
    a = r["exploracion_abdominal"]
    assert a.startswith("Presenta paresia facial central derecha. Debilidad en miembro superior derecho y miembro inferior derecho.")
    assert "Fuerza 3/5 en el segmento afectado." in a and "Patrón: hemiparesia derecha." in a
    assert "Resto de la exploración motora sin alteraciones." in a and "Signo de Babinski derecho." in a
    assert a.endswith("Presenta rigidez de nuca.")
    assert "inventado" not in a and N["motor"] not in a              # con hallazgos no se usa el texto normal


def test_nota_narrativa_y_textos_propios():
    mine = dict(N, motor="Motor sin datos patológicos (mi texto).")
    r = exam.compose(MultiDict([("motor-normal", "1")]), "narrativa", mine)
    assert r == {"narrativa": "Exploración física: Motor sin datos patológicos (mi texto)."}


def test_catalogo_diagnosticos_consulta_verificado():
    codes = set()
    for g, t, c, a in CDX.DIAGNOSES:
        if c:
            codes.update(x.strip() for x in c.split("+"))
        if a:
            assert c
    assert codes <= VERIFIED, codes - VERIFIED
    texts = [t for _, t, _, _ in CDX.DIAGNOSES]
    assert len(texts) == len(set(texts))
    assert ("Nervio periférico y músculo", "Polineuropatía diabética", "E11.4 + G63.2", False) in CDX.DIAGNOSES


def test_nota_con_exploracion_y_diagnosticos(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    pid = create_patient(med)
    nid = med.post("/notas/nueva", data={"csrf_token": tok, "patient_id": pid, "kind": "primera", "template": "soap"}
                   ).headers["Location"].rsplit("/", 1)[-1]
    html = med.get(f"/notas/{nid}").get_data(as_text=True)
    assert "Exploración física con clics" in html and 'id="exam-form"' in html and 'data-dx-open="f-diagnosticos"' in html
    assert 'id="f-diagnosticos"' in html
    dx = json.loads(H.unescape(re.search(r'data-dx="([^"]*)"', html).group(1)))
    assert {"g": "Epilepsia", "t": "Epilepsia, tipo no especificado", "c": "G40.9", "a": False} in dx
    r = med.post(f"/notas/{nid}/exploracion", data={"csrf_token": tok, "general-normal": "1", "motor-debilidad": "msi"},
                 headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.get_json()["campos"] == {"exploracion_general": N["general"],
                                                               "exploracion_abdominal": "Debilidad en miembro superior izquierdo."}
    assert med.post(f"/notas/{nid}/exploracion", data={"csrf_token": tok}).status_code == 422
    # textos normales propios desde Ajustes, y restaurar
    form = {"csrf_token": tok, **{f"normal-{k}": v for k, v in N.items()}}
    form["normal-general"] = "General normal a mi manera (ficticio)."
    med.post("/ajustes/exploracion-normal", data=form)
    r = med.post(f"/notas/{nid}/exploracion", data={"csrf_token": tok, "general-normal": "1"}, headers={"X-Requested-With": "fetch"})
    assert r.get_json()["campos"]["exploracion_general"] == "General normal a mi manera (ficticio)."
    med.post("/ajustes/exploracion-normal", data={"csrf_token": tok, "action": "restaurar"})
    assert env["db"].execute("SELECT exam_normal_texts FROM clinic_settings").fetchone()[0] is None
    assert login(env["app"], "recepcion").post(f"/notas/{nid}/exploracion", data={"csrf_token": tok}).status_code in (400, 403)
