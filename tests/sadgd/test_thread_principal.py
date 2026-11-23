"""Trabalho do PyTorch na thread principal (Python 3.15 + torch 2.14: cálculo em thread secundária = 0xC0000005)."""
import threading

import pytest

from app.infrastructure.modelos import thread_principal as tp


def _em_thread(fn):
    """Roda `fn` numa thread secundária enquanto a principal serve a fila; devolve (resultado, exceção)."""
    saida = {}

    def alvo():
        try:
            saida["r"] = fn()
        except BaseException as exc:  # noqa: BLE001
            saida["e"] = exc

    t = threading.Thread(target=alvo)
    tp.ativar()
    t.start()
    tp.servir_ate(lambda: not t.is_alive(), intervalo=0.01)
    t.join()
    return saida.get("r"), saida.get("e")


def test_sem_executor_ativo_roda_na_thread_atual():
    assert not tp.ativo()
    assert tp.executar(threading.get_ident) == threading.get_ident()


def test_com_executor_ativo_roda_na_thread_principal():
    principal = threading.get_ident()
    r, e = _em_thread(lambda: tp.executar(threading.get_ident))
    assert e is None and r == principal
    assert not tp.ativo()  # volta ao modo direto depois


def test_excecao_volta_para_quem_pediu():
    def falha():
        raise ValueError("x")

    _, e = _em_thread(lambda: tp.executar(falha))
    assert isinstance(e, ValueError)


def test_chamada_aninhada_na_principal_nao_trava():
    r, e = _em_thread(lambda: tp.executar(lambda: tp.executar(lambda: 42)))
    assert e is None and r == 42


def test_decorador_e_modelos_usam_o_executor():
    from app.infrastructure.modelos.embeddings import BgeM3Embedder
    from app.infrastructure.modelos.reranker import BgeReranker

    for metodo in (BgeM3Embedder.embed, BgeM3Embedder.liberar, BgeReranker.pontuar, BgeReranker.liberar):
        assert metodo.__wrapped__  # envolvido por na_thread_principal


def test_calculo_do_torch_pedido_por_thread_secundaria_nao_derruba_o_processo():
    torch = pytest.importorskip("torch")
    a = torch.randn(32, 32)

    def muitos():
        return sum(tp.executar(lambda: float((a @ a).sum().item())) is not None for _ in range(3000))

    r, e = _em_thread(muitos)
    assert e is None and r == 3000


class _ServidorQueFalha:
    should_exit = False

    def __init__(self, exc):
        self.exc = exc

    async def serve(self):
        raise self.exc


def test_falha_do_servidor_web_sai_com_codigo_1_para_o_vigia():
    from app.__main__ import rodar_servidores

    with pytest.raises(SystemExit) as saida:
        rodar_servidores([_ServidorQueFalha(SystemExit(1))])  # uvicorn: porta ocupada
    assert saida.value.code == 1
    assert not tp.ativo()


def test_encerramento_normal_do_servidor_web_nao_e_falha():
    from app.__main__ import rodar_servidores

    rodar_servidores([_ServidorQueFalha(SystemExit(0))])
