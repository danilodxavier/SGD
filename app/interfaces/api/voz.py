"""Pergunta por voz: o navegador envia WAV 16 kHz mono; a transcrição é local (ver `transcritor.py`).

O texto volta para a caixa de pergunta para o gestor conferir antes de enviar — um nome ou número mal reconhecido
mudaria a pergunta. O áudio não é gravado; a pergunta enviada é auditada como qualquer outra.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import require_login

router = APIRouter(prefix="/api/sadgd", dependencies=[Depends(require_login)], tags=["SAD-GD"])
MAX_BYTES = 4 * 1024 * 1024  # ≈ 2 min de WAV 16 kHz mono 16 bits
_transcritor = {}


def transcritor():
    if "t" not in _transcritor:
        from app.infrastructure.voz.transcritor import TranscritorLocal

        _transcritor["t"] = TranscritorLocal()
    return _transcritor["t"]


@router.post("/transcrever")
async def transcrever(request: Request):
    from app.infrastructure.voz.transcritor import AudioInvalido

    dados = await request.body()
    if not dados:
        raise HTTPException(400, "Nenhum áudio recebido.")
    if len(dados) > MAX_BYTES:
        raise HTTPException(413, "Áudio muito longo (máximo de 90 segundos).")
    try:
        return transcritor().transcrever(dados)
    except AudioInvalido as exc:
        raise HTTPException(400, str(exc)) from exc
