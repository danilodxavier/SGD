"""Adaptador OpenAI-compatível contra um servidor HTTP simulado (sem modelo real)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.application.portas import LLMPort
from app.infrastructure.llm.openai_compativel import ErroLLM, OpenAICompativelAdapter, endereco_local


class Servidor:
    def __init__(self, respostas):
        self.respostas = list(respostas)  # (status, corpo)
        self.recebidos = []
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                tamanho = int(self.headers["Content-Length"])
                servidor.recebidos.append(json.loads(self.rfile.read(tamanho)))
                status, corpo = servidor.respostas.pop(0)
                dados = json.dumps(corpo).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def log_message(self, *args):
                pass

        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_port}/v1"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def fechar(self):
        self.http.shutdown()


def ok(conteudo, entrada=12, saida=5):
    return 200, {"model": "fake", "choices": [{"message": {"content": conteudo}}],
                 "usage": {"prompt_tokens": entrada, "completion_tokens": saida}}


@pytest.fixture()
def servidor():
    criados = []

    def criar(*respostas):
        s = Servidor(respostas)
        criados.append(s)
        return s

    yield criar
    for s in criados:
        s.fechar()


def test_resposta_com_tokens_e_latencia(servidor):
    s = servidor(ok("Olá"))
    llm = OpenAICompativelAdapter("ollama", s.url, "m")
    assert isinstance(llm, LLMPort)
    r = llm.chat([{"role": "user", "content": "oi"}], max_tokens=10)
    assert (r.texto, r.tokens_entrada, r.tokens_saida) == ("Olá", 12, 5)
    assert r.latencia_ms >= 0 and s.recebidos[0]["max_tokens"] == 10


def test_saida_estruturada_valida_json_e_remove_cercas(servidor):
    s = servidor(ok('```json\n{"rota": "F1_simples"}\n```'))
    r = OpenAICompativelAdapter("ollama", s.url, "m").chat([], schema={"type": "object"})
    assert r.json == {"rota": "F1_simples"}
    assert s.recebidos[0]["response_format"]["type"] == "json_schema"


def test_json_livre_usa_json_object_sem_schema(servidor):
    s = servidor(ok('{"resposta": "x", "fontes": []}'))
    r = OpenAICompativelAdapter("ollama", s.url, "m").chat([], json_livre=True)
    assert r.json == {"resposta": "x", "fontes": []}
    assert s.recebidos[0]["response_format"] == {"type": "json_object"}


def test_json_invalido_gera_erro(servidor):
    s = servidor(ok("não é json"))
    with pytest.raises(ErroLLM):
        OpenAICompativelAdapter("ollama", s.url, "m").chat([], schema={"type": "object"})


def test_repete_em_falha_transitoria(servidor):
    s = servidor((500, {"error": "CUDA error"}), ok("recuperou"))
    r = OpenAICompativelAdapter("ollama", s.url, "m", espera_inicial=0).chat([])
    assert r.texto == "recuperou" and len(s.recebidos) == 2


def test_nao_repete_erro_do_cliente(servidor):
    s = servidor((404, {"error": "model not found"}), ok("nunca"))
    with pytest.raises(ErroLLM, match="404"):
        OpenAICompativelAdapter("ollama", s.url, "m", espera_inicial=0).chat([])
    assert len(s.recebidos) == 1


@pytest.mark.parametrize("url", ["file:///C:/Windows/win.ini", "ftp://exemplo/v1", "127.0.0.1:11434"])
def test_rejeita_esquema_nao_http(url):
    with pytest.raises(ValueError, match="http"):
        OpenAICompativelAdapter("x", url, "m")


@pytest.mark.parametrize("url,local", [
    ("http://127.0.0.1:11434/v1", True), ("http://localhost:1234/v1", True), ("http://[::1]:8080", True),
    ("https://generativelanguage.googleapis.com/v1beta/openai", False), ("http://192.168.0.10:11434", False),
])
def test_identifica_provedor_remoto(url, local):
    assert endereco_local(url) is local
    assert OpenAICompativelAdapter("x", url, "m").remoto is (not local)
