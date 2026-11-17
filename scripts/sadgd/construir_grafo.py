"""SAD-060/061/062 — Constrói o grafo documental no sadgd.db: contradições, relações, processos e vigência.

Uso: python scripts/sadgd/construir_grafo.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.linha_do_tempo.construcao import construir_grafo  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar, migrar  # noqa: E402
from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite  # noqa: E402


def main():
    conn = conectar(settings.database_path, vetores=False)
    migrar(conn)  # ex.: 005 (chave do processo nas decisões) é usada ao salvar
    conn.close()
    r = construir_grafo(RepositorioGrafoSqlite(lambda: conectar(settings.database_path, vetores=False)))
    print(f"Documentos: {r['documentos']} | Relações: {r['relacoes']} {r['por_tipo']}")
    print(f"Contradições: {r['contradicoes']} | Grupos: {r['grupos']} ({r['grupos_com_2_ou_mais']} com 2+ "
          f"documentos) | Normas revogadas pelo grafo: {r['revogadas']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
