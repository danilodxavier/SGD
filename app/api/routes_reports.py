"""Relatórios: catálogo, geração/download e relatórios já gerados em data\\reports."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from app.api.deps import require_login
from app.services import reports
from app.services.report_writers import FORMATS
from app.services.reports import ReportError

router = APIRouter(prefix="/api/reports", dependencies=[Depends(require_login)])


@router.get("")
def catalog():
    return {"reports": [{"kind": k, **v} for k, v in reports.REPORTS.items()], "formats": list(FORMATS)}


@router.get("/files")
def saved_files():
    return reports.list_files()


@router.get("/files/{name}")
def download_saved(name: str):
    path = reports.file_path(name)
    if path is None:
        raise HTTPException(404, "Relatório não encontrado.")
    return FileResponse(path, media_type=reports.media_type(path), filename=path.name)


@router.get("/{kind}")
def generate(kind: str, format: str = "pdf", question: str | None = None, checklist_id: int | None = None):
    if kind not in reports.REPORTS:
        raise HTTPException(404, "Relatório desconhecido.")
    try:
        filename, content, media = reports.generate(kind, format, question=question, checklist_id=checklist_id)
    except ReportError as exc:
        raise HTTPException(400, str(exc))
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
