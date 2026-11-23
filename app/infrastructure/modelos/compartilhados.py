"""Modelos de recuperação carregados UMA vez por processo e compartilhados (perguntas, precedentes, indexação).

Por padrão na CPU (`SADGD_DISPOSITIVO_RECUPERACAO`), deixando a GPU de 6 GB para o LLM do Ollama."""
import os
import threading

_trava = threading.Lock()
_cache = {}


def dispositivo():
    return os.environ.get("SADGD_DISPOSITIVO_RECUPERACAO", "cpu")


def embedder():
    with _trava:
        if "embedder" not in _cache:
            from app.infrastructure.modelos.embeddings import BgeM3Embedder

            _cache["embedder"] = BgeM3Embedder(dispositivo=dispositivo(), liberar_gpu=dispositivo() != "cpu")
        return _cache["embedder"]


def carregado(nome):
    """Instância já carregada (ou None) — usos oportunistas que não devem disparar o carregamento do modelo."""
    return _cache.get(nome)


def dispositivo_reranker():
    """O cross-encoder é a etapa mais cara da consulta (acervo real: 16,6 s na CPU × 4 s na GPU para 24 trechos
    longos, com ranking idêntico; na CPU ele ainda disputava núcleos com as camadas do LLM). Padrão: GPU quando
    houver (`auto`); `SADGD_DISPOSITIVO_RERANKER=cpu|cuda` força. O embedder da consulta (texto curto) segue na CPU."""
    escolha = os.environ.get("SADGD_DISPOSITIVO_RERANKER", "auto").strip().lower()
    if escolha != "auto":
        return escolha
    try:
        from app.infrastructure.modelos.embeddings import _cuda_ou_cpu

        return _cuda_ou_cpu()
    except ImportError:
        return "cpu"


def reranker():
    with _trava:
        if "reranker" not in _cache:
            from app.infrastructure.modelos.reranker import BgeReranker

            _cache["reranker"] = BgeReranker(dispositivo=dispositivo_reranker(),
                                             max_tokens=int(os.environ.get("SADGD_RERANK_MAX_TOKENS", "512")))
        return _cache["reranker"]
