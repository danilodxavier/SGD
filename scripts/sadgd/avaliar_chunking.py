"""Avaliação do chunking estrutural (RF-03): limites de dispositivos contra o gabarito do corpus sintético
e contagem de artigos em leis públicas de estrutura conhecida.

Uso: python scripts/sadgd/avaliar_chunking.py [--saida avaliacao/execucoes/chunking.json]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.ingestao.chunking import dividir  # noqa: E402
from app.infrastructure.extratores.adaptador import extrair  # noqa: E402

# leis públicas com número de artigos conhecido (texto oficial): usadas como verificação adicional
LEIS_REFERENCIA = {"publico/federal/lei/lei14133_2021.htm": 194, "publico/federal/lei/lei9784_1999.htm": 70}


def rotulos_previstos(trechos):
    unidades, subs = [], []
    for t in trechos:
        if t.tipo_dispositivo in ("artigo", "clausula"):
            base = t.dispositivo.split(", ")[0] if t.dispositivo else None
            if base and (not unidades or unidades[-1] != base):
                unidades.append(base)
            subs.extend(t.subdispositivos)
    return unidades, subs


def main(saida=None):
    gabarito = json.loads((RAIZ / "corpus/sintetico/GABARITO.json").read_text(encoding="utf-8"))
    por_formato = defaultdict(lambda: {"docs": 0, "unid_ok": 0, "unid_total": 0, "unid_prev": 0, "sub_ok": 0,
                                       "sub_total": 0})
    erros = []
    for doc in gabarito["documentos"]:
        ouro_unid = [d["rotulo"] for d in doc["dispositivos"] if d["tipo"] in ("artigo", "clausula")]
        if not ouro_unid:
            continue
        ouro_sub = [d["rotulo"] for d in doc["dispositivos"] if d["tipo"] == "sub"]
        r = extrair(RAIZ / "corpus" / doc["arquivo"])
        unidades, subs = rotulos_previstos(dividir(r.paginas))
        f = por_formato[doc["formato"]]
        f["docs"] += 1
        f["unid_total"] += len(ouro_unid)
        f["unid_prev"] += len(unidades)
        f["unid_ok"] += sum(1 for u in ouro_unid if u in unidades)
        f["sub_total"] += len(ouro_sub)
        f["sub_ok"] += sum(1 for s in ouro_sub if s in subs)
        faltam = [u for u in ouro_unid if u not in unidades]
        if faltam or len(unidades) != len(ouro_unid):
            erros.append({"id": doc["id"], "formato": doc["formato"], "faltam": faltam,
                          "extras": [u for u in unidades if u not in ouro_unid]})

    total = {k: sum(f[k] for f in por_formato.values()) for k in ("docs", "unid_ok", "unid_total", "unid_prev",
                                                                  "sub_ok", "sub_total")}
    resultado = {
        "documentos_avaliados": total["docs"],
        "limites_unidades_recall": round(total["unid_ok"] / total["unid_total"], 4),
        "limites_unidades_precisao": round(total["unid_ok"] / max(total["unid_prev"], 1), 4),
        "subdispositivos_recall": round(total["sub_ok"] / max(total["sub_total"], 1), 4),
        "por_formato": {k: {**v, "recall": round(v["unid_ok"] / v["unid_total"], 4)} for k, v in por_formato.items()},
        "divergencias": erros,
        "leis_publicas": {},
    }
    for arquivo, esperado in LEIS_REFERENCIA.items():
        trechos = dividir(extrair(RAIZ / "corpus" / arquivo).paginas)
        numeros = {re.match(r"art\. ([\d.]+)", t.dispositivo).group(1).replace(".", "")
                   for t in trechos if t.tipo_dispositivo == "artigo" and t.dispositivo
                   and re.match(r"art\. [\d.]+(?:º)?$", t.dispositivo.split(", ")[0])}
        principais = {n for n in numeros if n.isdigit() and 1 <= int(n) <= esperado}
        resultado["leis_publicas"][arquivo] = {
            "artigos_esperados": esperado, "artigos_encontrados": len(principais),
            "faltando": sorted(set(map(str, range(1, esperado + 1))) - principais, key=int)[:20],
            "trechos": len(trechos), "trechos_revogados": sum(t.revogado for t in trechos),
            "maior_trecho": max(len(t.texto) for t in trechos),
        }
    print(json.dumps({k: v for k, v in resultado.items() if k != "divergencias"}, ensure_ascii=False, indent=2))
    print(f"Divergências: {len(erros)}", *[json.dumps(e, ensure_ascii=False) for e in erros[:10]], sep="\n")
    if saida:
        Path(saida).parent.mkdir(parents=True, exist_ok=True)
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida")
    main(parser.parse_args().saida)
