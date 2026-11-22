"""Atualização das fichas de contrato ao fim de cada indexação (ADR-015).

Chamada pelo serviço de indexação do servidor (upload/atualização pela tela Acervo) e pelo `scripts/sadgd/indexar.py`.
O inventário de cada contrato é sempre refeito (rápido, sem LLM); a extração com o LLM local só roda para contratos
novos ou fichas sem a 2ª passada. Falha aqui não invalida a indexação: é registrada e a pergunta segue pelo caminho
completo até a próxima atualização.
"""
import logging

from app.core.config import settings

log = logging.getLogger(__name__)


def atualizar_fichas(fabrica=None, limite_s: float | None = None, ao_progredir=None) -> dict:
    from app.application.fichas.gerar import GerarFichas
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.sqlite.conexao import conectar, migrar
    from app.infrastructure.sqlite.repositorio_fichas import RepositorioFichasSqlite

    if settings.ai_allow_remote:  # fichas usam só o LLM local (dados reais)
        return {"pulada": "AI_ALLOW_REMOTE=true: fichas exigem uso apenas local"}
    fabrica = fabrica or (lambda: conectar(settings.database_path, vetores=False))
    conn = fabrica()
    try:
        migrar(conn)
    finally:
        conn.close()
    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", settings.llm_modelo_padrao, timeout=300)
    gerar = GerarFichas(RepositorioFichasSqlite(fabrica), llm)
    primeira = gerar.executar(limite_s, ao_progredir=ao_progredir)
    segunda = gerar.complementar(limite_s, ao_progredir=ao_progredir)
    _invalidar_cache_da_api()
    log.info("Fichas atualizadas: %s | %s", primeira, segunda)
    return {"primeira_passada": primeira, "segunda_passada": segunda}


def _invalidar_cache_da_api():
    """A consulta guarda as fichas por 60 s; após a atualização, a próxima pergunta já lê as novas."""
    try:
        from app.interfaces.api import perguntar

        consulta = perguntar._componentes.get("fichas")
        if consulta is not None:
            consulta._lido = 0.0
    except Exception:  # noqa: BLE001, S110 - processo sem a API (script): nada a invalidar
        pass
