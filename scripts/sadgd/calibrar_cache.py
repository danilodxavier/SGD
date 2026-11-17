"""Calibração do limiar do cache semântico (Fase 10) com o bge-m3 real.

Negativos: pares de perguntas DIFERENTES do golden set com o MESMO conjunto de identificadores (o filtro de
identificadores não os separa; só o limiar pode). Positivos: paráfrases equivalentes (redigidas para este teste).
Limiar escolhido: acima do maior negativo (nenhuma resposta errada reaproveitada); recall de paráfrases é secundário.

Uso: python scripts/sadgd/calibrar_cache.py [--saida avaliacao/execucoes/fase10_cache.json]
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.cache_semantico import identificadores, normalizar  # noqa: E402
from scripts.sadgd.avaliar import carregar_golden  # noqa: E402

PARAFRASES = [
    ("Qual o valor global do Contrato nº 044/2023?", "Qual é o valor total do Contrato nº 044/2023?"),
    ("Quando termina a vigência do Contrato nº 012/2023?", "Até quando vale o Contrato nº 012/2023?"),
    ("Qual o objeto do Contrato nº 072/2024?", "O que é contratado pelo Contrato nº 072/2024?"),
    ("O Decreto nº 7.892/2013 ainda está em vigor?", "O Decreto nº 7.892/2013 continua vigente?"),
    ("Quem é a contratada do Contrato nº 031/2023?", "Qual empresa foi contratada no Contrato nº 031/2023?"),
    ("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?",
     "É recomendável prorrogar mais uma vez o Contrato nº 044/2023 de vigilância?"),
    ("Qual a sequência de eventos do Contrato nº 031/2023?", "Qual a cronologia do Contrato nº 031/2023?"),
    ("Quais aditivos alteraram o Contrato nº 058/2023?", "Que termos aditivos modificaram o Contrato nº 058/2023?"),
    ("Qual lei revogou a Lei nº 8.666/1993?", "Que lei revogou a Lei nº 8.666/1993?"),
    ("Qual o prazo de vigência do Convênio nº 007/2023?", "Por quanto tempo vigora o Convênio nº 007/2023?"),
]


def cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))  # vetores normalizados


def main(saida=None):
    from app.infrastructure.modelos.embeddings import BgeM3Embedder

    emb = BgeM3Embedder(dispositivo="cpu", liberar_gpu=False)
    perguntas = sorted({normalizar(i["pergunta"]) for i in carregar_golden("todos")})
    grupos = {}
    for p in perguntas:
        ids = frozenset(identificadores(p))
        if ids:
            grupos.setdefault(ids, []).append(p)
    pares_neg = [par for g in grupos.values() if len(g) > 1 for par in itertools.combinations(g, 2)]
    textos = sorted({t for par in pares_neg for t in par} | {normalizar(t) for par in PARAFRASES for t in par})
    vet = dict(zip(textos, emb.embed(textos), strict=True))
    neg = sorted(((cos(vet[a], vet[b]), a, b) for a, b in pares_neg), reverse=True)
    pos = sorted((cos(vet[normalizar(a)], vet[normalizar(b)]), a, b) for a, b in PARAFRASES)
    maior_neg = neg[0][0] if neg else 0.0
    limiar = round(min(0.99, maior_neg + 0.01), 3)
    resultado = {"negativos": len(neg), "maior_negativo": round(maior_neg, 4),
                 "top_negativos": [(round(s, 4), a, b) for s, a, b in neg[:5]],
                 "positivos": [(round(s, 4), a, b) for s, a, b in pos], "limiar": limiar,
                 "recall_parafrases": round(sum(s >= limiar for s, _, _ in pos) / len(pos), 3)}
    print(json.dumps({k: v for k, v in resultado.items() if k != "positivos"}, ensure_ascii=False, indent=1))
    print("positivos:", [p[0] for p in resultado["positivos"]])
    if saida:
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida")
    sys.exit(main(ap.parse_args().saida))
