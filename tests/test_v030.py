"""v0.30.0: con logos, el informe lleva solo los logos arriba (sin el nombre del médico) y el endoscopista debajo de «Atención»."""
import io
import json

from pypdf import PdfReader

from conftest import create_patient, csrf, login
from tests.test_fase3 import full_form, new_proc, version
from tests.test_v027 import _png, _upload


def _text(b):
    return "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(b)).pages)


def test_informe_solo_logos_y_endoscopista_bajo_atencion(env):
    med = login(env["app"], "propietario")
    tok = csrf(med)
    db, org = env["db"], env["org"]["org_id"]
    owner, specialty = db.execute("SELECT doctor_display_name, specialty FROM clinic_settings WHERE org_id = ?", (org,)).fetchone()
    proc = new_proc(med, create_patient(med), tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc)))
    d = json.loads(db.execute("SELECT data FROM procedures WHERE id = ?", (proc,)).fetchone()[0])
    d["endoscopist"], d["endoscopist_2"], d["care_setting"], d["ward"] = "Dr. Ficticio Uno", "Dra. Ficticia Dos", "externa", "Medicina interna"
    db.execute("UPDATE procedures SET data = ? WHERE id = ?", (json.dumps(d), proc))
    db.commit()
    # sin logos: el nombre sigue arriba (para que el informe no quede sin identificar)
    txt = _text(med.get(f"/procedimientos/{proc}/pdf").data)
    assert "Dr. Ficticio Uno" in txt[:txt.index("Paciente:")] and "Endoscopista: Dr. Ficticio Uno" in txt
    assert _upload(med, tok, "logo", _png("red")).status_code == 302
    for style in ("clasico", "formal", "moderno"):
        med.post("/ajustes/estilo-informe", data={"csrf_token": tok, "report_style": style})
        txt = _text(med.get(f"/procedimientos/{proc}/pdf").data)
        head = txt[:txt.index("Paciente:")]
        assert "Dr. Ficticio Uno" not in head and owner not in head and (not specialty or specialty not in head), (style, head)
        assert "INFORME DE" in head
        box = txt[txt.index("Paciente:"):txt.lower().index("indicación")]
        assert "Endoscopista: Dr. Ficticio Uno" in box, style
        assert box.index("Atención:") < box.index("Endoscopista: Dr. Ficticio Uno")
        assert "Ficticia Dos" not in box                       # solo el endoscopista 1 en el recuadro
        assert "Endoscopista 2: Dra. Ficticia Dos" in txt      # el 2 sigue en su sección y en las firmas
