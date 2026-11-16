"""Extrator de atos normativos publicados em HTML (ex.: portal da legislação federal).

Texto tachado (<strike>, <s>, <del>) é a forma oficial de exibir dispositivos revogados ou com redação
substituída. O extrator insere o marcador "[REVOGADO]" logo após o rótulo do dispositivo (ou no início da
linha), preservando a estrutura para o chunking e registrando a revogação com base no próprio documento.
"""
import re
from html.parser import HTMLParser

BLOCOS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "title", "blockquote"}
IGNORAR = {"script", "style", "head"}
TACHADO = {"strike", "s", "del"}
MARCADOR = "[REVOGADO]"
RE_ROTULO = re.compile(
    r"^(Art\.\s*\d{1,3}(?:\.\d{3})*\s*(?:º|°|o)?(?:\s*-\s*[A-Z]{1,2})?\s*\.?"
    r"|§\s*\d+\s*(?:º|°|o)?|Par[áa]grafo\s+[úu]nico\.?|[IVXLC]+\s*[-–—]|[a-z]\))\s*")
RE_CHARSET = re.compile(rb"charset\s*=\s*[\"']?([\w-]+)", re.I)


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linhas = []
        self._partes = []  # (texto, tachado)
        self._ignorar = 0
        self._tachado = 0

    def _fechar(self):
        texto = " ".join("".join(t for t, _ in self._partes).replace("\xa0", " ").split())
        if texto:
            total = sum(len(t.strip()) for t, _ in self._partes) or 1
            riscado = sum(len(t.strip()) for t, r in self._partes if r)
            self.linhas.append(_marcar(texto) if riscado / total > 0.6 else texto)
        self._partes = []

    def handle_starttag(self, tag, attrs):
        if tag in IGNORAR:
            self._ignorar += 1
        elif tag in TACHADO:
            self._tachado += 1
        elif tag in BLOCOS:
            self._fechar()

    def handle_endtag(self, tag):
        if tag in IGNORAR:
            self._ignorar = max(0, self._ignorar - 1)
        elif tag in TACHADO:
            self._tachado = max(0, self._tachado - 1)
        elif tag in BLOCOS:
            self._fechar()

    def handle_data(self, data):
        if not self._ignorar:
            self._partes.append((data, self._tachado > 0))

    def close(self):
        super().close()
        self._fechar()


def _marcar(linha):
    m = RE_ROTULO.match(linha)
    if m:
        return f"{linha[:m.end()].rstrip()} {MARCADOR} {linha[m.end():]}".rstrip()
    return f"{MARCADOR} {linha}"


def decodificar(dados: bytes) -> str:
    m = RE_CHARSET.search(dados[:4000])
    candidatos = ([m.group(1).decode("ascii", "ignore")] if m else []) + ["utf-8", "cp1252"]
    for codificacao in candidatos:
        try:
            return dados.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return dados.decode("latin-1", "replace")


def extrair_texto(dados: bytes) -> str:
    parser = _Parser()
    parser.feed(decodificar(dados))
    parser.close()
    return "\n".join(parser.linhas) + "\n"
