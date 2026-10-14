"""Leitura de DOCX (python-docx), preservando a ordem de parágrafos e tabelas."""
from docx import Document
from docx.table import Table

from app.ingestion.extractor import Segment

HEADING_STYLES = ("heading", "título", "titulo", "title")


def _table_text(table):
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            value = cell.text.strip()
            if value and (not cells or cells[-1] != value):  # células mescladas se repetem
                cells.append(value)
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract(path):
    document = Document(str(path))
    segments = []
    section = None
    buffer = []

    def flush():
        if buffer:
            segments.append(Segment("\n".join(buffer), section=section))
            buffer.clear()

    for block in document.iter_inner_content():
        if isinstance(block, Table):
            buffer.append(_table_text(block))
            continue
        text = block.text.strip()
        if not text:
            continue
        style = (block.style.name if block.style is not None else "").lower()
        if style.startswith(HEADING_STYLES):
            flush()
            section = text[:150]
        buffer.append(text)
    flush()
    return segments, None
