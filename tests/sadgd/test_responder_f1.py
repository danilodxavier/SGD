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
    assert r.observacoes == ["citacoes_invalidas_descartadas", "resposta_factual_sem_citacao_valida",
                             "segunda_leitura_evidencias", "citacoes_invalidas_descartadas",
                             "resposta_factual_sem_citacao_valida"]


class LLMLeituras(LLMFalso):
    def __init__(self, *saidas):
        super().__init__(None)
        self.saidas, self.todas = list(saidas), []

    def chat(self, mensagens, **kw):
        self.saida = self.saidas.pop(0)
        self.todas.append(mensagens)
        return super().chat(mensagens, **kw)


def test_recusa_na_primeira_leitura_ganha_segunda_leitura_pelas_evidencias():
    llm = LLMLeituras(saida(classificacao="ausencia", resposta="Não localizei.", fontes=["T11", "T12"]),
                       {"evidencias": ["T11"], **saida()})
    r = ResponderF1(llm).responder("Qual o valor global?", TRECHOS)
    assert r.classificacao == "fato" and [t.id for t in r.fontes] == [11]
    assert "segunda_leitura_evidencias" in r.observacoes and r.tokens_entrada == 240
    primeira, segunda = (m[0]["content"].split("nesta ordem:")[1] for m in llm.todas)
    assert primeira.lstrip().startswith('"resposta"')
    assert segunda.index('"evidencias"') < segunda.index('"resposta"')


def test_resposta_na_primeira_leitura_nao_paga_segunda_chamada():
    llm = LLMLeituras(saida())
    assert ResponderF1(llm).responder("Qual o valor global?", TRECHOS).classificacao == "fato"
    assert len(llm.todas) == 1


def test_recusa_confirmada_na_segunda_leitura_continua_recusa():
    llm = LLMLeituras(saida(classificacao="ausencia", fontes=[]), saida(classificacao="ausencia", fontes=[]))
    r = ResponderF1(llm).responder("Qual a multa?", TRECHOS)
    assert r.resposta == MENSAGEM_AUSENCIA and r.fontes == [] and len(llm.todas) == 2


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


class ConflitosFalsos:
    def __init__(self, itens):
        self.itens, self.consultados = itens, None

    def entre(self, documentos):
        self.consultados = set(documentos)
        return [c for c in self.itens if c.origem in documentos and c.destino in documentos]


def test_conflito_do_grafo_gera_resposta_deterministica_sem_llm():
    from app.application.respostas.f1 import Conflito

    contrato = tr(11, "3.1. O valor global do contrato é de R$ 1.200.000,00.")
    relatorio = tr(21, "O Contrato nº 012/2023, de valor global de R$ 1.250.000,00, foi executado.",
                   arquivo="sintetico/P01/S021_relatorio.docx", dispositivo=None)
    relatorio.documento_id, relatorio.titulo = 2, "RELATÓRIO DE FISCALIZAÇÃO Nº 007/2024"
    llm = LLMFalso(saida())
    conflitos = ConflitosFalsos([Conflito(1, 2, "valor_global", "R$ 1.200.000,00", "R$ 1.250.000,00")])
    r = ResponderF1(llm, conflitos=conflitos).responder("Qual é o valor global do Contrato nº 012/2023?",
                                                         [contrato, relatorio])
    assert r.classificacao == "conflito" and llm.mensagens is None
    assert "R$ 1.200.000,00" in r.resposta and "R$ 1.250.000,00" in r.resposta and "[T11]" in r.resposta
    assert {t.id for t in r.fontes} == {11, 21}
    assert r.resposta.startswith("Foram identificadas informações divergentes")


def test_conflito_cita_o_trecho_que_contem_o_valor_mesmo_fora_do_contexto():
    """Caso real T015: o contexto tinha um trecho do aditivo sem a data vigente — a citação precisa conter o valor."""
    from app.application.respostas.f1 import Conflito

    aditivo_ctx = tr(31, "CLÁUSULA PRIMEIRA – DO OBJETO\n1.1. Prorrogação do Contrato nº 058/2023.")
    aditivo_ctx.documento_id = 1
    apost = tr(41, "a vigência do Contrato nº 058/2023 encerra-se em 30/07/2025", arquivo="sintetico/S062.pdf")
    apost.documento_id = 2
    evidencia = tr(32, "2.1. O término da vigência passa de 30/06/2024 para 30/06/2025.")
    evidencia.documento_id = 1
    conflito = Conflito(1, 2, "vigencia_fim", "30/06/2025", "30/07/2025", trecho_origem=evidencia, trecho_destino=apost)
    r = ResponderF1(LLMFalso(saida()), conflitos=ConflitosFalsos([conflito])).responder(
        "Qual a data de término da vigência do Contrato nº 058/2023?", [aditivo_ctx, apost])
    assert {t.id for t in r.fontes} == {32, 41} and "[T32]" in r.resposta


def test_conflito_de_outro_campo_nao_interfere():
    from app.application.respostas.f1 import Conflito

    relatorio = tr(21, "de valor global de R$ 1.250.000,00", arquivo="sintetico/P01/S021.docx")
    relatorio.documento_id = 2
    conflitos = ConflitosFalsos([Conflito(1, 2, "valor_global", "R$ 1.200.000,00", "R$ 1.250.000,00")])
    llm = LLMFalso(saida())
    r = ResponderF1(llm, conflitos=conflitos).responder("Qual o período de vigência do Contrato nº 012/2023?",
                                                         [TRECHOS[0], relatorio])
    assert r.classificacao == "fato" and llm.mensagens is not None  # pergunta sobre vigência; conflito é de valor


class LLMSequencia(LLMFalso):
    def __init__(self, saidas):
        super().__init__(saidas[0])
        self.saidas, self.chamadas = list(saidas), 0

    def chat(self, mensagens, **kw):
        self.saida = self.saidas[min(self.chamadas, len(self.saidas) - 1)]
        self.chamadas += 1
        return super().chat(mensagens, **kw)


def test_verificador_pede_correcao_e_aceita_a_segunda_versao():
    from app.application.agentes.verificador import verificar

    ruim = saida(resposta="O valor global é R$ 1.300.000,00 [T11].")
    boa = saida(resposta="O valor global é R$ 1.200.000,00 [T11].")
    llm = LLMSequencia([ruim, boa])
    r = ResponderF1(llm, verificador=verificar).responder("Qual o valor global?", TRECHOS)
    assert llm.chamadas == 2 and "1.200.000,00" in r.resposta
    assert "verificador_nova_tentativa" in r.observacoes
    assert "1.300.000,00" in llm.mensagens[-1]["content"]  # o problema foi informado ao modelo


def test_verificador_remove_frase_sem_suporte_se_persistir():
    from app.application.agentes.verificador import verificar

    ruim = saida(resposta="O contrato vale R$ 1.200.000,00 [T11]. A vigência termina em 31/12/2099 [T12].",
                 fontes=["T11", "T12"])
    llm = LLMSequencia([ruim, ruim])
    r = ResponderF1(llm, verificador=verificar).responder("Qual o valor e a vigência?", TRECHOS)
    assert "31/12/2099" not in r.resposta and "1.200.000,00" in r.resposta
    assert "verificador_frases_removidas" in r.observacoes and r.confianca <= 0.6


def test_verificador_sem_nada_aproveitavel_vira_ausencia():
    from app.application.agentes.verificador import verificar

    ruim = saida(resposta="A vigência termina em 31/12/2099 [T12].", fontes=["T12"])
    r = ResponderF1(LLMSequencia([ruim, ruim]), verificador=verificar).responder("Vigência?", TRECHOS)
    assert r.classificacao == "ausencia" and r.resposta == MENSAGEM_AUSENCIA


def test_conflito_preserva_as_duas_fontes():
    s = saida(classificacao="conflito", resposta="Divergência: R$ 1,2 mi [T11] e outro valor [T12].",
              fontes=["T11", "T12"])
    r = ResponderF1(LLMFalso(s)).responder("x", TRECHOS)
    assert r.classificacao == "conflito" and len(r.fontes) == 2


# ------------------------------------------------ compressão do contexto (A3, acervo real, 2026-11-20)
LONGO = ("O presente termo trata da prestação de serviços de manutenção predial. " * 20
         + "A vigência do contrato fica prorrogada até 31/12/2025, conforme cláusula segunda. "
         + "As demais cláusulas permanecem inalteradas e em pleno vigor. " * 20)


def test_compressao_mantem_as_frases_da_pergunta_e_corta_o_resto():
    t = tr(7, LONGO)
    ctx = montar_contexto([t], pergunta="Até quando vai a vigência do contrato prorrogada?", max_chars=400)
    corpo = ctx.split("\n", 1)[1]
    assert "31/12/2025" in corpo and "[…]" in corpo
    assert len(corpo) <= 400 + 10
    assert all(parte.strip(" […]") in LONGO for parte in corpo.split("[…]") if parte.strip(" […]"))  # literal


def test_sem_limite_ou_trecho_curto_nao_muda_nada():
    curto = tr(8, "O valor global do contrato é de R$ 1.200.000,00.")
    assert montar_contexto([curto]) == montar_contexto([curto], pergunta="valor", max_chars=400)
    longo = tr(9, LONGO)
    assert montar_contexto([longo]) == montar_contexto([longo], pergunta="vigência", max_chars=0)


def test_sem_termo_da_pergunta_mantem_o_inicio():
    t = tr(10, LONGO)
    corpo = montar_contexto([t], pergunta="xyzzy", max_chars=300).split("\n", 1)[1]
    assert corpo.startswith("O presente termo") and len(corpo) <= 310



def test_ficha_do_documento_vai_no_cabecalho_do_trecho():
    t = tr(20, "O suporte técnico será prestado em regime 24x7.",
           arquivo="contratos/CT 012-2023 EMPRESA X/aditivos/a.pdf")
    t.numero, t.processo = "012/2023", "PROC-77"
    cabecalho = montar_contexto([t]).split("\n", 1)[0]
    assert "tipo: contrato" in cabecalho and "nº 012/2023" in cabecalho and "processo: PROC-77" in cabecalho
    assert "pasta: contratos/CT 012-2023 EMPRESA X/aditivos" in cabecalho
    assert "a.pdf" not in cabecalho.split("pasta:")[1]


def test_evidencias_listadas_com_recusa_geram_correcao_dirigida():
    llm = LLMLeituras(saida(classificacao="ausencia", fontes=[]),
                      {"evidencias": ["T11"], **saida(classificacao="ausencia", fontes=["T11"])},
                      saida())
    r = ResponderF1(llm).responder("Qual o valor global?", TRECHOS)
    assert r.classificacao == "fato" and len(llm.todas) == 3
    assert "evidencias_contradizem_recusa" in r.observacoes and r.tokens_entrada == 360
    assert "T11" in llm.todas[2][-1]["content"] and llm.todas[2][-2]["role"] == "assistant"


def test_evidencia_com_id_inexistente_nao_gera_correcao():
    llm = LLMLeituras(saida(classificacao="ausencia", fontes=[]),
                      {"evidencias": ["T999"], **saida(classificacao="ausencia", fontes=[])})
    assert ResponderF1(llm).responder("Qual a multa?", TRECHOS).resposta == MENSAGEM_AUSENCIA
    assert len(llm.todas) == 2
