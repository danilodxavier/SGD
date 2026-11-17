"""RepositorioCachePort sobre SQLite: tabela `cache_semantico` (+ vetores em `cache_semantico_vec`)."""
import json
from datetime import datetime

from app.infrastructure.sqlite.vetores import serializar


class RepositorioCacheSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def exato(self, normalizada, versao):
        conn = self._conexao()
        try:
            return [(r[0], r[1], json.loads(r[2])) for r in conn.execute(
                "SELECT id, pergunta_normalizada, resposta_json FROM cache_semantico WHERE pergunta_normalizada = ? "
                "AND versao_indice = ? ORDER BY id DESC", (normalizada, versao))]
        finally:
            conn.close()

    def similares(self, vetor, k):
        conn = self._conexao()
        try:
            return [(r[0], 1.0 - float(r[1])) for r in conn.execute(
                "SELECT cache_id, distance FROM cache_semantico_vec WHERE embedding MATCH ? AND k = ? "
                "ORDER BY distance", (serializar(vetor), k))]
        finally:
            conn.close()

    def obter(self, ids, versao):
        ids = list(ids)
        if not ids:
            return []
        conn = self._conexao()
        try:
            marcadores = ",".join("?" * len(ids))
            sql = (f"SELECT id, pergunta_normalizada, resposta_json FROM cache_semantico "  # noqa: S608
                   f"WHERE versao_indice = ? AND id IN ({marcadores})")
            return [(r[0], r[1], json.loads(r[2])) for r in conn.execute(sql, [versao, *ids])]
        finally:
            conn.close()

    def gravar(self, normalizada, resposta, versao, vetor):
        conn = self._conexao()
        try:
            cid = conn.execute("INSERT INTO cache_semantico (pergunta_normalizada, resposta_json, versao_indice, "
                               "criado_em) VALUES (?, ?, ?, ?)",
                               (normalizada, json.dumps(resposta, ensure_ascii=False, default=str), versao,
                                datetime.now().isoformat(timespec="seconds"))).lastrowid
            if vetor is not None:
                conn.execute("INSERT INTO cache_semantico_vec (cache_id, embedding) VALUES (?, ?)",
                             (cid, serializar(vetor)))
            conn.commit()
            return cid
        finally:
            conn.close()

    def versao_do_acervo(self):
        """Muda a cada indexação, documento, trecho ou decisão novos/alterados → invalida o cache."""
        conn = self._conexao()
        try:
            partes = [conn.execute(sql).fetchone()[0] for sql in (
                "SELECT coalesce(max(id), 0) FROM indexacoes", "SELECT count(*) FROM documentos",
                "SELECT coalesce(max(id), 0) FROM trechos", "SELECT count(*) FROM decisoes",
                "SELECT coalesce(max(id), 0) FROM decisoes",
                "SELECT count(*) FROM decisoes WHERE avaliacao_resultado != 'pendente'")]
            return ":".join(str(p) for p in partes)
        finally:
            conn.close()
