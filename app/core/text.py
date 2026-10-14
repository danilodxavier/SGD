"""Utilitários de texto: normalização sem acentos que preserva posições."""
import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=8192)
def _fold_char(ch):
    low = ch.lower()
    if len(low) != 1:
        low = ch
    decomposed = unicodedata.normalize("NFD", low)
    return decomposed[0] if decomposed else low


def fold(text):
    """Minúsculas e sem acentos, com o MESMO comprimento do texto original.

    Isso permite aplicar expressões regulares sobre o texto normalizado e
    recortar o valor correspondente do texto original pelas mesmas posições.
    """
    return "".join(map(_fold_char, text))


def flatten(text):
    """Colapsa quebras de linha e espaços repetidos."""
    return re.sub(r"\s+", " ", text or "").strip()


def excerpt(text, start, end, margin=160):
    a = max(0, start - margin)
    b = min(len(text), end + margin)
    prefix = "…" if a > 0 else ""
    suffix = "…" if b < len(text) else ""
    return prefix + text[a:b].strip() + suffix
