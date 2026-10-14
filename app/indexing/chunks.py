"""Divisão do conteúdo em trechos pesquisáveis, com página e seção."""
import re

CLAUSE_RE = re.compile(r"^(cl[aá]usula|cap[ií]tulo|se[cç][aã]o|anexo|t[ií]tulo|art(igo)?\.?\s*\d)", re.IGNORECASE)
MAX_CHARS = 1200
OVERLAP_MAX_LINE = 300


def is_heading(line):
    s = line.strip()
    if not 3 <= len(s) <= 120:
        return False
    if CLAUSE_RE.match(s):
        return True
    if s.endswith((".", ",", ";")):  # frase em maiúsculas, não título
        return False
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and len(s) <= 90 and all(c.isupper() for c in letters)


def _pieces(text, max_chars):
    """Linhas com posição; linhas muito longas são quebradas em espaços."""
    for m in re.finditer(r"[^\n]+", text):
        line, base = m.group(), m.start()
        if not line.strip():
            continue
        pos = 0
        while len(line) - pos > max_chars:
            cut = line.rfind(" ", pos, pos + max_chars)
            if cut <= pos:
                cut = pos + max_chars
            yield base + pos, base + cut, line[pos:cut].strip()
            pos = cut
        if line[pos:].strip():
            yield base + pos, base + len(line), line[pos:].strip()


def chunk_segments(segments, max_chars=MAX_CHARS):
    chunks = []
    section = None

    for seg in segments:
        if seg.section:
            section = seg.section
        buf, buf_len, buf_section = [], 0, section
        carried = False  # buffer contém apenas a linha de sobreposição do trecho anterior

        def flush(keep_last):
            nonlocal buf, buf_len, buf_section, carried
            if buf:
                chunks.append({
                    "text": "\n".join(p[2] for p in buf),
                    "page": seg.page,
                    "section": buf_section,
                    "start": buf[0][0],
                    "end": buf[-1][1],
                })
            last = buf[-1] if buf else None
            if keep_last and last and len(last[2]) < OVERLAP_MAX_LINE:
                buf, buf_len = [last], len(last[2]) + 1  # pequena sobreposição entre trechos
                carried = True
            else:
                buf, buf_len, carried = [], 0, False
            buf_section = section

        for piece in _pieces(seg.text, max_chars):
            line = piece[2]
            if seg.detect_headings and is_heading(line):
                # cada seção começa um trecho novo; títulos consecutivos ficam juntos
                if carried:
                    buf, buf_len, carried = [], 0, False
                elif any(not is_heading(p[2]) for p in buf):
                    flush(keep_last=False)
                section = line[:150]
                buf_section = section
            if buf and buf_len + len(line) + 1 > max_chars:
                flush(keep_last=True)
            if not buf:
                buf_section = section
            buf.append(piece)
            buf_len += len(line) + 1
            carried = carried and len(buf) == 1
        flush(keep_last=False)

    for number, chunk in enumerate(chunks, start=1):
        chunk["number"] = number
    return chunks
