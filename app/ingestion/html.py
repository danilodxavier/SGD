"""HTML gravado com extensão .doc/.xls (exportações de sistemas): texto e tabelas."""
from html.parser import HTMLParser

from app.ingestion.extractor import Segment
from app.ingestion.text import read_text

BLOCKS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "title"}
SKIP = {"script", "style", "head"}


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.current, self.skip = [], [], 0
        self.tables, self.row, self.cell, self.in_cell = [], None, [], False

    def _flush(self):
        text = " ".join("".join(self.current).split())
        if text:
            self.lines.append(text)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag == "table":
            self._flush()
            self.tables.append([])
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell, self.in_cell = [], True
        elif tag in BLOCKS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in ("td", "th") and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        elif tag == "tr" and self.row is not None:
            if self.tables:
                self.tables[-1].append(self.row)
            if any(self.row):
                self.lines.append(" | ".join(c for c in self.row if c))
            self.row = None
        elif tag in BLOCKS:
            self._flush()

    def handle_data(self, data):
        if self.skip:
            return
        (self.cell if self.in_cell else self.current).append(data)


def parse(path):
    parser = _Parser()
    parser.feed(read_text(path))
    parser.close()
    parser._flush()
    return parser


def extract(path):
    return [Segment("\n".join(parse(path).lines))], None


def table_sheets(path):
    return [(f"Tabela {i}", rows) for i, rows in enumerate(parse(path).tables, start=1) if rows]
