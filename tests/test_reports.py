import csv
import io
import json
from datetime import date

import pytest
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from app.services import checklist, report_writers, reports
from app.services.report_writers import Report, Section, Table
from tests.test_checklist import CHECKLIST
from tests.helpers import logged_client

HEADERS = {"X-Requested-With": "AgenteDocumental"}
MAGIC = {"pdf": b"%PDF", "docx": b"PK", "xlsx": b"PK"}


@pytest.fixture()
def evaluated(indexed):
    c = checklist.create("Prorrogação 034/2022", CHECKLIST, "034/2022")
    checklist.run(c["checklist"]["id"], today=date(2026, 10, 14))
    return c["checklist"]["id"]


def _params(kind, checklist_id):
    return {"consulta": {"question": "Qual o valor do contrato 034/2022?"},
            "checklist": {"checklist_id": checklist_id}}.get(kind, {})


def _pdf_text(content):
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages)


def _docx_text(content):
    doc = Document(io.BytesIO(content))
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return "\n".join([p.text for p in doc.paragraphs] + cells)


@pytest.mark.parametrize("kind", list(reports.REPORTS))
@pytest.mark.parametrize("fmt", ["pdf", "docx", "xlsx", "csv", "json"])
def test_todos_os_relatorios_em_todos_os_formatos(evaluated, kind, fmt):
    name, content, media = reports.generate(kind, fmt, **_params(kind, evaluated))
    assert name.endswith(f".{fmt}") and content
    if fmt in MAGIC:
        assert content.startswith(MAGIC[fmt])
    if fmt == "json":
        assert json.loads(content)["relatorio"] == kind
    if fmt == "csv":
        assert content.startswith("﻿".encode())


def test_relatorio_conflitos_mostra_os_dois_valores(evaluated):
    text = _pdf_text(reports.generate("conflitos", "pdf")[1])
    assert "R$ 120.000,00" in text and "R$ 100.000,00" in text
    assert "1_Termo_Aditivo_034_2022.docx" in text and "28/02/2024" in text  # alteração por aditivo
    data = json.loads(reports.generate("conflitos", "json")[1])["dados"]
    assert {c["campo"] for c in data["conflitos"]} == {"Valor"}  # sem conflitos falsos


def test_relatorio_contratos_situacao_apos_aditivos(evaluated):
    text = _docx_text(reports.generate("contratos", "docx")[1])
    assert "ALFA SERVIÇOS DE LIMPEZA LTDA" in text
    assert "28/02/2024 (por aditivo)" in text
    assert "divergente" in text  # valor diverge entre documentos-base


def test_relatorio_inventario_xlsx(evaluated):
    wb = load_workbook(io.BytesIO(reports.generate("inventario", "xlsx")[1]))
    assert wb.sheetnames[0] == "Resumo"
    sheet = wb["Documentos"]
    assert sheet.max_row == 12  # cabeçalho + 11 documentos
    assert sheet["A1"].value == "Arquivo"


def test_relatorio_ausentes(evaluated):
    rows = reports.generate("ausentes", "csv")[1].decode("utf-8-sig").splitlines()
    assert rows[0].startswith("Checklist;Contrato;Item;Requisito")
    assert any("Garantia contratual" in r for r in rows)
    text = _pdf_text(reports.generate("ausentes", "pdf")[1])
    assert "Certidão negativa de débitos trabalhistas" in text  # seção de vencidos


def test_relatorio_consulta(evaluated):
    text = _pdf_text(reports.generate("consulta", "pdf", question="Qual é o objeto do contrato 034/2022?")[1])
    assert "limpeza e conservação predial" in text
    assert "Contrato_034_2022.pdf" in text
    with pytest.raises(reports.ReportError):
        reports.generate("consulta", "pdf", question="")


def test_relatorio_checklist(evaluated):
    text = _pdf_text(reports.generate("checklist", "pdf", checklist_id=evaluated)[1])
    assert "PARCIALMENTE ATENDIDO" in text and "Organização virtual" in text
    with pytest.raises(reports.ReportError):
        reports.generate("checklist", "pdf", checklist_id=9999)


def test_copia_salva_em_data_reports(evaluated):
    name, _, _ = reports.generate("contratos", "pdf")
    assert name in [f["name"] for f in reports.list_files()]
    assert reports.file_path(name) is not None
    for bad in ("..\\test.db", "../x.pdf", ".env", "a/b.pdf"):
        assert reports.file_path(bad) is None


def test_formato_invalido(evaluated):
    with pytest.raises(reports.ReportError):
        reports.generate("inventario", "exe")


def test_pdf_sem_fonte_unicode(evaluated, tmp_path, monkeypatch):
    monkeypatch.setattr(report_writers, "FONT_DIR", tmp_path / "sem_fontes")
    content = reports.generate("conflitos", "pdf")[1]
    assert "Conflitos documentais" in _pdf_text(content)


def test_texto_de_documento_nao_vira_formula():
    report = Report("x", "Teste", sections=[Section("Dados", table=Table(["Valor"], [["=HYPERLINK(\"http://x\")"]]))])
    wb = load_workbook(io.BytesIO(report_writers.to_xlsx(report)))
    cell = wb["Dados"]["A2"]
    assert cell.data_type == "s" and cell.value.startswith("=HYPERLINK")
    rows = list(csv.reader(io.StringIO(report_writers.to_csv(report).decode("utf-8-sig")), delimiter=";"))
    assert rows[1][0].startswith("'=")


def test_caracteres_de_controle_removidos():
    report = Report("x", "Teste\x00", sections=[Section("Dados", paragraphs=["linha\x07"],
                                                          table=Table(["A"], [["b\x0bc"]]))])
    assert report_writers.to_docx(report)[:2] == b"PK"
    assert report_writers.to_xlsx(report)[:2] == b"PK"


# ---------- API ----------

@pytest.fixture()
def client(evaluated):
    with logged_client() as c:
        yield c


def test_api_relatorios(client, evaluated):
    catalog = client.get("/api/reports").json()
    assert {r["kind"] for r in catalog["reports"]} == set(reports.REPORTS)

    r = client.get("/api/reports/contratos", params={"format": "pdf"})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]

    files = client.get("/api/reports/files").json()
    assert files and client.get(f"/api/reports/files/{files[0]['name']}").status_code == 200
    assert client.get("/api/reports/files/..%5C..%5Ctest.db").status_code == 404

    assert client.get("/api/reports/consulta", params={"format": "pdf"}).status_code == 400
    assert client.get("/api/reports/desconhecido").status_code == 404
    assert client.get("/api/reports/inventario", params={"format": "exe"}).status_code == 400


def test_api_checklist_em_pdf_docx_xlsx(client, evaluated):
    for fmt in ("pdf", "docx", "xlsx"):
        r = client.get(f"/api/checklists/{evaluated}/export", params={"format": fmt})
        assert r.status_code == 200 and r.content.startswith(MAGIC[fmt])
    assert client.get("/api/checklists/9999/export", params={"format": "pdf"}).status_code == 404
