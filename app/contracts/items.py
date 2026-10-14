"""Identificação de itens contratados em tabelas (XLSX, CSV e tabelas de DOCX).

Lê o arquivo original preservando as colunas, localiza o cabeçalho (Item, Descrição, Unidade,
Quantidade, Valor unitário, Valor total) e devolve os itens exatamente como constam do documento.
"""
import csv
import io
import re

from app.core.text import fold

FIELDS = ("item_number", "description", "unit", "quantity", "unit_value", "total_value")
MONEY_FIELDS = {"unit_value", "total_value"}
MAX_ITEMS = 2000


def classify_header(value):
    h = fold(str(value or "")).strip(" .:º°")
    if not h:
        return None
    if any(k in h for k in ("descri", "especifica", "discrimina")):
        return "description"
    if "unit" in h:  # valor unitário / preço unitário
        return "unit_value"
    if "total" in h:
        return "total_value"
    if h.startswith(("quant", "qtd", "qtde")):
        return "quantity"
    if h.startswith(("unid", "medida")) or h in ("un", "und", "u.m", "um"):
        return "unit"
    if h.startswith("item") or h in ("n", "no", "nº", "n°", "numero", "seq", "#", "ordem"):
        return "item_number"
    return None


def _br_number(value, money):
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if money:
            text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {text}"
        return str(int(value)) if float(value).is_integer() else str(value).replace(".", ",")
    text = str(value).strip()
    if money and text and not text.lower().startswith("r$") and re.fullmatch(r"[\d.]+,\d{2}", text):
        return f"R$ {text}"
    return text


def items_from_rows(rows, location):
    """Percorre linhas de uma tabela e devolve os itens das regiões com cabeçalho reconhecido."""
    items, mapping = [], None
    for row in rows:
        cells = list(row)
        candidate = {i: classify_header(v) for i, v in enumerate(cells)}
        fields = {f for f in candidate.values() if f}
        if "description" in fields and fields & {"quantity", "total_value", "unit_value"}:
            mapping = {i: f for i, f in candidate.items() if f}
            continue
        if mapping is None:
            continue
        values = {f: cells[i] for i, f in mapping.items() if i < len(cells)}
        description = str(values.get("description") or "").strip()
        if not description:
            if not any(str(v or "").strip() for v in cells):
                mapping = None  # linha em branco encerra a tabela
            continue
        if fold(description).startswith(("total", "valor global", "subtotal")) and not values.get("item_number"):
            continue
        item = {f: _br_number(values[f], f in MONEY_FIELDS) if values.get(f) not in (None, "") else None
                for f in FIELDS}
        item["description"] = description
        item["location"] = location
        items.append(item)
        if len(items) >= MAX_ITEMS:
            break
    return items


def _from_sheets(sheets):
    out = []
    for title, rows in sheets:
        out += items_from_rows(rows, f"Planilha: {title}")
    return out


def _xlsx(path):
    from app.ingestion.xlsx import xlsx_sheets

    return _from_sheets(xlsx_sheets(path))


def _xls(path):
    from app.ingestion.xlsx import xls_sheets

    return _from_sheets(xls_sheets(path))


def _ods(path):
    from app.ingestion.odf import ods_sheets

    return _from_sheets(ods_sheets(path))


def _text_tables(path):
    """DOC, RTF e ODT: as tabelas chegam como linhas “a | b | c” no texto extraído."""
    from app.ingestion import extractor

    text = extractor.extract(path, ocr_engine=None).full_text
    rows = [line.split(" | ") if " | " in line else [] for line in text.splitlines()]
    return items_from_rows(rows, "Tabela")


def _csv(path):
    from app.ingestion.text import read_text

    content = read_text(path)
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    return items_from_rows(csv.reader(io.StringIO(content), dialect), "Tabela CSV")


def _docx(path):
    from docx import Document

    out = []
    for n, table in enumerate(Document(str(path)).tables, start=1):
        rows = [[c.text for c in row.cells] for row in table.rows]
        out += items_from_rows(rows, f"Tabela {n}")
    return out


READERS = {".xlsx": _xlsx, ".xlsm": _xlsx, ".xls": _xls, ".ods": _ods, ".csv": _csv, ".docx": _docx,
           ".doc": _text_tables, ".rtf": _text_tables, ".odt": _text_tables}


def extract_items(path):
    reader = READERS.get(path.suffix.lower())
    return reader(path) if reader else []


def load_items(conn, contract_ref=None, doc_ids=None):
    """Itens gravados no índice, agrupados por documento de origem (cópias idênticas são ignoradas)."""
    sql = ("SELECT i.*, d.filename, d.doc_type, d.hash FROM contract_items i "
           "JOIN documents d ON d.id = i.source_document_id WHERE d.status != 'REMOVIDO'")
    params = []
    if doc_ids is not None:
        if not doc_ids:
            return {}
        sql += f" AND (i.source_document_id IN ({','.join('?' * len(doc_ids))})"
        params += list(doc_ids)
        sql += " OR i.contract_ref = ?)" if contract_ref else ")"
        params += [contract_ref] if contract_ref else []
    elif contract_ref:
        sql += " AND i.contract_ref = ?"
        params.append(contract_ref)
    groups, hashes = {}, {}
    for row in conn.execute(sql + " ORDER BY i.source_document_id, i.id", params):
        r = dict(row)
        owner = hashes.setdefault(r["hash"], r["source_document_id"])
        if owner != r["source_document_id"]:
            continue
        groups.setdefault(r["source_document_id"], []).append(r)
    return groups


def describe(item):
    parts = [f"Item {item['item_number']}" if item.get("item_number") else None, item["description"]]
    if item.get("quantity"):
        parts.append(f"{item['quantity']} {item.get('unit') or ''}".strip())
    if item.get("unit_value"):
        parts.append(f"valor unitário {item['unit_value']}")
    if item.get("total_value"):
        parts.append(f"valor total {item['total_value']}")
    return " — ".join(p for p in parts if p)
