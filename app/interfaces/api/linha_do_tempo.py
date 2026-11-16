"""SAD-063 — API da linha do tempo (RF-13): processos agrupados e cronologia com relações, fases e evidências."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_login
from app.application.linha_do_tempo.grafo import DocGrafo, Grupo, RelacaoGrafo, linha_do_tempo
from app.core.config import settings
from app.infrastructure.sqlite.conexao import conectar

router = APIRouter(prefix="/api/sadgd", dependencies=[Depends(require_login)], tags=["SAD-GD"])


def _conn():
    return conectar(settings.database_path, vetores=False)


@router.get("/processos")
def listar_processos(tipo: str | None = None, limite: int = 200):
    conn = _conn()
    try:
        sql = ("SELECT p.id, p.tipo, p.chave, p.titulo, count(dp.documento_id) AS documentos FROM processos p "
               "JOIN documento_processo dp ON dp.processo_id = p.id")
        params = []
        if tipo:
            sql += " WHERE p.tipo = ?"
            params.append(tipo)
        sql += " GROUP BY p.id HAVING documentos > 1 ORDER BY documentos DESC, p.chave LIMIT ?"
        params.append(min(max(limite, 1), 1000))
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


@router.get("/linha-do-tempo")
def obter_linha_do_tempo(processo_id: int | None = None, documento_id: int | None = None):
    if processo_id is None and documento_id is None:
        raise HTTPException(422, "Informe processo_id ou documento_id.")
    conn = _conn()
    try:
        if processo_id is None:
            linha = conn.execute("SELECT processo_id FROM documento_processo WHERE documento_id = ?",
                                 (documento_id,)).fetchone()
            if not linha:
                raise HTTPException(404, "Documento sem processo associado.")
            processo_id = linha[0]
        processo = conn.execute("SELECT id, tipo, chave, titulo FROM processos WHERE id = ?", (processo_id,)).fetchone()
        if not processo:
            raise HTTPException(404, "Processo não encontrado.")
        docs = [dict(r) for r in conn.execute(
            "SELECT d.id, d.tipo_documental, d.numero, d.data_documento, d.titulo, d.caminho_relativo, "
            "d.corpus_origem FROM documentos d JOIN documento_processo dp ON dp.documento_id = d.id "
            "WHERE dp.processo_id = ?", (processo_id,))]
        ids = [d["id"] for d in docs]
        marcadores = ",".join("?" * len(ids))
        relacoes = [dict(r) for r in conn.execute(  # noqa: S608 - apenas marcadores "?"
            "SELECT r.origem_id, r.destino_id, r.tipo, r.confianca, r.justificativa, r.evidencia_trecho_id, "
            f"t.texto, t.dispositivo FROM relacoes r JOIN trechos t ON t.id = r.evidencia_trecho_id "
            f"WHERE r.origem_id IN ({marcadores}) AND r.destino_id IN ({marcadores})", ids + ids)]
    finally:
        conn.close()
    grafo_docs = [DocGrafo(d["id"], d["tipo_documental"] or "outro", d["numero"],
                           date.fromisoformat(d["data_documento"]) if d["data_documento"] else None, d["titulo"],
                           d["corpus_origem"], []) for d in docs]
    grafo_rel = [RelacaoGrafo(r["origem_id"], r["destino_id"], r["tipo"], r["confianca"], r["evidencia_trecho_id"],
                              r["justificativa"] or "") for r in relacoes]
    tl = linha_do_tempo(Grupo((processo["tipo"], processo["chave"]), ids), grafo_docs, grafo_rel)
    por_id = {d["id"]: d for d in docs}
    return {
        "processo": dict(processo),
        "eventos": [{"documento_id": e.documento, "data": e.data.isoformat() if e.data else None,
                     "tipo_documental": e.tipo_documental, "titulo": e.titulo,
                     "arquivo": por_id[e.documento]["caminho_relativo"]} for e in tl.eventos],
        "relacoes": [{"origem": r["origem_id"], "destino": r["destino_id"], "tipo": r["tipo"],
                      "confianca": r["confianca"], "justificativa": r["justificativa"],
                      "evidencia": {"trecho_id": r["evidencia_trecho_id"], "dispositivo": r["dispositivo"],
                                    "texto": (r["texto"] or "")[:400]}} for r in relacoes],
        "fases": [{"nome": f.nome, "inicio": f.inicio.isoformat() if f.inicio else None, "documentos": f.documentos}
                  for f in tl.fases],
        "inconsistencias": tl.inconsistencias,
    }
