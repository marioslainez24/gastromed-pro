"""Creación de organización, roles, ajustes y usuarios (usado por scripts y pruebas)."""
import json

from .db import new_id, utcnow, write_tx
from .security import DEFAULT_ROLES, hash_password

DEFAULT_DURATIONS = {"primera_vez": 40, "seguimiento": 20, "procedimiento": 60, "teleconsulta": 20}


def create_organization(db, name: str, doctor_display_name: str = "Dr. Mario Lainez",
                        specialty: str = "Gastroenterología, Hepatología y Endoscopia") -> dict:
    org_id, site_id = new_id(), new_id()
    roles = {}
    with write_tx(db):
        db.execute("INSERT INTO organizations(id, name, created_at) VALUES (?,?,?)", (org_id, name, utcnow()))
        db.execute("INSERT INTO sites(id, org_id, name, created_at) VALUES (?,?,?,?)", (site_id, org_id, "Consultorio principal", utcnow()))
        for code, (rname, perms) in DEFAULT_ROLES.items():
            rid = new_id()
            roles[code] = rid
            db.execute("INSERT INTO roles(id, org_id, code, name) VALUES (?,?,?,?)", (rid, org_id, code, rname))
            for p in perms:
                db.execute("INSERT INTO role_permissions(role_id, permission) VALUES (?,?)", (rid, p))
        db.execute("INSERT INTO clinic_settings(org_id, doctor_display_name, specialty, appointment_durations, updated_at)"
                   " VALUES (?,?,?,?,?)", (org_id, doctor_display_name, specialty, json.dumps(DEFAULT_DURATIONS), utcnow()))
    return {"org_id": org_id, "site_id": site_id, "roles": roles}


def create_user(db, org: dict, email: str, full_name: str, password: str, role_code: str, is_practitioner: bool = False) -> str:
    uid = new_id()
    with write_tx(db):
        db.execute("INSERT INTO users(id, org_id, email, full_name, password_hash, role_id, is_practitioner, created_at)"
                   " VALUES (?,?,?,?,?,?,?,?)", (uid, org["org_id"], email.lower(), full_name, hash_password(password),
                                                 org["roles"][role_code], int(is_practitioner), utcnow()))
        db.execute("INSERT INTO user_sites(user_id, site_id) VALUES (?,?)", (uid, org["site_id"]))
    return uid
