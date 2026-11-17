"""SAD-076 — API de perguntas (RF-01, RF-15 a RF-18, RF-24): orquestrador multiagentes com auditoria.

Os modelos de recuperação (bge-m3 + reranker) rodam por padrão na CPU (`SADGD_DISPOSITIVO_RECUPERACAO`), deixando
a GPU de 6 GB para o LLM do Ollama. O orquestrador é criado sob demanda e reaproveitado (singleton)."""
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import require_login
from app.core.config import settings
from app.domain.politicas import AVISO_DECISAO
from app.infrastructure.sqlite.auditoria import AuditoriaSqlite, TracerDaConsulta
from app.infrastructure.sqlite.conexao import conectar

router = APIRouter(prefix="/api/sadgd", dependencies=[Depends(require_login)], tags=["SAD-GD"])

_lock = threading.Lock()
_componentes = {}


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=3, max_length=2000)


def _fabrica():
    return conectar(settings.database_path)


def _fabrica_sem_vetores():
    return conectar(settings.database_path, vetores=False)


def _modelos_recuperacao():
    """bge-m3 + reranker compartilhados por trechos, decisões e indexação (um único carregamento por processo)."""
    from app.infrastructure.modelos import compartilhados

    return compartilhados.embedder(), compartilhados.reranker()


def memoria_decisoes():
    from app.application.decisoes.memoria import MemoriaDecisoes
    from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite

    if "memoria" not in _componentes:
        embedder, reranker = _modelos_recuperacao()
        _componentes["memoria"] = MemoriaDecisoes(RepositorioDecisoesSqlite(_fabrica), embedder, reranker)
    return _componentes["memoria"]


def construir_orquestrador(tracer=None):
    """Monta o pipeline real (recuperação híbrida + rerank, ResponderF1 verificado, especialistas no Ollama)."""
    from app.application.agentes.orquestrador import Orquestrador
    from app.application.agentes.verificador import verificar
    from app.application.recuperacao.hibrida import RecuperadorHibrido
    from app.application.respostas.f1 import ResponderF1
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.sqlite.busca import BuscaLexicalSqlite, RepositorioTrechosSqlite
    from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite
    from app.infrastructure.sqlite.vetores import SqliteVecStore

    if "recuperador" not in _componentes:
        embedder, reranker = _modelos_recuperacao()
        _componentes["recuperador"] = RecuperadorHibrido(
            BuscaLexicalSqlite(_fabrica), RepositorioTrechosSqlite(_fabrica), embedder, SqliteVecStore(_fabrica),
            reranker)
    rec, memoria = _componentes["recuperador"], memoria_decisoes()
    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", settings.llm_modelo_padrao, timeout=300)
    grafo = RepositorioGrafoSqlite(_fabrica_sem_vetores)
    return Orquestrador(lambda p, k: rec.recuperar(p, k=k), ResponderF1(llm, conflitos=grafo, verificador=verificar),
                        llm, linha_do_tempo=grafo.resumo,
                        precedentes=lambda p, docs: memoria.precedentes(p, documento_ids=docs), tracer=tracer)


def _fonte(t):
    return {"trecho_id": t.id, "documento_id": t.documento_id, "titulo": t.titulo, "arquivo": t.caminho_relativo,
            "pagina": t.pagina, "dispositivo": t.dispositivo, "texto": t.texto[:600],
            "situacao_norma": t.situacao_norma, "revogado": t.revogado}


def serializar(estado):
    decisao, r = estado["decisao"], estado["resposta"]
    base = {"rota": decisao.rota, "agentes": decisao.agentes, "justificativa_rota": decisao.justificativa,
            "resposta": r.resposta, "fontes": [_fonte(t) for t in r.fontes], "observacoes": r.observacoes,
            "tokens": {"entrada": r.tokens_entrada, "saida": r.tokens_saida},
            "tempos_ms": dict(estado.get("tempos", [])), "aviso": AVISO_DECISAO}
    if decisao.rota == "F2":
        from app.application.decisoes.recomendacao import elementos_rf20

        base.update(confianca=r.dados.get("confianca"), recomendacao=r.dados, valido=r.valido,
                    elementos_rf20=elementos_rf20(r.dados),
                    pareceres=[{"agente": p.agente, "valido": p.valido_reparado, "parecer": p.dados}
                               for p in r.pareceres])
    else:
        base.update(classificacao=r.classificacao, confianca=r.confianca, lacunas=r.lacunas)
    return base


@router.post("/perguntar")
def perguntar(corpo: Pergunta, request: Request, user=Depends(require_login)):
    from app.infrastructure.tracing.sqlite_tracer import SqliteTracer

    auditoria = AuditoriaSqlite(_fabrica_sem_vetores)
    consulta_id = auditoria.iniciar(user["id"], corpo.pergunta, request.client.host if request.client else None)
    fabrica = _componentes.get("fabrica_orquestrador", construir_orquestrador)
    inicio = time.perf_counter()
    with _lock:  # um LLM local por vez (GPU de 6 GB)
        try:
            estado = fabrica(TracerDaConsulta(SqliteTracer(_fabrica_sem_vetores), consulta_id)).executar(corpo.pergunta)
        except Exception as exc:  # noqa: BLE001 - erro registrado na auditoria e devolvido de forma genérica
            auditoria.concluir(consulta_id, {}, int((time.perf_counter() - inicio) * 1000))
            raise HTTPException(503, f"Falha ao processar a pergunta ({type(exc).__name__}).") from exc
    latencia = int((time.perf_counter() - inicio) * 1000)
    auditoria.concluir(consulta_id, estado, latencia)
    return {"consulta_id": consulta_id, "latencia_ms": latencia, **serializar(estado)}
