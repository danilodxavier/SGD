"""Adaptador LLMPort para servidores com API compatível com OpenAI (Ollama, LM Studio e free tiers) — ADR-004.

Sem dependências externas (urllib). Mede tokens e latência, valida JSON quando há schema e repete chamadas
em falhas transitórias (ex.: inicialização CUDA na primeira carga do modelo).
"""
import ipaddress
import json
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app.application.portas import RespostaLLM

log = logging.getLogger("sadgd.llm")


class ErroLLM(RuntimeError):
    pass


def endereco_local(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class OpenAICompativelAdapter:
    def __init__(self, nome, base_url, modelo, *, chave=None, timeout=120, tentativas=3, espera_inicial=1.0,
                 extras=None):
        if urlparse(base_url).scheme not in ("http", "https"):
            raise ValueError(f"URL do servidor de IA deve usar http ou https: {base_url}")
        self.nome = nome
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self.remoto = not endereco_local(self.base_url)
        self._chave = chave
        self._timeout = timeout
        self._tentativas = tentativas
        self._espera = espera_inicial
        self._extras = dict(extras or {})  # campos adicionais do corpo da requisição, específicos do provedor

    def chat(self, mensagens, *, schema=None, max_tokens=700, temperatura=0.0, json_livre=False):
        corpo = {"model": self.modelo, "messages": list(mensagens), "max_tokens": max_tokens,
                 "temperature": temperatura, "stream": False, **self._extras}
        if schema is not None:
            corpo["response_format"] = {"type": "json_schema",
                                        "json_schema": {"name": "saida", "schema": schema, "strict": True}}
        elif json_livre:
            corpo["response_format"] = {"type": "json_object"}
        inicio = time.perf_counter()
        dados = self._post("/chat/completions", corpo)
        latencia = int((time.perf_counter() - inicio) * 1000)
        try:
            texto = dados["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ErroLLM("Resposta inesperada do servidor de IA.") from exc
        uso = dados.get("usage") or {}
        conteudo_json = None
        if schema is not None or json_livre:
            try:
                conteudo_json = json.loads(_sem_cercas(texto))
            except ValueError as exc:
                raise ErroLLM("O modelo não retornou JSON válido.") from exc
        return RespostaLLM(texto=texto, modelo=dados.get("model", self.modelo),
                           tokens_entrada=int(uso.get("prompt_tokens") or 0),
                           tokens_saida=int(uso.get("completion_tokens") or 0),
                           latencia_ms=latencia, json=conteudo_json)

    def _post(self, caminho, corpo):
        cabecalhos = {"Content-Type": "application/json; charset=utf-8"}
        if self._chave:
            cabecalhos["Authorization"] = f"Bearer {self._chave}"
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        ultimo_erro = None
        for tentativa in range(1, self._tentativas + 1):
            # esquema restrito a http/https no construtor
            requisicao = urllib.request.Request(self.base_url + caminho, data=dados,  # noqa: S310
                                                headers=cabecalhos, method="POST")
            try:
                with urllib.request.urlopen(requisicao, timeout=self._timeout) as resposta:  # noqa: S310
                    return json.loads(resposta.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detalhe = exc.read().decode("utf-8", "replace")[:300]
                ultimo_erro = ErroLLM(f"Servidor de IA respondeu {exc.code}: {detalhe}")
                if exc.code < 500 and exc.code != 429:
                    raise ultimo_erro from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                ultimo_erro = ErroLLM(f"Não foi possível conectar ao servidor de IA ({self.nome}).")
                ultimo_erro.__cause__ = exc
            log.warning("Falha na chamada ao LLM %s (tentativa %d/%d): %s", self.nome, tentativa,
                        self._tentativas, ultimo_erro)
            if tentativa < self._tentativas:
                time.sleep(self._espera * 2 ** (tentativa - 1))
        raise ultimo_erro


def _sem_cercas(texto: str) -> str:
    """Remove cercas ```json ... ``` que alguns modelos acrescentam."""
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()
