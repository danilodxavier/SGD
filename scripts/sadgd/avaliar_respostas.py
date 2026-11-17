"""SAD-051/054/055 — Avaliação das respostas (F1, linha do tempo e ausência; F2 fica para a Fase 8).

  (baseline v1: código removido na Fase 10; resultados em avaliacao/execucoes/fase5 e fase6;
   reprodutível pela tag git backup/pre-limpeza-v1)
  v2 : RAG — top-6 do recuperador híbrido+rerank (cache do estágio de recuperação) + ResponderF1 com LLM do Ollama

Retomável (cache por pergunta) e com limite de tempo, para caber na memória da máquina.
Uso:
  python scripts/sadgd/avaliar_respostas.py --sistema v2 --modelo sadgd-qwen2.5-7b --conjunto validacao
  python scripts/sadgd/avaliar_respostas.py --sistema v1 --conjunto todos
  python scripts/sadgd/avaliar_respostas.py --resumo
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.metricas import Fonte, TrechoAvaliado, julgar, percentil  # noqa: E402
from app.application.avaliacao.metricas_resposta import (  # noqa: E402
    classificacao_correta,
    contem_chaves,
    numeros_nao_suportados,
)
from app.core.config import settings  # noqa: E402
from scripts.sadgd.avaliar import EXECUCOES, _jsonl_existente, carregar_golden  # noqa: E402

TOP_CONTEXTO = 6
V1_CLASSES = {"FATO_DOCUMENTAL": "fato", "INFERENCIA": "inferencia", "CONFLITO": "conflito", "AUSENCIA": "ausencia",
              "TRECHOS": "fato"}


def metricas_item(it, resposta, classificacao, citados, suportes=None):
    """citados: TrechoAvaliado citados pela resposta. suportes: textos que o modelo viu para esses trechos
    (corpo + título/data extraídos do próprio documento); por padrão, só o corpo."""
    fontes = [Fonte(f["documento"], f["dispositivo"], f["evidencia"]) for f in it["fontes_esperadas"]]
    graus = [julgar(c, fontes)[0] for c in citados] if fontes else []
    afirmou = classificacao != "ausencia"
    return {
        "exato": contem_chaves(resposta, it["respostas_chave"]) if it["classificacao_esperada"] != "ausencia" else None,
        "classificacao_ok": classificacao_correta(it["classificacao_esperada"], classificacao),
        "citou_fonte_esperada": (any(g == 2 for g in graus) if afirmou else False) if fontes else None,
        "precisao_citacoes": (sum(g == 2 for g in graus) / len(graus)) if graus else None,
        "numeros_nao_suportados": numeros_nao_suportados(
            resposta, suportes if suportes is not None else [c.texto for c in citados], it["pergunta"])
        if afirmou else [],
    }


def responder_v2(modelo, rotulo, usar_grafo=True, usar_verificador=False):
    from app.application.respostas.f1 import ResponderF1
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite
    from app.infrastructure.sqlite.conexao import conectar
    from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite

    repo = RepositorioTrechosSqlite(lambda: conectar(settings.database_path))
    cache = _jsonl_existente(EXECUCOES / rotulo / "recuperacao_hibrido_rerank.jsonl")
    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", modelo, timeout=300)
    conflitos = RepositorioGrafoSqlite(lambda: conectar(settings.database_path, vetores=False)) if usar_grafo \
        else None
    if usar_verificador:
        from app.application.agentes.verificador import verificar
    caso = ResponderF1(llm, conflitos=conflitos, verificador=verificar if usar_verificador else None)

    def responder(it):
        ids = [r["trecho_id"] for r in cache[it["id"]]["recuperados"][:TOP_CONTEXTO]]
        trechos = repo.obter(ids)
        t0 = time.perf_counter()
        r = caso.responder(it["pergunta"], trechos)
        ms = int((time.perf_counter() - t0) * 1000)
        citados = [TrechoAvaliado(t.caminho_relativo, t.dispositivo, t.texto, t.subdispositivos) for t in r.fontes]
        return {"resposta": r.resposta, "classificacao": r.classificacao, "confianca": r.confianca, "ms": ms,
                "modelo": r.modelo, "tokens_entrada": r.tokens_entrada, "tokens_saida": r.tokens_saida,
                "observacoes": r.observacoes, "citados": [f"{t.caminho_relativo}#{t.dispositivo}" for t in r.fontes],
                "citados_ids": [t.id for t in r.fontes]}, citados, [suporte(t) for t in r.fontes]
    return responder


def suporte(t):
    """O que o modelo viu de um trecho citado: corpo + metadados extraídos do próprio documento."""
    return " ".join(str(x) for x in (t.texto, t.titulo, t.dispositivo, t.data_documento) if x)


def recalcular(rotulo):
    """Recalcula as métricas das respostas v2 já geradas (sem chamar o LLM de novo)."""
    from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite
    from app.infrastructure.sqlite.conexao import conectar

    repo = RepositorioTrechosSqlite(lambda: conectar(settings.database_path))
    conn = conectar(settings.database_path, vetores=False)
    itens = {i["id"]: i for i in carregar_golden("todos")}
    for arquivo in (EXECUCOES / rotulo).glob("respostas_v2_*.jsonl"):
        regs = list(_jsonl_existente(arquivo).values())
        for r in regs:
            ids = r.get("citados_ids")
            if ids is None:  # registros antigos: localiza pelos pares documento#dispositivo
                ids = []
                for c in r.get("citados", []):
                    caminho, _, disp = c.partition("#")
                    ids += [x[0] for x in conn.execute(
                        "SELECT t.id FROM trechos t JOIN documentos d ON d.id = t.documento_id "
                        "WHERE d.caminho_relativo = ? AND coalesce(t.dispositivo, 'None') = ?", (caminho, disp))]
                r["citados_ids"] = ids
            trechos = repo.obter(ids)
            citados = [TrechoAvaliado(t.caminho_relativo, t.dispositivo, t.texto, t.subdispositivos) for t in trechos]
            r.update(metricas_item(itens[r["id"]], r["resposta"], r["classificacao"], citados,
                                   [suporte(t) for t in trechos]))
        with arquivo.open("w", encoding="utf-8", newline="\n") as f:
            for r in regs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[OK] métricas recalculadas: {arquivo.name} ({len(regs)})")
    conn.close()
    return 0


def avaliar(sistema, modelo, conjunto, rotulo, limite_s, usar_grafo=True, usar_verificador=False):
    nome = "v1" if sistema == "v1" else f"v2_{modelo.replace(':', '_').replace('/', '_')}"
    arquivo = EXECUCOES / rotulo / f"respostas_{nome}.jsonl"
    feitos = _jsonl_existente(arquivo)
    itens = [i for i in carregar_golden(conjunto) if i["tipo"] != "F2" and i["id"] not in feitos]
    if not itens:
        print(f"[OK] {nome}: nada pendente ({len(feitos)} respostas)")
        return 0
    responder = responder_v2(modelo, rotulo, usar_grafo, usar_verificador)
    inicio = time.perf_counter()
    with arquivo.open("a", encoding="utf-8", newline="\n") as f:
        for n, it in enumerate(itens, start=1):
            if limite_s and time.perf_counter() - inicio > limite_s:
                print(f"[PARCIAL] {nome}: {n - 1} respondidas nesta execução; execute novamente para continuar")
                return 3
            try:
                saida, citados, suportes = responder(it)
                erro = None
            except Exception as exc:  # registra a falha como resposta inválida, sem interromper a avaliação
                saida, citados, suportes = {"resposta": "", "classificacao": "erro", "ms": 0}, [], []
                erro = repr(exc)[:300]
            conjunto_item = "validacao" if it["id"][0] == "V" else "teste"
            registro = {"id": it["id"], "tipo": it["tipo"], "esperada": it["classificacao_esperada"],
                        "conjunto": conjunto_item, **saida, "erro": erro,
                        **metricas_item(it, saida["resposta"], saida["classificacao"], citados, suportes)}
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            f.flush()
    print(f"[OK] {nome}: {len(itens)} respostas")
    return 0


def media(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def resumo(rotulo):
    destino = EXECUCOES / rotulo
    saida = {}
    for arquivo in sorted(destino.glob("respostas_*.jsonl")):
        regs = list(_jsonl_existente(arquivo).values())
        por_conjunto = defaultdict(list)
        for r in regs:
            por_conjunto[r["conjunto"]].append(r)
            por_conjunto["todos"].append(r)
        saida[arquivo.stem.replace("respostas_", "")] = {c: _agregar(rs) for c, rs in por_conjunto.items()}
    (destino / "respostas_resumo.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    cab = f"{'sistema':34} {'conj.':9} n    exat.  classif conflito recusa  cita_ok prec_cit aluc.num  p50ms  p95ms"
    print(cab)
    for nome, conjs in saida.items():
        for c, m in conjs.items():
            print(f"{nome:34} {c:9} {m['n']:<4} {m['exatidao']!s:6} {m['classificacao']!s:7} "
                  f"{m['acerto_conflito']!s:8} {m['acerto_recusa']!s:7} {m['citacao_correta']!s:7} "
                  f"{m['precisao_citacoes']!s:8} {m['taxa_alucinacao_numerica']!s:9} {m['latencia_ms']['p50']!s:6} "
                  f"{m['latencia_ms']['p95']}")
    return 0


def _agregar(rs):
    afirmativas = [r for r in rs if r["classificacao"] not in ("ausencia", "erro")]
    return {
        "n": len(rs),
        "exatidao": media([r["exato"] for r in rs]),
        "classificacao": media([r["classificacao_ok"] for r in rs]),
        "acerto_conflito": media([r["classificacao_ok"] for r in rs if r["esperada"] == "conflito"]),
        "acerto_recusa": media([r["classificacao_ok"] for r in rs if r["tipo"] == "ausente"]),
        "falsa_recusa": media([r["classificacao"] == "ausencia" for r in rs if r["tipo"] != "ausente"]),
        "citacao_correta": media([r["citou_fonte_esperada"] for r in rs if r["citou_fonte_esperada"] is not None]),
        "precisao_citacoes": media([r["precisao_citacoes"] for r in rs]),
        "taxa_alucinacao_numerica": media([bool(r["numeros_nao_suportados"]) for r in afirmativas]),
        "erros": sum(r["classificacao"] == "erro" for r in rs),
        "latencia_ms": {"p50": percentil([r["ms"] for r in rs], 50), "p95": percentil([r["ms"] for r in rs], 95)},
        "tokens_medios": {"entrada": media([r.get("tokens_entrada") for r in rs]),
                          "saida": media([r.get("tokens_saida") for r in rs])},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sistema", choices=["v2"], default="v2")
    p.add_argument("--modelo", default=settings.llm_modelo_padrao)
    p.add_argument("--conjunto", default="validacao", choices=["validacao", "teste", "todos"])
    p.add_argument("--rotulo", default="fase5")
    p.add_argument("--max-minutos", type=float, default=None)
    p.add_argument("--resumo", action="store_true")
    p.add_argument("--recalcular", action="store_true", help="recalcula métricas das respostas v2 já geradas")
    p.add_argument("--sem-grafo", action="store_true", help="desativa a detecção de conflitos pelo grafo (v2.0)")
    p.add_argument("--verificador", action="store_true", help="ativa o Verificador de Fontes no ResponderF1 (v2.2)")
    a = p.parse_args()
    if a.recalcular:
        return recalcular(a.rotulo)
    if a.resumo:
        return resumo(a.rotulo)
    return avaliar(a.sistema, a.modelo, a.conjunto, a.rotulo, a.max_minutos * 60 if a.max_minutos else None,
                   usar_grafo=not a.sem_grafo, usar_verificador=a.verificador)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
