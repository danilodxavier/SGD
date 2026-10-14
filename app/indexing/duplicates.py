"""Detecção de duplicidades (mesmo conteúdo) e de versões possivelmente relacionadas.

Apenas informa; nunca exclui arquivos.
"""
import re
from collections import defaultdict

from app.core.text import fold

VERSION_NOISE = re.compile(
    r"\b(copia|copy|c[oó]pia|final|versao|vers[aã]o|v\d+|rev\d*|revisad[oa]|atualizad[oa]|assinad[oa]|\(\d+\)|\d+)\b"
)


def _stem(filename):
    name = fold(filename.rsplit(".", 1)[0])
    name = re.sub(r"[_\-.]+", " ", name)
    name = VERSION_NOISE.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


def find_duplicates(conn):
    rows = conn.execute(
        "SELECT id, filename, relative_path, size, hash FROM documents "
        "WHERE status != 'REMOVIDO' AND hash IS NOT NULL ORDER BY filename"
    ).fetchall()

    by_hash = defaultdict(list)
    for r in rows:
        by_hash[r["hash"]].append(dict(r))
    identical = [g for g in by_hash.values() if len(g) > 1]

    identical_ids = {d["id"] for g in identical for d in g}
    by_stem = defaultdict(list)
    for r in rows:
        stem = _stem(r["filename"])
        if len(stem) >= 4:
            by_stem[stem].append(dict(r))
    versions = [
        g for g in by_stem.values()
        if len(g) > 1 and len({d["hash"] for d in g}) > 1 and not all(d["id"] in identical_ids for d in g)
    ]
    return {"identical": identical, "possible_versions": versions}
