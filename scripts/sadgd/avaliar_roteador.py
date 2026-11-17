"""SAD-070 — Avaliação do roteador no golden set: acurácia F1×F2 (o que define o custo), acurácia de 3 rotas e
precisão/recall dos especialistas acionados nas perguntas F2.

Mapeamento do golden set → rota esperada: F1_simples→F1_simples; ausente→F1_simples (o roteador não sabe que a
informação falta); F1_complexa e linha_do_tempo→F1_complexa; F2→F2.
Uso: python scripts/sadgd/avaliar_roteador.py [--saida avaliacao/execucoes/fase7_roteador.json]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.agentes.roteador import rotear  # noqa: E402
from scripts.sadgd.avaliar import carregar_golden  # noqa: E402

ESPERADA = {"F1_simples": "F1_simples", "ausente": "F1_simples", "F1_complexa": "F1_complexa",
            "linha_do_tempo": "F1_complexa", "F2": "F2"}


def avaliar(itens):
    binario = tres = 0
    matriz = Counter()
    p_tp = p_fp = p_fn = 0
    for it in itens:
        d = rotear(it["pergunta"])
        esperada = ESPERADA[it["tipo"]]
        binario += (d.rota == "F2") == (esperada == "F2")
        tres += d.rota == esperada
        matriz[(esperada, d.rota)] += 1
        if it["tipo"] == "F2":
            esperados, previstos = set(it.get("agentes_esperados") or []), set(d.agentes)
            p_tp += len(esperados & previstos)
            p_fp += len(previstos - esperados)
            p_fn += len(esperados - previstos)
    n = len(itens)
    return {"n": n, "acuracia_F1_x_F2": round(binario / n, 4), "acuracia_3_rotas": round(tres / n, 4),
            "agentes_precisao": round(p_tp / (p_tp + p_fp), 4) if p_tp + p_fp else None,
            "agentes_recall": round(p_tp / (p_tp + p_fn), 4) if p_tp + p_fn else None,
            "matriz": {f"{e}->{p}": c for (e, p), c in sorted(matriz.items())}}


def main(saida=None):
    resultado = {c: avaliar(carregar_golden(c)) for c in ("validacao", "teste")}
    for c, r in resultado.items():
        print(f"{c:9} n={r['n']} F1×F2={r['acuracia_F1_x_F2']} 3 rotas={r['acuracia_3_rotas']} "
              f"agentes P={r['agentes_precisao']} R={r['agentes_recall']}")
        print("          ", r["matriz"])
    if saida:
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida")
    main(ap.parse_args().saida)
