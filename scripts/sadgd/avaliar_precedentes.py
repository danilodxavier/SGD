"""SAD-080 — Avaliação da recuperação de precedentes (RF-19: Recall@3 ≥ 0,80).

Modos: bm25, denso, hibrido, hibrido_rerank (ablação, como na Fase 5). Métricas sobre as perguntas com precedente
esperado: Recall@1/@3, MRR; e, com o limiar do reranker ligado, a taxa de "falso precedente" nas perguntas sem
precedente (fração que devolve algum) e o Recall@3 após o filtro.

Uso: python scripts/sadgd/avaliar_precedentes.py [--saida avaliacao/execucoes/fase8_precedentes.json] [--cpu]
"""
import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.metricas import percentil  # noqa: E402
from app.application.decisoes.memoria import MODOS, MemoriaDecisoes  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite  # noqa: E402

GOLDEN = RAIZ / "avaliacao" / "golden_set"


def carregar(conjunto):
    return [json.loads(x) for x in (GOLDEN / f"precedentes_{conjunto}.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()]


def metricas(memoria, itens, modo, filtrar):
    com, sem, tempos = [], [], []
    for it in itens:
        t0 = time.perf_counter()
        achados = [p.decisao.codigo for p in memoria.precedentes(it["pergunta"], k=5, modo=modo, filtrar=filtrar)]
        tempos.append((time.perf_counter() - t0) * 1000)
        esperados = set(it["esperados"])
        if not esperados:
            sem.append(bool(achados[:3]))
            continue
        rank = next((i for i, c in enumerate(achados, start=1) if c in esperados), None)
        com.append({"r1": bool(rank and rank <= 1), "r3": bool(rank and rank <= 3),
                    "cobertura3": len(esperados & set(achados[:3])) / len(esperados),
                    "rr": 1 / rank if rank else 0.0, "id": it["id"], "achados": achados[:3]})
    media = lambda xs: round(sum(xs) / len(xs), 4) if xs else None  # noqa: E731
    return {"n": len(com), "recall@1": media([c["r1"] for c in com]), "recall@3": media([c["r3"] for c in com]),
            "cobertura@3": media([c["cobertura3"] for c in com]), "mrr": media([c["rr"] for c in com]),
            "falso_precedente": media(sem), "sem_precedente": len(sem),
            "p50_ms": percentil(tempos, 50), "erros": [c for c in com if not c["r3"]]}


def main(saida=None, cpu=False):
    from app.infrastructure.modelos.embeddings import BgeM3Embedder
    from app.infrastructure.modelos.reranker import BgeReranker

    disp = "cpu" if cpu else None
    memoria = MemoriaDecisoes(RepositorioDecisoesSqlite(lambda: conectar(settings.database_path)),
                              BgeM3Embedder(dispositivo=disp), BgeReranker(dispositivo=disp))
    resultado = {}
    for conjunto in ("validacao", "teste"):
        itens = carregar(conjunto)
        for modo in MODOS:
            resultado[f"{conjunto}/{modo}"] = metricas(memoria, itens, modo, filtrar=False)
        resultado[f"{conjunto}/hibrido_rerank+limiar"] = metricas(memoria, itens, "hibrido_rerank", filtrar=True)
    print(f"{'conjunto/modo':34} n   R@1    R@3    cob@3  MRR    falso_prec  p50ms")
    for nome, m in resultado.items():
        print(f"{nome:34} {m['n']:<3} {m['recall@1']!s:6} {m['recall@3']!s:6} {m['cobertura@3']!s:6} "
              f"{m['mrr']!s:6} {m['falso_precedente']!s:11} {m['p50_ms']}")
    for nome in ("validacao/hibrido_rerank+limiar", "teste/hibrido_rerank+limiar"):
        for e in resultado[nome]["erros"]:
            print(f"  erro {nome.split('/')[0]}: {e['id']} → {e['achados']}")
    if saida:
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.saida, a.cpu))
