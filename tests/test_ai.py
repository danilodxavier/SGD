"""IA opcional (LLM local): validação das respostas, falhas e privacidade.

Usa um servidor simulado compatível com a API da OpenAI (como Ollama/LM Studio), em 127.0.0.1.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.core.config import settings
from app.core.database import set_setting
from app.services import llm
from app.services.ai_provider import RESPOSTA_IA
from app.services.questions import AUSENCIA, CONFLITO, FATO, INFERENCIA, TRECHOS, answer_question
from tests.helpers import logged_client

HEADERS = {"X-Requested-With": "AgenteDocumental"}


class FakeLLM:
    def __init__(self):
        self.requests = []
        self.responder = lambda passages, messages: "Resposta sem fonte."
        handler = self._handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send({"data": [{"id": "modelo-teste"}, {"id": "outro"}]})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append(payload)
                user = payload["messages"][-1]["content"]
                passages = {int(n): t for n, t in re.findall(r"\[F(\d+)\][^\n]*\n(.*?)(?=\n\n\[F|\Z)", user, re.S)}
                text = fake.responder(passages, payload["messages"])
                self._send({"choices": [{"message": {"role": "assistant", "content": text}}]})

        return Handler

    def ref(self, passages, needle):
        return next(n for n, t in passages.items() if needle in t)

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def fake_llm(indexed):
    server = FakeLLM()
    set_setting("ai_provider", "llm_local")
    set_setting("llm_base_url", server.url)
    set_setting("llm_model", "modelo-teste")
    yield server
    server.close()


# ---------- respostas aceitas ----------

def test_resposta_validada_e_citada(fake_llm):
    def respond(p, _):
        return (f"A vigência foi prorrogada até 28/02/2024 pelo 1º Termo Aditivo [F{fake_llm.ref(p, '28/02/2024')}], "
                f"sendo o término original 28/02/2023 [F{fake_llm.ref(p, '28/02/2023')}]. Esta conclusão decorre "
                "da relação entre os documentos.")
    fake_llm.responder = respond
    res = answer_question("Quando encerra o contrato 034/2022?")
    assert res["kind"] == INFERENCIA and res["provider"] == "llm_local"
    assert res["ai"]["validated"] is True and res["ai"]["local_answer"]
    assert "[1]" in res["answer"] and "[F" not in res["answer"]
    assert [s["ref"] for s in res["sources"]] == [1, 2]
    assert res["sources"][0]["filename"] == "1_Termo_Aditivo_034_2022.docx"


def test_conflito_exige_todos_os_valores(fake_llm):
    fake_llm.responder = lambda p, _: f"O valor global é R$ 120.000,00 [F{fake_llm.ref(p, '120.000,00')}]."
    res = answer_question("Qual o valor do contrato 034/2022?")
    assert res["kind"] == CONFLITO and res["ai"]["validated"] is False
    assert "não apresentou todos os valores divergentes" in res["ai"]["reasons"][0]
    assert any("descartada" in w for w in res["warnings"])

    fake_llm.responder = lambda p, _: (
        f"Os documentos divergem: R$ 120.000,00 [F{fake_llm.ref(p, '120.000,00')}] e "
        f"R$ 100.000,00 [F{fake_llm.ref(p, '100.000,00')}]. É necessária conferência documental.")
    res = answer_question("Qual o valor do contrato 034/2022?")
    assert res["kind"] == CONFLITO and res["ai"]["validated"] is True


def test_pergunta_livre_redigida_pela_ia(fake_llm):
    fake_llm.responder = lambda p, _: (
        f"A reunião tratou da manutenção do ar-condicionado do bloco B [F{fake_llm.ref(p, 'ar-condicionado')}].")
    res = answer_question("manutenção do ar-condicionado do bloco B")
    assert res["kind"] == RESPOSTA_IA and res["confidence"] == "média"


# ---------- respostas descartadas ----------

@pytest.mark.parametrize("answer, reason", [
    ("O contrato encerra em 31/12/2025 [F1].", "data sem respaldo"),
    ("O valor é R$ 999.999,99 [F1].", "valor sem respaldo"),
    ("A contratada tem CNPJ 99.999.999/0001-99 [F1].", "CNPJ sem respaldo"),
    ("O contrato encerra em 28/02/2024 [F99].", "citou trechos inexistentes"),
    ("O contrato encerra em 28/02/2024.", "sem citação"),
    ("Não localizei essa informação nos documentos disponibilizados.", "não reconheceu"),
])
def test_alucinacoes_sao_descartadas(fake_llm, answer, reason):
    fake_llm.responder = lambda p, _: answer
    res = answer_question("Quando encerra o contrato 034/2022?")
    assert res["ai"]["validated"] is False
    assert any(reason in r for r in res["ai"]["reasons"]), res["ai"]["reasons"]
    assert res["kind"] == INFERENCIA and "28/02/2024" in res["answer"]  # resposta local preservada


def test_ia_considera_trechos_insuficientes(fake_llm):
    fake_llm.responder = lambda p, _: "Não localizei essa informação nos documentos disponibilizados."
    res = answer_question("manutenção do ar-condicionado do bloco B")
    assert res["kind"] == AUSENCIA and res["sources"] == []


def test_ausencia_nao_consulta_a_ia(fake_llm):
    res = answer_question("Qual a forma de pagamento do contrato 034/2022?")
    assert res["kind"] == AUSENCIA and fake_llm.requests == []


def test_servidor_indisponivel_usa_mecanismo_local(indexed):
    set_setting("ai_provider", "llm_local")
    set_setting("llm_base_url", "http://127.0.0.1:9/v1")  # porta sem servidor
    set_setting("llm_model", "modelo-teste")
    res = answer_question("Qual é o objeto do contrato 034/2022?")
    assert res["kind"] == FATO and res["ai"]["used"] is False
    assert any("IA indisponível" in w for w in res["warnings"])


# ---------- conteúdo enviado ----------

def test_envia_somente_trechos_e_regras(fake_llm, monkeypatch):
    monkeypatch.setattr(settings, "llm_max_passages", 3)
    fake_llm.responder = lambda p, _: f"O objeto é limpeza e conservação predial [F{fake_llm.ref(p, 'limpeza')}]."
    answer_question("Qual é o objeto do contrato 034/2022?")
    payload = fake_llm.requests[-1]
    system, user = payload["messages"][0]["content"], payload["messages"][1]["content"]
    assert "EXCLUSIVAMENTE" in system and payload["temperature"] == 0
    assert len(re.findall(r"^\[F\d+\]", user, re.M)) <= 3
    assert "Certidao_FGTS" not in user  # nada fora do contrato perguntado


# ---------- privacidade ----------

def test_mascaramento_de_dados_pessoais():
    text = ("Servidor CPF 123.456.789-09, e-mail fulano@exemplo.gov.br, telefone (65) 99999-1234. "
            "CNPJ 12.345.678/0001-90, processo 23188.000123/2022-11, valor R$ 120.000,00, data 28/02/2024.")
    masked, n = llm.mask_personal(text)
    assert n == 3
    assert "[CPF]" in masked and "[E-MAIL]" in masked and "[TELEFONE]" in masked
    for kept in ("12.345.678/0001-90", "23188.000123/2022-11", "R$ 120.000,00", "28/02/2024"):
        assert kept in masked


def test_endereco_externo_bloqueado_por_padrao():
    with pytest.raises(llm.LLMError, match="LOCAL ONLY"):
        llm.check_url("https://api.exemplo.com/v1")
    llm.check_url("http://localhost:1234/v1")


def test_endereco_externo_autorizado_recebe_dados_mascarados(monkeypatch):
    monkeypatch.setattr(settings, "ai_allow_remote", True)
    sent = {}

    def fake_request(url, payload=None, timeout=30):
        sent.update(payload)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(llm, "_request", fake_request)
    llm.chat("https://servidor.exemplo.com/v1", "m", [{"role": "user", "content": "CPF 123.456.789-09"}])
    assert sent["messages"][0]["content"] == "CPF [CPF]"


# ---------- API e painel ----------

def test_api_configuracao_e_teste(fake_llm):
    with logged_client() as client:
        st = client.get("/api/ai").json()
        assert st["provider"] == "llm_local" and st["reachable"] and "modelo-teste" in st["models"]
        assert client.get("/api/ai/models", params={"base_url": fake_llm.url}).json()["models"][0] == "modelo-teste"

        fake_llm.responder = lambda p, m: "OK"
        assert client.post("/api/ai/test", headers=HEADERS).json()["ok"] is True

        r = client.post("/api/ai", json={"provider": "llm_local", "base_url": "https://api.exemplo.com/v1",
                                         "model": "x"}, headers=HEADERS)
        assert r.status_code == 400 and "LOCAL ONLY" in r.json()["detail"]

        r = client.post("/api/ai", json={"provider": "local"}, headers=HEADERS)
        assert r.json()["provider"] == "local"
        res = client.post("/api/ask", json={"question": "Qual é o objeto do contrato 034/2022?"}, headers=HEADERS)
        assert res.json()["provider"] == "local"


def test_relatorio_da_consulta_registra_mecanismo(fake_llm):
    from app.services import reports

    fake_llm.responder = lambda p, _: f"O objeto é limpeza e conservação predial [F{fake_llm.ref(p, 'limpeza')}]."
    data = json.loads(reports.generate("consulta", "json", question="Qual é o objeto do contrato 034/2022?")[1])
    assert "IA local (modelo-teste)" in data["metadados"]["Mecanismo"]


def test_sem_ia_configurada_funciona_como_antes(indexed):
    res = answer_question("Qual é o objeto do contrato 034/2022?")
    assert res["provider"] == "local" and res["ai"] is None and res["kind"] == FATO
    assert answer_question("manutenção do ar-condicionado do bloco B")["kind"] == TRECHOS
