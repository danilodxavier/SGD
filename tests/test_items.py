"""Identificação de itens contratados (critério “identificar itens” da especificação)."""
from docx import Document
from openpyxl import Workbook

from app.contracts.items import classify_header, extract_items, items_from_rows
from app.core.database import get_conn


def test_cabecalhos_reconhecidos():
    assert [classify_header(h) for h in ("Item", "Descrição do serviço", "Unid.", "Qtde", "Valor Unitário (R$)",
                                         "Valor Total", "Observação")] == \
        ["item_number", "description", "unit", "quantity", "unit_value", "total_value", None]


def test_planilha_com_celulas_vazias_mantem_colunas(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["PLANILHA DE ITENS"])
    ws.append([None])
    ws.append(["Item", "Descrição", "Unidade", "Quantidade", "Valor Unitário", "Valor Total"])
    ws.append([1, "Serviço de copeiragem", None, 2, 3100.5, 6201.0])
    ws.append([2, "Lavagem de cortinas", "m²", None, None, 850])
    ws.append([None, "TOTAL", None, None, None, 7051.0])
    path = tmp_path / "itens.xlsx"
    wb.save(path)
    items = extract_items(path)
    assert len(items) == 2  # linha de total ignorada
    assert items[0]["unit"] is None and items[0]["quantity"] == "2"
    assert items[0]["unit_value"] == "R$ 3.100,50" and items[0]["total_value"] == "R$ 6.201,00"
    assert items[1]["unit"] == "m²" and items[1]["total_value"] == "R$ 850,00"


def test_tabela_de_docx_e_csv(tmp_path):
    doc = Document()
    doc.add_paragraph("Anexo I")
    table = doc.add_table(rows=1, cols=4)
    for cell, text in zip(table.rows[0].cells, ("Nº", "Especificação", "Qtd", "Preço unitário")):
        cell.text = text
    for row in (("1", "Resma de papel A4", "100", "25,90"), ("2", "Toner", "5", "310,00")):
        for cell, text in zip(table.add_row().cells, row):
            cell.text = text
    path = tmp_path / "anexo.docx"
    doc.save(path)
    items = extract_items(path)
    assert [i["description"] for i in items] == ["Resma de papel A4", "Toner"]
    assert items[0]["unit_value"] == "R$ 25,90" and items[0]["location"] == "Tabela 1"

    csv_path = tmp_path / "itens.csv"
    csv_path.write_text("Item;Descrição;Quantidade\n1;Cadeira;10\n", encoding="utf-8")
    assert extract_items(csv_path)[0]["quantity"] == "10"


def test_tabela_sem_cabecalho_de_itens_e_ignorada():
    rows = [["Nome", "Cargo"], ["Fulano", "Fiscal"]]
    assert items_from_rows(rows, "x") == []


def test_itens_gravados_na_indexacao(indexed):
    with get_conn() as conn:
        rows = conn.execute("SELECT contract_ref, item_number, description, total_value FROM contract_items "
                            "ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [
        ("034/2022", "1", "Servente de limpeza", "R$ 7.200,00"),
        ("034/2022", "2", "Encarregado de limpeza", "R$ 2.400,00"),
        ("034/2022", "3", "Material de limpeza", "R$ 3.000,00"),
    ]
