"""Persistência do grafo documental: processos, pertinência, relações (método 'regra') e vigência derivada.

A vigência derivada do grafo é gravada com evidência prefixada por "Grafo:" — assim pode ser recalculada sem
apagar a situação vinda da nota de revogação do próprio documento (Fase 4)."""
import re
from datetime import date

from app.application.linha_do_tempo.grafo import DocGrafo
from app.application.respostas.f1 import Conflito

RE_JUSTIFICATIVA = re.compile(r"^(\w+): vigente (.+?) × declarado (.+)$")

PESQUISAVEIS = ("COM_TEXTO", "COM_OCR")


class RepositorioGrafoSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def carregar(self):
        conn = self._conexao()
        try:
            docs = {}
            for r in conn.execute("SELECT id, tipo_documental, numero, data_documento, titulo, corpus_origem "
                                  "FROM documentos WHERE status IN (?, ?)", PESQUISAVEIS):
                data = date.fromisoformat(r["data_documento"]) if r["data_documento"] else None
                docs[r["id"]] = DocGrafo(r["id"], r["tipo_documental"] or "outro", r["numero"], data, r["titulo"],
                                         r["corpus_origem"], [])
            for r in conn.execute("SELECT id, documento_id, texto FROM trechos ORDER BY documento_id, ordem"):
                if r["documento_id"] in docs:
                    docs[r["documento_id"]].trechos.append((r["id"], r["texto"]))
            return [d for d in docs.values() if d.trechos]
        finally:
            conn.close()

    def entre(self, documentos):
        """ConflitosPort: contradições registradas no grafo entre os documentos informados."""
        ids = list(documentos)
        if len(ids) < 2:
            return []
        marcadores = ",".join("?" * len(ids))
        conn = self._conexao()
        try:
            # a interpolação contém apenas marcadores "?"; os ids vão como parâmetros
            linhas = conn.execute(
                f"SELECT origem_id, destino_id, justificativa FROM relacoes WHERE tipo = 'contradicao' "  # noqa: S608
                f"AND origem_id IN ({marcadores}) AND destino_id IN ({marcadores})", ids + ids).fetchall()
        finally:
            conn.close()
        conflitos = []
        for origem, destino, justificativa in linhas:
            if m := RE_JUSTIFICATIVA.match(justificativa or ""):
                campo, vigente, declarado = m.group(1), m.group(2), m.group(3)
                conflitos.append(Conflito(origem, destino, campo, vigente, declarado,
                                          self._trecho_com(origem, vigente), self._trecho_com(destino, declarado)))
        return conflitos

    def _trecho_com(self, documento_id, valor):
        """Trecho do documento que contém literalmente o valor (para a citação da resposta de conflito)."""
        from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite

        conn = self._conexao()
        try:
            linha = conn.execute("SELECT id FROM trechos WHERE documento_id = ? AND instr(texto, ?) > 0 "
                                 "ORDER BY ordem LIMIT 1", (documento_id, valor)).fetchone()
        finally:
            conn.close()
        return RepositorioTrechosSqlite(self._conexao).obter([linha[0]])[0] if linha else None

    def salvar(self, grupos, relacoes, revogados, titulos):
        conn = self._conexao()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM relacoes WHERE metodo = 'regra'")
            conn.execute("DELETE FROM documento_processo")
            conn.execute("DELETE FROM processos")
            for g in grupos:
                pid = conn.execute("INSERT INTO processos (tipo, chave, titulo) VALUES (?, ?, ?)",
                                   (g.chave[0], g.chave[1], titulos.get(g.documentos[0]))).lastrowid
                conn.executemany("INSERT INTO documento_processo (documento_id, processo_id, papel, confianca) "
                                 "VALUES (?, ?, NULL, 1.0)", [(d, pid) for d in g.documentos])
            conn.executemany(
                "INSERT INTO relacoes (origem_id, destino_id, tipo, confianca, metodo, evidencia_trecho_id, "
                "justificativa) VALUES (?, ?, ?, ?, 'regra', ?, ?)",
                [(r.origem, r.destino, r.tipo, r.confianca, r.trecho_id,
                  r.justificativa + (" (revogação parcial)" if r.parcial else ""))
                 for r in relacoes if r.trecho_id])
            conn.execute("UPDATE normas SET situacao = 'vigente', evidencia_situacao = NULL "
                         "WHERE evidencia_situacao LIKE 'Grafo:%'")
            for doc_id, r in revogados.items():
                acao = "revogada" if r.tipo == "revogacao" else "substituída integralmente"
                conn.execute("UPDATE normas SET situacao = 'revogada', evidencia_situacao = ? "
                             "WHERE documento_id = ? AND situacao != 'revogada'",
                             (f"Grafo: {acao} por {titulos.get(r.destino) or r.destino} (trecho T{r.trecho_id})",
                              doc_id))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
