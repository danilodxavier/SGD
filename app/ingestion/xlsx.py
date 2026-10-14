"""Planilhas: XLSX/XLSM (openpyxl), XLS do Excel 97-2003 (xlrd) e ODS (OpenDocument).

Cada formato fornece as abas como [(nome, linhas)], com as colunas preservadas; a montagem dos
trechos (uma seção por aba, cabeçalho repetido a cada bloco) é comum a todos.
"""
from app.ingestion.extractor import ExtractionError, Segment

ROWS_PER_SEGMENT = 40


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


def segments_from_sheets(sheets):
    segments = []
    for title, rows in sheets:
        header = None
        lines = []
        for row in rows:
            cells = [c for c in (fmt(v) for v in row) if c]
            if not cells:
                continue
            line = " | ".join(cells)
            if header is None and len(cells) > 1:
                header = line
            lines.append(line)
        # blocos de linhas repetindo o cabeçalho, para que cada trecho seja compreensível
        for start in range(0, len(lines), ROWS_PER_SEGMENT):
            block = lines[start:start + ROWS_PER_SEGMENT]
            if start > 0 and header:
                block = [header] + block
            segments.append(Segment("\n".join(block), section=f"Planilha: {title}", detect_headings=False))
    return segments


# ---------------------------------------------------------------- XLSX

def xlsx_sheets(path):
    from openpyxl import load_workbook

    workbook = load_workbook(str(path), read_only=True, data_only=True)
    try:
        return [(sheet.title, [list(r) for r in sheet.iter_rows(values_only=True)]) for sheet in workbook.worksheets]
    finally:
        workbook.close()


def extract(path):
    return segments_from_sheets(xlsx_sheets(path)), None


# ---------------------------------------------------------------- XLS (Excel 97-2003)

def xls_sheets(path):
    import xlrd

    with open(path, "rb") as fh:
        head = fh.read(512)
    if not head.startswith(b"\xd0\xcf\x11\xe0"):
        # muitos sistemas exportam "planilhas .xls" que são HTML ou texto separado por tabulação
        from app.ingestion import html

        if b"<" in head:
            return html.table_sheets(path)
        raise ExtractionError("O arquivo .xls não é uma planilha do Excel válida.")
    try:
        book = xlrd.open_workbook(str(path), on_demand=True)
    except xlrd.XLRDError as exc:
        if "encrypt" in str(exc).lower():
            raise ExtractionError("A planilha está protegida por senha.") from exc
        raise ExtractionError("O arquivo .xls está corrompido ou em formato inválido.") from exc
    try:
        sheets = []
        for sheet in book.sheets():
            rows = []
            for r in range(sheet.nrows):
                row = []
                for c in range(sheet.ncols):
                    cell = sheet.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                        except (ValueError, OverflowError):
                            row.append(cell.value)
                    elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR):
                        row.append(None)
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        row.append("Sim" if cell.value else "Não")
                    else:
                        row.append(cell.value)
                rows.append(row)
            sheets.append((sheet.name, rows))
        return sheets
    finally:
        book.release_resources()


def extract_xls(path):
    return segments_from_sheets(xls_sheets(path)), None
