"""Leitura de DOC (Word 97-2003) sem o Microsoft Office.

O texto do corpo é remontado pela tabela de peças (Clx/PlcPcd) do formato [MS-DOC]. Campos
(hiperlinks, numeração de página...) mantêm apenas o resultado exibido; marcas de célula viram " | ".
Arquivos .doc que na verdade são RTF ou HTML (comum em exportações de sistemas) também são lidos.
"""
import re
import struct

import olefile

from app.ingestion.extractor import ExtractionError, Segment

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
FIELD_BEGIN, FIELD_SEPARATOR, FIELD_END = "\x13", "\x14", "\x15"


def _pieces(word, table, fc_clx, lcb_clx):
    """Lê o Clx e devolve [(cp_inicio, cp_fim, fc, comprimido)]."""
    clx = table[fc_clx:fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx) and clx[pos] == 0x01:  # Prc (formatação): ignorado
        cb = struct.unpack_from("<H", clx, pos + 1)[0]
        pos += 3 + cb
    if pos >= len(clx) or clx[pos] != 0x02:
        raise ExtractionError("Estrutura interna do documento Word não reconhecida.")
    lcb = struct.unpack_from("<I", clx, pos + 1)[0]
    plc = clx[pos + 5:pos + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    out = []
    for i in range(n):
        fc_raw = struct.unpack_from("<I", plc, 4 * (n + 1) + 8 * i + 2)[0]
        compressed = bool(fc_raw & 0x40000000)
        fc = fc_raw & 0x3FFFFFFF
        out.append((cps[i], cps[i + 1], fc // 2 if compressed else fc, compressed))
    return out


def _clean(text):
    """Remove códigos de campo, objetos e marcas internas do Word."""
    out, stack = [], []  # pilha de campos: True enquanto estiver na instrução (antes do separador)
    for ch in text:
        if ch == FIELD_BEGIN:
            stack.append(True)
        elif ch == FIELD_SEPARATOR:
            if stack:
                stack[-1] = False
        elif ch == FIELD_END:
            if stack:
                stack.pop()
        elif not any(stack):
            out.append(ch)
    text = "".join(out)
    text = text.replace("\x07\r\x07", "\n").replace("\r\x07", "\n").replace("\x07\x07", "\n").replace("\x07", " | ")
    text = text.replace("\r", "\n").replace("\x0b", "\n").replace("\x0c", "\n").replace("\x1e", "-")
    text = re.sub(r"[\x00-\x06\x08\x0e-\x1d\x1f]", "", text).replace("\xa0", " ")
    text = re.sub(r"[ \t]*\|[ \t]*\n", "\n", text)  # marca de fim de linha da tabela
    return re.sub(r"\n{3,}", "\n\n", text)


def read_word97(path):
    try:
        ole = olefile.OleFileIO(str(path))
    except OSError as exc:
        raise ExtractionError("O arquivo .doc está corrompido ou em formato inválido.") from exc
    try:
        if not ole.exists("WordDocument"):
            raise ExtractionError("O arquivo .doc não contém um documento do Word.")
        word = ole.openstream("WordDocument").read()
        if len(word) < 0x1AA or struct.unpack_from("<H", word, 0)[0] != 0xA5EC:
            raise ExtractionError("Formato do Word não reconhecido.")
        n_fib = struct.unpack_from("<H", word, 2)[0]
        flags = struct.unpack_from("<H", word, 0x0A)[0]
        if flags & 0x0100:
            raise ExtractionError("O documento do Word está protegido por senha.")
        if n_fib < 101:
            raise ExtractionError("Documento do Word anterior à versão 97 (não suportado). Salve-o como DOCX.")
        table_name = "1Table" if flags & 0x0200 else "0Table"
        if not ole.exists(table_name):
            raise ExtractionError("Estrutura interna do documento Word incompleta.")
        table = ole.openstream(table_name).read()
    finally:
        ole.close()

    ccp_text = struct.unpack_from("<I", word, 0x4C)[0]  # caracteres do corpo principal
    fc_clx, lcb_clx = struct.unpack_from("<II", word, 0x1A2)
    parts = []
    for cp_start, cp_end, fc, compressed in _pieces(word, table, fc_clx, lcb_clx):
        if cp_start >= ccp_text:
            break  # cabeçalhos, notas e caixas de texto vêm depois do corpo
        length = min(cp_end, ccp_text) - cp_start
        if compressed:
            parts.append(word[fc:fc + length].decode("cp1252", errors="replace"))
        else:
            parts.append(word[fc:fc + 2 * length].decode("utf-16-le", errors="replace"))
    return _clean("".join(parts))


def extract(path):
    with open(path, "rb") as fh:
        head = fh.read(512)
    if head.startswith(OLE_MAGIC):
        text = read_word97(path)
    elif head.lstrip().startswith(b"{\\rtf"):
        from app.ingestion import rtf

        return rtf.extract(path)
    elif b"<html" in head.lower() or b"<!doctype html" in head.lower():
        from app.ingestion import html

        return html.extract(path)
    else:
        raise ExtractionError("O arquivo .doc está corrompido ou em formato não reconhecido.")
    return [Segment(text)], None
