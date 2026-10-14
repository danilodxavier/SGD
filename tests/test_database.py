"""Banco de dados: criação, migração sem perda de dados, integridade e exclusões em cascata."""
import sqlite3

from app.core import database
from app.core.config import settings
from app.services import checklist


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_tabelas_da_especificacao(db):
    with database.get_conn() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table')")}
        assert {"documents", "document_chunks", "contracts", "contract_items", "checklist", "checklist_items",
                "checklist_matches"} <= tables
        assert {"id", "filename", "full_path", "extension", "size", "hash", "modified_at", "indexed_at", "status",
                "mime_type"} <= _columns(conn, "documents")
        assert {"id", "document_id", "chunk_number", "text", "page", "section", "start_offset",
                "end_offset"} <= _columns(conn, "document_chunks")
        assert {"contract_number", "process_number", "contractor", "cnpj", "object", "value", "signature_date",
                "start_date", "end_date", "term", "source_document_id"} <= _columns(conn, "contracts")
        assert {"contract_id", "item_number", "description", "quantity", "unit", "unit_value", "total_value",
                "source_document_id"} <= _columns(conn, "contract_items")
        assert {"checklist_item_id", "document_id", "status", "confidence",
                "justification"} <= _columns(conn, "checklist_matches")


def test_init_db_idempotente(db):
    database.init_db()
    database.init_db()
    with database.get_conn() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_migracao_de_banco_antigo_preserva_dados(tmp_path, monkeypatch):
    path = tmp_path / "antigo.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE checklist (id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT);
        CREATE TABLE checklist_items (id INTEGER PRIMARY KEY, checklist_id INTEGER, description TEXT,
                                      requirement TEXT, priority TEXT);
        INSERT INTO checklist (name, created_at) VALUES ('Checklist antigo', '2026-01-01');
    """)
    old.commit()
    old.close()
    monkeypatch.setattr(settings, "database_path", path)
    database.init_db()
    with database.get_conn() as conn:
        assert {"contract_ref", "source_text", "last_run_at"} <= _columns(conn, "checklist")
        assert {"position", "status", "justification"} <= _columns(conn, "checklist_items")
        assert conn.execute("SELECT name FROM checklist").fetchone()[0] == "Checklist antigo"


def test_configuracao_persistida(db):
    database.set_setting("documents_root", r"D:\Teste")
    database.set_setting("documents_root", r"D:\Outro")
    assert database.get_documents_root() == r"D:\Outro"


def test_exclusao_do_checklist_remove_itens_e_resultados(indexed):
    c = checklist.create("Teste", "1. Contrato assinado\n2. Certidão do FGTS", "034/2022")
    cid = c["checklist"]["id"]
    checklist.run(cid)
    with database.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM checklist_matches").fetchone()[0] > 0
    checklist.delete(cid)
    with database.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM checklist_matches").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 11  # documentos intactos


def test_reindexacao_nao_duplica_trechos(indexed):
    from app.indexing.indexer import run_index

    with database.get_conn() as conn:
        before = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
        fts_before = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    run_index(force=True)
    with database.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == before
        assert conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == fts_before
        assert conn.execute("SELECT COUNT(*) FROM contract_items").fetchone()[0] == 3
