"""Aplicação FastAPI: API + painel web (HTML/CSS/JS servidos localmente)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import (
    routes_auth, routes_checklist, routes_documents, routes_questions, routes_reports, routes_search, routes_system,
)
from app.core.config import BASE_DIR, settings
from app.core.database import get_documents_root, init_db
from app.core.logging import get_logger, setup_logging
from app.core.security import NetworkGuard
from app.indexing import indexer
from app.ingestion.scanner import check_root

FRONTEND_DIR = BASE_DIR / "frontend"
log = get_logger("main")


@asynccontextmanager
async def lifespan(app):
    setup_logging()
    init_db()
    log.info("Aplicação iniciada (versão %s, %s)", __version__,
             "acesso pela rede" if settings.network_mode else "acesso somente local")
    if app.state.auto_index and settings.auto_index:
        ok, message = check_root(get_documents_root())
        if ok:
            indexer.start_background()
        else:
            log.warning("Indexação automática não executada: %s", message)
    yield
    log.info("Aplicação encerrada")


def create_app(auto_index=True):
    app = FastAPI(title="Agente de Inteligência Documental", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.state.auto_index = auto_index
    app.add_middleware(NetworkGuard)

    for module in (routes_auth, routes_system, routes_documents, routes_search, routes_questions, routes_checklist,
                   routes_reports):
        app.include_router(module.router)
    from app.interfaces.api import linha_do_tempo as api_linha_do_tempo  # SAD-GD (Fase 6)

    from app.interfaces.api import perguntar as api_perguntar  # SAD-GD (Fase 7)

    app.include_router(api_linha_do_tempo.router)
    app.include_router(api_perguntar.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse({"detail": "Dados inválidos na requisição."}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        log.exception("Erro inesperado em %s %s", request.method, request.url.path)
        return JSONResponse(
            {"detail": "Não foi possível concluir a operação. Os detalhes técnicos foram registrados nos logs."},
            status_code=500,
        )

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
