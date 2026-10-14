"""Leitura de TXT, MD e CSV."""
import csv
import io

from app.ingestion.extractor import Segment

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def read_text(path):
    data = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract(path):
    return [Segment(read_text(path))], None


def extract_csv(path):
    content = read_text(path)
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [" | ".join(c.strip() for c in row if c.strip()) for row in csv.reader(io.StringIO(content), dialect)]
    rows = [r for r in rows if r]
    return [Segment("\n".join(rows), section="Tabela CSV", detect_headings=False)], None
