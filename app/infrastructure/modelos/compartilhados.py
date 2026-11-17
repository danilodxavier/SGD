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


def reranker():
    with _trava:
        if "reranker" not in _cache:
            from app.infrastructure.modelos.reranker import BgeReranker

            _cache["reranker"] = BgeReranker(dispositivo=dispositivo())
        return _cache["reranker"]
