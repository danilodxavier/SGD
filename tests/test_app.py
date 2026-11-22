"""Ciclo de vida do servidor (equivalente a start.bat/stop.bat), rotas de sistema e diagnóstico."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from app.core.config import BASE_DIR
from app.services import diagnostics
from tests.helpers import logged_client

HEADERS = {"X-Requested-With": "AgenteDocumental"}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_iniciar_e_parar_servidor(docs_dir, tmp_path):
    port = _free_port()
    env = {**os.environ, "APP_PORT": str(port), "DATA_DIR": str(tmp_path / "data"),
           "DATABASE_PATH": str(tmp_path / "data" / "srv.db"), "DOCUMENTS_ROOT": str(docs_dir),
           "OCR_ENABLED": "false", "AI_PROVIDER": "local", "PYTHONIOENCODING": "utf-8",
           "APP_HOST": "127.0.0.1", "ALLOWED_HOSTS": "", "SSL_CERTFILE": "", "SSL_KEYFILE": ""}  # independe do .env
    server = subprocess.Popen([sys.executable, "-m", "app", "--sem-navegador"], cwd=BASE_DIR, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        health = None
        for _ in range(60):
            try:
                health = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1))
                break
            except OSError:
                time.sleep(0.25)
        assert health and health["database"] == "ok" and health["documents_root"] == "ok"
        pid_file = tmp_path / "data" / "app.pid"
        assert json.loads(pid_file.read_text())["port"] == port

        stop = subprocess.run([sys.executable, "-m", "app", "parar"], cwd=BASE_DIR, env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=60)
        assert "[OK] Servidor encerrado." in stop.stdout
        server.wait(timeout=30)
        assert not pid_file.exists()
        again = subprocess.run([sys.executable, "-m", "app", "parar"], cwd=BASE_DIR, env=env, capture_output=True,
                               text=True, encoding="utf-8", timeout=60)
        assert "Nenhum servidor em execução" in again.stdout
    finally:
        if server.poll() is None:
            server.kill()


def test_diagnostico_em_processo(indexed):  # raiz documental de amostra
    checks = {c["name"]: c for c in diagnostics.run_checks()}
    for name in ("Windows", "Python", "pip", "venv", "SQLite", "diretório documental", "permissão de leitura",
                 "permissão de escrita", "espaço em disco", "FastAPI", "Uvicorn", "bibliotecas de documentos", "OCR",
                 "banco de dados", "sqlite-vec", "migrações SAD-GD", "Tesseract"):
        assert name in checks, name
    assert checks["SQLite"]["level"] == "OK" and checks["banco de dados"]["level"] == "OK"
    assert not [c for c in checks.values() if c["level"] == "ERRO"]


@pytest.fixture()
def client(indexed):
    with logged_client() as c:
        yield c


def test_rotas_de_sistema(client, indexed, tmp_path):
    cfg = client.get("/api/config").json()
    assert cfg["documents_root_ok"] and cfg["app_host"] == "127.0.0.1"
    other = tmp_path / "outro"
    other.mkdir()
    assert client.post("/api/config", json={"documents_root": str(other)}, headers=HEADERS).json()[
        "documents_root"] == str(other)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/sadgd/indexacao").json()["executando"] is False
    assert client.get("/api/diagnostics").json()["checks"]
    assert isinstance(client.get("/api/logs", params={"lines": 5}).json()["lines"], list)
    assert client.post("/api/system/shutdown", headers=HEADERS).status_code == 403  # sem token


def test_requisicao_invalida_tem_mensagem_amigavel(client):
    r = client.post("/api/sadgd/perguntar", json={"texto": "x"}, headers=HEADERS)
    assert r.status_code == 422 and r.json()["detail"] == "Dados inválidos na requisição."
