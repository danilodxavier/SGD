from app.contracts.extractor import extract, parse_contract_ref, parse_date, summarize
from app.ingestion import extractor
from tests.sample_docs import CONTRATO_P1, CONTRATO_P2


def _values(text, field):
    return [m.value for m in extract(text)[1] if m.field == field]


def test_resumo_do_contrato():
    info = summarize(CONTRATO_P1 + "\n" + CONTRATO_P2)
    assert info["contract_number"] == "034/2022"
    assert info["process_number"] == "23188.000123/2022-11"
    assert info["contractor"] == "ALFA SERVIÇOS DE LIMPEZA LTDA"
    assert info["cnpj"] == "12.345.678/0001-90"  # o CNPJ do contratante não é confundido
    assert info["value"] == "R$ 120.000,00"
    assert info["start_date"] == "01/03/2022"
    assert info["end_date"] == "28/02/2023"
    assert info["term"] == "12 meses"
    assert info["object"].startswith("a prestação de serviços contínuos de limpeza")
    assert info["signature_date"] == "25/02/2022"


def test_limite_de_prorrogacao_nao_e_prazo():
    assert "60 meses" not in _values(CONTRATO_P1, "vigencia_prazo")


def test_aditivo_prorrogacao():
    text = "Fica prorrogada a vigência do Contrato nº 034/2022 por mais 12 (doze) meses, com término em 28/02/2024."
    assert _values(text, "vigencia_fim") == ["28/02/2024"]
    prazo = [m for m in extract(text)[1] if m.field == "vigencia_prazo"]
    assert prazo[0].qualifier == "prorrogacao"


def test_valor_unitario_nao_e_valor_global():
    assert _values("O valor unitário do item é R$ 10,00.", "valor") == []


def test_datas_por_extenso():
    assert parse_date("1º de março de 2022")[0] == "01/03/2022"
    assert parse_date("31/02/1800") is None


def test_numero_do_contrato_na_pergunta():
    assert parse_contract_ref("Quando encerra o contrato 34/2022?") == "034/2022"
    assert parse_contract_ref("Qual o valor do contrato nº 034/2022?") == "034/2022"
    assert parse_contract_ref("Qual o valor?") is None


def test_documento_classificado_e_contrato_registrado(indexed):
    from app.core.database import get_conn

    with get_conn() as conn:
        rows = {r["filename"]: dict(r) for r in conn.execute("SELECT filename, doc_type, ordinal, contract_ref, status "
                                                             "FROM documents")}
        contracts = conn.execute("SELECT contract_number, contractor FROM contracts").fetchall()
    assert rows["Contrato_034_2022.pdf"]["doc_type"] == "CONTRATO"
    assert rows["1_Termo_Aditivo_034_2022.docx"]["doc_type"] == "ADITIVO"
    assert rows["1_Termo_Aditivo_034_2022.docx"]["ordinal"] == 1
    assert rows["Planilha_Itens_034_2022.xlsx"]["contract_ref"] == "034/2022"
    assert rows["arquivo_corrompido.pdf"]["status"] == extractor.STATUS_CORROMPIDO
    assert {c["contract_number"] for c in contracts} == {"034/2022"}


def test_rotulo_contratada_termina_no_fim_da_linha():
    text = "Contratada: ALFA SERVIÇOS DE LIMPEZA LTDA\nValor global de R$ 100.000,00 conforme planilha."
    assert _values(text, "contratada") == ["ALFA SERVIÇOS DE LIMPEZA LTDA"]


def test_texto_achatado_identico_ao_flatten():
    from app.contracts.extractor import _flatten_with_breaks
    from app.core.text import flatten

    sample = "  linha 1\n\n  linha\t2  \r\n fim  "
    flat, breaks = _flatten_with_breaks(sample)
    assert flat == flatten(sample)
    assert [flat[b] for b in breaks] == [" ", " "]
