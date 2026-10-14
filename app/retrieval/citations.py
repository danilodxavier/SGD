"""Montagem de fontes e recortes de texto para citação."""
from app.core.text import excerpt, flatten, fold


def best_excerpt(text, terms, margin=160):
    flat = flatten(text)
    folded = fold(flat)
    for term in terms:
        pos = folded.find(fold(term))
        if pos >= 0:
            return excerpt(flat, pos, pos + len(term), margin)
    return excerpt(flat, 0, 0, margin * 2)


def page_label(page):
    return f"pág. {page}" if page else None


def source(document_id, filename, page=None, section=None, excerpt_text=None, doc_type=None):
    return {
        "document_id": document_id,
        "filename": filename,
        "page": page,
        "section": section,
        "excerpt": excerpt_text,
        "doc_type": doc_type,
    }


def dedupe_sources(sources):
    seen, out = set(), []
    for s in sources:
        key = (s["document_id"], s.get("page"), s.get("excerpt"))
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out
