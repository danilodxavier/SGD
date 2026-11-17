"""RepositorioDecisoesPort sobre SQLite: tabela `decisoes`, fontes, FTS5 (`decisoes_fts`) e vetores (`decisoes_vec`)."""
from datetime import datetime

from app.application.decisoes.memoria import Candidato
from app.domain.decisoes import AvaliacaoResultado, Decisao
from app.infrastructure.sqlite.vetores import serializar

CAMPOS = ("id, codigo, processo_id, titulo, contexto, decisao, fundamentos, decisor_perfil, data, resultado, "
          "avaliacao_resultado, corpus_origem, consulta_id")


class RepositorioDecisoesSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def registrar(self, d: Decisao, documento_ids=(), trecho_ids=(), registrado_por=None) -> int:
        conn = self._conexao()
        try:
            valores = (d.processo_id, d.titulo, d.contexto, d.decisao, d.fundamentos, d.decisor_perfil, d.data,
                       d.resultado, d.avaliacao_resultado.value, d.corpus_origem, d.consulta_id)
            existente = conn.execute("SELECT id FROM decisoes WHERE codigo = ?", (d.codigo,)).fetchone() \
                if d.codigo else None
            if existente:  # reimportação idempotente pelo código
                decisao_id = existente[0]
                conn.execute("UPDATE decisoes SET processo_id=?, titulo=?, contexto=?, decisao=?, fundamentos=?, "
                             "decisor_perfil=?, data=?, resultado=?, avaliacao_resultado=?, corpus_origem=?, "
                             "consulta_id=? WHERE id = ?", (*valores, decisao_id))
                conn.execute("DELETE FROM decisao_fontes WHERE decisao_id = ?", (decisao_id,))
            else:
                decisao_id = conn.execute(
                    "INSERT INTO decisoes (processo_id, titulo, contexto, decisao, fundamentos, decisor_perfil, data, "
                    "resultado, avaliacao_resultado, corpus_origem, consulta_id, codigo, registrado_por, criado_em) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*valores, d.codigo, registrado_por, datetime.now().isoformat(timespec="seconds"))).lastrowid
            conn.execute("UPDATE decisoes SET processo_chave = (SELECT chave FROM processos WHERE id = "
                         "decisoes.processo_id) WHERE id = ?", (decisao_id,))
            conn.executemany("INSERT INTO decisao_fontes (decisao_id, documento_id, trecho_id) VALUES (?, ?, ?)",
                             [(decisao_id, doc, None) for doc in documento_ids] +
                             [(decisao_id, None, t) for t in trecho_ids])
            conn.commit()
            return decisao_id
        finally:
            conn.close()

    def obter(self, ids):
        ids = list(ids)
        if not ids:
            return []
        conn = self._conexao()
        try:
            marcadores = ",".join("?" * len(ids))
            linhas = conn.execute(f"SELECT {CAMPOS} FROM decisoes WHERE id IN ({marcadores})", ids).fetchall()  # noqa: S608
            fontes = {}
            for r in conn.execute(f"SELECT decisao_id, documento_id FROM decisao_fontes "  # noqa: S608
                                  f"WHERE documento_id IS NOT NULL AND decisao_id IN ({marcadores})", ids):
                fontes.setdefault(r[0], []).append(r[1])
        finally:
            conn.close()
        por_id = {r[0]: _decisao(r, fontes.get(r[0], [])) for r in linhas}
        return [por_id[i] for i in ids if i in por_id]

    def listar(self, processo_id=None, limite=200):
        conn = self._conexao()
        try:
            sql, params = "SELECT id FROM decisoes", []
            if processo_id is not None:
                sql += " WHERE processo_id = ?"
                params.append(processo_id)
            ids = [r[0] for r in conn.execute(sql + " ORDER BY data DESC, id DESC LIMIT ?", params + [limite])]
        finally:
            conn.close()
        return self.obter(ids)

    def buscar_lexical(self, expressao, k):
        conn = self._conexao()
        try:
            linhas = conn.execute("SELECT rowid, bm25(decisoes_fts, 2.0, 1.0, 1.0, 0.5, 0.5) AS s FROM decisoes_fts "
                                  "WHERE decisoes_fts MATCH ? ORDER BY s LIMIT ?", (expressao, k)).fetchall()
        finally:
            conn.close()
        return [Candidato(r[0], -float(r[1])) for r in linhas]

    def buscar_densa(self, vetor, k):
        conn = self._conexao()
        try:
            linhas = conn.execute("SELECT decisao_id, distance FROM decisoes_vec WHERE embedding MATCH ? AND k = ? "
                                  "ORDER BY distance", (serializar(vetor), k)).fetchall()
        finally:
            conn.close()
        return [Candidato(r[0], 1.0 - float(r[1])) for r in linhas]

    def salvar_vetor(self, decisao_id, vetor, modelo):
        conn = self._conexao()
        try:
            conn.execute("DELETE FROM decisoes_vec WHERE decisao_id = ?", (decisao_id,))
            conn.execute("INSERT INTO decisoes_vec (decisao_id, embedding) VALUES (?, ?)",
                         (decisao_id, serializar(vetor)))
            conn.execute("UPDATE decisoes SET modelo_embedding = ? WHERE id = ?", (modelo, decisao_id))
            conn.commit()
        finally:
            conn.close()

    def atualizar_resultado(self, decisao_id, resultado, avaliacao):
        avaliacao = AvaliacaoResultado(avaliacao).value
        conn = self._conexao()
        try:
            n = conn.execute("UPDATE decisoes SET resultado = ?, avaliacao_resultado = ? WHERE id = ?",
                             (resultado, avaliacao, decisao_id)).rowcount
            conn.commit()
            return n > 0
        finally:
            conn.close()

    def processos_dos_documentos(self, documento_ids):
        ids = list(documento_ids)
        if not ids:
            return set()
        conn = self._conexao()
        try:
            marcadores = ",".join("?" * len(ids))
            sql = f"SELECT processo_id FROM documento_processo WHERE documento_id IN ({marcadores})"  # noqa: S608
            return {r[0] for r in conn.execute(sql, ids)}
        finally:
            conn.close()

    def processo_por_chave(self, chave):
        conn = self._conexao()
        try:
            r = conn.execute("SELECT id FROM processos WHERE chave = ? ORDER BY id LIMIT 1", (chave,)).fetchone()
            return r[0] if r else None
        finally:
            conn.close()

    def documento_por_numero(self, tipo, numero):
        conn = self._conexao()
        try:
            r = conn.execute("SELECT id FROM documentos WHERE tipo_documental = ? AND numero = ? LIMIT 1",
                             (tipo, numero)).fetchone()
            return r[0] if r else None
        finally:
            conn.close()


def _decisao(r, documento_ids):
    return Decisao(id=r[0], codigo=r[1], processo_id=r[2], titulo=r[3], contexto=r[4] or "", decisao=r[5],
                   fundamentos=r[6] or "", decisor_perfil=r[7], data=r[8], resultado=r[9] or "",
                   avaliacao_resultado=r[10], corpus_origem=r[11], consulta_id=r[12], documento_ids=documento_ids)
