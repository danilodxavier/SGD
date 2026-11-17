"""Saúde, configuração (raiz documental, OCR), diagnóstico, logs e encerramento.

A indexação e o painel do acervo ficam na API do SAD-GD (`/api/sadgd/indexar`, `/api/sadgd/painel`)."""
import hmac
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import require_admin, require_local
from app.core.config import settings
from app.core.database import get_conn, get_documents_root, set_setting
from app.core.logging import get_logger
from app.ingestion import ocr
from app.ingestion.scanner import check_root
from app.services import diagnostics

router = APIRouter()
log = get_logger("api.system")


class ConfigIn(BaseModel):
    documents_root: str


class OcrConfigIn(BaseModel):
    enabled: bool
    engine: str = "auto"


@router.get("/health")
def health():
    database = "ok"
    index = "vazio"
    try:
        with get_conn() as conn:
            if conn.execute("SELECT COUNT(*) FROM trechos").fetchone()[0] > 0:
                index = "ok"
    except Exception:
        database = "erro"
        index = "erro"
    root_ok, _ = check_root(get_documents_root()) if database == "ok" else (False, "")
    root = "ok" if root_ok else "indisponivel"
    status = "erro" if database != "ok" else ("ok" if root_ok else "atencao")
    return {"status": status, "database": database, "documents_root": root, "index": index}


@router.get("/api/config", dependencies=[Depends(require_admin)])
def get_config():
    root = get_documents_root()
    ok, message = check_root(root)
    return {
        "documents_root": root,
        "documents_root_ok": ok,
        "documents_root_message": message,
        "app_host": settings.app_host,
        "app_port": settings.app_port,
        "ocr_enabled": ocr.current_config()["enabled"],
        "llm_modelo": settings.llm_modelo_padrao,
        "ollama_url": settings.ollama_url,
        "auto_index": settings.auto_index,
    }


@router.post("/api/config", dependencies=[Depends(require_admin)])
def set_config(body: ConfigIn):
    root = body.documents_root.strip().strip('"')
    ok, message = check_root(root)
    if not ok:
        raise HTTPException(400, message)
    root = str(Path(root).resolve())
    set_setting("documents_root", root)
    log.info("Diretório documental alterado para %s", root)
    return get_config()


@router.post("/api/config/browse", dependencies=[Depends(require_admin), Depends(require_local)])
def browse_directory():
    """Abre a janela do Windows para escolher a pasta (o servidor roda na própria máquina)."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        window = tk.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        try:
            chosen = filedialog.askdirectory(initialdir=get_documents_root(), mustexist=True,
                                             title="Selecione o diretório documental")
        finally:
            window.destroy()
    except Exception:
        log.exception("Falha ao abrir seletor de pastas")
        raise HTTPException(500, "Não foi possível abrir o seletor de pastas. Digite o caminho manualmente.")
    return {"path": str(Path(chosen)) if chosen else None}


@router.get("/api/ocr", dependencies=[Depends(require_admin)])
def ocr_status():
    return ocr.status(refresh=True)


@router.post("/api/ocr", dependencies=[Depends(require_admin)])
def ocr_configure(body: OcrConfigIn):
    if body.engine not in ocr.ENGINE_CHOICES:
        raise HTTPException(400, "Mecanismo de OCR inválido.")
    set_setting("ocr_enabled", "true" if body.enabled else "false")
    set_setting("ocr_engine", body.engine)
    log.info("OCR configurado: ativo=%s mecanismo=%s", body.enabled, body.engine)
    return ocr.status(refresh=True)


@router.post("/api/ocr/test", dependencies=[Depends(require_admin)])
def ocr_test():
    return ocr.run_test()


@router.get("/api/diagnostics", dependencies=[Depends(require_admin)])
def run_diagnostics():
    return {"checks": diagnostics.run_checks(check_port=False)}


@router.get("/api/logs", dependencies=[Depends(require_admin)])
def read_logs(lines: int = 200):
    path = settings.logs_dir / "app.log"
    if not path.exists():
        return {"lines": []}
    with open(path, encoding="utf-8", errors="replace") as fh:
        content = fh.readlines()
    return {"lines": [line.rstrip("\n") for line in content[-max(1, min(lines, 2000)):]]}


@router.post("/api/system/shutdown", dependencies=[Depends(require_local)])
def shutdown(request: Request):
    token = getattr(request.app.state, "shutdown_token", None)
    server = getattr(request.app.state, "server", None)
    given = request.headers.get("x-shutdown-token", "")
    if not token or server is None or not hmac.compare_digest(token, given):
        raise HTTPException(403, "Encerramento não autorizado.")
    log.info("Encerramento solicitado (pid %s)", os.getpid())
    server.should_exit = True
    return {"stopping": True}
