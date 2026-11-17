"""Banco de dados: criação, migração sem perda de dados, integridade e exclusões em cascata."""
import sqlite3

from app.core import database
from app.core.config import settings


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_tabelas_do_sad_gd(db):
    """init_db aplica as migrações do SAD-GD (documentos, grafo, decisões, auditoria) sobre o banco único."""
    with sqlite3.connect(settings.database_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
    assert {"documentos", "trechos", "trechos_fts", "normas", "processos", "relacoes", "decisoes", "decisoes_fts",
            "consultas", "consulta_fontes", "pareceres", "auditoria", "spans", "users", "settings"} <= tables


def test_init_db_idempotente(db):
    database.init_db()
    database.init_db()
    with database.get_conn() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_configuracao_persistida(db):
    database.set_setting("documents_root", r"D:\Teste")
    database.set_setting("documents_root", r"D:\Outro")
    assert database.get_documents_root() == r"D:\Outro"

