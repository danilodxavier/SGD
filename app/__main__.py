"""Inicialização e encerramento do servidor.

    python -m app                 inicia o painel em APP_HOST:APP_PORT (padrão 127.0.0.1:8000)
    python -m app --sem-navegador inicia sem abrir o navegador
    python -m app parar           encerra o servidor em execução
"""
import asyncio
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
    settings.pid_file.write_text(json.dumps({"pid": os.getpid(), "token": token, "host": settings.app_host,
                                             "port": settings.app_port, "https": settings.https_principal}), encoding="utf-8")


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


async def _servir(servidores):
    """Roda todos; quando um termina (encerramento pedido ou falha), encerra os demais."""
    tarefas = [asyncio.create_task(s.serve()) for s in servidores]
    await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
    for s in servidores:
        s.should_exit = True
    resultados = await asyncio.gather(*tarefas, return_exceptions=True)
    erro = next((r for r in resultados if isinstance(r, BaseException)), None)
    if erro is not None:
        raise erro


def start(open_browser=True):
    from app.main import app

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
        asyncio.run(_servir(servidores))
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
