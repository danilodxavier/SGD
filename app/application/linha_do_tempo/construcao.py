"""Caso de uso: (re)constrói o grafo documental — contradições, relações, processos e vigência derivada.

Usado pelo script `construir_grafo.py` e pelo serviço de indexação após um upload (Fase 9)."""
from collections import Counter

from app.application.linha_do_tempo.contradicoes import detectar_contradicoes
from app.application.linha_do_tempo.grafo import agrupar, classificar_relacoes
from app.application.linha_do_tempo.vigencia import revogacoes_por_relacao


def construir_grafo(repo) -> dict:
    docs = repo.carregar()
    contradicoes = detectar_contradicoes(docs)
    relacoes = classificar_relacoes(docs, contradicoes)
    grupos = agrupar(docs, relacoes)
    revogados = revogacoes_por_relacao(relacoes)
    repo.salvar(grupos, relacoes, revogados, {d.id: d.titulo for d in docs})
    return {"documentos": len(docs), "relacoes": len(relacoes), "por_tipo": dict(Counter(r.tipo for r in relacoes)),
            "contradicoes": len(contradicoes), "grupos": len(grupos),
            "grupos_com_2_ou_mais": sum(1 for g in grupos if len(g.documentos) > 1), "revogadas": len(revogados)}
