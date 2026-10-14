"""Extração de campos contratuais por padrões textuais.

Todas as expressões são aplicadas sobre o texto normalizado (minúsculo, sem
acentos, mesmo comprimento) e o valor é recortado do texto original, de modo
que o que se apresenta ao usuário é exatamente o que consta do documento.
Nenhum valor é inferido: sem correspondência, nada é retornado.
"""
import bisect
import re
from dataclasses import dataclass

from app.core.text import excerpt, flatten, fold

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_MONTHS = "|".join(MONTHS)
_DATE_LONG = rf"\d{{1,2}}\s*[º°o]?\s+de\s+(?:{_MONTHS})\s+de\s+\d{{4}}"
DATE = rf"(?<!\d)(\d{{1,2}}[/.\-]\d{{1,2}}[/.\-]\d{{4}}|{_DATE_LONG})(?!\d)"
MONEY = r"r\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})"
CNPJ = r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"
NUMBER_PREFIX = r"(?:n\.?\s*[º°o]?\.?\s*|numero\s+)?"


def gap(n):
    """Trecho de até n caracteres que não atravessa o fim de uma frase."""
    return rf"(?:(?!\.\s)[^;]){{0,{n}}}?"


P_CONTRACT = re.compile(rf"\bcontrato\s+(?:administrativo\s+)?{NUMBER_PREFIX}(\d{{1,4}})\s*[/\-]\s*(\d{{4}})(?!\d)")
P_REF_LOOSE = re.compile(r"(?<![\d.,/])(\d{1,4})\s*/\s*(\d{4})(?![\d/])")
P_PROCESS = re.compile(
    rf"\bprocesso\s+(?:administrativo\s+|sei\s+|eletronico\s+)?{NUMBER_PREFIX}(\d[\d.\-/]{{5,28}}\d)"
)
P_CNPJ = re.compile(CNPJ)
P_VALUE = re.compile(
    rf"\bvalor\b\s*(?:(global|total|anual|mensal|estimado|atualizado|contratual|do\s+contrato)\b)?({gap(120)}){MONEY}"
)
P_RANGE = re.compile(
    rf"(?:vigencia|vigorara|vigor){gap(200)}\b(?:inicio\s+em|a\s+partir\s+de|iniciando-se\s+em|de)\s+{DATE}"
    rf"{gap(80)}\b(?:termino\s+em|encerrando-se\s+em|ate|a)\s+(?:o\s+dia\s+)?{DATE}"
)
P_START = re.compile(
    rf"(?:vigencia|vigorara){gap(200)}\b(?:inicio\s+em|a\s+partir\s+de|iniciando-se\s+em|contad[oa]\s+a\s+partir\s+de)\s+{DATE}"
)
P_END = re.compile(
    rf"(?:vigencia|vigorara|vigor|prorrogad[oa]|prorrogacao|encerra\w*|termino|vencimento){gap(200)}"
    rf"\b(?:termino\s+em|encerrando-se\s+em|encerrar-se-a\s+em|vencimento\s+em|ate)\s+(?:o\s+dia\s+)?{DATE}"
)
P_TERM = re.compile(
    rf"(?:vigencia|vigorara|prorrogad[oa])({gap(150)})(?<!\d)(\d{{1,3}})\s*(?:\([a-z\s]+\)\s*)?(meses|mes|anos|ano|dias)\b"
)
P_SIGNED = re.compile(
    rf"(?:assinad[oa]\s+em|data\s+d[ae]\s+assinatura\s*[:\-]?|celebrad[oa]\s+em|firmad[oa]\s+em)\s*{DATE}"
)
P_CLOSING = re.compile(rf"(?:^|[\s.])[a-z][a-z' ]{{2,40}}?\s*(?:[-/]\s*[a-z]{{2}}\s*)?,\s*(?:em\s+)?({_DATE_LONG})")
P_OBJECT_STRONG = re.compile(r"\btem\s+(?:como|por)\s+objeto\s+(.{15,400}?)(?:\.\s|\.$|;|$)")
P_OBJECT_WEAK = re.compile(
    r"\bobjeto\s+(?:d[oe]\s+(?:presente\s+)?(?:contrato|termo|instrumento)\s+)?(?:e|consiste\s+n[ao]|:|-|–)\s+(.{15,400}?)(?:\.\s|\.$|;|$)"
)
P_CONTRACTOR_ROLE = re.compile(r"denominad[ao]\s+(?:simplesmente\s+)?(?:de\s+)?contratada\b")
P_CONTRACTOR_LABEL = re.compile(r"\bcontratada\s*[:|\-–]\s*")
P_NAME_END = re.compile(r",|;|\s+(?:inscrit|pessoa\s+jur|cnpj|com\s+sede|estabelecid|neste\s+ato)")

VALUE_EXCLUDE = ("unitari", "parcela", "item", "multa", "garantia", "limite")
VIGENCIA_FIELDS = ("vigencia_inicio", "vigencia_fim", "vigencia_prazo")
ALL_FIELDS = ("contrato", "processo", "valor", "objeto", "contratada", "cnpj", "assinatura") + VIGENCIA_FIELDS


@dataclass
class Match:
    field: str
    value: str
    key: str
    start: int
    end: int
    qualifier: str = ""
    confidence: str = "alta"


def normalize_contract(number, year):
    return f"{int(number):03d}/{year}"


def parse_date(raw):
    """Converte data numérica ou por extenso em (dd/mm/aaaa, aaaa-mm-dd)."""
    s = fold(raw)
    m = re.match(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(rf"(\d{{1,2}})\s*[º°o]?\s+de\s+({_MONTHS})\s+de\s+(\d{{4}})", s)
        if not m:
            return None
        d, mo, y = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
    if not (1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100):
        return None
    return f"{d:02d}/{mo:02d}/{y}", f"{y:04d}-{mo:02d}-{d:02d}"


def money_key(raw):
    return raw.replace(".", "").replace(",", ".")


def find_contract_numbers(text):
    folded = fold(flatten(text))
    seen = []
    for m in P_CONTRACT.finditer(folded):
        ref = normalize_contract(m.group(1), m.group(2))
        if ref not in seen:
            seen.append(ref)
    return seen


def parse_contract_ref(question):
    """Número de contrato mencionado na pergunta (ex.: 034/2022), se houver."""
    folded = fold(question)
    m = P_CONTRACT.search(folded)
    if not m and ("contrato" in folded or "aditivo" in folded):
        m = P_REF_LOOSE.search(folded)
    return normalize_contract(m.group(1), m.group(2)) if m else None


def _flatten_with_breaks(text):
    """Igual a flatten(), devolvendo também as posições (no texto achatado) onde havia quebra de linha."""
    stripped = (text or "").strip()
    parts, breaks, pos, last = [], [], 0, 0
    for m in re.finditer(r"\s+", stripped):
        parts.append(stripped[last:m.start()])
        pos += m.start() - last
        if "\n" in m.group():
            breaks.append(pos)
        parts.append(" ")
        pos += 1
        last = m.end()
    parts.append(stripped[last:])
    return "".join(parts), breaks


def _contractors(flat, folded, breaks=()):
    out = []
    for m in P_CONTRACTOR_ROLE.finditer(folded):
        window_start = max(0, m.start() - 500)
        window = folded[window_start:m.start()]
        start = None
        for pattern in (r"\bempresa\s+", r"\be\s+(?:a|o)\s+"):
            hits = list(re.finditer(pattern, window))
            if hits:
                start = window_start + hits[-1].end()
                break
        if start is None:
            continue
        end_match = P_NAME_END.search(folded, start, m.start())
        name_end = end_match.start() if end_match else m.start()
        name = flat[start:name_end].strip(" ,;:-")
        if 3 <= len(name) <= 150:
            out.append(Match("contratada", name, _name_key(name), start, name_end))
        cnpjs = list(P_CNPJ.finditer(folded, start, m.start()))
        if cnpjs:
            c = cnpjs[-1]
            out.append(Match("cnpj", flat[c.start():c.end()], re.sub(r"\D", "", c.group()), c.start(), c.end()))

    for m in P_CONTRACTOR_LABEL.finditer(folded):
        # "CONTRATADA: nome" termina no fim da linha original
        i = bisect.bisect_right(breaks, m.end())
        line_end = breaks[i] if i < len(breaks) else len(folded)
        limit = min(line_end, m.end() + 160)
        end_match = P_NAME_END.search(folded, m.end(), limit)
        name_end = end_match.start() if end_match else min(line_end, m.end() + 120)
        name = flat[m.end():name_end].strip(" ,;:-")
        if 3 <= len(name) <= 150 and not name[0].isdigit():
            out.append(Match("contratada", name, _name_key(name), m.end(), name_end, confidence="media"))
        c = P_CNPJ.search(folded, m.end(), min(len(folded), m.end() + 200))
        if c:
            out.append(Match("cnpj", flat[c.start():c.end()], re.sub(r"\D", "", c.group()), c.start(), c.end(),
                             confidence="media"))
    return out


def _name_key(name):
    return re.sub(r"[^a-z0-9]", "", fold(name))


def _clean_sentence(text):
    text = text.strip(" ,;:-–")
    return text[0].lower() + text[1:] if text[:1].isupper() and not text[1:2].isupper() else text


def extract(text, fields=ALL_FIELDS):
    """Retorna (texto_achatado, [Match]) para os campos solicitados."""
    flat, breaks = _flatten_with_breaks(text)
    folded = fold(flat)
    fields = set(fields)
    found = []

    if "contrato" in fields:
        for m in P_CONTRACT.finditer(folded):
            ref = normalize_contract(m.group(1), m.group(2))
            found.append(Match("contrato", ref, ref, m.start(), m.end()))

    if "processo" in fields:
        for m in P_PROCESS.finditer(folded):
            value = flat[m.start(1):m.end(1)]
            found.append(Match("processo", value, re.sub(r"\D", "", value), m.start(1), m.end(1)))

    if "valor" in fields:
        for m in P_VALUE.finditer(folded):
            if any(word in m.group(2) for word in VALUE_EXCLUDE):
                continue
            qualifier = (m.group(1) or "").replace("do contrato", "global")
            qualifier = {"total": "global", "contratual": "global", "estimado": "global",
                         "atualizado": "global", "": "global"}.get(qualifier, qualifier)
            raw = flat[m.start(3):m.end(3)]
            found.append(Match("valor", f"R$ {raw}", money_key(raw), m.start(), m.end(3), qualifier,
                               "alta" if m.group(1) else "media"))

    if fields & set(VIGENCIA_FIELDS):
        for m in P_RANGE.finditer(folded):
            for field_name, group in (("vigencia_inicio", 1), ("vigencia_fim", 2)):
                parsed = parse_date(flat[m.start(group):m.end(group)])
                if parsed:
                    found.append(Match(field_name, parsed[0], parsed[1], m.start(), m.end()))
        for m in P_START.finditer(folded):
            parsed = parse_date(flat[m.start(1):m.end(1)])
            if parsed:
                found.append(Match("vigencia_inicio", parsed[0], parsed[1], m.start(), m.end()))
        for m in P_END.finditer(folded):
            parsed = parse_date(flat[m.start(1):m.end(1)])
            if parsed:
                found.append(Match("vigencia_fim", parsed[0], parsed[1], m.start(), m.end()))
        for m in P_TERM.finditer(folded):
            if "limite" in m.group(1):
                continue
            unit = {"mes": "meses", "ano": "anos"}.get(m.group(3), m.group(3))
            qualifier = "prorrogacao" if re.search(r"\bmais\s*$", m.group(1)) else ""
            value = f"{int(m.group(2))} {unit if int(m.group(2)) != 1 else m.group(3)}"
            found.append(Match("vigencia_prazo", value, value, m.start(), m.end(), qualifier))

    if "assinatura" in fields:
        for m in P_SIGNED.finditer(folded):
            parsed = parse_date(flat[m.start(1):m.end(1)])
            if parsed:
                found.append(Match("assinatura", parsed[0], parsed[1], m.start(), m.end()))
        for m in P_CLOSING.finditer(folded):
            parsed = parse_date(flat[m.start(1):m.end(1)])
            if parsed:
                found.append(Match("assinatura", parsed[0], parsed[1], m.start(1), m.end(1), "fecho", "media"))

    if "objeto" in fields:
        for pattern, confidence in ((P_OBJECT_STRONG, "alta"), (P_OBJECT_WEAK, "media")):
            for m in pattern.finditer(folded):
                value = _clean_sentence(flat[m.start(1):m.end(1)])
                if len(value) >= 15:
                    found.append(Match("objeto", value, _name_key(value)[:120], m.start(1), m.end(1),
                                       confidence=confidence))

    if fields & {"contratada", "cnpj"}:
        found.extend(c for c in _contractors(flat, folded, breaks) if c.field in fields)

    # remove repetições do mesmo campo/valor no mesmo trecho, mantendo a de maior confiança
    unique = {}
    for match in found:
        k = (match.field, match.key, match.qualifier)
        if k not in unique or (unique[k].confidence != "alta" and match.confidence == "alta"):
            unique[k] = match
    return flat, list(unique.values())


def summarize(text):
    """Resumo de um contrato para a tabela contracts (primeiro valor de cada campo)."""
    _, matches = extract(text)
    best = {}
    for m in matches:
        if m.field == "valor" and m.qualifier != "global":
            continue
        if m.field == "vigencia_prazo" and m.qualifier:
            continue
        current = best.get(m.field)
        if current is None or (current.confidence != "alta" and m.confidence == "alta"):
            best[m.field] = m
    get = lambda f: best[f].value if f in best else None  # noqa: E731
    return {
        "contract_number": get("contrato"),
        "process_number": get("processo"),
        "contractor": get("contratada"),
        "cnpj": get("cnpj"),
        "object": get("objeto"),
        "value": get("valor"),
        "signature_date": get("assinatura"),
        "start_date": get("vigencia_inicio"),
        "end_date": get("vigencia_fim"),
        "term": get("vigencia_prazo"),
    }


P_VALIDITY = re.compile(r"\b(?:validade|valid[oa]\s+ate|vencimento|vence\s+em)\b")
P_DATE = re.compile(DATE)


def validity_dates(text):
    """Datas de validade/vencimento declaradas no documento (ex.: certidões).

    Retorna [(aaaa-mm-dd, dd/mm/aaaa, trecho)], considerando a maior data citada logo após a expressão.
    """
    flat = flatten(text)
    folded = fold(flat)
    out = []
    for m in P_VALIDITY.finditer(folded):
        window_end = min(len(folded), m.end() + 80)
        dates = []
        for d in P_DATE.finditer(folded, m.end(), window_end):
            parsed = parse_date(flat[d.start(1):d.end(1)])
            if parsed:
                dates.append((parsed[1], parsed[0], d.end()))
        if dates:
            iso, display, end = max(dates)
            out.append((iso, display, excerpt(flat, m.start(), end, 100)))
    return out

