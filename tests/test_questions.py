"""Perguntas: intenções menos frequentes e cenário com mais de um contrato."""
import pytest

from app.indexing.indexer import run_index
from app.services.questions import AUSENCIA, CONFLITO, FATO, TRECHOS, answer_question, detect_intent
from tests.sample_docs import write_pdf

OUTRO_CONTRATO = """CONTRATO Nº 099/2023
PROCESSO Nº 23188.000999/2023-55
O INSTITUTO FEDERAL DE EXEMPLO, doravante denominado CONTRATANTE, e a empresa BETA VIGILÂNCIA LTDA, inscrita no CNPJ sob o nº 98.765.432/0001-10, doravante denominada CONTRATADA, celebram o presente contrato.
CLÁUSULA PRIMEIRA – DO OBJETO
1.1. O presente contrato tem por objeto a prestação de serviços de vigilância patrimonial armada.
CLÁUSULA SEGUNDA – DA VIGÊNCIA
2.1. A vigência deste contrato será de 24 (vinte e quatro) meses, com início em 01/07/2023 e término em 30/06/2025.
CLÁUSULA TERCEIRA – DO VALOR
3.1. O valor global do contrato é de R$ 480.000,00.
Assinado em 20/06/2023."""


@pytest.fixture()
def two_contracts(indexed):
    write_pdf(indexed["root"] / "Contratos" / "Contrato_099_2023.pdf", [OUTRO_CONTRATO])
    run_index()
    return indexed


@pytest.mark.parametrize("question, intent", [
    ("Quais documentos comprovam a vigência?", "comprova_vigencia"),
    ("Quais documentos estão relacionados ao contrato?", "relacionados"),
    ("Qual o valor atualizado?", "valor_atualizado"),
    ("Qual o CNPJ da contratada?", "cnpj"),
    ("Quando começa a vigência?", "inicio"),
    ("Qual foi o último aditivo?", "ultimo_aditivo"),
    ("Qual o número do processo?", "processo"),
    ("Quem é o fornecedor?", "contratada"),
    ("bom dia", None),
])
def test_deteccao_de_intencoes(question, intent):
    assert detect_intent(question) == intent


def test_inicio_e_processo(indexed):
    res = answer_question("Quando começa a vigência do contrato 034/2022?")
    assert res["kind"] == FATO and "01/03/2022" in res["answer"]
    res = answer_question("Qual o número do processo do contrato 034/2022?")
    assert res["kind"] == FATO and "23188.000123/2022-11" in res["answer"]


def test_valor_atualizado_com_conflito(indexed):
    res = answer_question("Qual o valor atualizado do contrato 034/2022?")
    assert res["kind"] == CONFLITO  # base divergente: nada é escolhido automaticamente


def test_pergunta_curta_e_sem_termos(indexed):
    assert answer_question("?")["kind"] == AUSENCIA
    assert answer_question("qual o?")["kind"] == AUSENCIA


def test_relacionados_sem_numero_lista_contratos(two_contracts):
    res = answer_question("Quais documentos estão relacionados ao contrato?")
    assert res["kind"] == TRECHOS and "034/2022" in res["answer"] and "099/2023" in res["answer"]


def test_varios_contratos_sem_numero(two_contracts):
    res = answer_question("Qual o objeto do contrato?")
    assert "034/2022" in res["answer"] and "099/2023" in res["answer"]
    assert "Informe o número do contrato" in res["answer"]


def test_contrato_especifico_entre_varios(two_contracts):
    res = answer_question("Qual o valor do contrato 099/2023?")
    assert res["kind"] == FATO and "R$ 480.000,00" in res["answer"]
    res = answer_question("Quando foi assinado o contrato 099/2023?")
    assert res["kind"] == FATO and "20/06/2023" in res["answer"]
    res = answer_question("Quem é a contratada do contrato 099/2023?")
    assert "BETA VIGILÂNCIA LTDA" in res["answer"] and "98.765.432/0001-10" in res["answer"]
    res = answer_question("Quais termos aditivos existem no contrato 099/2023?")
    assert res["kind"] == AUSENCIA and "099/2023" in res["answer"]


def test_ultimo_aditivo_sem_numeracao_e_inferencia(indexed):
    from docx import Document

    doc = Document()
    doc.add_paragraph("TERMO ADITIVO AO CONTRATO Nº 034/2022 — repactuação")
    doc.add_paragraph("O valor global do contrato passa a ser de R$ 130.000,00.")
    doc.save(str(indexed["root"] / "Contratos" / "034-2022" / "Aditivo_repactuacao_034.docx"))
    run_index()
    res = answer_question("Qual foi o último aditivo do contrato 034/2022?")
    assert "data de modificação" in res["answer"]


def test_clausula_transcrita_literalmente(indexed):
    res = answer_question("Como é feita a fiscalização do contrato 034/2022?")
    assert res["kind"] == FATO
    assert "«4.1. A fiscalização será exercida por servidor designado por portaria." in res["answer"]
    assert res["sources"][0]["section"] == "CLÁUSULA QUARTA – DA FISCALIZAÇÃO" and res["sources"][0]["page"] == 2
    assert "Copia_Contrato.pdf" not in res["answer"]  # cópia idêntica não é repetida


def test_clausula_inexistente_continua_ausente(indexed):
    res = answer_question("Quais são as penalidades do contrato 034/2022?")
    assert res["kind"] == AUSENCIA
