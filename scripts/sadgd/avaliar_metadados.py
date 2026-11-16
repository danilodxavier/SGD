"""Avaliação da extração de metadados (RF-04): tipo, número e data contra o gabarito sintético e o manifesto
do corpus público. Meta: acurácia >= 0,90 em tipo e número.

Uso: python scripts/sadgd/avaliar_metadados.py [--saida avaliacao/execucoes/metadados.json]
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.ingestao.metadados import extrair_metadados  # noqa: E402
from app.infrastructure.extratores.adaptador import extrair  # noqa: E402


def texto_de(arquivo):
    r = extrair(RAIZ / "corpus" / arquivo)
    return "".join(p.texto for p in r.paginas)


def main(saida=None):
    linhas = []
    gabarito = json.loads((RAIZ / "corpus/sintetico/GABARITO.json").read_text(encoding="utf-8"))
    for d in gabarito["documentos"]:
        texto = texto_de(d["arquivo"])
        m = extrair_metadados(texto)
        numero_no_texto = d["numero"].split(" ao Contrato ")[-1] in texto
        linhas.append({"origem": "sintetico", "arquivo": d["arquivo"], "formato": d["formato"],
                       "tipo_ouro": d["tipo_documental"], "tipo": m.tipo_documental,
                       "numero_ouro": d["numero"], "numero": m.numero, "numero_extraivel": numero_no_texto,
                       "data_ouro": d["data"], "data": m.data.isoformat() if m.data else None})
    with (RAIZ / "corpus/MANIFESTO.csv").open(encoding="utf-8") as f:
        publicos = [r for r in csv.DictReader(f) if r["corpus_origem"] == "publico"]
    for r in publicos:
        m = extrair_metadados(texto_de(r["arquivo"]))
        linhas.append({"origem": "publico", "arquivo": r["arquivo"], "formato": "html",
                       "tipo_ouro": r["especie"], "tipo": m.tipo_documental, "numero_ouro": r["numero"],
                       "numero": m.numero, "numero_extraivel": True, "data_ouro": r["ano"],
                       "data": str(m.data.year) if m.data else None, "situacao": m.situacao,
                       "evidencia_situacao": m.evidencia_situacao})

    def acc(itens, campo, filtro=lambda x: True):
        sel = [x for x in itens if filtro(x)]
        return round(sum(x[campo] == x[f"{campo}_ouro"] for x in sel) / len(sel), 4) if sel else None

    resultado = {}
    for origem in ("sintetico", "publico", "todos"):
        sel = [x for x in linhas if origem == "todos" or x["origem"] == origem]
        resultado[origem] = {
            "documentos": len(sel),
            "acuracia_tipo": acc(sel, "tipo"),
            "acuracia_numero": acc(sel, "numero", lambda x: x["numero_extraivel"]),
            "numero_nao_extraivel": sum(not x["numero_extraivel"] for x in sel),
            "acuracia_data": acc(sel, "data"),
        }
    resultado["erros_tipo"] = Counter(f"{x['tipo_ouro']}->{x['tipo']}" for x in linhas if x["tipo"] != x["tipo_ouro"])
    resultado["erros_detalhe"] = [x for x in linhas if x["tipo"] != x["tipo_ouro"]
                                  or (x["numero_extraivel"] and x["numero"] != x["numero_ouro"])
                                  or x["data"] != x["data_ouro"]][:40]
    resultado["normas_revogadas_por_evidencia"] = [(x["arquivo"], x["evidencia_situacao"]) for x in linhas
                                                   if x.get("situacao") == "revogada"]
    print(json.dumps({k: v for k, v in resultado.items() if k != "erros_detalhe"}, ensure_ascii=False, indent=2))
    for e in resultado["erros_detalhe"][:25]:
        print({k: e[k] for k in ("arquivo", "tipo_ouro", "tipo", "numero_ouro", "numero", "data_ouro", "data")})
    if saida:
        Path(saida).parent.mkdir(parents=True, exist_ok=True)
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida")
    main(parser.parse_args().saida)
