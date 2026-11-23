"""A porta de escuta sobrevive a conexões derrubadas com RST (WinError 10054) — regressão de 2026-11-23.

No laço Proactor (padrão do uvicorn no Windows), um RST antes do `accept()` fechava a porta de escuta: o processo
seguia vivo, mas a porta 8000 parou de atender. O servidor usa o laço Selector (`_novo_laco`).
"""
import asyncio
import socket
import struct
import threading
import time
import urllib.request

import uvicorn

from app.__main__ import _novo_laco, _servir


async def _app(scope, receive, send):
    if scope["type"] != "http":
        return
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok"})


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(porta):
    with urllib.request.urlopen(f"http://127.0.0.1:{porta}/", timeout=5) as r:  # noqa: S310 - local
        return r.status


def _rajada_de_rst(porta, n):
    for _ in range(n):
        try:
            s = socket.create_connection(("127.0.0.1", porta), timeout=2)
        except OSError:
            return  # porta já fechada (no Windows cada recusa leva ~2 s)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))  # fecha com RST
        s.close()


def sobrevive_a_rst(fabrica_de_laco, n=200):
    porta = _porta_livre()
    servidor = uvicorn.Server(uvicorn.Config(_app, host="127.0.0.1", port=porta, log_level="critical",
                                             lifespan="off"))
    t = threading.Thread(target=lambda: asyncio.run(_servir([servidor]), loop_factory=fabrica_de_laco), daemon=True)
    t.start()
    for _ in range(100):
        if servidor.started:
            break
        time.sleep(0.05)
    try:
        assert _get(porta) == 200
        _rajada_de_rst(porta, n)
        time.sleep(0.5)
        try:
            return _get(porta) == 200
        except OSError:
            return False
    finally:
        servidor.should_exit = True
        t.join(10)


def test_porta_continua_atendendo_apos_rajada_de_rst():
    assert sobrevive_a_rst(_novo_laco)
