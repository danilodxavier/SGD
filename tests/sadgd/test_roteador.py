"""Roteador (SAD-070, RF-15) — TDD."""
import pytest

from app.application.agentes.roteador import rotear


@pytest.mark.parametrize("pergunta,rota", [
    ("Qual é o valor global do Contrato nº 012/2023?", "F1_simples"),
    ("Qual o CNPJ da empresa contratada no Contrato nº 031/2023?", "F1_simples"),
    ("A Portaria nº 010/2023 ainda está vigente?", "F1_complexa"),
    ("Após o termo aditivo de prorrogação, até quando vigora o Contrato nº 044/2023?", "F1_complexa"),
    ("Quais leis foram revogadas pela Lei nº 14.133/2021?", "F1_complexa"),
    ("O que substituiu a Instrução Normativa nº 01/2022?", "F1_complexa"),
    ("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?", "F2"),
    ("Posso contratar novamente a empresa Brilho Serviços Gerais Ltda.?", "F2"),
    ("É recomendável pagar a próxima fatura do Contrato nº 044/2023?", "F2"),
    ("Como devo tratar a divergência de valor do Contrato nº 120/2022 antes de autorizar pagamentos?", "F2"),
    ("Vale a pena aditar o valor da obra novamente?", "F2"),
    ("A compra de mobiliário pode prosseguir sem a declaração orçamentária?", "F2"),
])
def test_rota(pergunta, rota):
    assert rotear(pergunta).rota == rota


def test_f1_simples_nao_aciona_especialistas_e_f2_aciona_gestor_e_no_maximo_4():
    assert rotear("Qual o valor do Contrato nº 012/2023?").agentes == []
    d = rotear("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância considerando o orçamento?")
    assert "gestor_publico" in d.agentes and len(d.agentes) <= 4
    assert "fiscal_contrato" in d.agentes and "analista_orcamentario_financeiro" in d.agentes


def test_agentes_por_tema():
    licit = rotear("Devo usar dispensa de licitação ou pregão para a nova contratação?")
    assert "especialista_licitacoes" in licit.agentes
    ctrl = rotear("Posso pagar a fatura apesar da irregularidade apontada pelo TCE?")
    assert "controlador_geral" in ctrl.agentes
    jur = rotear("É legal rescindir o contrato e aplicar sanção sem notificação prévia?")
    assert {"procurador_estado", "advogado"} & set(jur.agentes)


def test_consultas_de_busca_e_filtros():
    d = rotear("Qual é o valor global do Contrato nº 012/2023?")
    assert d.consultas_busca[0] == "Qual é o valor global do Contrato nº 012/2023?"
    assert d.filtros.get("contrato") == "012/2023"
    assert d.metodo == "regras"
