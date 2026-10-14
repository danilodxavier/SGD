"""Busca textual sobre o índice FTS5 (palavras, frases, números, CNPJ, datas)."""
import re

from app.core.text import fold
from app.retrieval.citations import best_excerpt

STOPWORDS = set("""
a ao aos as ate com como da das de do dos e em entre esta este esse essa estao foi foram ha isso la mais me
na nas no nos o os ou para pela pelas pelo pelos por qual quais quando que quem se sem ser sao seu sua sobre
tem um uma umas uns onde existe existem favor informe mostre liste listar diga eh e qual quais documento
documentos
""".split())

TERM_RE = re.compile(r"[0-9A-Za-zÀ-ÿº°]+(?:[./\-][0-9A-Za-zÀ-ÿ]+)*")


def query_terms(text, extra_stopwords=()):
    terms = []
    for raw in TERM_RE.findall(text):
        folded = fold(raw)
        if folded in STOPWORDS or folded in extra_stopwords:
            continue
        if len(folded) < 2 and not folded.isdigit():
            continue
        if re.fullmatch(r"\d{14}", folded):  # CNPJ digitado sem pontuação
            raw = f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
        if raw not in terms:
            terms.append(raw)
    return terms


def fts_expression(terms):
    parts = []
    for term in terms:
        quoted = '"' + term.replace('"', '""') + '"'
        if term.isalpha() and len(term) >= 4:
            quoted += "*"  # tolera plural e flexões simples
        parts.append(quoted)
    return " OR ".join(parts)


def _stem(term):
    """Radical simples: remove o final da palavra (designação → design, prorrogação → prorrog)."""
    f = fold(term)
    if len(f) <= 4 or not f.isalpha():
        return f
    return f[: max(5, len(f) - 4)] if len(f) >= 8 else f[: max(4, len(f) - 2)]


def coverage(terms, text):
    if not terms:
        return 0.0
    folded = fold(text)
    return sum(1 for t in terms if _stem(t) in folded) / len(terms)


def _doc_filter(doc_ids):
    return f" AND c.document_id IN ({','.join('?' * len(doc_ids))})", list(doc_ids)


def run_fts(conn, expression, doc_ids=None, limit=50):
    sql = (
        "SELECT c.id AS chunk_id, c.document_id, c.text, c.page, c.section, d.filename, d.doc_type, "
        "d.extension, d.ordinal, d.modified_at, d.contract_ref, d.hash, bm25(chunks_fts, 1.0, 0.3) AS score "
        "FROM chunks_fts JOIN document_chunks c ON c.id = chunks_fts.rowid "
        "JOIN documents d ON d.id = c.document_id "
        "WHERE chunks_fts MATCH ? AND d.status != 'REMOVIDO'"
    )
    params = [expression]
    if doc_ids is not None:
        if not doc_ids:
            return []
        clause, extra = _doc_filter(doc_ids)
        sql += clause
        params += extra
    sql += " ORDER BY score LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params)]


def search(conn, query, limit=20, doc_ids=None, terms=None, min_coverage=None):
    """Retorna trechos ordenados por relevância, com recorte do texto."""
    terms = query_terms(query) if terms is None else terms
    if not terms:
        return []
    rows = run_fts(conn, fts_expression(terms), doc_ids, limit=max(limit * 3, 30))
    if min_coverage is None:
        # todos os termos quando a pergunta é curta; maioria quando é longa
        min_coverage = 1.0 if len(terms) <= 2 else 0.6
    results = []
    for row in rows:
        cov = coverage(terms, row["text"])
        if cov < min_coverage:
            continue
        row["coverage"] = round(cov, 2)
        row["excerpt"] = best_excerpt(row["text"], terms)
        results.append(row)
        if len(results) >= limit:
            break
    return results


def documents_for_contract(conn, ref):
    """Documentos que mencionam o número do contrato (no texto ou no nome do arquivo)."""
    number, year = ref.split("/")
    n = int(number)
    variants = {f"{n}/{year}", f"{n:02d}/{year}", f"{n:03d}/{year}", f"{n:04d}/{year}"}
    expression = " OR ".join(f'"{v}"' for v in sorted(variants))
    ids = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT c.document_id FROM chunks_fts JOIN document_chunks c ON c.id = chunks_fts.rowid "
            "JOIN documents d ON d.id = c.document_id WHERE chunks_fts MATCH ? AND d.status != 'REMOVIDO'",
            (expression,),
        )
    }
    ids |= {r[0] for r in conn.execute(
        "SELECT id FROM documents WHERE contract_ref = ? AND status != 'REMOVIDO'", (ref,))}
    return sorted(ids)
