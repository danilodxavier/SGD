"""SAD-078 — Avaliação da F2 (apoio à decisão) ponta a ponta no orquestrador multiagentes (Fase 7).

Usa a recuperação em cache (top-8 do híbrido+rerank) e executa rotear → contexto (linha do tempo do grafo) →
especialistas escolhidos → relator, com o LLM local do Ollama. Métricas por item: rota, seleção de agentes
(precisão/recall vs agentes_esperados), validade de schema dos pareceres (bruto e após reparo), validade do relator,
recall de documentos citados vs fontes esperadas, presença de alternativas/riscos/aviso, confiança, latência e tokens.

Fase 8: precedentes da memória de decisões no contexto (bge-m3 + reranker na CPU, para não disputar a GPU com o
LLM) e presença dos 6 elementos de RF-20 (alternativas, riscos, base legal, precedentes, confiança, aviso).

Uso: python scripts/sadgd/avaliar_f2.py [--rotulo fase8] [--modelo M] [--max-minutos 4] [--sem-precedentes] [--resumo]
"""
import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.metricas import percentil  # noqa: E402
from app.core.config import settings  # noqa: E402
from scripts.sadgd.avaliar import EXECUCOES, _jsonl_existente, carregar_golden  # noqa: E402

K = 8


def media(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def construir(modelo, rotulo, precedentes=True, modelo_especialistas=None):
    from app.application.agentes.orquestrador import Orquestrador
    from app.application.agentes.verificador import verificar
    from app.application.respostas.f1 import ResponderF1
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite
    from app.infrastructure.sqlite.conexao import conectar
    from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite

    repo = RepositorioTrechosSqlite(lambda: conectar(settings.database_path))
    cache = _jsonl_existente(EXECUCOES / rotulo / "recuperacao_hibrido_rerank.jsonl")
    por_pergunta = {it["pergunta"]: it["id"] for it in carregar_golden("todos")}

    def recuperar(pergunta, k):
        return repo.obter([r["trecho_id"] for r in cache[por_pergunta[pergunta]]["recuperados"][:k]])

    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", modelo, timeout=300)
    llm_esp = (OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", modelo_especialistas, timeout=300)
               if modelo_especialistas else llm)
    grafo = RepositorioGrafoSqlite(lambda: conectar(settings.database_path, vetores=False))
    buscar_precedentes = None
    if precedentes:
        from app.application.decisoes.memoria import MemoriaDecisoes
        from app.infrastructure.modelos.embeddings import BgeM3Embedder
        from app.infrastructure.modelos.reranker import BgeReranker
        from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite

        memoria = MemoriaDecisoes(RepositorioDecisoesSqlite(lambda: conectar(settings.database_path)),
                                  BgeM3Embedder(dispositivo="cpu", liberar_gpu=False), BgeReranker(dispositivo="cpu"))

        def buscar_precedentes(pergunta, documentos):
            return memoria.precedentes(pergunta, documento_ids=documentos)
    return Orquestrador(recuperar, ResponderF1(llm, conflitos=grafo, verificador=verificar), llm_esp,
                        linha_do_tempo=grafo.resumo, precedentes=buscar_precedentes, k=K, llm_relator=llm)


def metricas(it, estado, ms):
    d, r = estado["decisao"], estado["resposta"]
    esperados, previstos = set(it.get("agentes_esperados") or []), set(d.agentes)
    docs_esperados = {f["documento"] for f in it["fontes_esperadas"]}
    docs_citados = {t.caminho_relativo for t in r.fontes}
    pareceres = estado.get("pareceres") or []
    f2 = d.rota == "F2"
    dados = r.dados if f2 else {}
    from app.application.decisoes.recomendacao import elementos_rf20

    elementos = elementos_rf20(dados) if f2 else {}
    return {
        "id": it["id"], "conjunto": "validacao" if it["id"][0] == "V" else "teste", "rota": d.rota,
        "agentes": d.agentes, "agentes_esperados": sorted(esperados),
        "agentes_tp": len(esperados & previstos), "agentes_fp": len(previstos - esperados),
        "agentes_fn": len(esperados - previstos),
        "pareceres": len(pareceres), "pareceres_validos_bruto": sum(p.valido_bruto for p in pareceres),
        "pareceres_validos_reparado": sum(p.valido_reparado for p in pareceres),
        "afirmacoes_removidas": sum(p.afirmacoes_removidas for p in pareceres),
        "erros_schema_bruto": {p.agente: p.erros_schema[:3] for p in pareceres},
        "tentativas": {p.agente: p.tentativas for p in pareceres},
        "relator_valido": r.valido if f2 else None, "observacoes": r.observacoes,
        "recall_documentos": len(docs_citados & docs_esperados) / len(docs_esperados) if docs_esperados else None,
        "precisao_documentos": len(docs_citados & docs_esperados) / len(docs_citados) if docs_citados else None,
        "fontes": len(r.fontes), "tem_alternativas": bool(dados.get("alternativas")),
        "tem_riscos": bool(dados.get("riscos")), "tem_aviso": dados.get("aviso") is not None,
        "confianca": dados.get("confianca"), "ms": ms, "elementos_rf20": elementos,
        "precedentes": [p.get("codigo") for p in dados.get("precedentes", [])],
        "base_legal": len(dados.get("base_legal", [])),
        "normas_no_historico": len(dados.get("normas_no_historico", [])),
        "alertas": dados.get("alertas", []),
        "tokens_entrada": r.tokens_entrada + sum(p.tokens_entrada for p in pareceres),
        "tokens_saida": r.tokens_saida + sum(p.tokens_saida for p in pareceres),
        "tempos": dict(estado.get("tempos", [])), "resposta": r.resposta, "recomendacao": dados,
    }


def avaliar(modelo, rotulo, limite_s, precedentes=True, modelo_especialistas=None, conjunto="todos"):
    sufixo = f"__esp_{modelo_especialistas.replace(':', '_')}" if modelo_especialistas else ""
    (EXECUCOES / rotulo).mkdir(parents=True, exist_ok=True)
    arquivo = EXECUCOES / rotulo / f"f2_{modelo.replace(':', '_')}{sufixo}.jsonl"
    feitos = _jsonl_existente(arquivo)
    itens = [i for i in carregar_golden(conjunto) if i["tipo"] == "F2" and i["id"] not in feitos]
    if not itens:
        print(f"[OK] F2: nada pendente ({len(feitos)} itens)")
        return 0
    orq = construir(modelo, rotulo, precedentes, modelo_especialistas)
    inicio = time.perf_counter()
    with arquivo.open("a", encoding="utf-8", newline="\n") as f:
        for n, it in enumerate(itens, start=1):
            if limite_s and time.perf_counter() - inicio > limite_s:
                print(f"[PARCIAL] F2: {n - 1} itens nesta execução; execute novamente para continuar")
                return 3
            t0 = time.perf_counter()
            try:
                reg = metricas(it, orq.executar(it["pergunta"]), int((time.perf_counter() - t0) * 1000))
            except Exception as exc:  # noqa: BLE001 - falha registrada como item inválido
                reg = {"id": it["id"], "conjunto": "validacao" if it["id"][0] == "V" else "teste", "rota": "erro",
                       "erro": repr(exc)[:300], "ms": int((time.perf_counter() - t0) * 1000)}
            f.write(json.dumps(reg, ensure_ascii=False, default=str) + "\n")
            f.flush()
            print(f"  {it['id']}: {reg['rota']} {reg['ms']} ms")
    print(f"[OK] F2: {len(itens)} itens")
    return 0


def resumo(rotulo):
    saida = {}
    for arquivo in sorted((EXECUCOES / rotulo).glob("f2_*.jsonl")):
        regs = list(_jsonl_existente(arquivo).values())
        ok = [r for r in regs if r["rota"] != "erro"]
        f2 = [r for r in ok if r["rota"] == "F2"]
        tp, fp, fn = (sum(r[c] for r in ok) for c in ("agentes_tp", "agentes_fp", "agentes_fn"))
        npar = sum(r["pareceres"] for r in f2)
        saida[arquivo.stem] = {
            "n": len(regs), "erros": len(regs) - len(ok), "rota_f2": media([r["rota"] == "F2" for r in ok]),
            "agentes_precisao": round(tp / (tp + fp), 4) if tp + fp else None,
            "agentes_recall": round(tp / (tp + fn), 4) if tp + fn else None,
            "pareceres_por_consulta": media([r["pareceres"] for r in f2]),
            "schema_pareceres_bruto": round(sum(r["pareceres_validos_bruto"] for r in f2) / npar, 4) if npar else None,
            "schema_pareceres_reparado": round(sum(r["pareceres_validos_reparado"] for r in f2) / npar, 4)
            if npar else None,
            "schema_relator": media([r["relator_valido"] for r in f2]),
            "afirmacoes_removidas_por_consulta": media([r["afirmacoes_removidas"] for r in f2]),
            "recall_documentos": media([r["recall_documentos"] for r in ok]),
            "precisao_documentos": media([r["precisao_documentos"] for r in ok]),
            "com_alternativas": media([r["tem_alternativas"] for r in f2]),
            "com_riscos": media([r["tem_riscos"] for r in f2]),
            "com_aviso": media([r["tem_aviso"] for r in f2]),
            "confianca_media": media([r["confianca"] for r in f2]),
            "rf20_completo": media([all(v in ("presente", "declarado") for v in r.get("elementos_rf20", {}).values())
                                    and len(r.get("elementos_rf20", {})) == 6 for r in f2]),
            "rf20_todos_preenchidos": media([all(v == "presente" for v in r.get("elementos_rf20", {}).values())
                                             and len(r.get("elementos_rf20", {})) == 6 for r in f2]),
            "rf20_por_elemento": {e: media([r.get("elementos_rf20", {}).get(e) == "presente" for r in f2])
                                  for e in ("alternativas", "riscos", "base_legal", "precedentes", "confianca",
                                            "aviso")},
            "com_precedentes": media([bool(r.get("precedentes")) for r in f2]),
            "base_legal_media": media([r.get("base_legal") for r in f2]),
            "latencia_ms": {"p50": percentil([r["ms"] for r in ok], 50), "p95": percentil([r["ms"] for r in ok], 95)},
            "tokens_medios": {"entrada": media([r["tokens_entrada"] for r in ok]),
                              "saida": media([r["tokens_saida"] for r in ok])},
        }
    (EXECUCOES / rotulo / "f2_resumo.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--modelo", default=settings.llm_modelo_padrao)
    p.add_argument("--rotulo", default="fase8")
    p.add_argument("--max-minutos", type=float, default=None)
    p.add_argument("--resumo", action="store_true")
    p.add_argument("--sem-precedentes", action="store_true")
    p.add_argument("--modelo-especialistas", default=None, help="LLM dos especialistas (o relator usa --modelo)")
    p.add_argument("--conjunto", default="todos", choices=["validacao", "teste", "todos"])
    a = p.parse_args()
    if a.resumo:
        return resumo(a.rotulo)
    return avaliar(a.modelo, a.rotulo, a.max_minutos * 60 if a.max_minutos else None, not a.sem_precedentes,
                   a.modelo_especialistas, a.conjunto)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
