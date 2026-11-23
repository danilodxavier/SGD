"""Pré-carregamento dos modelos ao iniciar o servidor."""
from app.infrastructure.modelos.aquecimento import aquecer


def test_aquece_na_ordem_reranker_embedder_llm():
    ordem = []
    r = aquecer(reranker=lambda: ordem.append("reranker"), embedder=lambda: ordem.append("embedder"),
                llm=lambda: ordem.append("llm"))
    assert ordem == ["reranker", "embedder", "llm"]
    assert set(r) == {"reranker", "embedder", "llm"} and all(isinstance(v, int) for v in r.values())


def test_falha_numa_etapa_nao_impede_as_seguintes():
    ordem = []

    def falha():
        raise RuntimeError("CUDA out of memory")

    r = aquecer(reranker=falha, embedder=lambda: ordem.append("embedder"), llm=None)
    assert r["reranker"].startswith("falhou") and ordem == ["embedder"] and "llm" not in r


def test_testes_nao_disparam_o_aquecimento(monkeypatch):
    chamado = []
    monkeypatch.setattr("app.infrastructure.modelos.aquecimento.aquecer_em_segundo_plano",
                        lambda: chamado.append(1))
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(auto_index=False)):
        pass
    assert chamado == []
