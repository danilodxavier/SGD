"""Conexão SQLite do SAD-GD com sqlite-vec e migrações versionadas (ADR-006)."""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger("sadgd.sqlite")

MIGRACOES = Path(__file__).parent / "migracoes"


class ExtensaoVetorialIndisponivel(RuntimeError):
    pass


def carregar_sqlite_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ExtensaoVetorialIndisponivel("Pacote sqlite-vec não instalado (requirements-ia.txt).") from exc
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)


def conectar(caminho: Path | str, *, vetores: bool = True) -> sqlite3.Connection:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    if vetores:
        carregar_sqlite_vec(conn)
    return conn


def migrar(conn: sqlite3.Connection) -> list[str]:
    """Aplica, em ordem e uma única vez, os scripts NNN_*.sql de migracoes/. Retorna os aplicados agora."""
    conn.commit()
    isolamento_original = conn.isolation_level
    conn.isolation_level = None  # controle explícito da transação: cada migração é atômica
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicadas = {r[0] for r in conn.execute("SELECT versao FROM schema_migrations")}
        novas = []
        for script in sorted(MIGRACOES.glob("[0-9][0-9][0-9]_*.sql")):
            versao = script.stem
            if versao in aplicadas:
                continue
            sql = script.read_text(encoding="utf-8")
            conn.execute("BEGIN")
            try:
                for comando in _comandos(sql):
                    conn.execute(comando)
                conn.execute("INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
                             (versao, datetime.now().isoformat(timespec="seconds")))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                log.exception("Falha na migração %s", versao)
                raise
            log.info("Migração aplicada: %s", versao)
            novas.append(versao)
        return novas
    finally:
        conn.isolation_level = isolamento_original


def _comandos(sql: str):
    """Divide o script em comandos completos (respeita BEGIN...END de gatilhos)."""
    atual = []
    for linha in sql.splitlines():
        if linha.strip().startswith("--") and not atual:
            continue
        atual.append(linha)
        trecho = "\n".join(atual)
        if sqlite3.complete_statement(trecho):
            if trecho.strip():
                yield trecho
            atual = []
    resto = "\n".join(atual).strip()
    if resto and not all(linha.strip().startswith("--") or not linha.strip() for linha in atual):
        raise ValueError(f"Comando SQL incompleto no fim do script: {resto[:80]}")
