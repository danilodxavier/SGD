"""Regressão da F1 pelo CAMINHO DO SERVIDOR (fichas + documentos-chave + busca + LLM + verificador) no banco
ACADÊMICO — exigida a cada mudança no formato do contexto/prompt da F1 (CLAUDE.md). Retomável.

Uso: python scripts/sadgd/avaliar_caminho_servidor.py --rotulo fase12_r18 [--conjunto validacao] [--max-minutos 8]
     python scripts/sadgd/avaliar_caminho_servidor.py --rotulo fase12_r18 --resumo
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
os.environ.setdefault("DATABASE_PATH", str(RAIZ / "data" / "database" / "sadgd_academico.db"))
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.metricas_resposta import classificacao_correta, contem_chaves  # noqa: E402

GOLDEN = RAIZ / "avaliacao" / "golden_set"
EXECUCOES = RAIZ / "avaliacao" / "execucoes"


def _ler(arquivo):
    return [json.loads(x) for x in arquivo.read_text(encoding="utf-8").splitlines() if x.strip()]


def _itens(conjunto):
    nomes = ["validacao", "teste"] if conjunto == "todos" else [conjunto]
    return [i for n in nomes for i in _ler(GOLDEN / f"{n}.jsonl") if i["tipo"] != "F2"]


def executar(a, arquivo):
    feitos = {r["id"] for r in _ler(arquivo)} if arquivo.exists() else set()
    pendentes = [i for i in _itens(a.conjunto) if i["id"] not in feitos]
    if not pendentes:
        print(f"[OK] nada pendente ({len(feitos)}).")
        return 0
    from app.interfaces.api import perguntar as api

    orq, inicio, n = api.construir_orquestrador(), time.time(), 0
    with open(arquivo, "a", encoding="utf-8") as saida:
        for it in pendentes:
            if a.max_minutos and time.time() - inicio > a.max_minutos * 60:
                break
            t = time.time()
            estado = orq.executar(it["pergunta"])
            d = api.serializar(estado)
            reg = {"id": it["id"], "tipo": it["tipo"], "ms": round((time.time() - t) * 1000), "ficha": d["ficha"],
                   "classificacao": d.get("classificacao"), "confianca": d.get("confianca"),
                   "exato": contem_chaves(d["resposta"], it["respostas_chave"])
                   if it["classificacao_esperada"] != "ausencia" else None,
                   "classificacao_ok": classificacao_correta(it["classificacao_esperada"], d.get("classificacao")),
                   "esperada": it["classificacao_esperada"], "tokens": d["tokens"], "observacoes": d["observacoes"],
                   "resposta": d["resposta"]}
            saida.write(json.dumps(reg, ensure_ascii=False) + "\n")
            saida.flush()
            n += 1
            print(f"  {reg['id']}: {'ok' if reg['exato'] in (True, None) else 'ERRO'} {reg['ms'] / 1000:.1f} s",
                  flush=True)
    print(f"[{'PARCIAL' if n < len(pendentes) else 'OK'}] {n} nesta rodada; faltam {len(pendentes) - n}.")
    return 0


def resumo(arquivo):
    rs = _ler(arquivo)
    exatos = [r["exato"] for r in rs if r["exato"] is not None]
    ausentes = [r for r in rs if r["esperada"] == "ausencia"]
    ms = sorted(r["ms"] for r in rs)
    llm = sorted(r["ms"] for r in rs if not r["ficha"])
    saida = {"n": len(rs), "exatidao": round(sum(exatos) / len(exatos), 3),
             "classificacao": round(sum(r["classificacao_ok"] for r in rs) / len(rs), 3),
             "recusa_correta": round(sum(r["classificacao_ok"] for r in ausentes) / len(ausentes), 3)
             if ausentes else None,
             "falsa_recusa": round(sum(r["classificacao"] == "ausencia" for r in rs if r["esperada"] != "ausencia")
                                   / max(1, len([r for r in rs if r["esperada"] != "ausencia"])), 3),
             "via_ficha": sum(r["ficha"] for r in rs),
             "p50_s": round(statistics.median(ms) / 1000, 1), "p95_s": round(ms[int(0.95 * (len(ms) - 1))] / 1000, 1),
             "p50_llm_s": round(statistics.median(llm) / 1000, 1) if llm else None,
             "erros": [r["id"] for r in rs if r["exato"] is False]}
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rotulo", required=True)
    p.add_argument("--conjunto", default="validacao", choices=["validacao", "teste", "todos"])
    p.add_argument("--max-minutos", type=float, default=None)
    p.add_argument("--resumo", action="store_true")
    a = p.parse_args()
    pasta = EXECUCOES / a.rotulo
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"caminho_servidor_{a.conjunto}.jsonl"
    return resumo(arquivo) if a.resumo else executar(a, arquivo)


if __name__ == "__main__":
    sys.exit(main())
