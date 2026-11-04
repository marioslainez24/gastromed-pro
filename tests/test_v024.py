"""v0.24.0: licencia por computadora (clave firmada) y titular visible en el programa y en los documentos."""
import base64
import io

import pytest
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from conftest import create_patient, csrf, login
from app import license as L


@pytest.fixture
def keys(monkeypatch):
    k = Ed25519PrivateKey.generate()
    priv = base64.b64encode(k.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption())).decode()
    pub = base64.b64encode(k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)).decode()
    monkeypatch.setattr(L, "PUBLIC_KEY_B64", pub)
    monkeypatch.delenv("GASTROMED_LICENSE_PUBKEY", raising=False)
    monkeypatch.setenv("GASTROMED_MACHINE_ID_TEST", "pc-del-consultorio")
    yield priv
    L.configure(None)


def test_codigo_de_equipo_estable_y_distinto_por_pc():
    a, b = L.machine_code("win:aaaa"), L.machine_code("win:bbbb")
    assert a == L.machine_code("win:aaaa") and a != b and L.CODE_RE.match(a)


def test_clave_valida_solo_en_su_computadora(keys):
    code = L.machine_code()
    clave = L.sign(keys, code, "Dr. Mario Lainez", "2026-11-04")
    assert L.verify(clave)["titular"] == "Dr. Mario Lainez"
    assert L.verify("  " + clave[:40] + "\n" + clave[40:] + " ")["equipo"] == code      # tolera saltos de línea al pegar
    with pytest.raises(L.LicenseError, match="OTRA computadora"):
        L.verify(clave, L.machine_code("win:otra-pc"))
    # clave firmada con OTRA llave (alguien que intenta fabricar claves): no sirve
    otra = base64.b64encode(Ed25519PrivateKey.generate().private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption())).decode()
    with pytest.raises(L.LicenseError, match="no es válida"):
        L.verify(L.sign(otra, code, "Pirata", "2026-11-04"))
    # cambiar el titular dentro de la clave rompe la firma
    head, payload, sig = clave.split(".")
    fake = base64.urlsafe_b64encode(base64.urlsafe_b64decode(payload + "==").replace(b"Mario Lainez", b"Otro Medico!")).decode().rstrip("=")
    with pytest.raises(L.LicenseError):
        L.verify(f"{head}.{fake}.{sig}")
    for bad in ("", "hola", "GM1.x.y"):
        with pytest.raises(L.LicenseError):
            L.verify(bad)


def test_sin_licencia_solo_abre_la_activacion(env, keys, tmp_path):
    L.configure(tmp_path / "licencia.txt")
    c = env["app"].test_client()
    for path in ("/", "/ingresar", "/pacientes", "/configuracion-inicial", "/agenda"):
        r = c.get(path)
        assert r.status_code == 302 and r.headers["Location"].endswith("/activar"), path
    html = c.get("/activar").get_data(as_text=True)
    assert L.machine_code() in html and "Pegue aquí la clave" in html
    # desde otro equipo de la red no se puede activar
    r = c.get("/activar", environ_base={"REMOTE_ADDR": "192.168.1.50"})
    assert r.status_code == 403 and "Pegue aquí" not in r.get_data(as_text=True)


def test_activar_y_reiniciar(env, keys, tmp_path):
    f = tmp_path / "licencia.txt"
    L.configure(f)
    c = env["app"].test_client()
    html = c.get("/activar").get_data(as_text=True)
    import re
    tok = re.search(r'name="activar_csrf" value="([^"]+)"', html).group(1)
    r = c.post("/activar", data={"activar_csrf": tok, "clave": "GM1.no.sirve"})
    assert r.status_code == 422 and "no es válida" in r.get_data(as_text=True) and not f.exists()
    tok = re.search(r'name="activar_csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
    clave = L.sign(keys, L.machine_code(), "Dr. Mario Lainez", "2026-11-04")
    r = c.post("/activar", data={"activar_csrf": tok, "clave": clave})
    assert r.status_code == 302 and f.exists()
    assert c.get("/activar").status_code == 302                       # ya activado
    # al reiniciar el programa lee la licencia guardada
    L.configure(f)
    assert L.active() and L.holder() == "Dr. Mario Lainez"
    # copiada a otra computadora: deja de servir
    import os
    os.environ["GASTROMED_MACHINE_ID_TEST"] = "pc-de-otra-clinica"
    L.configure(f)
    assert not L.active()
    assert c.get("/pacientes").headers["Location"].endswith("/activar")


def test_titular_en_el_programa_y_en_los_pdf(env, keys, tmp_path):
    from pypdf import PdfReader
    from tests.test_fase3 import full_form, new_proc, version
    f = tmp_path / "licencia.txt"
    f.write_text(L.sign(keys, L.machine_code(), "Dr. Mario Lainez", "2026-11-04"))
    L.configure(f)
    med = login(env["app"], "propietario")
    tok = csrf(med)
    assert "Licencia de uso: <b>Dr. Mario Lainez</b>" in med.get("/pacientes/").get_data(as_text=True)
    pid = create_patient(med)
    proc = new_proc(med, pid, tok, "eda")
    med.post(f"/procedimientos/{proc}/guardar", data=full_form(tok, version(env, proc)))
    txt = PdfReader(io.BytesIO(med.get(f"/procedimientos/{proc}/pdf").data)).pages[0].extract_text()
    assert "Licencia de uso: Dr. Mario Lainez" in txt


def test_en_pruebas_y_desarrollo_no_se_exige(env):
    L.configure(None)
    assert L.active() and L.holder() == ""
    assert env["app"].test_client().get("/ingresar").status_code == 200
