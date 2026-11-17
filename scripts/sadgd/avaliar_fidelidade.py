"""Fase 10 — Faithfulness (fidelidade) das respostas F1 com LLM-juiz de outra família (Llama 3.1 8B).

  calibrar : respostas BOAS da validação (exatas, sem número sem suporte, com citações) + 3 corrupções de cada
             (número trocado, sentido invertido, frase inventada). Mede se o juiz aprova as boas e reprova as
             corrompidas: sensibilidade, especificidade e κ de Cohen contra o rótulo conhecido por construção.
  medir    : respostas da v2.2 no TESTE (avaliacao/execucoes/fase7) → faithfulness média (frases sustentadas /
             frases) e taxa de alucinação (respostas com ≥ 1 frase não sustentada).
  resumo   : consolida em avaliacao/execucoes/fase10_fidelidade.json

Retomável (cache por item) e com --max-minutos. Uso:
  python scripts/sadgd/avaliar_fidelidade.py calibrar|medir|resumo [--juiz <tag Ollama>] [--max-minutos 4]
"""
import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.fidelidade import corromper, interpretar, kappa, mensagens_juiz  # noqa: E402
from app.core.config import settings  # noqa: E402
from scripts.sadgd.avaliar import EXECUCOES, _jsonl_existente, carregar_golden  # noqa: E402

JUIZ = "llama3.1:8b-instruct-q4_K_M"
DESTINO = EXECUCOES / "fase10"
TIPOS = ("numero", "inversao", "invencao")


def _itens_calibracao():
    regs = list(_jsonl_existente(EXECUCOES / "fase5" / "respostas_v2_sadgd-qwen2.5-7b.jsonl").values())
    boas = [r for r in regs if r["conjunto"] == "validacao" and r["classificacao"] not in ("ausencia", "erro")
            and r["exato"] and not r["numeros_nao_suportados"] and r.get("citados_ids")]
    itens = []
    for n, r in enumerate(sorted(boas, key=lambda r: r["id"])):
        itens.append({"chave": f"{r['id']}|original", "id": r["id"], "resposta": r["resposta"], "fiel": True,
                      "citados_ids": r["citados_ids"]})
        corrompida = corromper(r["resposta"], TIPOS[n % 3], n)  # um tipo por resposta, em rodízio
        if corrompida:
            itens.append({"chave": f"{r['id']}|{TIPOS[n % 3]}", "id": r["id"], "resposta": corrompida,
                          "fiel": False, "citados_ids": r["citados_ids"]})
    return itens


def _itens_medicao():
    regs = _jsonl_existente(EXECUCOES / "fase7" / "respostas_v2_sadgd-qwen2.5-7b.jsonl").values()
    return [{"chave": r["id"], "id": r["id"], "resposta": r["resposta"], "classificacao": r["classificacao"],
             "citados_ids": r.get("citados_ids") or []} for r in regs if r["classificacao"] not in ("ausencia", "erro")]


def executar(etapa, juiz, limite_s):
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite
    from app.infrastructure.sqlite.conexao import conectar

    DESTINO.mkdir(parents=True, exist_ok=True)
    arquivo = DESTINO / f"fidelidade_{etapa}_{juiz.replace(':', '_')}.jsonl"
    feitos = _jsonl_existente(arquivo, chave="chave")
    itens = [i for i in (_itens_calibracao() if etapa == "calibrar" else _itens_medicao()) if i["chave"] not in feitos]
    if not itens:
        print(f"[OK] {etapa}: nada pendente ({len(feitos)})")
        return 0
    perguntas = {i["id"]: i["pergunta"] for i in carregar_golden("todos")}
    repo = RepositorioTrechosSqlite(lambda: conectar(settings.database_path))
    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", juiz, timeout=300)
    inicio = time.perf_counter()
    with arquivo.open("a", encoding="utf-8", newline="\n") as f:
        for n, it in enumerate(itens):
            if limite_s and time.perf_counter() - inicio > limite_s:
                print(f"[PARCIAL] {etapa}: {n} nesta execução")
                return 3
            lista, msgs = mensagens_juiz(perguntas.get(it["id"], ""), it["resposta"], repo.obter(it["citados_ids"]))
            t0 = time.perf_counter()
            try:
                r = llm.chat(msgs, max_tokens=60 + 45 * len(lista), temperatura=0.0, json_livre=True)
                vereditos, erro = interpretar(r.json, len(lista)), None
            except Exception as exc:  # noqa: BLE001 - juiz falhou: registrado, conta como não julgado
                vereditos, erro = [], repr(exc)[:200]
            f.write(json.dumps({**{k: v for k, v in it.items() if k != "citados_ids"}, "frases": lista,
                                "vereditos": vereditos, "erro": erro,
                                "ms": int((time.perf_counter() - t0) * 1000)}, ensure_ascii=False) + "\n")
            f.flush()
    print(f"[OK] {etapa}: {len(itens)} itens")
    return 0


def _metricas_juiz(itens, previsto, rotulo):
    """Positivo = resposta INFIEL (o que o juiz precisa detectar)."""
    vp = sum(not r and not p for r, p in zip(rotulo, previsto, strict=True))
    vn = sum(r and p for r, p in zip(rotulo, previsto, strict=True))
    por_tipo = {}
    for c, p, r in zip(itens, previsto, rotulo, strict=True):
        por_tipo.setdefault(c["chave"].split("|")[1], []).append(p == r)
    return {"n": len(itens), "infieis": sum(not r for r in rotulo),
            "sensibilidade_infiel": round(vp / max(1, sum(not r for r in rotulo)), 4),
            "especificidade_fiel": round(vn / max(1, sum(rotulo)), 4),
            "acuracia": round((vp + vn) / max(1, len(itens)), 4), "kappa": kappa(rotulo, previsto),
            "acerto_por_tipo": {t: round(sum(v) / len(v), 4) for t, v in por_tipo.items()}}


def resumo(juiz):
    saida = {"juiz": juiz}
    nome = juiz.replace(":", "_")
    cal = list(_jsonl_existente(DESTINO / f"fidelidade_calibrar_{nome}.jsonl", chave="chave").values())
    if cal:
        validos = [c for c in cal if not c["erro"] and c["vereditos"]]
        previsto = [all(c["vereditos"]) for c in validos]  # juiz considera a resposta fiel se TODAS as frases passam
        arq_adj = DESTINO / "fidelidade_adjudicacao.json"
        adjud = json.loads(arq_adj.read_text(encoding="utf-8"))["rotulos"] if arq_adj.exists() else {}
        saida["calibracao"] = _metricas_juiz(validos, previsto, [c["fiel"] for c in validos])
        saida["calibracao"]["erros_juiz"] = len(cal) - len(validos)
        if adjud:
            rot_adj = [adjud.get(c["chave"], {}).get("fiel", c["fiel"]) for c in validos]
            saida["calibracao_adjudicada"] = _metricas_juiz(validos, previsto, rot_adj) | {
                "rotulos_revistos": len(adjud), "originais_na_verdade_infieis": sum(
                    1 for v in adjud.values() if not v["fiel"])}
    med = list(_jsonl_existente(DESTINO / f"fidelidade_medir_{nome}.jsonl", chave="chave").values())
    if med:
        validos = [m for m in med if not m["erro"] and m["vereditos"]]
        fid = [sum(m["vereditos"]) / len(m["vereditos"]) for m in validos]
        saida["teste_v2_2"] = {
            "n": len(validos), "erros_juiz": len(med) - len(validos),
            "faithfulness": round(sum(fid) / len(fid), 4) if fid else None,
            "taxa_alucinacao": round(sum(not all(m["vereditos"]) for m in validos) / len(validos), 4)
            if validos else None,
            "nao_sustentadas": [{"id": m["id"], "frases": [f for f, v in zip(m["frases"], m["vereditos"], strict=True)
                                                           if not v]} for m in validos if not all(m["vereditos"])]}
        aparente = saida["teste_v2_2"]["taxa_alucinacao"]
        cal = saida.get("calibracao_adjudicada") or saida.get("calibracao")
        if cal and aparente is not None:  # Rogan–Gladen: prevalência corrigida pelos erros conhecidos do juiz
            sens, esp = cal["sensibilidade_infiel"], cal["especificidade_fiel"]
            saida["teste_v2_2"]["taxa_alucinacao_corrigida_rogan_gladen"] = round(
                min(1.0, max(0.0, (aparente + esp - 1) / (sens + esp - 1))), 4)
        arq_adj = DESTINO / "fidelidade_adjudicacao_teste.json"
        if arq_adj.exists():
            adj = json.loads(arq_adj.read_text(encoding="utf-8"))["rotulos"]
            fid_adj, infieis = [], 0
            for m in validos:
                if m["id"] in adj:  # reprovada pelo juiz e revista: vale a revisão
                    ruins = set(adj[m["id"]]["frases_infieis"])
                    vereditos = [i not in ruins for i in range(1, len(m["frases"]) + 1)]
                else:  # aprovada pelo juiz (não revista)
                    vereditos = m["vereditos"]
                fid_adj.append(sum(vereditos) / len(vereditos))
                infieis += not all(vereditos)
            sens = (saida.get("calibracao_adjudicada") or {}).get("sensibilidade_infiel")
            saida["teste_v2_2_adjudicado"] = {
                "faithfulness": round(sum(fid_adj) / len(fid_adj), 4), "respostas_infieis": infieis,
                "taxa_alucinacao": round(infieis / len(validos), 4),
                "falsos_negativos_estimados": round(infieis * (1 - sens) / sens, 1) if sens else None,
                "revistas": len(adj), "falsos_alarmes_do_juiz": sum(1 for v in adj.values() if not v["frases_infieis"])}
    (EXECUCOES / "fase10_fidelidade.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in saida.items() if k != "teste_v2_2"} | {
        "teste_v2_2": {k: v for k, v in saida.get("teste_v2_2", {}).items() if k != "nao_sustentadas"}},
        ensure_ascii=False, indent=1))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("etapa", choices=["calibrar", "medir", "resumo"])
    p.add_argument("--juiz", default=JUIZ)
    p.add_argument("--max-minutos", type=float, default=None)
    a = p.parse_args()
    if a.etapa == "resumo":
        return resumo(a.juiz)
    return executar(a.etapa, a.juiz, a.max_minutos * 60 if a.max_minutos else None)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
