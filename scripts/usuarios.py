"""Administración de usuarios por línea de comandos (mientras se construye la pantalla de usuarios).

Ejemplos:
  python scripts/usuarios.py crear-clinica "Clínica Dr. Mario Lainez" medico@ejemplo.hn "Dr. Mario Lainez"
  python scripts/usuarios.py crear-usuario medico@ejemplo.hn recepcion@ejemplo.hn "Nombre Apellido" recepcion
  python scripts/usuarios.py desactivar recepcion@ejemplo.hn
  python scripts/usuarios.py listar

Roles: propietario, medico, enfermeria, recepcion, caja. La contraseña se pide de forma oculta.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.bootstrap import create_organization, create_user  # noqa: E402
from app.config import Config  # noqa: E402
from app.db import connect, migrate, utcnow, write_tx  # noqa: E402
from app.security import DEFAULT_ROLES, password_problems  # noqa: E402


def ask_password() -> str:
    while True:
        p1 = getpass.getpass("Contraseña nueva: ")
        problems = password_problems(p1)
        if problems:
            print("  ✗ " + " ".join(problems))
            continue
        if getpass.getpass("Repita la contraseña: ") != p1:
            print("  ✗ No coinciden.")
            continue
        return p1


def main(argv):
    cfg = Config()
    migrate(cfg.DATABASE_PATH)
    db = connect(cfg.DATABASE_PATH)
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "crear-clinica" and len(argv) == 4:
        org = create_organization(db, argv[1], doctor_display_name=argv[3])
        create_user(db, org, argv[2], argv[3], ask_password(), "propietario", True)
        print("Clínica y usuario propietario creados.")
    elif cmd == "crear-usuario" and len(argv) == 5:
        admin = db.execute("SELECT * FROM users WHERE email = ?", (argv[1].lower(),)).fetchone()
        if not admin or argv[4] not in DEFAULT_ROLES:
            print("Administrador o rol no válido.")
            return 1
        roles = {r["code"]: r["id"] for r in db.execute("SELECT code, id FROM roles WHERE org_id = ?", (admin["org_id"],))}
        site = db.execute("SELECT id FROM sites WHERE org_id = ? ORDER BY created_at LIMIT 1", (admin["org_id"],)).fetchone()
        org = {"org_id": admin["org_id"], "roles": roles, "site_id": site["id"]}
        create_user(db, org, argv[2], argv[3], ask_password(), argv[4], argv[4] in ("propietario", "medico"))
        print("Usuario creado.")
    elif cmd == "desactivar" and len(argv) == 2:
        with write_tx(db):
            n = db.execute("UPDATE users SET active = 0, deactivated_at = ? WHERE email = ?", (utcnow(), argv[1].lower())).rowcount
            db.execute("UPDATE sessions SET revoked_at = ? WHERE revoked_at IS NULL AND user_id IN (SELECT id FROM users WHERE email = ?)",
                       (utcnow(), argv[1].lower()))
        print("Usuario desactivado (sus registros conservan la autoría)." if n else "No existe ese usuario.")
    elif cmd == "listar":
        for u in db.execute("SELECT u.email, u.full_name, r.code, u.active FROM users u JOIN roles r ON r.id = u.role_id ORDER BY u.email"):
            print(f"{u['email']:35s} {u['full_name']:30s} {u['code']:12s} {'activo' if u['active'] else 'desactivado'}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
