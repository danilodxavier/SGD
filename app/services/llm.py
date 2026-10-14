"""Cliente de LLM local (Ollama, LM Studio ou outro servidor compatível com a API da OpenAI).

Regra de privacidade: por padrão só são aceitos endereços desta máquina (127.0.0.1/localhost).
Um endereço externo exige AI_ALLOW_REMOTE=true no .env e, nesse caso, CPF, e-mail e telefone
são mascarados antes do envio.
"""
import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("llm")

PROVIDERS = {"local": "Local — somente documentos (sem IA)", "llm_local": "LLM local (Ollama / LM Studio)"}
ALIASES = {"llm": "llm_local", "ollama": "llm_local", "lmstudio": "llm_local", "local_llm": "llm_local"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}

CPF = re.compile(r"(?<![\d./-])\d{3}\.\d{3}\.\d{3}-\d{2}(?![\d/-])|(?<![\d./-])\d{11}(?![\d./-])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}|(?<![\d./-])\d{2}\s9\d{4}-\d{4}(?![\d/-])")


class LLMError(Exception):
    """Falha de comunicação ou configuração (mensagem para o usuário)."""


def current_config():
    """Configuração efetiva: o painel prevalece sobre o .env."""
    from app.core.database import get_setting

    provider = (get_setting("ai_provider") or settings.ai_provider or "local").lower()
    provider = ALIASES.get(provider, provider)
    return {
        "provider": provider if provider in PROVIDERS else "local",
        "base_url": (get_setting("llm_base_url") or settings.llm_base_url).rstrip("/"),
        "model": get_setting("llm_model") or settings.llm_model,
    }


def is_local(url):
    return (urlparse(url).hostname or "").lower() in LOOPBACK


def check_url(url):
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LLMError("Endereço do servidor de IA inválido (ex.: http://127.0.0.1:11434/v1).")
    if not is_local(url) and not settings.ai_allow_remote:
        raise LLMError("Endereço externo bloqueado: a aplicação opera em modo LOCAL ONLY. "
                       "Use um servidor nesta máquina (127.0.0.1).")


def mask_personal(text):
    """Substitui CPF, e-mail e telefone por marcadores. Retorna (texto, quantidade)."""
    total = 0
    for pattern, label in ((EMAIL, "[E-MAIL]"), (CPF, "[CPF]"), (PHONE, "[TELEFONE]")):
        text, n = pattern.subn(label, text)
        total += n
    return text, total


def _request(url, payload=None, timeout=30):
    check_url(url)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    # sem proxy para o servidor local (proxies corporativos não devem interceptar 127.0.0.1)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if is_local(url) \
        else urllib.request.build_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        log.warning("Servidor de IA respondeu %s: %s", exc.code, body)
        if exc.code == 404:
            raise LLMError("Modelo ou endereço não encontrado no servidor de IA.") from exc
        raise LLMError(f"O servidor de IA respondeu com erro {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMError("Não foi possível conectar ao servidor de IA local. Verifique se o Ollama/LM Studio "
                       "está em execução.") from exc
    except ValueError as exc:
        raise LLMError("Resposta inválida do servidor de IA.") from exc


def list_models(base_url):
    data = _request(f"{base_url.rstrip('/')}/models", timeout=10)
    return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))


def chat(base_url, model, messages, timeout=None, max_tokens=700):
    if not model:
        raise LLMError("Nenhum modelo de IA selecionado. Escolha o modelo em Configurações.")
    if not is_local(base_url):
        masked = []
        for m in messages:
            content, _ = mask_personal(m["content"])
            masked.append({**m, "content": content})
        messages = masked
    payload = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens, "stream": False}
    data = _request(f"{base_url.rstrip('/')}/chat/completions", payload, timeout=timeout or settings.llm_timeout)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError("Resposta inválida do servidor de IA.") from exc


def status():
    cfg = current_config()
    out = {**cfg, "providers": PROVIDERS, "local_only": not settings.ai_allow_remote,
           "url_is_local": is_local(cfg["base_url"]), "reachable": None, "models": [], "message": ""}
    if cfg["provider"] != "llm_local":
        out["message"] = "Respostas geradas apenas pelo mecanismo local, sem IA."
        return out
    try:
        out["models"] = list_models(cfg["base_url"])
        out["reachable"] = True
        if not cfg["model"]:
            out["message"] = "Servidor encontrado. Selecione um modelo."
        elif cfg["model"] not in out["models"]:
            out["message"] = f"O modelo “{cfg['model']}” não está instalado no servidor."
        else:
            out["message"] = f"Pronto: {cfg['model']}."
    except LLMError as exc:
        out["reachable"] = False
        out["message"] = str(exc)
    return out


def test_connection():
    cfg = current_config()
    start = time.time()
    reply = chat(cfg["base_url"], cfg["model"], [
        {"role": "system", "content": "Responda em português, em uma única palavra."},
        {"role": "user", "content": "Responda apenas: OK"},
    ], timeout=min(settings.llm_timeout, 120), max_tokens=10)
    return {"ok": bool(reply), "reply": reply[:200], "seconds": round(time.time() - start, 1), "model": cfg["model"]}
