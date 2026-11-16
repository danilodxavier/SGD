"""Infraestrutura SQLite do SAD-GD: migrações, FTS5 sincronizado, sqlite-vec, restrições do grafo e tracer."""
import sqlite3
import struct

import pytest

pytest.importorskip("sqlite_vec")

from app.infrastructure.sqlite.conexao import conectar, migrar  # noqa: E402
from app.infrastructure.tracing.sqlite_tracer import SqliteTracer, percentis_latencia  # noqa: E402

TABELAS = {
    "documentos", "trechos", "trechos_fts", "trechos_vec", "normas", "processos", "documento_processo", "relacoes",
    "contratos", "contrato_itens", "decisoes", "decisao_fontes", "decisoes_vec", "consultas", "consulta_fontes",
    "pareceres", "spans", "auditoria", "cache_semantico", "cache_semantico_vec", "schema_migrations",
}


def vetor(*inicio):
    v = list(inicio) + [0.0] * (1024 - len(inicio))
    return struct.pack(f"{len(v)}f", *v)


@pytest.fixture()
def banco(tmp_path):
    caminho = tmp_path / "sadgd.db"
    conn = conectar(caminho)
    migrar(conn)
    yield conn, caminho
    conn.close()


def novo_documento(conn, caminho="a.pdf", origem="sintetico"):
    cur = conn.execute("INSERT INTO documentos (caminho, status, corpus_origem) VALUES (?, 'COM_TEXTO', ?)",
                       (caminho, origem))
    return cur.lastrowid


def novo_trecho(conn, documento_id, texto, ordem=1):
    cur = conn.execute("INSERT INTO trechos (documento_id, ordem, texto, dispositivo) VALUES (?,?,?,?)",
                       (documento_id, ordem, texto, "art. 1º"))
    return cur.lastrowid


def test_migracoes_criam_esquema_completo_e_sao_idempotentes(banco):
    conn, _ = banco
    nomes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table')")}
    assert nomes >= TABELAS
    assert migrar(conn) == []
    assert [r[0] for r in conn.execute("SELECT versao FROM schema_migrations ORDER BY versao")] == \
        ["001_esquema_inicial", "002_vetores"]


def test_fts_acompanha_insercao_e_remocao_em_cascata(banco):
    conn, _ = banco
    doc = novo_documento(conn)
    novo_trecho(conn, doc, "A vigência do contrato será prorrogada por doze meses.")
    conn.commit()
    busca = "SELECT count(*) FROM trechos_fts WHERE trechos_fts MATCH ?"
    assert conn.execute(busca, ("vigencia",)).fetchone()[0] == 1  # remove_diacritics
    conn.execute("DELETE FROM documentos WHERE id = ?", (doc,))
    conn.commit()
    assert conn.execute(busca, ("vigencia",)).fetchone()[0] == 0


def test_busca_vetorial_e_remocao_do_vetor_orfao(banco):
    conn, _ = banco
    doc = novo_documento(conn)
    t1 = novo_trecho(conn, doc, "trecho um", 1)
    t2 = novo_trecho(conn, doc, "trecho dois", 2)
    conn.execute("INSERT INTO trechos_vec (trecho_id, embedding) VALUES (?, ?)", (t1, vetor(1.0, 0.0)))
    conn.execute("INSERT INTO trechos_vec (trecho_id, embedding) VALUES (?, ?)", (t2, vetor(0.0, 1.0)))
    conn.commit()
    linhas = conn.execute("SELECT trecho_id, distance FROM trechos_vec WHERE embedding MATCH ? AND k = 2 "
                          "ORDER BY distance", (vetor(0.9, 0.1),)).fetchall()
    assert [r[0] for r in linhas] == [t1, t2]
    conn.execute("DELETE FROM trechos WHERE id = ?", (t1,))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM trechos_vec").fetchone()[0] == 1


def test_grafo_rejeita_relacao_invalida(banco):
    conn, _ = banco
    a, b = novo_documento(conn, "a.pdf"), novo_documento(conn, "b.pdf")
    t = novo_trecho(conn, b, "Fica revogado o Decreto anterior.")
    sql = ("INSERT INTO relacoes (origem_id, destino_id, tipo, confianca, metodo, evidencia_trecho_id) "
           "VALUES (?,?,?,?,?,?)")
    conn.execute(sql, (b, a, "revogacao", 0.95, "regra", t))
    for invalida in [(a, a, "revogacao", 0.9, "regra", t), (b, a, "parecido", 0.9, "regra", t),
                     (b, a, "aditivo", 1.2, "regra", t)]:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, invalida)


def test_corpus_origem_e_obrigatorio_e_restrito(banco):
    conn, _ = banco
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO documentos (caminho, status, corpus_origem) "
                     "VALUES ('x', 'COM_TEXTO', 'desconhecida')")


def test_tracer_registra_spans_e_calcula_percentis(banco):
    conn, caminho = banco
    tracer = SqliteTracer(lambda: conectar(caminho, vetores=False))
    for i in range(3):
        with tracer.span("roteador", modelo="qwen2.5:7b") as s:
            s.tokens_entrada, s.tokens_saida = 100 + i, 20
    with pytest.raises(RuntimeError), tracer.span("relator"):
        raise RuntimeError("falha simulada")
    linhas = conn.execute("SELECT no, tokens_entrada, erro FROM spans ORDER BY id").fetchall()
    assert [tuple(r) for r in linhas] == [("roteador", 100, None), ("roteador", 101, None),
                                          ("roteador", 102, None), ("relator", 0, "RuntimeError")]
    p = percentis_latencia(conn, "roteador")
    assert p[50] is not None and p[95] >= p[50]
