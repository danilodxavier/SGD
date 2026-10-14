"""Modelo neutro de relatório e sua gravação em PDF, DOCX, XLSX, CSV e JSON.

Os relatórios são montados uma única vez (título, metadados, seções com parágrafos,
listas e tabelas) e cada formato apenas os desenha.
"""
import csv
import io
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

FORMATS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
}
APP_NAME = "Agente de Inteligência Documental"
MAX_CELL = 1500  # evita células maiores que uma página no PDF
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
FORMULA_START = ("=", "+", "@", "\t", "\r")


@dataclass
class Table:
    columns: list
    rows: list
    widths: list | None = None  # proporções relativas das colunas


@dataclass
class Section:
    title: str
    paragraphs: list = field(default_factory=list)
    bullets: list = field(default_factory=list)
    table: Table | None = None


@dataclass
class Report:
    kind: str
    title: str
    subtitle: str = ""
    meta: list = field(default_factory=list)  # [(rótulo, valor)]
    sections: list = field(default_factory=list)
    landscape: bool = False
    primary: int | None = None  # seção cuja tabela vai para o CSV
    data: dict | None = None  # conteúdo estruturado para o JSON
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    def main_table(self):
        if self.primary is not None and self.sections[self.primary].table:
            return self.sections[self.primary].table
        return next((s.table for s in self.sections if s.table), None)


def clean(value, limit=None):
    """Texto seguro para qualquer formato: sem caracteres de controle e com tamanho limitado."""
    if value is None:
        return ""
    text = CONTROL_CHARS.sub("", str(value))
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def safe_cell(value):
    """Impede que texto vindo de documentos seja interpretado como fórmula por planilhas."""
    text = clean(value)
    return "'" + text if text.startswith(FORMULA_START) else text


# ---------------------------------------------------------------- PDF

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
FONT_FILES = {"": "arial.ttf", "B": "arialbd.ttf", "I": "ariali.ttf"}
LATIN1_REPLACEMENTS = str.maketrans({
    "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-", "·": "-",
    "├": "|", "└": "`", "│": "|", "✓": "v",
})


def unicode_font_available():
    return all((FONT_DIR / f).exists() for f in FONT_FILES.values())


def to_pdf(report):
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    class PDF(FPDF):
        family = "helvetica"
        unicode = False

        def t(self, text, limit=None):
            text = clean(text, limit)
            if self.unicode:
                return text
            return text.translate(LATIN1_REPLACEMENTS).encode("latin-1", "replace").decode("latin-1")

        def footer(self):
            self.set_y(-12)
            self.set_font(self.family, "I", 7.5)
            self.set_text_color(110, 110, 110)
            self.cell(0, 6, self.t(f"{APP_NAME} — gerado localmente em {report.generated_at} · "
                                   f"Página {self.page_no()}/{{nb}}"), align="C")

    pdf = PDF(orientation="L" if report.landscape else "P", format="A4")
    if unicode_font_available():
        for style, name in FONT_FILES.items():
            pdf.add_font("arial", style, str(FONT_DIR / name))
        pdf.family, pdf.unicode = "arial", True
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    pdf.set_font(pdf.family, "B", 16)
    pdf.set_text_color(22, 40, 61)
    pdf.multi_cell(0, 8, pdf.t(report.title), new_x="LMARGIN", new_y="NEXT")
    if report.subtitle:
        pdf.set_font(pdf.family, "", 10)
        pdf.set_text_color(93, 107, 122)
        pdf.multi_cell(0, 5, pdf.t(report.subtitle), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(28, 39, 51)
    for label, value in report.meta + [("Gerado em", report.generated_at)]:
        pdf.set_font(pdf.family, "B", 9)
        pdf.cell(42, 5, pdf.t(f"{label}:"))
        pdf.set_font(pdf.family, "", 9)
        pdf.multi_cell(0, 5, pdf.t(value), new_x="LMARGIN", new_y="NEXT")

    for section in report.sections:
        pdf.ln(4)
        pdf.set_font(pdf.family, "B", 12)
        pdf.set_text_color(31, 95, 168)
        pdf.multi_cell(0, 7, pdf.t(section.title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(28, 39, 51)
        pdf.set_font(pdf.family, "", 9.5)
        for paragraph in section.paragraphs:
            pdf.multi_cell(0, 5, pdf.t(paragraph), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        for bullet in section.bullets:
            pdf.multi_cell(0, 5, pdf.t(f"•  {bullet}"), new_x="LMARGIN", new_y="NEXT")
        if section.table:
            tbl = section.table
            if not tbl.rows:
                pdf.set_font(pdf.family, "I", 9)
                pdf.multi_cell(0, 5, pdf.t("Nenhum registro."), new_x="LMARGIN", new_y="NEXT")
                continue
            pdf.set_font(pdf.family, "", 7.5)
            with pdf.table(
                col_widths=tbl.widths or [1] * len(tbl.columns),
                text_align="LEFT",
                line_height=pdf.font_size * 1.45,
                padding=1,
                headings_style=FontFace(emphasis="BOLD", fill_color=(225, 232, 241)),
            ) as table:
                for row in [tbl.columns] + tbl.rows:
                    cells = table.row()
                    for value in row:
                        cells.cell(pdf.t(value, MAX_CELL))
    return bytes(pdf.output())


# ---------------------------------------------------------------- DOCX

def to_docx(report):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    if report.landscape:
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(1.6))
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    sec.footer.paragraphs[0].text = f"{APP_NAME} — gerado localmente em {report.generated_at}"

    doc.add_heading(clean(report.title), 0)
    if report.subtitle:
        p = doc.add_paragraph()
        run = p.add_run(clean(report.subtitle))
        run.italic = True
        run.font.color.rgb = RGBColor(0x5D, 0x6B, 0x7A)
    for label, value in report.meta + [("Gerado em", report.generated_at)]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.add_run(f"{clean(label)}: ").bold = True
        p.add_run(clean(value))

    for section in report.sections:
        doc.add_heading(clean(section.title), 1)
        for paragraph in section.paragraphs:
            doc.add_paragraph(clean(paragraph))
        for bullet in section.bullets:
            doc.add_paragraph(clean(bullet), style="List Bullet")
        if section.table:
            tbl = section.table
            if not tbl.rows:
                doc.add_paragraph("Nenhum registro.").runs[0].italic = True
                continue
            table = doc.add_table(rows=1, cols=len(tbl.columns))
            table.style = "Light Grid Accent 1"
            for cell, name in zip(table.rows[0].cells, tbl.columns):
                cell.text = clean(name)
            for row in tbl.rows:
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = clean(value, MAX_CELL)
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for run in p.runs:
                            run.font.size = Pt(8)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- XLSX

def _sheet_name(title, used):
    base = re.sub(r"[\[\]:*?/\\]", " ", title).strip()[:28] or "Dados"
    name, n = base, 2
    while name.lower() in used:
        name = f"{base[:25]} {n}"
        n += 1
    used.add(name.lower())
    return name


def to_xlsx(report):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    used = {"resumo"}

    def put(sheet, row, col, value, **style):
        cell = sheet.cell(row=row, column=col)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cell.value = value
        else:
            cell.value = clean(value, 32000)
            cell.data_type = "s"  # nunca interpretar texto de documento como fórmula
        for k, v in style.items():
            setattr(cell, k, v)
        return cell

    put(ws, 1, 1, report.title, font=Font(bold=True, size=14))
    r = 2
    if report.subtitle:
        put(ws, r, 1, report.subtitle, font=Font(italic=True, color="5D6B7A"))
        r += 1
    r += 1
    for label, value in report.meta + [("Gerado em", report.generated_at)]:
        put(ws, r, 1, label, font=Font(bold=True))
        put(ws, r, 2, value)
        r += 1
    header_fill = PatternFill("solid", fgColor="E1E8F1")
    for section in report.sections:
        r += 1
        put(ws, r, 1, section.title, font=Font(bold=True, size=12, color="1F5FA8"))
        r += 1
        for text in section.paragraphs + [f"• {b}" for b in section.bullets]:
            put(ws, r, 1, text, alignment=Alignment(wrap_text=False))
            r += 1
        if not section.table:
            continue
        name = _sheet_name(section.title, used)
        put(ws, r, 1, f"Tabela na aba “{name}” ({len(section.table.rows)} linhas).", font=Font(italic=True))
        r += 1
        sheet = wb.create_sheet(name)
        tbl = section.table
        for c, column in enumerate(tbl.columns, start=1):
            put(sheet, 1, c, column, font=Font(bold=True), fill=header_fill)
        for i, row in enumerate(tbl.rows, start=2):
            for c, value in enumerate(row, start=1):
                put(sheet, i, c, value, alignment=Alignment(wrap_text=True, vertical="top"))
        for c, column in enumerate(tbl.columns, start=1):
            longest = max([len(str(column))] + [len(str(row[c - 1])) for row in tbl.rows[:500]])
            sheet.column_dimensions[get_column_letter(c)].width = min(max(10, longest + 2), 60)
        sheet.freeze_panes = "A2"
        if tbl.rows:
            sheet.auto_filter.ref = f"A1:{get_column_letter(len(tbl.columns))}{len(tbl.rows) + 1}"
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 80
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- CSV / JSON

def to_csv(report):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")  # ponto e vírgula: abre corretamente no Excel em pt-BR
    tbl = report.main_table()
    if tbl:
        writer.writerow([safe_cell(c) for c in tbl.columns])
        writer.writerows([[safe_cell(v) for v in row] for row in tbl.rows])
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def to_json(report):
    payload = {
        "relatorio": report.kind,
        "titulo": report.title,
        "gerado_em": report.generated_at,
        "metadados": dict(report.meta),
        "dados": report.data if report.data is not None else [asdict(s) for s in report.sections],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


WRITERS = {"pdf": to_pdf, "docx": to_docx, "xlsx": to_xlsx, "csv": to_csv, "json": to_json}


def render(report, fmt):
    return WRITERS[fmt](report)
