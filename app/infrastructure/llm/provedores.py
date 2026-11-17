"""Provedores de LLM em nuvem (plano gratuito) para a F2 do corpus acadêmico (ADR-004; Fase 10/11).

A chave é lida do ambiente no momento do uso (GEMINI_API_KEY no .env) — nunca fica em `settings`, em log ou em
mensagem de erro. Sem SADGD_LLM_F2=gemini ou sem chave, não há provedor remoto e tudo roda localmente."""
import json
import os

from app.core.config import settings
from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter


def gemini_configurado() -> bool:
    return settings.llm_f2 == "gemini" and bool(os.getenv("GEMINI_API_KEY", "").strip())


def llm_f2_remoto(timeout=120):
    """Adaptador do Gemini (endpoint compatível com OpenAI) ou None se não configurado."""
    if not gemini_configurado():
        return None
    try:
        extras = json.loads(settings.gemini_extras) if settings.gemini_extras else {}
    except ValueError:
        extras = {}
    return OpenAICompativelAdapter(f"gemini:{settings.gemini_modelo}", settings.gemini_url, settings.gemini_modelo,
                                   chave=os.environ["GEMINI_API_KEY"].strip(), timeout=timeout, tentativas=2,
                                   espera_inicial=2.0, extras=extras)
