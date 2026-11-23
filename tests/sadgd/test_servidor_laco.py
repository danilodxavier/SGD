"""Laço de eventos do servidor: conexão derrubada pelo navegador não vira erro no log."""
from app.__main__ import _tratar_excecao_do_laco


class _Laco:
    def __init__(self):
        self.padrao = []

    def default_exception_handler(self, contexto):
        self.padrao.append(contexto)


def test_conexao_derrubada_pelo_cliente_e_ignorada():
    laco = _Laco()
    for exc in (ConnectionResetError(10054, "reset"), ConnectionAbortedError(10053, "abort"), BrokenPipeError()):
        _tratar_excecao_do_laco(laco, {"message": "Exception in callback", "exception": exc})
    assert laco.padrao == []


def test_outros_erros_seguem_para_o_tratador_padrao():
    laco = _Laco()
    _tratar_excecao_do_laco(laco, {"message": "x", "exception": ValueError("bug")})
    _tratar_excecao_do_laco(laco, {"message": "sem exceção"})
    assert len(laco.padrao) == 2
