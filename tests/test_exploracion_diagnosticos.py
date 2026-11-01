"""v0.13.0: exploración física con clics y diagnósticos de consulta con CIE-10 verificado."""
import html as H
import json
import re

from werkzeug.datastructures import MultiDict

from app import consult_diagnoses as CDX, exam
from conftest import create_patient, csrf, login

N = exam.DEFAULT_NORMAL

# Códigos comprobados en classbrowser.nhs.uk (CIE-10 OMS 5.ª ed.). Si se agrega uno nuevo hay que verificarlo y añadirlo aquí.
VERIFIED = {"R10.1", "R10.4", "R11", "R12", "R13", "R14", "R15", "R19.4", "R16.0", "R17", "R18", "R74.0", "K21.0", "K21.9", "K22.7",
            "K20", "K22.0", "K44.9", "K30", "K29.5", "B98.0", "K29.4", "K25.9", "K26.9", "K31.8", "K58.0", "K58.9", "K59.0", "K59.1",
            "A09.0", "A04.7", "K90.0", "K50.0", "K50.1", "K50.9", "K51.2", "K51.5", "K51.0", "K51.9", "K57.3", "K63.5", "K64.9", "K64.0",
            "K64.1", "K64.2", "K64.3", "K64.5", "K60.0", "K60.1", "K60.3", "K61.0", "K62.5", "K92.0", "K92.1", "K92.2", "K76.0", "K75.8",
            "K70.0", "K70.1", "K70.3", "K74.6", "K76.6", "K72.9", "K74.3", "K75.4", "B18.1", "B18.2", "B15.9", "B16.9", "K71.9", "K75.0",
            "K80.2", "K81.1", "K80.5", "K91.5", "K85.1", "K85.2", "K85.9", "K86.0", "K86.1", "K86.3", "C15.9", "C16.9", "C18.9", "C20",
            "C22.0", "C25.9", "Z80.0", "Z85.0", "Z86.0", "Z93.2", "Z93.3"}


def test_todo_normal_y_sin_marcar():
    r = exam.compose(MultiDict([("general-normal", "1"), ("cardiopulmonar-normal", "1"), ("abdomen-normal", "1")]), "soap", N)
    assert r == {"exploracion_general": N["general"] + " " + N["cardiopulmonar"], "exploracion_abdominal": N["abdomen"]}
    assert exam.compose(MultiDict(), "soap", N) == {}                      # nada marcado: no escribe nada


def test_hallazgos_solo_lo_marcado_y_resto_normal():
    src = MultiDict([("abdomen-inspeccion", "distendido"), ("abdomen-dolor", "epigastrio"), ("abdomen-dolor", "hipocondrio_der"),
                     ("abdomen-signos", "murphy"), ("abdomen-higado_cm", "3"), ("abdomen-peristalsis", "disminuida"), ("abdomen-resto", "1"),
                     ("abdomen-inspeccion", "inventado"), ("general-hallazgos", "ictericia_escleras"), ("rectal-guante", "melena")])
    r = exam.compose(src, "soap", N)
    assert r["exploracion_general"] == "Presenta ictericia de escleras."
    a = r["exploracion_abdominal"]
    assert a.startswith("Abdomen distendido. Doloroso a la palpación en epigastrio y hipocondrio derecho. Con signo de Murphy positivo.")
    assert "Borde hepático a 3 cm por debajo del reborde costal." in a and "Peristalsis disminuida." in a
    assert "Resto de la exploración abdominal sin alteraciones." in a and a.endswith("Guante con melena.")
    assert "inventado" not in a and N["abdomen"] not in a              # con hallazgos no se usa el texto normal


def test_nota_narrativa_y_textos_propios():
    mine = dict(N, abdomen="Abdomen sin datos patológicos (mi texto).")
    r = exam.compose(MultiDict([("abdomen-normal", "1")]), "narrativa", mine)
    assert r == {"narrativa": "Exploración física: Abdomen sin datos patológicos (mi texto)."}


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
    assert ("Esófago y estómago", "Gastritis crónica asociada a Helicobacter pylori", "K29.5 + B98.0", False) in CDX.DIAGNOSES


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
    assert {"g": "Hígado", "t": "Cirrosis hepática", "c": "K74.6", "a": False} in dx
    r = med.post(f"/notas/{nid}/exploracion", data={"csrf_token": tok, "general-normal": "1", "abdomen-dolor": "epigastrio"},
                 headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.get_json()["campos"] == {"exploracion_general": N["general"],
                                                               "exploracion_abdominal": "Doloroso a la palpación en epigastrio."}
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
