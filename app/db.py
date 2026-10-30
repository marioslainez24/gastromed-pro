"""Acceso a base de datos (SQLite en modo WAL) y ejecutor de migraciones."""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id() -> str:
    return uuid.uuid4().hex


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["GM"].DATABASE_PATH)
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextmanager
def write_tx(db: sqlite3.Connection):
    """Transacción de escritura exclusiva (BEGIN IMMEDIATE): serializa escrituras concurrentes."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def migrate(path: str) -> list[str]:
    conn = connect(path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL) STRICT")
        done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        applied = []
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if f.stem in done:
                continue
            conn.execute("BEGIN IMMEDIATE")
            try:
                # executescript hace COMMIT implícito; por eso se ejecuta sentencia por sentencia.
                for stmt in _split_sql(f.read_text(encoding="utf-8")):
                    conn.execute(stmt)
                conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (f.stem, utcnow()))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            applied.append(f.stem)
        return applied
    finally:
        conn.close()


def _split_sql(script: str) -> list[str]:
    """Divide un script en sentencias completas (respeta bloques BEGIN...END de triggers)."""
    stmts, buf = [], ""
    for line in script.splitlines(keepends=True):
        if line.strip().startswith("--") and not buf.strip():
            continue
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                stmts.append(buf.strip())
            buf = ""
    if buf.strip():
        stmts.append(buf.strip())
    return stmts


def next_counter(db: sqlite3.Connection, org_id: str, name: str) -> int:
    """Debe llamarse dentro de write_tx."""
    db.execute("INSERT INTO counters(org_id, name, value) VALUES (?, ?, 0) ON CONFLICT DO NOTHING", (org_id, name))
    db.execute("UPDATE counters SET value = value + 1 WHERE org_id = ? AND name = ?", (org_id, name))
    return db.execute("SELECT value FROM counters WHERE org_id = ? AND name = ?", (org_id, name)).fetchone()["value"]
