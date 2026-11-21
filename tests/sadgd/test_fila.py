"""Fila de consultas: FIFO com um executor, posição, etapa, isolamento por usuário e falhas."""
import threading
import time
from contextlib import contextmanager

from app.application.consultas.fila import FilaDeConsultas, TracerComProgresso


def esperar(condicao, limite=5.0):
    fim = time.time() + limite
    while time.time() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_fifo_posicao_etapa_e_resultado():
    liberar, ordem = threading.Event(), []

    def executar(c, mudar_etapa):
        mudar_etapa("recuperar")
        if c.pergunta == "primeira":
            liberar.wait(5)
        ordem.append(c.pergunta)
        return {"resposta": c.pergunta.upper()}

    fila = FilaDeConsultas(executar)
    a, b = fila.enfileirar(1, "primeira"), fila.enfileirar(1, "segunda")
    assert esperar(lambda: fila.situacao(a.id, 1)["estado"] == "processando")
    sa, sb = fila.situacao(a.id, 1), fila.situacao(b.id, 1)
    assert sa["posicao"] == 1 and sa["etapa"] == "recuperar" and sa["etapa_descricao"] == "Buscando nos documentos"
    assert sb["estado"] == "fila" and sb["posicao"] == 2
    liberar.set()
    assert esperar(lambda: fila.situacao(b.id, 1)["estado"] == "concluida")
    assert ordem == ["primeira", "segunda"] and fila.situacao(a.id, 1)["resultado"] == {"resposta": "PRIMEIRA"}
    assert fila.situacao(b.id, 1)["posicao"] is None and fila.tamanho() == 0


def test_so_o_dono_ve_a_consulta():
    fila = FilaDeConsultas(lambda c, m: {"ok": True})
    c = fila.enfileirar(7, "pergunta do gestor")
    assert fila.situacao(c.id, 8) is None and fila.situacao(999, 7) is None
    assert esperar(lambda: fila.situacao(c.id, 7)["estado"] == "concluida")


def test_falha_vira_erro_generico_e_a_fila_continua():
    def executar(c, m):
        if c.pergunta == "quebra":
            raise RuntimeError("detalhe interno")
        return {"ok": True}

    fila = FilaDeConsultas(executar)
    ruim, boa = fila.enfileirar(1, "quebra"), fila.enfileirar(1, "segue")
    assert esperar(lambda: fila.situacao(boa.id, 1)["estado"] == "concluida")
    s = fila.situacao(ruim.id, 1)
    assert s["estado"] == "erro" and "RuntimeError" in s["erro"] and "detalhe interno" not in s["erro"]


def test_tracer_com_progresso_informa_a_etapa_e_delega_o_span():
    etapas, spans = [], []

    class TracerFalso:
        @contextmanager
        def span(self, no, **kw):
            spans.append(no)
            yield {}

    tracer = TracerComProgresso(TracerFalso(), etapas.append)
    with tracer.span("rotear"):
        pass
    with tracer.span("especialista"):
        pass
    assert etapas == spans == ["rotear", "especialista"]
