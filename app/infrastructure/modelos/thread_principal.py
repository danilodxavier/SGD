"""Executa o trabalho do PyTorch na thread principal do processo.

Com Python 3.15.0 e torch 2.14.1 (CPU, MKL/OpenMP), qualquer operação de cálculo (`matmul`, `sum`, `softmax`) feita
numa thread secundária derruba o processo com 0xC0000005 em `python315.dll+0x17f78` (região de `PyThreadState_Clear`)
— reproduzido em segundos em 2026-11-23, com ou sem trava, `set_num_threads(1)`, `inference_mode` ou
`OMP_NUM_THREADS=1`. Na thread principal, 1,8 milhão de operações sem queda, mesmo com outras threads ativas. Foi a
causa da queda do servidor às 11:30 (as rotas síncronas do FastAPI rodam em threads do anyio).

O servidor (`python -m app`) roda o uvicorn numa thread e chama `servir_ate()` na principal; embedder, reranker e
consultas à GPU passam por `executar()`. Fora do servidor (scripts, testes), `executar()` roda direto na thread atual.
"""
import functools
import queue
import threading
from concurrent.futures import Future

_fila: "queue.Queue[tuple[Future, object, tuple, dict]]" = queue.Queue()
_estado = {"ident": None}


def ativar():
    """Marca a thread atual como executora ANTES de iniciar as demais (sem corrida: um pedido feito antes de
    `servir_ate()` começar fica na fila em vez de rodar na thread secundária)."""
    _estado["ident"] = threading.get_ident()


def ativo():
    return _estado["ident"] is not None


def executar(fn, *args, **kwargs):
    """Roda `fn` na thread principal (se o executor estiver ativo) e devolve o resultado ou relança a exceção."""
    ident = _estado["ident"]
    if ident is None or threading.get_ident() == ident:
        return fn(*args, **kwargs)
    futuro = Future()
    _fila.put((futuro, fn, args, kwargs))
    return futuro.result()


def na_thread_principal(fn):
    """Decorador: a função sempre executa via `executar()`."""
    @functools.wraps(fn)
    def envoltorio(*args, **kwargs):
        return executar(fn, *args, **kwargs)
    return envoltorio


def _rodar(item):
    futuro, fn, args, kwargs = item
    if not futuro.set_running_or_notify_cancel():
        return
    try:
        futuro.set_result(fn(*args, **kwargs))
    except BaseException as exc:  # noqa: BLE001 - a exceção volta para quem pediu
        futuro.set_exception(exc)


def servir_ate(parar, intervalo=0.25):
    """Laço da thread principal: executa os pedidos até `parar()` ser verdadeiro. Depois volta ao modo direto."""
    ativar()
    try:
        while not parar():
            try:
                item = _fila.get(timeout=intervalo)
            except queue.Empty:
                continue
            _rodar(item)
    finally:
        _estado["ident"] = None
        while True:  # pedidos que chegaram no fim: executa aqui mesmo para ninguém ficar esperando
            try:
                _rodar(_fila.get_nowait())
            except queue.Empty:
                break
