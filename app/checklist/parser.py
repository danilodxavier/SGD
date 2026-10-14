"""Interpretação de checklists colados no painel ou carregados de arquivo.

Aceita listas numeradas (1., 1), 1.1, a), ITEM 01), marcadores (-, •, [ ]), linhas de
planilha ("1 | Contrato assinado | Obrigatório") e títulos de grupo ("DOCUMENTOS FISCAIS:").
"""
import re
from dataclasses import dataclass

from app.core.text import fold

PREFIX = re.compile(
    r"^\s*(?:item\s*)?(?:\(?\d{1,3}(?:\.\d{1,3})*\s*[.)\-–:]?|\(?[a-z][.)]|[-•*–·▪◦>]|\[\s*[xX]?\s*\])\s+",
    re.IGNORECASE,
)
MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+(.+)$")
HIGH = re.compile(r"\bobrigatori[oa]\b|\bimprescindivel\b|\bessencial\b")
LOW = re.compile(r"\bopcional\b|\bse\s+houver\b|\bquando\s+couber\b|\bse\s+aplicavel\b|\bfacultativ[oa]\b")
PRIORITY_CELL = re.compile(r"^(obrigatori[oa]|opcional|facultativ[oa]|alta|media|baixa|sim|nao|x)$")
PRIORITY_MARK = re.compile(r"\s*[\(\[]\s*(obrigat[óo]ri[oa]|opcional|facultativ[oa]|se houver|quando couber)\s*[\)\]]\s*",
                           re.IGNORECASE)
HEADER_WORDS = {"item", "itens", "n", "no", "nº", "numero", "descricao", "documento", "documentos", "requisito",
                "requisitos", "status", "obrigatoriedade", "prioridade", "observacao", "observacoes", "exigencia"}


@dataclass
class ParsedItem:
    position: int
    description: str
    requirement: str
    priority: str
    category: str | None


def _priority(text):
    folded = fold(text)
    if HIGH.search(folded):
        return "alta"
    if LOW.search(folded):
        return "baixa"
    return "normal"


def _is_category(line, allow_uppercase):
    s = line.strip()
    if PREFIX.match(s) or len(s) > 70:
        return None
    m = MARKDOWN_HEADING.match(s)
    if m:
        return m.group(1).strip(" :")
    if s.endswith(":"):
        return s.rstrip(":").strip()
    letters = [c for c in s if c.isalpha()]
    if allow_uppercase and len(letters) >= 4 and all(c.isupper() for c in letters) and not s.endswith("."):
        return s
    return None


def _from_cells(line):
    """Linha de planilha/tabela: descarta número, cabeçalho e coluna de prioridade."""
    cells = [c.strip() for c in line.split("|") if c.strip()]
    if all(fold(c).strip(" .º") in HEADER_WORDS for c in cells):
        return None, ""
    priority_text = " ".join(c for c in cells if PRIORITY_CELL.match(fold(c)))
    texts = [c for c in cells if not re.fullmatch(r"[\d.)\-–º°]+", c) and not PRIORITY_CELL.match(fold(c))]
    if not texts:
        return None, ""
    return texts[0], " — ".join(texts[1:]) + (" " + priority_text if priority_text else "")


def parse(text):
    items = []
    category = None
    lines = (text or "").splitlines()
    # linha em maiúsculas só é título de grupo quando os itens são numerados/marcados;
    # numa lista simples ela é um item escrito em maiúsculas
    allow_uppercase = any(PREFIX.match(l) for l in lines)
    for raw in lines:
        line = raw.strip()
        if len(line) < 3:
            continue
        extra = ""
        if " | " in line:
            line, extra = _from_cells(line)
            if not line:
                continue
        else:
            heading = _is_category(line, allow_uppercase)
            if heading:
                category = heading[:120]
                continue
        priority = _priority(line + " " + extra)
        description = PRIORITY_MARK.sub(" ", PREFIX.sub("", line, count=1)).strip(" ;.-–")
        if len(description) < 3:
            continue
        requirement = f"{description} — {extra.strip()}" if extra.strip() else description
        items.append(ParsedItem(len(items) + 1, description[:500], requirement[:1000], priority, category))
    return items


def item_key(description):
    """Chave para detectar itens repetidos no checklist."""
    return re.sub(r"[^a-z0-9]", "", fold(description))
