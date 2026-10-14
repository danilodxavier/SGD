"""Formatos legados e OpenDocument: DOC, XLS, PPT, PPTX, RTF, ODT e ODS.

As fixtures em tests/fixtures/legados foram salvas pelo próprio Microsoft Office (conteúdo fictício;
ver gerar_fixtures_legados.ps1). Os testes não dependem do Office.
"""
import hashlib
import shutil
from pathlib import Path

import pytest

from app.contracts.items import extract_items
from app.core.database import get_conn, set_setting
from app.indexing.indexer import run_index
from app.ingestion import extractor
from app.ingestion.odf import _rows
from app.ingestion.rtf import to_text
from app.services.questions import FATO, answer_question

FIXTURES = Path(__file__).parent / "fixtures" / "legados"
CONTRACT_TEXT = [
    "CONTRATO Nº 077/2021",
    "GAMA CLIMATIZAÇÃO LTDA, inscrita no CNPJ sob o nº 11.222.333/0001-81",
    "CLÁUSULA PRIMEIRA – DO OBJETO",
    "término em 31/03/2022",
    "O valor global do contrato é de R$ 45.600,00",
    "Item | Descrição | Quantidade | Valor Unitário",
    "1 | Manutenção preventiva mensal | 12 | 2.800,00",
]


@pytest.mark.parametrize("name", ["contrato_legado.doc", "contrato_legado.rtf", "contrato_legado.odt"])
def test_documentos_de_texto(name):
    result = extractor.extract(FIXTURES / name, ocr_engine=None)
    assert result.status == extractor.STATUS_TEXTO, result.error
    for expected in CONTRACT_TEXT:
        assert expected in result.full_text, expected
    assert "Portal de Contratos" in result.full_text  # texto exibido do hiperlink
    assert "HYPERLINK" not in result.full_text and "exemplo.gov.br" not in result.full_text  # código do campo


@pytest.mark.parametrize("name", ["planilha_legada.xls", "planilha_legada.ods"])
def test_planilhas(name):
    result = extractor.extract(FIXTURES / name, ocr_engine=None)
    assert result.status == extractor.STATUS_TEXTO, result.error
    assert [s.section for s in result.segments] == ["Planilha: Itens", "Planilha: Observações"]
    assert "1 | Manutenção preventiva mensal | serviço | 12 | 2800 | 33600" in result.full_text
    assert "Data de referência | 01/04/2021" in result.full_text  # data convertida, não número serial


@pytest.mark.parametrize("name", ["apresentacao_legada.ppt", "apresentacao.pptx"])
def test_apresentacoes_por_slide(name):
    result = extractor.extract(FIXTURES / name, ocr_engine=None)
    assert result.status == extractor.STATUS_TEXTO, result.error
    assert result.pages == 2 and [s.page for s in result.segments] == [1, 2]
    assert "Contrato nº 077/2021 – manutenção de ar-condicionado" in result.segments[0].text
    assert "Atraso na recarga de gás em 15/06/2021" in result.segments[1].text
    assert "Fiscal: servidor fictício de exemplo" in result.segments[1].text  # caixa de texto avulsa
    assert "Clique para editar" not in result.full_text  # slide mestre ignorado


@pytest.mark.parametrize("name", ["protegido.doc", "protegido.xls"])
def test_arquivos_com_senha(name):
    result = extractor.extract(FIXTURES / name, ocr_engine=None)
    assert result.status == extractor.STATUS_CORROMPIDO
    assert "senha" in result.error


@pytest.mark.parametrize("ext", [".doc", ".xls", ".ppt", ".pptx", ".odt", ".ods", ".rtf"])
def test_arquivo_invalido_nao_gera_excecao(tmp_path, ext):
    path = tmp_path / f"quebrado{ext}"
    path.write_bytes(b"\x00\x01conteudo invalido" * 10)
    result = extractor.extract(path, ocr_engine=None)
    assert result.status == extractor.STATUS_CORROMPIDO and "Traceback" not in (result.error or "")


def test_doc_e_xls_disfarcados(tmp_path):
    """Sistemas costumam exportar RTF/HTML com extensão .doc/.xls."""
    rtf_as_doc = tmp_path / "relatorio.doc"
    shutil.copy(FIXTURES / "contrato_legado.rtf", rtf_as_doc)
    assert "R$ 45.600,00" in extractor.extract(rtf_as_doc, ocr_engine=None).full_text

    html_xls = tmp_path / "exportacao_sistema.xls"
    html_xls.write_text("<html><body><table><tr><th>Item</th><th>Descrição</th><th>Quantidade</th></tr>"
                        "<tr><td>1</td><td>Cadeira giratória</td><td>15</td></tr></table></body></html>",
                        encoding="utf-8")
    result = extractor.extract(html_xls, ocr_engine=None)
    assert "1 | Cadeira giratória | 15" in result.full_text
    assert extract_items(html_xls)[0]["description"] == "Cadeira giratória"


@pytest.mark.parametrize("name", ["planilha_legada.xls", "planilha_legada.ods", "contrato_legado.doc",
                                  "contrato_legado.rtf", "contrato_legado.odt"])
def test_itens_em_formatos_legados(name):
    items = extract_items(FIXTURES / name)
    assert [i["description"] for i in items] == ["Manutenção preventiva mensal", "Recarga de gás refrigerante"]
    assert items[0]["quantity"] == "12"


def test_rtf_escapes_unicode_e_grupos_ignorados():
    rtf = (r"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0 Arial;}}{\*\generator Teste;}"
           r"{\info{\title Oculto}}Vig\'eancia at\'e9 " + chr(92) + "u8364?100" + r"\par"
           r"{\field{\*\fldinst HYPERLINK https://exemplo.gov.br}{\fldrslt Portal}}\par"
           r"\trowd A\cell B\cell\row}")
    assert to_text(rtf) == "Vigência até €100\nPortal\nA | B"


def test_ods_limita_colunas_repetidas():
    from defusedxml import ElementTree as ET

    xml = ('<t:table xmlns:t="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
           'xmlns:x="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
           '<t:table-row><t:table-cell><x:p>A</x:p></t:table-cell>'
           '<t:table-cell t:number-columns-repeated="16384"/></t:table-row>'
           '<t:table-row t:number-rows-repeated="1048576"><t:table-cell/></t:table-row></t:table>')
    assert _rows(ET.fromstring(xml)) == [["A"]]


def test_indexacao_e_perguntas_com_formatos_legados(db, tmp_path):
    root = tmp_path / "legados"
    shutil.copytree(FIXTURES, root)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    set_setting("documents_root", str(root))
    result = run_index()
    assert result["found"] == 9 and result["errors"] == 2  # os dois arquivos com senha
    with get_conn() as conn:
        statuses = {r["filename"]: r["status"] for r in conn.execute("SELECT filename, status FROM documents")}
    assert all(s == "COM_TEXTO" for n, s in statuses.items() if not n.startswith("protegido"))

    res = answer_question("Qual o valor do contrato 077/2021?")
    assert res["kind"] == FATO and "R$ 45.600,00" in res["answer"]
    res = answer_question("Quem é a contratada do contrato 077/2021?")
    assert "GAMA CLIMATIZAÇÃO LTDA" in res["answer"] and "11.222.333/0001-81" in res["answer"]
    res = answer_question("Quais são os itens do contrato 077/2021?")
    assert "Manutenção preventiva mensal" in res["answer"]
    assert "A mesma relação consta de:" in res["answer"]  # DOC, RTF e ODT com a mesma tabela: listada uma vez
    assert res["answer"].count("Item 1 — Manutenção preventiva mensal") == 2  # tabela do contrato e planilha
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}


def test_conteudo_compactado_desproporcional_e_recusado(monkeypatch):
    from app.ingestion import odf

    monkeypatch.setattr(odf, "MAX_MEMBER_BYTES", 1000)  # simula um arquivo que se expande demais
    for name in ("contrato_legado.odt", "apresentacao.pptx"):
        result = extractor.extract(FIXTURES / name, ocr_engine=None)
        assert result.status == extractor.STATUS_CORROMPIDO and "tamanho máximo" in result.error
