"""Inicialização e encerramento do servidor.

    python -m app                 inicia o painel em APP_HOST:APP_PORT (padrão 127.0.0.1:8000)
    python -m app --sem-navegador inicia sem abrir o navegador
    python -m app parar           encerra o servidor em execução
"""
import asyncio
import faulthandler
import json
import os
import secrets
import ssl as ssl_module
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app.core.config import settings


def _write_pid(token):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    info = {"pid": os.getpid(), "token": token, "host": settings.app_host, "port": settings.app_port,
            "https": settings.https_principal}
    settings.pid_file.write_text(json.dumps(info), encoding="utf-8")


def _alive(pid):
    """Consulta o Windows diretamente (mais confiável que interpretar a saída do tasklist)."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def criar_servidores(app):
    """Servidor principal em APP_PORT e, com HTTPS_PORT + certificado, um 2º só de HTTPS (mesmo app, sem lifespan:
    indexação e pré-carregamento rodam uma vez só)."""
    ssl = {"ssl_certfile": settings.ssl_certfile, "ssl_keyfile": settings.ssl_keyfile}
    principal = uvicorn.Config(app, host=settings.app_host, port=settings.app_port, log_level="warning",
                               **(ssl if settings.https_principal else {}))
    servidores = [uvicorn.Server(principal)]
    if settings.https and settings.https_port and settings.https_port != settings.app_port:
        extra = uvicorn.Config(app, host=settings.app_host, port=settings.https_port, log_level="warning",
                               lifespan="off", **ssl)
        servidores.append(uvicorn.Server(extra))
    return servidores


_CONEXAO_DERRUBADA = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


def _tratar_excecao_do_laco(loop, contexto):
    """Conexão derrubada pelo navegador (WinError 10054/10053) não é erro do servidor: não polui o console.

    O Edge/Chrome abrem conexões antecipadas e as descartam com RST (frequente com HTTPS). Falha ao aceitar conexões
    vira aviso no app.log — no laço Proactor ela fechava a porta de escuta (ver `_novo_laco`). O resto segue para o
    tratador padrão do asyncio.
    """
    if "accept" in str(contexto.get("message", "")).lower():
        from app.core.logging import get_logger

        get_logger("servidor").warning("Falha ao aceitar conexão: %r", contexto.get("exception"))
        return
    if isinstance(contexto.get("exception"), _CONEXAO_DERRUBADA):
        return
    loop.default_exception_handler(contexto)


def _novo_laco():
    """Laço Selector no Windows (no lugar do Proactor, padrão do uvicorn).

    No Proactor, qualquer OSError no `accept()` — p. ex. o navegador derrubar a conexão antes do aceite (10054) —
    executa `sock.close()` na porta de escuta (asyncio/proactor_events.py, `_start_serving`): o processo segue vivo,
    a porta para de atender e o vigia não percebe (aconteceu na porta 8000 em 2026-11-23). O Selector ignora a falha
    e continua aceitando. Limite de 512 conexões simultâneas do select() — suficiente para a rede interna.
    """
    return asyncio.SelectorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()


async def _servir(servidores):
    """Roda todos; quando um termina (encerramento pedido ou falha), encerra os demais."""
    asyncio.get_running_loop().set_exception_handler(_tratar_excecao_do_laco)
    tarefas = [asyncio.create_task(s.serve()) for s in servidores]
    await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
    for s in servidores:
        s.should_exit = True
    resultados = await asyncio.gather(*tarefas, return_exceptions=True)
    erro = next((r for r in resultados if isinstance(r, BaseException)), None)
    if erro is not None:
        raise erro


def rodar_servidores(servidores):
    """uvicorn numa thread; a thread principal executa o trabalho do PyTorch (ver modelos/thread_principal.py).

    Falha na thread do servidor (inclusive SystemExit do uvicorn ao não conseguir abrir a porta) termina o processo
    com código 1, para o vigia de `iniciar_rede.bat` reiniciar. Ctrl+C na principal pede o encerramento controlado.
    """
    from app.infrastructure.modelos import thread_principal

    erro = []

    def alvo():
        try:
            asyncio.run(_servir(servidores), loop_factory=_novo_laco)
        except BaseException as exc:  # noqa: BLE001 - repassado à thread principal
            erro.append(exc)

    web = threading.Thread(target=alvo, name="servidor-web")
    thread_principal.ativar()  # antes de qualquer thread: o pré-carregamento começa junto com o servidor
    web.start()
    try:
        thread_principal.servir_ate(lambda: not web.is_alive())
    except KeyboardInterrupt:
        for s in servidores:
            s.should_exit = True
        thread_principal.servir_ate(lambda: not web.is_alive())
    web.join()
    if erro and not (isinstance(erro[0], SystemExit) and erro[0].code in (0, None)):
        print(f"[ERRO] Servidor encerrado por falha: {erro[0]!r}", file=sys.stderr)
        sys.exit(1)


def _registrar_falhas_nativas():
    """Queda nativa (ex.: 0xC0000005 em 2026-11-23) grava a pilha de cada thread em data/logs/falha_nativa.log."""
    try:
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        arq = open(settings.logs_dir / "falha_nativa.log", "a", encoding="utf-8")  # noqa: SIM115 - aberto até o fim
        arq.write(f"==== {time.strftime('%Y-%m-%d %H:%M:%S')} servidor iniciado (pid {os.getpid()}) ====\n")
        arq.flush()
        faulthandler.enable(file=arq, all_threads=True)
    except OSError:
        pass


def start(open_browser=True):
    from app.main import app

    _registrar_falhas_nativas()

    scheme = "https" if settings.https_principal else "http"
    if settings.network_mode:
        from app.core.security import local_names

        print("[REDE] O painel aceitará acessos de outros computadores autorizados (ALLOWED_CLIENTS):")
        for name in sorted(n for n in local_names() if n not in ("127.0.0.1", "localhost", "::1") and ":" not in n):
            print(f"       {scheme}://{name}:{settings.app_port}")
            if settings.https and settings.https_port:
                print(f"       https://{name}" + ("" if settings.https_port == 443 else f":{settings.https_port}"))
        if not settings.https:
            print("[WARNING] Sem HTTPS: as senhas trafegam sem criptografia na rede interna (ver SSL_CERTFILE).")
    token = secrets.token_urlsafe(24)
    servidores = criar_servidores(app)
    server = servidores[0]
    app.state.server = server
    app.state.shutdown_token = token
    _write_pid(token)

    url = f"{scheme}://127.0.0.1:{settings.app_port}"
    print(f"Painel disponível em {url}  (para encerrar: stop.bat ou Ctrl+C)")
    if open_browser:
        threading.Timer(2.0, webbrowser.open, args=(url,)).start()
    try:
        rodar_servidores(servidores)
    finally:
        try:
            if json.loads(settings.pid_file.read_text(encoding="utf-8")).get("pid") == os.getpid():
                settings.pid_file.unlink()
        except (OSError, ValueError):
            pass


def stop():
    try:
        info = json.loads(settings.pid_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("[OK] Nenhum servidor em execução (arquivo data\\app.pid não encontrado).")
        return 0
    pid = info["pid"]
    if not _alive(pid):
        settings.pid_file.unlink(missing_ok=True)
        print("[OK] O servidor já estava encerrado.")
        return 0
    try:
        scheme = "https" if info.get("https") else "http"
        req = urllib.request.Request(
            f"{scheme}://127.0.0.1:{info['port']}/api/system/shutdown", method="POST", data=b"",
            headers={"X-Shutdown-Token": info["token"], "X-Requested-With": "AgenteDocumental"},
        )
        # o certificado é emitido para o nome do servidor, não para 127.0.0.1: a conexão local não o valida
        context = ssl_module._create_unverified_context() if info.get("https") else None
        urllib.request.urlopen(req, timeout=5, context=context).read()
    except Exception as exc:
        print(f"[WARNING] Encerramento controlado não respondeu: {exc}")
    for _ in range(20):
        if not _alive(pid):
            settings.pid_file.unlink(missing_ok=True)
            print("[OK] Servidor encerrado.")
            return 0
        time.sleep(0.5)
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    settings.pid_file.unlink(missing_ok=True)
    print("[WARNING] O servidor não encerrou a tempo e foi finalizado à força.")
    return 0


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]
    if args and args[0] in ("parar", "stop"):
        sys.exit(stop())
    start(open_browser="--sem-navegador" not in args)
