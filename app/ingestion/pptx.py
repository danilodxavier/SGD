"""Apresentações: PPTX (XML no pacote zip) e PPT do PowerPoint 97-2003 (registros binários).

Cada slide vira um segmento com o número do slide como página; os slides mestres não são lidos.
"""
import re
import struct
import zipfile

from defusedxml import ElementTree as ET

from app.ingestion.extractor import ExtractionError, Segment
from app.ingestion.odf import read_member

A ="{http://schemas.openxmlformats.org/drawingml/2006/main}"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


# ---------------------------------------------------------------- PPTX

def extract(path):
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ExtractionError("O arquivo .pptx está corrompido ou protegido por senha.") from exc
    with zf:
        slides = sorted((n for n in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        segments = []
        for number, name in enumerate(slides, start=1):
            root = ET.fromstring(read_member(zf, name))
            paragraphs = []
            for p in root.iter(A + "p"):
                text = "".join(t.text or "" for t in p.iter(A + "t")).strip()
                if text:
                    paragraphs.append(text)
            if paragraphs:
                segments.append(Segment("\n".join(paragraphs), page=number))
    return segments, len(slides)


# ---------------------------------------------------------------- PPT (PowerPoint 97-2003)

TEXT_CHARS, TEXT_BYTES = 0x0FA0, 0x0FA8
SLIDE_LIST_WITH_TEXT, SLIDE_PERSIST, SLIDE, CLIENT_TEXTBOX = 0x0FF0, 0x03F3, 0x03EE, 0xF00D
SKIPPED_CONTAINERS = {0x03F8, 0x0FC9, 0x03F0}  # slide mestre, folheto, anotações


def _records(data, start, end):
    pos = start
    while pos + 8 <= end:
        ver_inst, rec_type, length = struct.unpack_from("<HHI", data, pos)
        body = pos + 8
        if body + length > end:
            break
        yield ver_inst & 0x0F, ver_inst >> 4, rec_type, body, body + length
        pos = body + length


def _decode(data, rec_type, start, end):
    raw = data[start:end]
    text = raw.decode("utf-16-le", errors="replace") if rec_type == TEXT_CHARS else raw.decode("latin-1")
    return " ".join(text.replace("\r", "\n").replace("\x0b", "\n").split(" ")).strip()


def read_ppt(path):
    import olefile

    try:
        ole = olefile.OleFileIO(str(path))
    except OSError as exc:
        raise ExtractionError("O arquivo .ppt está corrompido ou em formato inválido.") from exc
    try:
        if ole.exists("EncryptedSummary"):
            raise ExtractionError("A apresentação está protegida por senha.")
        if not ole.exists("PowerPoint Document"):
            raise ExtractionError("O arquivo .ppt não contém uma apresentação do PowerPoint.")
        data = ole.openstream("PowerPoint Document").read()
    finally:
        ole.close()

    slides = {}  # número do slide -> textos

    def add(number, text):
        if text and text not in slides.setdefault(number, []):
            slides[number].append(text)

    def walk(start, end, state):
        for ver, inst, rec_type, body, stop in _records(data, start, end):
            if ver == 0x0F:  # contêiner
                if rec_type in SKIPPED_CONTAINERS:
                    continue
                if rec_type == SLIDE_LIST_WITH_TEXT:
                    if inst == 0:  # lista de slides (1 = mestres, 2 = anotações)
                        walk(body, stop, {"mode": "list", "slide": 0})
                    continue
                if rec_type == SLIDE:
                    state["slide_containers"] += 1
                    walk(body, stop, {"mode": "slide", "slide": state["slide_containers"],
                                      "slide_containers": state["slide_containers"]})
                    continue
                walk(body, stop, state)
            elif rec_type == SLIDE_PERSIST and state.get("mode") == "list":
                state["slide"] += 1
            elif rec_type in (TEXT_CHARS, TEXT_BYTES) and state.get("mode") in ("list", "slide"):
                add(state["slide"] or 1, _decode(data, rec_type, body, stop))

    walk(0, len(data), {"mode": None, "slide_containers": 0})
    segments = [Segment("\n".join(texts), page=n) for n, texts in sorted(slides.items()) if texts]
    return segments, (max(slides) if slides else None)


def extract_ppt(path):
    with open(path, "rb") as fh:
        if not fh.read(8).startswith(OLE_MAGIC):
            raise ExtractionError("O arquivo .ppt está corrompido ou em formato não reconhecido.")
    return read_ppt(path)
