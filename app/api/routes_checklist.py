"""Checklists: inserir, salvar, executar, visualizar, organizar e exportar.

Qualquer usuário conectado cria, executa e exporta checklists; alterar ou excluir é permitido
apenas a quem o criou e aos administradores.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import require_login
from app.services import checklist
from app.services.checklist import ChecklistError

router = APIRouter(prefix="/api/checklists", dependencies=[Depends(require_login)])

OWNER_REQUIRED = "Somente quem criou este checklist ou um administrador pode alterá-lo ou excluí-lo."


class ChecklistIn(BaseModel):
    name: str = Field(..., max_length=200)
    text: str = Field(..., max_length=200_000)
    contract_ref: str | None = Field(None, max_length=30)


class UploadIn(BaseModel):
    filename: str = Field(..., max_length=260)
    content_base64: str


def _found(value):
    if value is None:
        raise HTTPException(404, "Checklist não encontrado.")
    return value


def _can_edit(user, data):
    return user["is_admin"] or data["checklist"].get("created_by") == user["id"]


def _with_permission(data, user):
    data["checklist"]["can_edit"] = _can_edit(user, data)
    return data


def _check_owner(checklist_id, user):
    data = _found(checklist.get(checklist_id))
    if not _can_edit(user, data):
        raise HTTPException(403, OWNER_REQUIRED)


@router.get("")
def list_checklists():
    return checklist.list_all()


@router.post("")
def create_checklist(body: ChecklistIn, user=Depends(require_login)):
    try:
        return _with_permission(checklist.create(body.name, body.text, body.contract_ref, created_by=user["id"]), user)
    except ChecklistError as exc:
        raise HTTPException(400, str(exc))


@router.post("/parse-file")
def parse_file(body: UploadIn):
    try:
        return {"text": checklist.text_from_upload(body.filename, body.content_base64)}
    except ChecklistError as exc:
        raise HTTPException(400, str(exc))


@router.get("/{checklist_id}")
def get_checklist(checklist_id: int, user=Depends(require_login)):
    return _with_permission(_found(checklist.get(checklist_id)), user)


@router.put("/{checklist_id}")
def update_checklist(checklist_id: int, body: ChecklistIn, user=Depends(require_login)):
    _check_owner(checklist_id, user)
    try:
        return _with_permission(_found(checklist.update(checklist_id, body.name, body.text, body.contract_ref)), user)
    except ChecklistError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/{checklist_id}")
def delete_checklist(checklist_id: int, user=Depends(require_login)):
    _check_owner(checklist_id, user)
    checklist.delete(checklist_id)
    return {"deleted": True}


@router.post("/{checklist_id}/run")
def run_checklist(checklist_id: int, user=Depends(require_login)):
    return _with_permission(_found(checklist.run(checklist_id)), user)


@router.get("/{checklist_id}/organization")
def organization(checklist_id: int):
    return _found(checklist.organization(checklist_id))


@router.get("/{checklist_id}/export")
def export(checklist_id: int, format: str = "csv"):
    try:
        filename, content, media = _found(checklist.export(checklist_id, format.lower()))
    except ChecklistError as exc:
        raise HTTPException(400, str(exc))
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
