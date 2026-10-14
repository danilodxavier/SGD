"""Documentos: listagem, metadados, abertura, reindexação, duplicidades e contratos."""
import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import require_admin, require_local, require_login
from app.indexing import indexer
from app.services import documents

router = APIRouter(prefix="/api", dependencies=[Depends(require_login)])


@router.get("/documents")
def list_documents(q: str | None = None, status: str | None = None, doc_type: str | None = None,
                   limit: int = 500, offset: int = 0):
    return documents.list_documents(q, status, doc_type, min(max(limit, 1), 2000), max(offset, 0))


@router.get("/documents/duplicates")
def duplicates():
    return documents.duplicates()


@router.get("/documents/{document_id}")
def get_document(document_id: int):
    doc = documents.get_document(document_id)
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    return doc


@router.get("/documents/{document_id}/file")
def document_file(document_id: int):
    path = documents.document_path(document_id)
    if path is None:
        raise HTTPException(404, "O arquivo original não está mais disponível no diretório documental.")
    media = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return FileResponse(path, media_type=media, filename=path.name, content_disposition_type="inline")


@router.post("/documents/{document_id}/open", dependencies=[Depends(require_local)])
def open_document(document_id: int):
    if not documents.open_in_windows(document_id):
        raise HTTPException(404, "O arquivo original não está mais disponível no diretório documental.")
    return {"opened": True}


@router.post("/documents/{document_id}/reindex", dependencies=[Depends(require_admin)])
def reindex_document(document_id: int):
    try:
        status = indexer.reindex_document(document_id)
    except FileNotFoundError:
        raise HTTPException(404, "O arquivo original não foi encontrado.")
    if status is None:
        raise HTTPException(404, "Documento não encontrado.")
    return documents.get_document(document_id)


@router.get("/contracts")
def contracts():
    return documents.list_contracts()
