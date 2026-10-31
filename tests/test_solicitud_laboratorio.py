"""v0.9.0: solicitud de laboratorio como la hoja de papel (secciones, casillas y perfiles)."""
import io

from pypdf import PdfReader

from app import lab_order_catalog as LC
from conftest import create_patient, csrf, login


def test_catalogo_completo_y_perfiles_enlazados():
    names = [n for _, ns in LC.SECTIONS for n in ns]
    assert len(names) == len(set(names)) == len(LC.TESTS)
    assert len(names) > 300
    for n in ("Hemograma Completo", "Calprotectina Fecal", "Anticuerpos Helicobacter pylori Totales IgG, IgM, IgA", "Xpert Carba R",
              "Vitamina D (25-OH)", "Gamma Glutamil Transpeptidasa (GGT)", "LIAT SARS-CoV-2/FLU (PCR)", "Espermograma"):
        assert n in LC.BY_NAME, n
    assert len(LC.PROFILES) == 24
    # casi todos los componentes de los perfiles son pruebas del catálogo; los que no, se imprimen como texto
    comps = [c for _, cs in LC.PROFILES for c in cs]
    missing = {c for c in comps if c not in LC.BY_NAME}
    assert missing <= {"Albúmina", "PSA Total (masculino)", "Microalbuminuria en 24 horas", "Relación PSA libre / PSA total",
                       "Toxo avidez", "Herpes II IgM, IgG"}, missing
    assert all(n in LC.BY_NAME for n in LC.RESULT_CODE)


def test_orden_con_perfil_y_pruebas_sueltas_sin_duplicar(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    html = med.get(f"/ordenes/nueva?patient_id={pid}&order_type=laboratorio").get_data(as_text=True)
    assert "Perfil Pre-operatorio" in html and "Química en sangre" in html and "Biología molecular" in html
    pf = LC.slug("perfil Hepático")
    r = med.post("/ordenes/nueva", data={"csrf_token": tok, "patient_id": pid, "order_type": "laboratorio",
                                         "perfil": [pf, "perfil-inventado"],
                                         "lab": [LC.BY_NAME["TGO (Aspartato)"], LC.BY_NAME["Calprotectina Fecal"], LC.BY_NAME["Ferritina"], "x-falsa"],
                                         "items_text": "Curva de insulina 3 horas", "responsible_id": env["users"]["propietario"],
                                         "priority": "rutina", "indication": "Hipertransaminasemia (ficticio)"})
    assert r.status_code == 302, r.get_data(as_text=True)[:500]
    oid = r.headers["Location"].rsplit("/", 1)[-1]
    items = env["db"].execute("SELECT description, grp, test_code FROM order_items WHERE order_id = ? ORDER BY position", (oid,)).fetchall()
    descs = [i["description"] for i in items]
    assert descs[0].startswith("Perfil Hepático:") and items[0]["grp"] == "Perfiles"
    assert "TGO (Aspartato)" not in descs                  # ya va en el perfil
    assert "Calprotectina Fecal" in descs and "Ferritina" in descs and "Curva de insulina 3 horas" in descs
    calpro = [i for i in items if i["description"] == "Calprotectina Fecal"][0]
    assert calpro["grp"] == "Heces" and calpro["test_code"] == "calpro"
    assert len(items) == 4
    view = med.get(f"/ordenes/{oid}").get_data(as_text=True)
    assert "Heces" in view and "Perfiles" in view
    pdf = med.get(f"/ordenes/{oid}/pdf?papel=carta")
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf.data)).pages)
    for t in ("Perfil Hepático", "Calprotectina Fecal", "Inmunología", "Heces", "Curva de insulina 3 horas"):
        assert t in text, t


def test_orden_vacia_rechazada(env):
    med = login(env["app"], "propietario")
    pid = create_patient(med)
    tok = csrf(med)
    r = med.post("/ordenes/nueva", data={"csrf_token": tok, "patient_id": pid, "order_type": "laboratorio", "priority": "rutina"})
    assert r.status_code == 422 and "Seleccione al menos un estudio" in r.get_data(as_text=True)
