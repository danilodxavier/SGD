"""Repositório SQLite do caso de uso IndexarCorpus (tabelas documentos, trechos, normas, indexacoes)."""
import json
from datetime import datetime

from app.application.ingestao.metadados import ESPECIE
from app.domain.normas import EspecieNormativa

ESFERA_PADRAO = {"publico": "federal", "sintetico": "estadual"}


class RepositorioIndexacaoSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def estado(self):
        conn = self._conexao()
        try:
            return {r["caminho"]: (r["id"], r["tamanho"], r["mtime"], r["modelo_embedding"])
                    for r in conn.execute("SELECT id, caminho, tamanho, mtime, modelo_embedding FROM documentos")}
        finally:
            conn.close()

    def salvar(self, doc, trechos):
        md, arq = doc.metadados, doc.arquivo
        conn = self._conexao()
        try:
            conn.execute("BEGIN")
            antigo = conn.execute("SELECT id FROM documentos WHERE caminho = ?", (str(arq.caminho),)).fetchone()
            if antigo:  # reprocessamento: apaga em cascata trechos, FTS (gatilho), vetores (gatilho) e norma
                conn.execute("DELETE FROM documentos WHERE id = ?", (antigo["id"],))
            cur = conn.execute(
                "INSERT INTO documentos (caminho, caminho_relativo, hash, extensao, tamanho, mtime, status,"
                " corpus_origem, tipo_documental, numero, orgao, titulo, data_documento, vigencia_inicio,"
                " vigencia_fim, paginas, erro, indexado_em, processo, motor_ocr)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(arq.caminho), arq.relativo, doc.hash, arq.caminho.suffix.lower(), arq.tamanho, arq.mtime,
                 doc.status, doc.corpus_origem.value, md.tipo_documental, md.numero, md.orgao, md.titulo,
                 _iso(md.data), _iso(md.vigencia_inicio), _iso(md.vigencia_fim), doc.paginas, doc.erro,
                 datetime.now().isoformat(timespec="seconds"), md.processo, doc.motor_ocr))
            doc_id = cur.lastrowid
            ids = []
            for t in trechos:
                c = conn.execute(
                    "INSERT INTO trechos (documento_id, ordem, texto, pagina, dispositivo, tipo_dispositivo, caminho,"
                    " inicio, fim, tokens, revogado, subdispositivos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (doc_id, t.ordem, t.texto, t.pagina, t.dispositivo, t.tipo_dispositivo, t.caminho, t.inicio,
                     t.fim, len(t.texto) // 4, int(t.revogado),
                     json.dumps(t.subdispositivos, ensure_ascii=False) if t.subdispositivos else None))
                ids.append(c.lastrowid)
            especie = ESPECIE.get(md.tipo_documental)
            if especie and especie is not EspecieNormativa.PARECER:
                ano = md.data.year if md.data else None
                conn.execute(
                    "INSERT INTO normas (documento_id, especie, nivel, esfera, numero, ano, situacao,"
                    " evidencia_situacao) VALUES (?,?,?,?,?,?,?,?)",
                    (doc_id, md.tipo_documental, especie.nivel, ESFERA_PADRAO.get(doc.corpus_origem.value),
                     md.numero, ano, md.situacao or "vigente", md.evidencia_situacao))
            conn.execute("COMMIT")
            return ids
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def remover(self, ids_documentos):
        conn = self._conexao()
        try:
            conn.executemany("DELETE FROM documentos WHERE id = ?", [(i,) for i in ids_documentos])
            conn.commit()
        finally:
            conn.close()

    def marcar_modelo(self, ids_documentos, modelo):
        conn = self._conexao()
        try:
            conn.executemany("UPDATE documentos SET modelo_embedding = ? WHERE id = ?",
                             [(modelo, i) for i in ids_documentos])
            conn.commit()
        finally:
            conn.close()

    def registrar_execucao(self, resumo):
        campos = ["inicio", "fim", "raiz", "encontrados", "novos", "alterados", "inalterados", "removidos", "erros",
                  "trechos", "vetores", "segundos", "modelo_embedding"]
        conn = self._conexao()
        try:
            # nomes de colunas vêm da lista constante acima; valores sempre como parâmetros
            conn.execute(f"INSERT INTO indexacoes ({', '.join(campos)}) "  # noqa: S608
                         f"VALUES ({', '.join('?' * len(campos))})",
                         [resumo.get(c) for c in campos])
            conn.commit()
        finally:
            conn.close()


def _iso(d):
    return d.isoformat() if d else None
