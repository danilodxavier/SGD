"""OpenDocument: ODT (texto) e ODS (planilha), lidos do content.xml dentro do pacote zip."""
import zipfile
from datetime import datetime

from defusedxml import ElementTree as ET  # XML de terceiros: protegido contra entidades maliciosas

from app.ingestion.extractor import ExtractionError, Segment
from app.ingestion.xlsx import fmt

NS = {
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}
T = "{%s}" % NS["text"]
TB = "{%s}" % NS["table"]
O = "{%s}" % NS["office"]
MAX_REPEAT = 200  # células/linhas repetidas (ex.: colunas vazias até o fim da planilha)
MAX_MEMBER_BYTES = 200 * 1024 * 1024  # proteção contra arquivos compactados maliciosos (zip bomb)


def read_member(zf, name):
    """Lê uma parte do pacote zip recusando conteúdos descompactados desproporcionais."""
    info = zf.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ExtractionError("O arquivo excede o tamanho máximo de conteúdo suportado.")
    with zf.open(info) as fh:
        data = fh.read(MAX_MEMBER_BYTES + 1)
    if len(data) > MAX_MEMBER_BYTES:
        raise ExtractionError("O arquivo excede o tamanho máximo de conteúdo suportado.")
    return data


def _content(path):
    try:
        with zipfile.ZipFile(path) as zf:
            if "content.xml" not in zf.namelist():
                raise ExtractionError("Documento OpenDocument sem conteúdo (content.xml).")
            if "META-INF/manifest.xml" in zf.namelist() and b"encryption-data" in zf.read("META-INF/manifest.xml"):
                raise ExtractionError("O documento OpenDocument está protegido por senha.")
            return ET.fromstring(read_member(zf, "content.xml"))
    except zipfile.BadZipFile as exc:
        raise ExtractionError("O arquivo OpenDocument está corrompido.") from exc


def text_of(element):
    """Texto de um elemento, respeitando espaços (text:s), tabulações e quebras de linha."""
    parts = [element.text or ""]
    for child in element:
        if child.tag == T + "s":
            parts.append(" " * int(child.get(T + "c", "1")))
        elif child.tag == T + "tab":
            parts.append("\t")
        elif child.tag == T + "line-break":
            parts.append("\n")
        elif child.tag not in (T + "note", T + "bookmark-ref"):
            parts.append(text_of(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _cell_text(cell):
    return "\n".join(text_of(p) for p in cell.iter(T + "p")).strip()


def _cell_value(cell):
    """Valor tipado gravado no arquivo (número, data); o texto exibido é usado como alternativa."""
    kind = cell.get(O + "value-type")
    try:
        if kind in ("float", "currency", "percentage"):
            return float(cell.get(O + "value"))
        if kind == "date":
            return datetime.fromisoformat(cell.get(O + "date-value", "")[:19])
    except (TypeError, ValueError):
        pass
    return _cell_text(cell)


def _rows(table):
    rows = []
    for row in table.iter(TB + "table-row"):
        values = []
        for cell in row:
            if cell.tag not in (TB + "table-cell", TB + "covered-table-cell"):
                continue
            value = _cell_value(cell)
            repeat = int(cell.get(TB + "number-columns-repeated", "1"))
            values += [value] * (min(repeat, MAX_REPEAT) if value != "" else min(repeat, 1))
        while values and values[-1] == "":
            values.pop()
        repeat_rows = int(row.get(TB + "number-rows-repeated", "1"))
        rows += [values] * (min(repeat_rows, MAX_REPEAT) if any(v != "" for v in values) else 1)
    while rows and not any(v != "" for v in rows[-1]):
        rows.pop()
    return rows


# ---------------------------------------------------------------- ODT

def extract_odt(path):
    body = _content(path).find("office:body/office:text", NS)
    if body is None:
        raise ExtractionError("O arquivo não é um documento de texto OpenDocument.")
    segments, buffer, section = [], [], None

    def flush():
        if buffer:
            segments.append(Segment("\n".join(buffer), section=section))
            buffer.clear()

    def walk(element):
        nonlocal section
        for child in element:
            if child.tag == T + "h":
                flush()
                section = " ".join(text_of(child).split())[:150] or section
                buffer.append(text_of(child))
            elif child.tag == T + "p":
                text = text_of(child)
                if text.strip():
                    buffer.append(text)
            elif child.tag == TB + "table":
                for row in _rows(child):
                    cells = [c for c in (fmt(v) for v in row) if c]
                    if cells:
                        buffer.append(" | ".join(cells))
            elif child.tag in (T + "list", T + "list-item", T + "section", T + "list-header"):
                walk(child)

    walk(body)
    flush()
    return segments, None


# ---------------------------------------------------------------- ODS

def ods_sheets(path):
    body = _content(path).find("office:body/office:spreadsheet", NS)
    if body is None:
        raise ExtractionError("O arquivo não é uma planilha OpenDocument.")
    return [(table.get(TB + "name", "Planilha"), _rows(table)) for table in body.findall("table:table", NS)]


def extract_ods(path):
    from app.ingestion.xlsx import segments_from_sheets

    return segments_from_sheets(ods_sheets(path)), None
