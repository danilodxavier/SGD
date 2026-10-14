"""Busca textual direta no índice."""
from fastapi import APIRouter, Depends

from app.api.deps import require_login
from app.core.database import get_conn
from app.retrieval.search import search

router = APIRouter(prefix="/api", dependencies=[Depends(require_login)])


@router.get("/search")
def search_documents(q: str, limit: int = 20):
    with get_conn() as conn:
        results = search(conn, q, limit=min(max(limit, 1), 100), min_coverage=0.0)
    for r in results:
        r.pop("text", None)
    return {"query": q, "results": results}
