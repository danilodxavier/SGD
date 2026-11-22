"""O reranker sem memória na GPU segue na CPU em vez de derrubar a pergunta (rodada 14)."""
import pytest

from app.infrastructure.modelos.reranker import BgeReranker


class ModeloFalso:
    def predict(self, pares, **kw):
        return [0.5 for _ in pares]


def test_falta_de_memoria_na_gpu_cai_para_a_cpu():
    r = BgeReranker(dispositivo="cuda")
    tentativas = []

    def carregar():
        tentativas.append(r.dispositivo)
        if r.dispositivo == "cuda":
            raise RuntimeError("CUDA out of memory. Tried to allocate 978.00 MiB")
        return ModeloFalso()

    r._carregar = carregar
    r.liberar = lambda: None
    assert r.pontuar("pergunta", ["a", "b"]) == [0.5, 0.5]
    assert tentativas == ["cuda", "cpu"] and r.dispositivo == "cpu"


def test_outros_erros_nao_sao_mascarados():
    r = BgeReranker(dispositivo="cuda")

    def carregar():
        raise RuntimeError("arquivo do modelo corrompido")

    r._carregar = carregar
    with pytest.raises(RuntimeError, match="corrompido"):
        r.pontuar("pergunta", ["a"])
