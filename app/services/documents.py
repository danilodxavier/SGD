"""Consultas sobre documentos, contratos e indicadores do painel."""
import os
from pathlib import Path

from app.core.database import get_conn, get_documents_root
from app.indexing import indexer
from app.indexing.duplicates import find_duplicates
from app.indexing.metadata import DOC_TYPE_LABELS
from app.ingestion import extractor

STATUS_LABELS = {
    extractor.STATUS_TEXTO: "Documento com texto",
    extractor.STATUS_ESCANEADO: "Documento escaneado",
    extractor.STATUS_OCR: "Documento com OCR",
    extractor.STATUS_SEM_TEXTO: "Sem texto extraível",
    extractor.STATUS_CORROMPIDO: "Corrompido / protegido",
    extractor.STATUS_NAO_SUPORTADO: "Formato não suportado",
    extractor.STATUS_REMOVIDO: "Removido do diretório",
}

DOC_COLUMNS = ("id, filename, relative_path, extension, size, modified_at, indexed_at, status, mime_type, pages, "
               "doc_type, ordinal, contract_ref, error, hash, ocr, ocr_pages")


def _decorate(row):
    d = dict(row)
    d["status_label"] = STATUS_LABELS.get(d["status"], d["status"])
    d["doc_type_label"] = DOC_TYPE_LABELS.get(d["doc_type"], d["doc_type"])
    return d


def list_documents(q=None, status=None, doc_type=None, limit=500, offset=0):
    sql = f"SELECT {DOC_COLUMNS} FROM documents WHERE 1=1"
    params = []
    if q:
        sql += " AND (filename LIKE ? OR relative_path LIKE ? OR contract_ref LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if status:
        sql += " AND status = ?"
        params.append(status)
    else:
        sql += " AND status != 'REMOVIDO'"
    if doc_type:
        sql += " AND doc_type = ?"
        params.append(doc_type)
    with get_conn() as conn:
        total = conn.execute(sql.replace(f"SELECT {DOC_COLUMNS}", "SELECT COUNT(*)"), params).fetchone()[0]
        rows = conn.execute(sql + " ORDER BY relative_path LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    return {"total": total, "items": [_decorate(r) for r in rows]}


def get_document(document_id):
    with get_conn() as conn:
        row = conn.execute(f"SELECT {DOC_COLUMNS}, full_path FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return None
        doc = _decorate(row)
        doc["chunks"] = conn.execute("SELECT COUNT(*) FROM document_chunks WHERE document_id = ?",
                                     (document_id,)).fetchone()[0]
        doc["sections"] = [r[0] for r in conn.execute(
            "SELECT DISTINCT section FROM document_chunks WHERE document_id = ? AND section IS NOT NULL "
            "ORDER BY chunk_number LIMIT 30", (document_id,))]
    return doc


def document_path(document_id):
    """Caminho do arquivo original, somente se ainda existir e estiver ativo."""
    with get_conn() as conn:
        row = conn.execute("SELECT full_path, status FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not row or row["status"] == extractor.STATUS_REMOVIDO:
        return None
    path = Path(row["full_path"])
    return path if path.is_file() else None


def open_in_windows(document_id):
    path = document_path(document_id)
    if path is None:
        return False
    os.startfile(str(path))  # abre com o programa padrão do Windows (somente leitura do original)
    return True


def list_contracts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, d.filename FROM contracts c JOIN documents d ON d.id = c.source_document_id "
            "WHERE d.status != 'REMOVIDO' ORDER BY c.contract_number"
        ).fetchall()
    return [dict(r) for r in rows]


def duplicates():
    with get_conn() as conn:
        return find_duplicates(conn)


def dashboard():
    with get_conn() as conn:
        by_status = {r[0]: r[1] for r in conn.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")}
        contracts = conn.execute("SELECT COUNT(DISTINCT contract_number) FROM contracts").fetchone()[0]
        checklists = conn.execute("SELECT COUNT(*) FROM checklist").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
        last_run = conn.execute("SELECT * FROM index_runs ORDER BY id DESC LIMIT 1").fetchone()
    active = sum(v for k, v in by_status.items() if k != extractor.STATUS_REMOVIDO)
    return {
        "documents_root": get_documents_root(),
        "found": active,
        "indexed": sum(by_status.get(s, 0) for s in extractor.SEARCHABLE_STATUSES),
        "errors": by_status.get(extractor.STATUS_CORROMPIDO, 0),
        "without_text": by_status.get(extractor.STATUS_ESCANEADO, 0) + by_status.get(extractor.STATUS_SEM_TEXTO, 0),
        "unsupported": by_status.get(extractor.STATUS_NAO_SUPORTADO, 0),
        "contracts": contracts,
        "checklists": checklists,
        "chunks": chunks,
        "by_status": {STATUS_LABELS.get(k, k): v for k, v in by_status.items()},
        "last_run": dict(last_run) if last_run else None,
        "indexer": indexer.status(),
    }
