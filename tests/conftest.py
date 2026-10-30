import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.bootstrap import create_organization, create_user  # noqa: E402
from app.config import Config  # noqa: E402
from app.db import connect  # noqa: E402

PASSWORDS = {"propietario": "Propietario-Prueba-123", "medico": "Medico-Prueba-123", "enfermeria": "Enfermeria-Prueba-123",
             "recepcion": "Recepcion-Prueba-123", "caja": "Caja-Prueba-123", "otra": "OtraClinica-Prueba-123"}


@pytest.fixture()
def env(tmp_path):
    cfg = Config(ENV="pruebas", DATABASE_PATH=str(tmp_path / "test.sqlite3"), FILES_DIR=str(tmp_path / "archivos"),
                 SECRET_KEY="x" * 40, COOKIE_SECURE=False)
    app = create_app(cfg)
    db = connect(cfg.DATABASE_PATH)
    org = create_organization(db, "Clínica de prueba")
    users = {}
    for role, prac in [("propietario", True), ("medico", True), ("enfermeria", False), ("recepcion", False), ("caja", False)]:
        users[role] = create_user(db, org, f"{role}@prueba.hn", f"Usuario {role}", PASSWORDS[role], role, prac)
    other = create_organization(db, "Otra clínica")
    users["otra"] = create_user(db, other, "otra@prueba.hn", "Médico otra clínica", PASSWORDS["otra"], "propietario", True)
    yield {"app": app, "db": db, "org": org, "other": other, "users": users, "cfg": cfg}
    db.close()


def login(app, role, email=None):
    c = app.test_client()
    page = c.get("/ingresar").get_data(as_text=True)
    tok = re.search(r'name="login_csrf" value="([^"]+)"', page).group(1)
    r = c.post("/ingresar", data={"login_csrf": tok, "email": email or f"{role}@prueba.hn", "password": PASSWORDS[role]})
    assert r.status_code == 302, r.get_data(as_text=True)[:500]
    return c


def csrf(client) -> str:
    html = client.get("/agenda/").get_data(as_text=True)
    if 'name="csrf_token"' not in html:
        html = client.get("/pacientes/").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def create_patient(client, **over):
    data = {"csrf_token": csrf(client), "first_names": "Paciente", "last_names": "De Prueba", "birth_date": "1980-05-10",
            "sex": "femenino", "document_type": "dni", "document_number": "0801198000001", "phone": "+504 9999-0000"}
    data.update(over)
    r = client.post("/pacientes/nuevo", data=data)
    assert r.status_code == 302, r.get_data(as_text=True)[:800]
    return r.headers["Location"].rstrip("/").split("/")[-1]
