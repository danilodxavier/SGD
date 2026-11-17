"""SAD-080 — Importa a memória de decisões (JSONL) para o banco, com vínculo ao processo, documento-fonte e vetor.

Idempotente pelo código da decisão (DG-xxx/aaaa). O processo é localizado pela chave do contrato/convênio no grafo
(rodar depois de `construir_grafo.py`); a decisão que também existe como documento do corpus (tipo decisao_gestao)
é ligada a ele como fonte.

Uso: python scripts/sadgd/importar_decisoes.py [--arquivo corpus/sintetico/decisoes/MEMORIA_DECISOES.jsonl]
                                               [--sem-embeddings] [--cpu]
"""
import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.decisoes.memoria import MemoriaDecisoes  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.domain.decisoes import Decisao  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar, migrar  # noqa: E402
from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite  # noqa: E402

PADRAO = RAIZ / "corpus" / "sintetico" / "decisoes" / "MEMORIA_DECISOES.jsonl"


def main(arquivo, embeddings=True, cpu=False):
    conn = conectar(settings.database_path)
    migrar(conn)
    conn.close()
    repo = RepositorioDecisoesSqlite(lambda: conectar(settings.database_path))
    embedder = None
    if embeddings:
        from app.infrastructure.modelos.embeddings import BgeM3Embedder

        embedder = BgeM3Embedder(dispositivo="cpu" if cpu else None)
    memoria = MemoriaDecisoes(repo, embedder)
    inicio, n, sem_processo = time.perf_counter(), 0, []
    for linha in Path(arquivo).read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        r = json.loads(linha)
        processo = repo.processo_por_chave(r["contrato"]) if r.get("contrato") else None
        if r.get("contrato") and processo is None:
            sem_processo.append(r["codigo"])
        doc = repo.documento_por_numero("decisao_gestao", r["codigo"])
        d = Decisao(titulo=r["titulo"], decisao=r["decisao"], data=r["data"], contexto=r["contexto"],
                    fundamentos=r["fundamentos"], resultado=r["resultado"],
                    avaliacao_resultado=r["avaliacao_resultado"], codigo=r["codigo"], processo_id=processo,
                    decisor_perfil=r.get("decisor_perfil"), corpus_origem=r.get("corpus_origem", "real"))
        memoria.registrar(d, documento_ids=[doc] if doc else [])
        n += 1
    print(f"[OK] {n} decisões importadas em {time.perf_counter() - inicio:.1f} s "
          f"({'com' if embedder else 'sem'} vetores)")
    if sem_processo:
        print(f"[AVISO] processo não encontrado no grafo para: {', '.join(sem_processo)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arquivo", default=str(PADRAO))
    ap.add_argument("--sem-embeddings", action="store_true")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.arquivo, not a.sem_embeddings, a.cpu))
