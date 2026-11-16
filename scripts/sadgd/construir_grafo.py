"""SAD-060/061/062 — Constrói o grafo documental no sadgd.db: contradições, relações, processos e vigência.

Uso: python scripts/sadgd/construir_grafo.py
"""
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.linha_do_tempo.contradicoes import detectar_contradicoes  # noqa: E402
from app.application.linha_do_tempo.grafo import agrupar, classificar_relacoes  # noqa: E402
from app.application.linha_do_tempo.vigencia import revogacoes_por_relacao  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite  # noqa: E402


def main():
    repo = RepositorioGrafoSqlite(lambda: conectar(settings.database_path, vetores=False))
    docs = repo.carregar()
    contradicoes = detectar_contradicoes(docs)
    relacoes = classificar_relacoes(docs, contradicoes)
    grupos = agrupar(docs, relacoes)
    revogados = revogacoes_por_relacao(relacoes)
    repo.salvar(grupos, relacoes, revogados, {d.id: d.titulo for d in docs})
    print(f"Documentos: {len(docs)} | Relações: {len(relacoes)} {dict(Counter(r.tipo for r in relacoes))}")
    print(f"Contradições: {len(contradicoes)} | Grupos: {len(grupos)} "
          f"({sum(1 for g in grupos if len(g.documentos) > 1)} com 2+ documentos) | "
          f"Normas revogadas pelo grafo: {len(revogados)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
