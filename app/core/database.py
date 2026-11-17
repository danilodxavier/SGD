"""Acesso ao banco SQLite e criação do esquema."""
import sqlite3
from contextlib import contextmanager

from app.core.config import settings

# Tabelas de acesso (herdadas da v1). O restante do esquema é do SAD-GD, em migrações versionadas
# (app/infrastructure/sqlite/migracoes; a 006 removeu as tabelas da v1).
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    profile TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    last_login_at TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT,
    expires_at TEXT NOT NULL,
    ip TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
"""


def connect():
    path = settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    preparar_esquema_sadgd()


def preparar_esquema_sadgd():
    """Aplica as migrações versionadas do SAD-GD no mesmo arquivo de banco (ADR-006: banco único)."""
    from app.infrastructure.sqlite.conexao import conectar, migrar

    conn = conectar(settings.database_path)
    try:
        return migrar(conn)
    finally:
        conn.close()


def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_documents_root():
    """Diretório documental: o definido no painel prevalece sobre o .env."""
    return get_setting("documents_root") or settings.documents_root
