"""SAD-061/RF-12 — Avaliação da classificação de relações e do agrupamento.

  - Corpus sintético: P/R/F1 por classe, F1-macro das 8 classes avaliadas e matriz de confusão contra GABARITO.json
  - Agrupamento: pureza e pureza inversa contra o processo do gabarito
  - Corpus público: relações fortes (revogação, alteração, regulamentação, substituição) listadas com evidência
    para conferência manual, e verificação contra uma lista curada de relações oficiais conhecidas

Uso: python scripts/sadgd/avaliar_relacoes.py [--saida avaliacao/execucoes/fase6_relacoes.json]
"""
import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.core.config import settings  # noqa: E402

AVALIADAS = ["continuacao", "aditivo", "alteracao", "revogacao", "substituicao", "ruptura", "contradicao",
             "retomada"]
AUXILIARES = ["regulamenta", "fundamenta"]
# relações oficiais conhecidas no corpus público, cada uma conferida no texto (nota de compilação ou dispositivo)
PUBLICAS = [
    ("lei8666_1993.htm", "lei14133_2021.htm", "revogacao"),
    ("lei10520_2002.htm", "lei14133_2021.htm", "revogacao"),
    ("d7892_2013.htm", "d11462_2023.htm", "revogacao"),
    ("d8420_2015.htm", "d11129_2022.htm", "revogacao"),
    ("d2271_1997.htm", "d9507_2018.htm", "revogacao"),
    ("d11317_2022.htm", "d11871_2023.htm", "revogacao"),
    ("d11871_2023.htm", "d12343_2024.htm", "revogacao"),
    ("d6170_2007.htm", "d11531_2023.htm", "revogacao"),
    ("lei8429_1992.htm", "lei14230_2021.htm", "alteracao"),
    ("del4657_1942.htm", "lei13655_2018.htm", "alteracao"),
]


def carregar():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    docs = {r["id"]: dict(r) for r in conn.execute("SELECT id, caminho_relativo, corpus_origem, tipo_documental "
                                                   "FROM documentos")}
    rels = [dict(r) for r in conn.execute(
        "SELECT r.origem_id, r.destino_id, r.tipo, r.confianca, r.justificativa, t.texto FROM relacoes r "
        "LEFT JOIN trechos t ON t.id = r.evidencia_trecho_id WHERE r.metodo = 'regra'")]
    grupos = defaultdict(set)
    for r in conn.execute("SELECT documento_id, processo_id FROM documento_processo"):
        grupos[r["processo_id"]].add(r["documento_id"])
    conn.close()
    return docs, rels, grupos


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return round(p, 4), round(r, 4), round(2 * p * r / (p + r), 4) if p + r else 0.0


def main(saida=None):
    docs, rels, grupos = carregar()
    gab = json.loads((RAIZ / "corpus/sintetico/GABARITO.json").read_text(encoding="utf-8"))
    por_caminho = {d["caminho_relativo"]: i for i, d in docs.items()}
    por_nome = {Path(d["caminho_relativo"]).name: i for i, d in docs.items()}
    gid = {g["id"]: por_caminho[g["arquivo"]] for g in gab["documentos"] if g["arquivo"] in por_caminho}

    def resolve(x):
        return por_nome.get(x[4:] + ".htm") if x.startswith("PUB:") else gid.get(x)

    ouro = {}
    for r in gab["relacoes"]:
        o, d = resolve(r["origem"]), resolve(r["destino"])
        if o and d:
            ouro[(o, d)] = r["tipo"]
    sinteticos = {i for i, d in docs.items() if d["corpus_origem"] == "sintetico"}
    previsto = {(r["origem_id"], r["destino_id"]): r["tipo"] for r in rels
                if r["destino_id"] in sinteticos and (r["origem_id"] in sinteticos or (r["origem_id"], r["destino_id"])
                                                      in ouro)}
    classes = AVALIADAS + AUXILIARES
    por_classe = {}
    for c in classes:
        tp = sum(1 for p, t in previsto.items() if t == c and ouro.get(p) == c)
        fp = sum(1 for p, t in previsto.items() if t == c and ouro.get(p) != c)
        fn = sum(1 for p, t in ouro.items() if t == c and previsto.get(p) != c)
        por_classe[c] = dict(zip(("precisao", "recall", "f1"), prf(tp, fp, fn), strict=True), suporte=tp + fn)
    f1_macro = round(sum(por_classe[c]["f1"] for c in AVALIADAS) / len(AVALIADAS), 4)
    rotulos = classes + ["nenhuma"]
    matriz = {o: {p: 0 for p in rotulos} for o in rotulos}
    for par in set(ouro) | set(previsto):
        matriz[ouro.get(par, "nenhuma")][previsto.get(par, "nenhuma")] += 1
    def nome(i):
        return docs[i]["caminho_relativo"].split("/")[-1]

    erros = [{"origem": nome(o), "destino": nome(d), "ouro": ouro.get((o, d), "nenhuma"),
              "previsto": previsto.get((o, d), "nenhuma")}
             for (o, d) in sorted(set(ouro) | set(previsto)) if ouro.get((o, d)) != previsto.get((o, d))]

    # agrupamento × processo do gabarito (apenas sintéticos)
    proc = {gid[g["id"]]: g["processo"] for g in gab["documentos"] if g["id"] in gid}
    grupos_sint = [g & set(proc) for g in grupos.values() if g & set(proc)]
    pureza = sum(max(Counter(proc[d] for d in g).values()) for g in grupos_sint) / len(proc)
    por_proc = defaultdict(set)
    for d, p in proc.items():
        por_proc[p].add(d)
    inversa = sum(max(len(m & g) for g in grupos_sint) for m in por_proc.values()) / len(proc)

    # corpus público
    publicos = {i for i, d in docs.items() if d["corpus_origem"] == "publico"}
    fortes = [{"origem": docs[r["origem_id"]]["caminho_relativo"].split("/")[-1],
               "destino": docs[r["destino_id"]]["caminho_relativo"].split("/")[-1], "tipo": r["tipo"],
               "parcial": "parcial" in (r["justificativa"] or ""), "justificativa": r["justificativa"],
               "evidencia": (r["texto"] or "")[:160].replace("\n", " / ")}
              for r in rels if r["origem_id"] in publicos and r["destino_id"] in publicos
              and r["tipo"] in ("revogacao", "alteracao", "regulamenta", "substituicao")]
    previstas_pub = {(f["origem"], f["destino"]): f["tipo"] for f in fortes}
    verificacao_publica = [{"origem": o, "destino": d, "esperado": t, "previsto": previstas_pub.get((o, d), "nenhuma")}
                           for o, d, t in PUBLICAS]
    acertos_pub = sum(v["esperado"] == v["previsto"] for v in verificacao_publica)

    resultado = {
        "sintetico": {"f1_macro_8_classes": f1_macro, "por_classe": por_classe, "pares_ouro": len(ouro),
                      "pares_previstos": len(previsto), "matriz_confusao": matriz, "erros": erros},
        "agrupamento": {"pureza": round(pureza, 4), "pureza_inversa": round(inversa, 4),
                        "grupos_com_sinteticos": len(grupos_sint), "processos_ouro": len(por_proc)},
        "publico": {"relacoes_oficiais_conhecidas": len(PUBLICAS), "recuperadas": acertos_pub,
                    "verificacao": verificacao_publica, "relacoes_fortes_previstas": fortes},
    }
    print(f"F1-macro (8 classes, sintético): {f1_macro}  | pares ouro {len(ouro)} previstos {len(previsto)}")
    for c in classes:
        m = por_classe[c]
        print(f"  {c:13} P={m['precisao']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} (suporte {m['suporte']})")
    print(f"Agrupamento: pureza {pureza:.3f} | pureza inversa {inversa:.3f}")
    print(f"Público: {acertos_pub}/{len(PUBLICAS)} relações oficiais conhecidas recuperadas; "
          f"{len(fortes)} relações fortes previstas entre atos públicos")
    for e in erros[:20]:
        print("  [ERRO]", e)
    if saida:
        Path(saida).parent.mkdir(parents=True, exist_ok=True)
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida")
    main(ap.parse_args().saida)
