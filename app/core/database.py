"""Acesso ao banco SQLite e criação do esquema."""
import sqlite3
from contextlib import contextmanager

from app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    full_path TEXT NOT NULL UNIQUE,
    relative_path TEXT,
    extension TEXT,
    size INTEGER,
    hash TEXT,
    modified_at TEXT,
    mtime REAL,
    indexed_at TEXT,
    status TEXT,
    mime_type TEXT,
    pages INTEGER,
    doc_type TEXT,
    ordinal INTEGER DEFAULT 0,
    contract_ref TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_documents_hash ON documents(hash);
CREATE INDEX IF NOT EXISTS ix_documents_contract ON documents(contract_ref);

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_number INTEGER,
    text TEXT,
    page INTEGER,
    section TEXT,
    start_offset INTEGER,
    end_offset INTEGER
);
CREATE INDEX IF NOT EXISTS ix_chunks_document ON document_chunks(document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, filename, tokenize = "unicode61 remove_diacritics 2"
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY,
    contract_number TEXT,
    process_number TEXT,
    contractor TEXT,
    cnpj TEXT,
    object TEXT,
    value TEXT,
    signature_date TEXT,
    start_date TEXT,
    end_date TEXT,
    term TEXT,
    source_document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contract_items (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    item_number TEXT,
    description TEXT,
    quantity TEXT,
    unit TEXT,
    unit_value TEXT,
    total_value TEXT,
    source_document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checklist (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id INTEGER PRIMARY KEY,
    checklist_id INTEGER REFERENCES checklist(id) ON DELETE CASCADE,
    description TEXT,
    requirement TEXT,
    priority TEXT
);

CREATE TABLE IF NOT EXISTS checklist_matches (
    id INTEGER PRIMARY KEY,
    checklist_item_id INTEGER REFERENCES checklist_items(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    status TEXT,
    confidence TEXT,
    justification TEXT
);

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

CREATE TABLE IF NOT EXISTS index_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT,
    finished_at TEXT,
    documents_root TEXT,
    found INTEGER,
    new INTEGER,
    changed INTEGER,
    unchanged INTEGER,
    removed INTEGER,
    errors INTEGER,
    status TEXT
);
"""

# Colunas acrescentadas após a primeira versão: criadas sem perder dados existentes.
MIGRATIONS = {
    "documents": {
        "ocr": "TEXT",  # mecanismo de OCR já aplicado (None = nunca tentado)
        "ocr_pages": "INTEGER",
    },
    "contract_items": {
        "contract_ref": "TEXT",
        "location": "TEXT",
    },
    "checklist": {
        "created_by": "INTEGER",  # usuário que criou (pode editar/excluir, além dos administradores)
        "contract_ref": "TEXT",
        "source_text": "TEXT",
        "updated_at": "TEXT",
        "last_run_at": "TEXT",
    },
    "checklist_items": {
        "position": "INTEGER",
        "category": "TEXT",
        "status": "TEXT",
        "confidence": "TEXT",
        "justification": "TEXT",
        "evaluated_at": "TEXT",
    },
    "checklist_matches": {
        "page": "INTEGER",
        "section": "TEXT",
        "evidence": "TEXT",
    },
}


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
        for table, columns in MIGRATIONS.items():
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for column, kind in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


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
