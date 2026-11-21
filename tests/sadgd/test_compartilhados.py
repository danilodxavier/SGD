"""Escolha de dispositivo dos modelos de recuperação (A3, 2026-11-20)."""
from app.infrastructure.modelos import compartilhados


def test_reranker_forcado_pela_variavel(monkeypatch):
    monkeypatch.setenv("SADGD_DISPOSITIVO_RERANKER", "cpu")
    assert compartilhados.dispositivo_reranker() == "cpu"
    monkeypatch.setenv("SADGD_DISPOSITIVO_RERANKER", "CUDA")
    assert compartilhados.dispositivo_reranker() == "cuda"


def test_reranker_auto_usa_gpu_so_quando_existe(monkeypatch):
    import torch

    monkeypatch.delenv("SADGD_DISPOSITIVO_RERANKER", raising=False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert compartilhados.dispositivo_reranker() == "cpu"  # ex.: runner do CI
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert compartilhados.dispositivo_reranker() == "cuda"


def test_embedder_da_consulta_continua_na_cpu_por_padrao(monkeypatch):
    monkeypatch.delenv("SADGD_DISPOSITIVO_RECUPERACAO", raising=False)
    assert compartilhados.dispositivo() == "cpu"
