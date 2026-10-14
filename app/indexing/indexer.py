"""Indexação incremental do diretório documental.

Os documentos originais são apenas lidos; tudo o que é produzido fica no banco
em data\\. Arquivos com mesmo tamanho e data de modificação não são reprocessados.
"""
import threading
from datetime import datetime
from pathlib import Path

from app.contracts.extractor import summarize
from app.contracts.items import READERS, extract_items
from app.core.config import settings
from app.core.database import get_conn, get_documents_root
from app.core.logging import get_logger
from app.indexing import metadata
from app.indexing.chunks import chunk_segments
from app.ingestion import extractor, ocr
from app.ingestion.scanner import FileInfo, check_root, file_hash, scan

log = get_logger("indexer")

OCR_CANDIDATES = (extractor.STATUS_ESCANEADO, extractor.STATUS_SEM_TEXTO)


def app_folders():
    """Pastas da própria aplicação: nunca indexadas, mesmo que o diretório documental as contenha."""
    from app.core.config import BASE_DIR

    return [settings.data_dir, BASE_DIR / ".venv", BASE_DIR / "BACKUP", BASE_DIR / "app", BASE_DIR / "tests",
            BASE_DIR / "frontend", BASE_DIR / "scripts"]

_lock = threading.Lock()
_state = {
    "running": False,
    "phase": "parado",
    "total": 0,
    "processed": 0,
    "current": "",
    "started_at": None,
    "finished_at": None,
    "last_result": None,
    "error": None,
}


class IndexBusy(Exception):
    pass


class IndexRootError(Exception):
    pass


def status():
    return dict(_state)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _delete_content(conn, document_id):
    conn.execute(
        "DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM document_chunks WHERE document_id = ?)",
        (document_id,),
    )
    conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM contracts WHERE source_document_id = ?", (document_id,))
    conn.execute("DELETE FROM contract_items WHERE source_document_id = ?", (document_id,))


def process_file(conn, info, ocr_engine=extractor.AUTO):
    """Extrai, divide em trechos e grava um arquivo. Retorna o status obtido."""
    path = info.path
    result = extractor.extract(path, ocr_engine)
    if result.ocr_pages:
        log.info("OCR (%s): %s — %d página(s)", result.ocr_engine, path.name, result.ocr_pages)
    text = result.full_text
    doc_type = metadata.classify(path.name, text)
    values = {
        "filename": path.name,
        "full_path": str(path),
        "relative_path": info.relative,
        "extension": path.suffix.lower(),
        "size": info.size,
        "hash": file_hash(path),
        "modified_at": datetime.fromtimestamp(info.mtime).isoformat(timespec="seconds"),
        "mtime": info.mtime,
        "indexed_at": _now(),
        "status": result.status,
        "mime_type": metadata.mime_type(path),
        "pages": result.pages,
        "doc_type": doc_type,
        "ordinal": metadata.amendment_ordinal(path.name, text) if doc_type == "ADITIVO" else 0,
        "contract_ref": metadata.primary_contract(path.name, text) if text else None,
        "error": result.error,
        "ocr": result.ocr_engine,
        "ocr_pages": result.ocr_pages,
    }
    row = conn.execute("SELECT id FROM documents WHERE full_path = ?", (str(path),)).fetchone()
    if row:
        document_id = row["id"]
        _delete_content(conn, document_id)
        conn.execute(
            f"UPDATE documents SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
            (*values.values(), document_id),
        )
    else:
        cur = conn.execute(
            f"INSERT INTO documents ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
            tuple(values.values()),
        )
        document_id = cur.lastrowid

    for chunk in chunk_segments(result.segments):
        cur = conn.execute(
            "INSERT INTO document_chunks (document_id, chunk_number, text, page, section, start_offset, end_offset) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (document_id, chunk["number"], chunk["text"], chunk["page"], chunk["section"], chunk["start"], chunk["end"]),
        )
        searchable = chunk["text"]
        if chunk["section"] and chunk["section"] not in searchable:
            searchable = f"{chunk['section']}\n{searchable}"
        conn.execute("INSERT INTO chunks_fts (rowid, text, filename) VALUES (?, ?, ?)",
                     (cur.lastrowid, searchable, path.name))

    if doc_type == "CONTRATO" and text:
        info_contract = summarize(text)
        if info_contract["contract_number"]:
            conn.execute(
                "INSERT INTO contracts (contract_number, process_number, contractor, cnpj, object, value, "
                "signature_date, start_date, end_date, term, source_document_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (*info_contract.values(), document_id),
            )

    if result.status in extractor.SEARCHABLE_STATUSES and path.suffix.lower() in READERS:
        try:
            found = extract_items(path)
        except Exception:
            log.exception("Falha ao identificar itens em %s", path)
            found = []
        for it in found:
            conn.execute(
                "INSERT INTO contract_items (contract_ref, item_number, description, quantity, unit, unit_value, "
                "total_value, location, source_document_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (values["contract_ref"], it["item_number"], it["description"], it["quantity"], it["unit"],
                 it["unit_value"], it["total_value"], it["location"], document_id),
            )
        if found:
            log.info("Itens identificados em %s: %d", path.name, len(found))
    return result.status


def _needs_ocr(previous, engine, retry_ocr):
    """Documento sem texto que ainda não passou pelo OCR (ou nova tentativa solicitada)."""
    return (engine is not None and previous["status"] in OCR_CANDIDATES
            and (retry_ocr or previous["ocr"] is None))


def run_index(force=False, root=None, retry_ocr=False):
    """Executa a indexação de forma síncrona e retorna o resumo.

    retry_ocr: reprocessa documentos digitalizados/sem texto mesmo que o OCR já tenha sido tentado.
    """
    if not _lock.acquire(blocking=False):
        raise IndexBusy("Já existe uma indexação em andamento.")
    try:
        root = str(root or get_documents_root())
        ok, message = check_root(root)
        if not ok:
            raise IndexRootError(message)

        _state.update(running=True, phase="varrendo diretório", total=0, processed=0, current="",
                      started_at=_now(), finished_at=None, error=None)
        log.info("Indexação iniciada em %s (forçar=%s)", root, force)
        db = settings.database_path
        scanned = scan(root, exclude=app_folders(),
                       exclude_files=[db, f"{db}-wal", f"{db}-shm", f"{db}-journal", settings.pid_file])
        counts = {"found": len(scanned.files), "new": 0, "changed": 0, "unchanged": 0,
                  "removed": 0, "errors": len(scanned.errors), "ocr": 0}
        engine = ocr.get_engine(refresh=True)
        log.info("OCR: %s", engine.label if engine else "desativado ou indisponível")
        for err in scanned.errors:
            log.warning("Erro na varredura: %s", err)

        _state.update(phase="processando arquivos", total=len(scanned.files))
        with get_conn() as conn:
            known = {r["full_path"]: r for r in conn.execute(
                "SELECT id, full_path, size, mtime, status, ocr FROM documents")}
            for info in scanned.files:
                previous = known.pop(str(info.path), None)
                _state["current"] = info.relative
                unchanged = (
                    previous is not None and previous["status"] != extractor.STATUS_REMOVIDO
                    and previous["size"] == info.size and previous["mtime"] == info.mtime
                )
                if unchanged and not force and not _needs_ocr(previous, engine, retry_ocr):
                    counts["unchanged"] += 1
                else:
                    counts["changed" if previous else "new"] += 1
                    try:
                        status_ = process_file(conn, info, engine)
                        conn.commit()
                        if status_ == extractor.STATUS_OCR:
                            counts["ocr"] += 1
                        if status_ == extractor.STATUS_CORROMPIDO:
                            counts["errors"] += 1
                        log.info("Processado: %s [%s]", info.relative, status_)
                    except Exception:
                        conn.rollback()
                        counts["errors"] += 1
                        log.exception("Falha ao indexar %s", info.path)
                _state["processed"] += 1

            for gone in known.values():  # arquivos que deixaram de existir no diretório
                if gone["status"] != extractor.STATUS_REMOVIDO:
                    _delete_content(conn, gone["id"])
                    conn.execute("UPDATE documents SET status = ?, indexed_at = ? WHERE id = ?",
                                 (extractor.STATUS_REMOVIDO, _now(), gone["id"]))
                    counts["removed"] += 1
            conn.execute(
                "INSERT INTO index_runs (started_at, finished_at, documents_root, found, new, changed, unchanged, "
                "removed, errors, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (_state["started_at"], _now(), root, counts["found"], counts["new"], counts["changed"],
                 counts["unchanged"], counts["removed"], counts["errors"], "concluida"),
            )
        log.info("Indexação concluída: %s", counts)
        _state.update(last_result=counts)
        return counts
    except Exception as exc:
        _state["error"] = str(exc) if isinstance(exc, (IndexRootError, IndexBusy)) else "Falha na indexação. Consulte os logs."
        if not isinstance(exc, IndexRootError):
            log.exception("Falha na indexação")
        raise
    finally:
        _state.update(running=False, phase="parado", current="", finished_at=_now())
        _lock.release()


def start_background(force=False, retry_ocr=False):
    """Inicia a indexação em segundo plano. Retorna False se já houver uma em andamento."""
    if _lock.locked():
        return False

    def worker():
        try:
            run_index(force=force, retry_ocr=retry_ocr)
        except (IndexBusy, IndexRootError) as exc:
            log.warning("Indexação não executada: %s", exc)
        except Exception:
            pass  # já registrado em log

    threading.Thread(target=worker, name="indexador", daemon=True).start()
    return True


def reindex_document(document_id):
    with get_conn() as conn:
        row = conn.execute("SELECT full_path, relative_path FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return None
        path = Path(row["full_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))
        st = path.stat()
        status_ = process_file(conn, FileInfo(path, row["relative_path"], st.st_size, st.st_mtime))
    log.info("Documento reindexado: %s [%s]", path, status_)
    return status_
