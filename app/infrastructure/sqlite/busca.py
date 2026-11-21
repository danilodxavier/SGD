"""Busca lexical (FTS5/BM25) e leitura de trechos com metadados para a recuperação híbrida."""
import json
from pathlib import PurePosixPath

from app.application.portas import ResultadoBusca
from app.application.recuperacao.regras import TrechoRecuperado


class BuscaLexicalSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def buscar(self, expressao, k):
        conn = self._conexao()
        try:
            linhas = conn.execute(
                "SELECT rowid, bm25(trechos_fts, 1.0, 0.5) AS s FROM trechos_fts WHERE trechos_fts MATCH ? "
                "ORDER BY s LIMIT ?", (expressao, k)).fetchall()
        finally:
            conn.close()
        return [ResultadoBusca(r[0], -float(r[1]), "bm25") for r in linhas]


class RepositorioTrechosSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def obter(self, ids):
        if not ids:
            return []
        conn = self._conexao()
        try:
            marcadores = ",".join("?" * len(ids))
            # a interpolação contém apenas marcadores "?"; os valores vão como parâmetros
            linhas = conn.execute(
                "SELECT t.id, t.documento_id, t.texto, t.dispositivo, t.pagina, t.revogado, t.caminho, "  # noqa: S608
                "t.subdispositivos, d.caminho_relativo, d.titulo, d.tipo_documental, d.corpus_origem, "
                "d.data_documento, d.numero, d.processo, "
                "n.situacao FROM trechos t JOIN documentos d ON d.id = t.documento_id "
                "LEFT JOIN normas n ON n.documento_id = d.id "
                f"WHERE t.id IN ({marcadores})", list(ids)).fetchall()
        finally:
            conn.close()
        por_id = {}
        for r in linhas:
            t = TrechoRecuperado(r["id"], r["documento_id"], r["texto"], PurePosixPath(r["caminho_relativo"]).name,
                                 r["caminho_relativo"], r["titulo"], r["dispositivo"], r["pagina"],
                                 r["tipo_documental"], r["corpus_origem"], r["data_documento"], bool(r["revogado"]),
                                 r["situacao"], caminho=r["caminho"],
                                 subdispositivos=json.loads(r["subdispositivos"]) if r["subdispositivos"] else [],
                                 numero=r["numero"], processo=r["processo"])
            por_id[t.id] = t
        return [por_id[i] for i in ids if i in por_id]

    def iniciais(self, documento_ids, ate_ordem=4):
        """Primeiros trechos (ordem ≤ ate_ordem) de cada documento, em ordem — abertura e cláusula do objeto."""
        if not documento_ids:
            return {}
        conn = self._conexao()
        try:
            marcadores = ",".join("?" * len(documento_ids))
            ids = [r[0] for r in conn.execute(
                f"SELECT id FROM trechos WHERE documento_id IN ({marcadores}) AND ordem <= ? "  # noqa: S608
                "ORDER BY documento_id, ordem", [*documento_ids, ate_ordem]).fetchall()]
        finally:
            conn.close()
        por_doc = {}
        for t in self.obter(ids):
            por_doc.setdefault(t.documento_id, []).append(t)
        return por_doc
