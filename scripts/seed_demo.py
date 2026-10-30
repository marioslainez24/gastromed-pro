"""Crea una base de datos de DEMOSTRACIÓN con pacientes ficticios y un usuario por rol.

Uso:  python scripts/seed_demo.py
Las contraseñas generadas se guardan en instance/credenciales_demo.txt (archivo excluido del repositorio).
NUNCA use esta base con pacientes reales.
"""
import json
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.bootstrap import create_organization, create_user  # noqa: E402
from app.config import Config  # noqa: E402
from app.db import connect, migrate, new_id, utcnow, write_tx  # noqa: E402
from app.util import normalize  # noqa: E402


def pw() -> str:
    return "Demo-" + secrets.token_urlsafe(9) + "7a"


def main():
    cfg = Config()
    db_path = Path(cfg.DATABASE_PATH)
    if db_path.exists() and "--forzar" not in sys.argv:
        print(f"Ya existe {db_path}. Para recrearla ejecute: python scripts/seed_demo.py --forzar")
        sys.exit(1)
    for suffix in ("", "-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    migrate(str(db_path))
    db = connect(str(db_path))
    org = create_organization(db, "Clínica GastroMed (DEMOSTRACIÓN)")
    creds = []
    users = {}
    for email, name, role, prac in [
        ("medico@demo.gastromed", "Dr. Mario Lainez", "propietario", True),
        ("colaborador@demo.gastromed", "Dra. Ana Ficticia", "medico", True),
        ("enfermeria@demo.gastromed", "Lic. Rosa Ejemplo", "enfermeria", False),
        ("recepcion@demo.gastromed", "Carla Recepción (demo)", "recepcion", False),
        ("caja@demo.gastromed", "Luis Caja (demo)", "caja", False),
    ]:
        p = pw()
        users[role] = create_user(db, org, email, name, p, role, prac)
        creds.append(f"{role:12s} {email:30s} {p}")
    with write_tx(db):
        db.execute("UPDATE clinic_settings SET phones = ?, address = ? WHERE org_id = ?",
                   ("+504 0000-0000 (demo)", "Dirección de demostración, San Pedro Sula", org["org_id"]))

    tz = ZoneInfo("America/Tegucigalpa")
    owner = users["propietario"]
    demo_patients = [
        ("María José", "Ficticia Pérez", "1975-04-12", "femenino", "dni", "0801-1975-00001", "+504 9000-0001", "Tegucigalpa, FM"),
        ("Juan Carlos", "Ejemplo López", "1962-11-30", "masculino", "dni", "0501-1962-00002", "+504 9000-0002", "San Pedro Sula, Cortés"),
        ("Ana Lucía", "Prueba Martínez", "1990-02-03", "femenino", "pasaporte", "DEMO123456", "+504 9000-0003", "La Ceiba, Atlántida"),
        ("Pedro", "Simulado Reyes", "1948-07-21", "masculino", "sin_documento", None, "+504 9000-0004", "Comayagua"),
        ("Sofía", "Demostración Cruz", "2001-09-15", "femenino", "dni", "0801-2001-00005", None, "Choluteca"),
    ]
    pids = []
    with write_tx(db):
        for i, (fn, ln, bd, sex, dt, dn, ph, origin) in enumerate(demo_patients, 1):
            pid = new_id()
            pids.append(pid)
            mrn = f"GM-{i:06d}"
            db.execute("INSERT INTO patients(id, org_id, mrn, first_names, last_names, birth_date, sex, document_type, document_number,"
                       " phone, origin, payer, search_text, created_at, created_by, updated_at, updated_by)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (pid, org["org_id"], mrn, fn, ln, bd, sex, dt, dn, ph, origin, "Particular",
                        " ".join(filter(None, [normalize(fn), normalize(ln), mrn.lower(), "".join(c for c in (dn or "") if c.isdigit()),
                                               "".join(c for c in (ph or "") if c.isdigit())])),
                        utcnow(), owner, utcnow(), owner))
        db.execute("INSERT INTO counters(org_id, name, value) VALUES (?, 'mrn', ?)", (org["org_id"], len(demo_patients)))
        db.execute("INSERT INTO patient_allergies(id, patient_id, substance, reaction, severity, recorded_by, recorded_at)"
                   " VALUES (?,?,?,?,?,?,?)", (new_id(), pids[1], "Penicilina", "Urticaria generalizada", "moderada", owner, utcnow()))
        db.execute("UPDATE patients SET allergy_status = 'con_alergias', clinical_alerts = 'Anticoagulado (demo)' WHERE id = ?", (pids[1],))
        db.execute("UPDATE patients SET allergy_status = 'sin_alergias_conocidas' WHERE id IN (?, ?)", (pids[0], pids[2]))
        today = datetime.now(tz).date()
        slots = [(pids[0], time(8, 0), 40, "primera_vez", "confirmada"), (pids[1], time(9, 0), 20, "seguimiento", "solicitada"),
                 (pids[2], time(9, 30), 60, "procedimiento", "solicitada"), (pids[3], time(11, 0), 20, "seguimiento", "solicitada")]
        for pid, t, mins, typ, st in slots:
            start = datetime.combine(today, t, tz).astimezone(timezone.utc)
            aid = new_id()
            db.execute("INSERT INTO appointments(id, org_id, site_id, practitioner_id, patient_id, appt_type, status, starts_at, ends_at,"
                       " created_at, created_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (aid, org["org_id"], org["site_id"], owner, pid, typ, st, start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        (start + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ"), utcnow(), owner, utcnow()))
            db.execute("INSERT INTO appointment_events(id, appointment_id, at, user_id, action, to_status) VALUES (?,?,?,?,?,?)",
                       (new_id(), aid, utcnow(), owner, "creada", st))
    out = Path(cfg.DATABASE_PATH).parent / "credenciales_demo.txt"
    out.write_text("CREDENCIALES DE DEMOSTRACIÓN (solo datos ficticios)\n\n" + "\n".join(creds) + "\n", encoding="utf-8")
    print("Base de demostración creada en", db_path)
    print("Credenciales guardadas en", out)
    print("\n".join(creds))


if __name__ == "__main__":
    main()
