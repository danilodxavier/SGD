"""Pré-carregamento dos modelos ao iniciar o servidor (em segundo plano).

Sem ele, a 1ª pergunta após cada reinício pagava ≈ 20–25 s de carga (bge-m3 na CPU + reranker na GPU + LLM no Ollama);
as seguintes buscam em 1–2 s. Ordem: reranker primeiro (o Ollama dimensiona as camadas na GPU com o que sobra),
depois o embedder e o LLM. Falhas não impedem o servidor de atender — o carregamento sob demanda continua valendo.
"""
import json
import logging
import threading
import time
import urllib.request

log = logging.getLogger("agente.aquecimento")  # hierarquia com handler em data/logs/app.log


def _aquecer_llm(url, modelo, timeout=180):
    corpo = json.dumps({"model": modelo, "prompt": "ok", "stream": False, "options": {"num_predict": 1}}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/generate", data=corpo,  # noqa: S310 - URL local de config
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=timeout).read()  # noqa: S310 - URL local de config


def aquecer(reranker=None, embedder=None, llm=None):
    """Executa as etapas na ordem; cada uma é uma função sem argumentos (None = pula). Devolve {etapa: ms | erro}."""
    resultado = {}
    for nome, etapa in (("reranker", reranker), ("embedder", embedder), ("llm", llm)):
        if etapa is None:
            continue
        inicio = time.perf_counter()
        try:
            etapa()
            resultado[nome] = int((time.perf_counter() - inicio) * 1000)
        except Exception as exc:  # noqa: BLE001 - aquecimento é oportunista
            resultado[nome] = f"falhou: {type(exc).__name__}"
    log.info("Modelos pré-carregados: %s", resultado)
    return resultado


def aquecer_em_segundo_plano():
    from app.core.config import settings
    from app.infrastructure.modelos import compartilhados

    def tarefa():
        aquecer(reranker=lambda: compartilhados.reranker().pontuar("aquecimento", ["aquecimento"]),
                embedder=lambda: compartilhados.embedder().embed(["aquecimento"]),
                llm=lambda: _aquecer_llm(settings.ollama_url, settings.llm_modelo_padrao))

    t = threading.Thread(target=tarefa, name="aquecimento-modelos", daemon=True)
    t.start()
    return t
