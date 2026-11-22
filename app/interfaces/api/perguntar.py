"""SAD-076 — API de perguntas (RF-01, RF-15 a RF-18, RF-24): orquestrador multiagentes com auditoria.

Os modelos de recuperação (bge-m3 + reranker) rodam por padrão na CPU (`SADGD_DISPOSITIVO_RECUPERACAO`), deixando
a GPU de 6 GB para o LLM do Ollama; o reranker pode ir para a GPU (`SADGD_DISPOSITIVO_RERANKER`), quantos trechos
reranquear é `SADGD_PARA_RERANK`. O orquestrador é criado sob demanda e reaproveitado (singleton)."""
import os
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
    usar_cache: bool = True


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


def cache_semantico():
    """Cache semântico (Fase 10). Paráfrases só quando o bge-m3 já está carregado (nunca o carrega só para isso)."""
    from app.application.cache_semantico import CacheSemantico
    from app.infrastructure.modelos import compartilhados
    from app.infrastructure.sqlite.cache_semantico import RepositorioCacheSqlite

    if "cache" in _componentes:
        return _componentes["cache"]
    return CacheSemantico(RepositorioCacheSqlite(_fabrica), compartilhados.carregado("embedder"))


def construir_orquestrador(tracer=None):
    """Monta o pipeline real (recuperação híbrida + rerank, ResponderF1 verificado, especialistas no Ollama)."""
    from app.application.agentes.orquestrador import Orquestrador
    from app.application.agentes.verificador import verificar
    from app.application.recuperacao.hibrida import RecuperadorHibrido
    from app.application.respostas.f1 import ResponderF1
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.llm.provedores import llm_f2_remoto
    from app.infrastructure.sqlite.busca import BuscaLexicalSqlite, RepositorioTrechosSqlite
    from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite
    from app.infrastructure.sqlite.vetores import SqliteVecStore

    if "recuperador" not in _componentes:
        embedder, reranker = _modelos_recuperacao()
        _componentes["recuperador"] = RecuperadorHibrido(
            BuscaLexicalSqlite(_fabrica), RepositorioTrechosSqlite(_fabrica), embedder, SqliteVecStore(_fabrica),
            reranker, para_rerank=int(os.environ.get("SADGD_PARA_RERANK", "24")),
            aberturas=int(os.environ.get("SADGD_ABERTURAS", "3")))  # abertura dos 3 documentos mais relevantes
    rec, memoria = _componentes["recuperador"], memoria_decisoes()
    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", settings.llm_modelo_padrao, timeout=300)
    grafo = RepositorioGrafoSqlite(_fabrica_sem_vetores)
    contexto = int(os.environ.get("SADGD_CONTEXTO_MAX_CHARS", "1200"))  # compressão na F1 e na F2 (A3)
    f1 = ResponderF1(llm, conflitos=grafo, verificador=verificar, contexto_max_chars=contexto)
    return Orquestrador(lambda p, k, **kw: rec.recuperar(p, k=k, **kw).trechos, f1, llm, linha_do_tempo=grafo.resumo,
                        precedentes=lambda p, docs: memoria.precedentes(p, documento_ids=docs), tracer=tracer,
                        llm_f2_remoto=llm_f2_remoto(), envio_externo_permitido=settings.ai_allow_remote,
                        contexto_max_chars=contexto, fichas=fichas().responder, escopo_contrato=fichas().escopo,
                        ficha_decisao=fichas().contexto_decisao)


def fichas():
    """Respostas pela ficha do contrato (pré-processada por scripts/sadgd/gerar_fichas.py): ~1 s, sem LLM."""
    if "fichas" not in _componentes:
        from app.application.fichas.consulta import ResponderPorFicha
        from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite
        from app.infrastructure.sqlite.repositorio_fichas import RepositorioFichasSqlite
        from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite

        _componentes["fichas"] = ResponderPorFicha(RepositorioFichasSqlite(_fabrica_sem_vetores),
                                                   RepositorioTrechosSqlite(_fabrica_sem_vetores),
                                                   conflitos=RepositorioGrafoSqlite(_fabrica_sem_vetores))
    return _componentes["fichas"]


def _fonte(t):
    return {"trecho_id": t.id, "documento_id": t.documento_id, "titulo": t.titulo, "arquivo": t.caminho_relativo,
            "pagina": t.pagina, "dispositivo": t.dispositivo, "texto": t.texto[:600],
            "situacao_norma": t.situacao_norma, "revogado": t.revogado}


def serializar(estado):
    decisao, r = estado["decisao"], estado["resposta"]
    base = {"rota": decisao.rota, "agentes": decisao.agentes, "justificativa_rota": decisao.justificativa,
            "resposta": r.resposta, "fontes": [_fonte(t) for t in r.fontes], "observacoes": r.observacoes,
            "tokens": {"entrada": r.tokens_entrada, "saida": r.tokens_saida},
            "tempos_ms": dict(estado.get("tempos", [])), "aviso": AVISO_DECISAO,
            "provedor_f2": estado.get("provedor_f2"), "ficha": bool(estado.get("via_ficha"))}
    if decisao.rota == "F2":
        from app.application.decisoes.recomendacao import elementos_rf20

        base.update(confianca=r.dados.get("confianca"), recomendacao=r.dados, valido=r.valido,
                    elementos_rf20=elementos_rf20(r.dados),
                    pareceres=[{"agente": p.agente, "valido": p.valido_reparado, "parecer": p.dados}
                               for p in r.pareceres])
    else:
        base.update(classificacao=r.classificacao, confianca=r.confianca, lacunas=r.lacunas)
    return base


class FalhaNaConsulta(Exception):
    pass


def processar(pergunta, usuario_id, ip=None, usar_cache=True, ao_mudar_etapa=None):
    """Cache semântico → orquestrador (um LLM local por vez) → auditoria → cache. Usado pelo endpoint síncrono e
    pela fila de consultas; `ao_mudar_etapa(nó)` informa o andamento à interface."""
    from app.application.consultas.fila import TracerComProgresso
    from app.infrastructure.tracing.sqlite_tracer import SqliteTracer

    from app.infrastructure.sqlite.auditoria import concluir_por_cache
    from app.infrastructure.sqlite.cache_semantico import RepositorioCacheSqlite

    auditoria = AuditoriaSqlite(_fabrica_sem_vetores)
    consulta_id = auditoria.iniciar(usuario_id, pergunta, ip)
    fabrica = _componentes.get("fabrica_orquestrador", construir_orquestrador)
    inicio = time.perf_counter()
    versao = RepositorioCacheSqlite(_fabrica_sem_vetores).versao_do_acervo()
    cache = cache_semantico() if usar_cache else None
    if cache is not None:
        reaproveitada = cache.buscar(pergunta, versao)
        if reaproveitada is not None:
            latencia = int((time.perf_counter() - inicio) * 1000)
            concluir_por_cache(_fabrica_sem_vetores, consulta_id, reaproveitada, latencia)
            return {"consulta_id": consulta_id, "latencia_ms": latencia, "cache": True, **reaproveitada}
    tracer = TracerDaConsulta(SqliteTracer(_fabrica_sem_vetores), consulta_id)
    if ao_mudar_etapa is not None:
        tracer = TracerComProgresso(tracer, ao_mudar_etapa)
    with _lock:  # um LLM local por vez (GPU de 6 GB)
        try:
            estado = fabrica(tracer).executar(pergunta)
        except Exception as exc:  # noqa: BLE001 - erro registrado na auditoria e devolvido de forma genérica
            auditoria.concluir(consulta_id, {}, int((time.perf_counter() - inicio) * 1000))
            raise FalhaNaConsulta(f"Falha ao processar a pergunta ({type(exc).__name__}).") from exc
    latencia = int((time.perf_counter() - inicio) * 1000)
    auditoria.concluir(consulta_id, estado, latencia)
    payload = serializar(estado)
    if usar_cache and not estado.get("via_ficha"):  # a ficha já é instantânea e muda com o acervo
        cache_semantico().gravar(pergunta, payload, versao)  # o embedder pode ter sido carregado agora
    return {"consulta_id": consulta_id, "latencia_ms": latencia, "cache": False, **payload}


@router.post("/perguntar")
def perguntar(corpo: Pergunta, request: Request, user=Depends(require_login)):
    try:
        return processar(corpo.pergunta, user["id"], request.client.host if request.client else None, corpo.usar_cache)
    except FalhaNaConsulta as exc:
        raise HTTPException(503, str(exc)) from exc


def fila():
    """Fila única do servidor (criada sob demanda)."""
    from app.application.consultas.fila import FilaDeConsultas

    if "fila" not in _componentes:
        _componentes["fila"] = FilaDeConsultas(
            lambda c, mudar: processar(c.pergunta, c.usuario_id, c.extras.get("ip"), c.extras.get("usar_cache", True),
                                       mudar))
    return _componentes["fila"]


@router.post("/consultas", status_code=202)
def nova_consulta(corpo: Pergunta, request: Request, user=Depends(require_login)):
    """Enfileira a pergunta e responde na hora com o número e a posição; o resultado é obtido por GET."""
    c = fila().enfileirar(user["id"], corpo.pergunta, ip=request.client.host if request.client else None,
                          usar_cache=corpo.usar_cache)
    return fila().situacao(c.id, user["id"])


@router.get("/consultas/{consulta_id}")
def situacao_da_consulta(consulta_id: int, user=Depends(require_login)):
    situacao = fila().situacao(consulta_id, user["id"])
    if situacao is None:
        raise HTTPException(404, "Consulta não encontrada.")
    return situacao
