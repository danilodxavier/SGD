"""ResponderF1 (SAD-051, RF-07/08/10) com LLM falso — TDD das salvaguardas determinísticas."""
import json

from app.application.portas import RespostaLLM
from app.application.recuperacao.regras import TrechoRecuperado
from app.application.respostas.f1 import ResponderF1, carregar_prompt, montar_contexto
from app.domain.politicas import MENSAGEM_AUSENCIA


def tr(id_, texto, arquivo="sintetico/P01/S001_contrato.docx", dispositivo="cláusula terceira"):
    return TrechoRecuperado(id_, 1, texto, arquivo.split("/")[-1], arquivo, "CONTRATO Nº 012/2023", dispositivo,
                            1, "contrato", "sintetico", "2023-03-01", False, None)


class LLMFalso:
    nome, remoto = "falso", False

    def __init__(self, saida):
        self.saida, self.mensagens = saida, None

    def chat(self, mensagens, *, schema=None, max_tokens=700, temperatura=0.0, json_livre=False):
        self.mensagens, self.json_livre = mensagens, json_livre
        texto = json.dumps(self.saida, ensure_ascii=False)
        return RespostaLLM(texto, "falso", 120, 30, 5, json=self.saida)


TRECHOS = [tr(11, "3.1. O valor global do contrato é de R$ 1.200.000,00, para todo o período de vigência."),
           tr(12, "2.1. O prazo de vigência deste contrato é de 12 (doze) meses.", dispositivo="cláusula segunda")]


def saida(**kw):
    base = {"resposta": "O valor global é R$ 1.200.000,00 [T11].", "classificacao": "fato", "confianca": 0.9,
            "fontes": ["T11"], "lacunas": [], "aviso": ""}
    return {**base, **kw}


def test_prompt_inclui_regras_comuns_e_relator():
    texto = carregar_prompt("relator")
    assert "FONTE ÚNICA" in texto and "Papel: RELATOR" in texto and "nome:" not in texto


def test_contexto_rotula_trechos_com_metadados():
    ctx = montar_contexto(TRECHOS)
    assert ctx.startswith("[T11]") and "cláusula terceira" in ctx and "CONTRATO Nº 012/2023" in ctx


def test_resposta_factual_com_citacao_valida():
    llm = LLMFalso(saida())
    r = ResponderF1(llm).responder("Qual o valor global do Contrato nº 012/2023?", TRECHOS)
    assert r.classificacao == "fato" and [t.id for t in r.fontes] == [11]
    assert r.tokens_entrada == 120 and r.modelo == "falso"
    assert llm.json_livre is True  # sem schema estrito: a ordem dos campos é definida no prompt
    assert '"resposta"' in llm.mensagens[0]["content"].split("nesta ordem:")[1][:20]
    assert "[T11]" in llm.mensagens[-1]["content"] and "Qual o valor global" in llm.mensagens[-1]["content"]


def test_citacao_inexistente_e_descartada_e_sem_fonte_vira_ausencia():
    r = ResponderF1(LLMFalso(saida(resposta="O valor é R$ 9,99 [T999].", fontes=["T999"]))).responder("pergunta",
                                                                                                     TRECHOS)
    assert r.classificacao == "ausencia" and r.resposta == MENSAGEM_AUSENCIA and r.fontes == []
    assert r.observacoes == ["citacoes_invalidas_descartadas", "resposta_factual_sem_citacao_valida"]


def test_ausencia_declarada_pelo_modelo_usa_mensagem_institucional():
    r = ResponderF1(LLMFalso(saida(classificacao="ausencia", resposta="Não sei.", fontes=[]))).responder("x", TRECHOS)
    assert r.resposta == MENSAGEM_AUSENCIA and r.fontes == []


def test_sem_trechos_nao_chama_o_llm():
    llm = LLMFalso(saida())
    r = ResponderF1(llm).responder("pergunta sem base", [])
    assert r.classificacao == "ausencia" and llm.mensagens is None


def test_citacoes_no_texto_tambem_contam():
    r = ResponderF1(LLMFalso(saida(fontes=[]))).responder("x", TRECHOS)
    assert [t.id for t in r.fontes] == [11]


def test_fontes_numericas_sao_normalizadas_mas_continuam_validadas():
    # caso real (Llama 3.1): "fontes": [8306] em vez de ["T8306"]
    r = ResponderF1(LLMFalso(saida(resposta="O valor é R$ 1.200.000,00.", fontes=[11, "12", 999]))).responder(
        "x", TRECHOS)
    assert [t.id for t in r.fontes] == [11, 12]
    assert r.observacoes == ["citacoes_invalidas_descartadas"]  # o 999 não estava no contexto


def test_conflito_preserva_as_duas_fontes():
    s = saida(classificacao="conflito", resposta="Divergência: R$ 1,2 mi [T11] e outro valor [T12].",
              fontes=["T11", "T12"])
    r = ResponderF1(LLMFalso(s)).responder("x", TRECHOS)
    assert r.classificacao == "conflito" and len(r.fontes) == 2
