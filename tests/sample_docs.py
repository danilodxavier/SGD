"""Gera documentos FICTÍCIOS para testes e demonstração.

Nenhum dado real: órgão, empresa, CNPJs e valores são inventados.
"""
import textwrap
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont

CONTRATO_P1 = """CONTRATO Nº 034/2022
PROCESSO Nº 23188.000123/2022-11
CONTRATO DE PRESTAÇÃO DE SERVIÇOS QUE ENTRE SI CELEBRAM O INSTITUTO FEDERAL DE EXEMPLO E A EMPRESA ALFA SERVIÇOS DE LIMPEZA LTDA.
O INSTITUTO FEDERAL DE EXEMPLO, inscrito no CNPJ sob o nº 00.111.222/0001-33, doravante denominado CONTRATANTE, e a empresa ALFA SERVIÇOS DE LIMPEZA LTDA, inscrita no CNPJ sob o nº 12.345.678/0001-90, com sede na Rua Fictícia, 100, doravante denominada CONTRATADA, resolvem celebrar o presente contrato, mediante as cláusulas a seguir.
CLÁUSULA PRIMEIRA – DO OBJETO
1.1. O presente contrato tem por objeto a prestação de serviços contínuos de limpeza e conservação predial nas dependências do Campus Exemplo.
CLÁUSULA SEGUNDA – DA VIGÊNCIA
2.1. A vigência deste contrato será de 12 (doze) meses, com início em 01/03/2022 e término em 28/02/2023, podendo ser prorrogada até o limite de 60 (sessenta) meses."""

CONTRATO_P2 = """CLÁUSULA TERCEIRA – DO VALOR
3.1. O valor global do contrato é de R$ 120.000,00 (cento e vinte mil reais).
CLÁUSULA QUARTA – DA FISCALIZAÇÃO
4.1. A fiscalização será exercida por servidor designado por portaria.
Cuiabá-MT, 25 de fevereiro de 2022.
INSTITUTO FEDERAL DE EXEMPLO
ALFA SERVIÇOS DE LIMPEZA LTDA"""

ADITIVO_PARAGRAFOS = [
    ("PRIMEIRO TERMO ADITIVO AO CONTRATO Nº 034/2022", "Title"),
    ("O INSTITUTO FEDERAL DE EXEMPLO e a empresa ALFA SERVIÇOS DE LIMPEZA LTDA resolvem celebrar o presente "
     "termo aditivo.", None),
    ("CLÁUSULA PRIMEIRA – DA PRORROGAÇÃO", "Heading 1"),
    ("Fica prorrogada a vigência do Contrato nº 034/2022 por mais 12 (doze) meses, com término em 28/02/2024.", None),
    ("CLÁUSULA SEGUNDA – DO VALOR", "Heading 1"),
    ("O valor global do contrato passa a ser de R$ 126.000,00 (cento e vinte e seis mil reais).", None),
]

RESUMO_TXT = """Resumo do Contrato nº 034/2022
Contratada: ALFA SERVIÇOS DE LIMPEZA LTDA
Valor global de R$ 100.000,00 conforme planilha preliminar.
"""

CERTIDAO_FGTS = """CERTIFICADO DE REGULARIDADE DO FGTS - CRF
Inscrição: 12.345.678/0001-90
Razão Social: ALFA SERVIÇOS DE LIMPEZA LTDA
A empresa acima encontra-se em situação regular perante o FGTS.
Validade: 01/09/2026 a 30/12/2030
"""

CERTIDAO_TRABALHISTA = """CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS
Nome: ALFA SERVIÇOS DE LIMPEZA LTDA
CNPJ: 12.345.678/0001-90
Certidão emitida em 12/07/2022, com validade até 10/01/2023.
"""

PORTARIA_DIGITALIZADA = [
    "PORTARIA Nº 015/2022",
    "Designa servidor para a fiscalização de contrato.",
    "O DIRETOR-GERAL DO INSTITUTO FEDERAL DE EXEMPLO resolve:",
    "Art. 1º Designar o servidor FULANO DE TAL, matrícula 0000000, como fiscal",
    "do Contrato nº 034/2022, firmado com a empresa ALFA SERVIÇOS DE LIMPEZA LTDA.",
    "Art. 2º Esta portaria entra em vigor na data de sua publicação.",
    "Cuiabá-MT, 01 de março de 2022.",
]

ITENS = [
    ("Item", "Descrição", "Unidade", "Quantidade", "Valor Unitário", "Valor Total"),
    (1, "Servente de limpeza", "posto", 4, 1800.0, 7200.0),
    (2, "Encarregado de limpeza", "posto", 1, 2400.0, 2400.0),
    (3, "Material de limpeza", "mês", 12, 250.0, 3000.0),
]


def _pdf_escape(line):
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path, pages):
    """PDF mínimo com texto real (Helvetica, WinAnsi), uma lista de linhas por página."""
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
               3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"}
    kids = []
    next_id = 4
    for text in pages:
        lines = []
        for raw in text.splitlines():
            lines += textwrap.wrap(raw, 95) or [""]
        ops = " ".join(f"({_pdf_escape(line)}) Tj T*" for line in lines)
        stream = f"BT /F1 10 Tf 13 TL 50 800 Td {ops} ET".encode("cp1252")
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        kids.append(page_id)
        objects[page_id] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>").encode()
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for oid in sorted(objects):
        offsets[oid] = len(out)
        out += b"%d 0 obj\n" % oid + objects[oid] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for oid in range(1, size):
        out += b"%010d 00000 n \n" % offsets[oid]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    Path(path).write_bytes(bytes(out))


def write_scanned_pdf(path, lines):
    """PDF apenas com imagem (sem camada de texto), simulando um documento digitalizado."""
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        font = ImageFont.load_default(size=30)
    page = Image.new("L", (1654, 2339), 255)  # A4 a 200 dpi
    draw = ImageDraw.Draw(page)
    for i, line in enumerate(lines):
        draw.text((140, 200 + 60 * i), line, fill=0, font=font)
    page.save(str(path), "PDF", resolution=200)


def write_docx(path, paragraphs):
    doc = Document()
    for text, style in paragraphs:
        doc.add_paragraph(text, style=style) if style else doc.add_paragraph(text)
    doc.save(str(path))


def write_xlsx(path, rows, title="Itens"):
    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.append(["Planilha de itens do Contrato 034/2022"])
    for row in rows:
        ws.append(list(row))
    wb.save(str(path))


def build(folder):
    """Cria o conjunto de documentos fictícios em `folder` e devolve o caminho."""
    folder = Path(folder)
    contratos = folder / "Contratos" / "034-2022"
    contratos.mkdir(parents=True, exist_ok=True)
    write_pdf(contratos / "Contrato_034_2022.pdf", [CONTRATO_P1, CONTRATO_P2])
    write_docx(contratos / "1_Termo_Aditivo_034_2022.docx", ADITIVO_PARAGRAFOS)
    write_xlsx(contratos / "Planilha_Itens_034_2022.xlsx", ITENS)
    (contratos / "Resumo_contrato_034.txt").write_text(RESUMO_TXT, encoding="utf-8")

    regularidade = folder / "Regularidade"
    regularidade.mkdir(parents=True, exist_ok=True)
    (regularidade / "Certidao_FGTS.txt").write_text(CERTIDAO_FGTS, encoding="utf-8")
    (regularidade / "CNDT_Trabalhista.txt").write_text(CERTIDAO_TRABALHISTA, encoding="utf-8")
    write_scanned_pdf(contratos / "Portaria_Fiscal_digitalizada.pdf", PORTARIA_DIGITALIZADA)

    outros = folder / "Outros"
    outros.mkdir(parents=True, exist_ok=True)
    (outros / "Copia_Contrato.pdf").write_bytes((contratos / "Contrato_034_2022.pdf").read_bytes())
    (outros / "arquivo_corrompido.pdf").write_bytes(b"%PDF-1.4\nisto nao e um pdf valido")
    (outros / "foto_documento.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    (outros / "anotacoes.txt").write_text("Reunião sobre manutenção do ar-condicionado do bloco B.", encoding="utf-8")
    return folder
