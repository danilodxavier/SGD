"""SAD-053 — Suíte de avaliação (ADR-011), em estágios com cache para caber na memória da máquina.

  recuperacao : top-10 de cada sistema para cada pergunta (v1, bm25, denso, hibrido, hibrido_rerank)
  resposta    : respostas do v1 (regras) e do v2 (RAG com LLM local) — ver scripts/sadgd/avaliar_respostas.py
  relatorio   : métricas agregadas por sistema e por tipo → avaliacao/execucoes/<rotulo>/relatorio.json

Uso:
  python scripts/sadgd/avaliar.py recuperacao --rotulo fase5 [--sistemas v1,bm25,...] [--conjunto todos]
  python scripts/sadgd/avaliar.py relatorio --rotulo fase5
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.metricas import Fonte, TrechoAvaliado, avaliar_recuperacao, percentil  # noqa: E402
from app.core.config import settings  # noqa: E402

GOLDEN = RAIZ / "avaliacao" / "golden_set"
EXECUCOES = RAIZ / "avaliacao" / "execucoes"
SISTEMAS = ["v1", "bm25", "denso", "hibrido", "hibrido_rerank"]
K = 10


def carregar_golden(conjunto):
    nomes = ["validacao", "teste"] if conjunto == "todos" else [conjunto]
    itens = []
    for nome in nomes:
        with (GOLDEN / f"{nome}.jsonl").open(encoding="utf-8") as f:
            itens += [json.loads(linha) for linha in f if linha.strip()]
    return itens


def _jsonl_existente(caminho):
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f) if r}


def recuperador_v1():
    from app.core.database import get_conn
    from app.retrieval.search import search

    def buscar(pergunta):
        with get_conn() as conn:
            ids = {r["id"]: r["relative_path"] for r in conn.execute("SELECT id, relative_path FROM documents")}
            linhas = search(conn, pergunta, limit=K)
        return [{"arquivo": (ids.get(r["document_id"]) or "").replace("\\", "/"), "dispositivo": None,
                 "texto": r["text"], "subdispositivos": []} for r in linhas]
    return buscar


def recuperador_v2(modo):
    from app.application.recuperacao.hibrida import RecuperadorHibrido
    from app.infrastructure.sqlite.busca import BuscaLexicalSqlite, RepositorioTrechosSqlite
    from app.infrastructure.sqlite.conexao import conectar
    from app.infrastructure.sqlite.vetores import SqliteVecStore

    def fabrica():
        return conectar(settings.database_path)

    embedder = reranker = None
    if modo != "bm25":
        from app.infrastructure.modelos.embeddings import BgeM3Embedder

        embedder = recuperador_v2.embedder = getattr(recuperador_v2, "embedder", None) or BgeM3Embedder()
    if modo == "hibrido_rerank":
        from app.infrastructure.modelos.reranker import BgeReranker

        reranker = recuperador_v2.reranker = getattr(recuperador_v2, "reranker", None) or BgeReranker()
    rec = RecuperadorHibrido(BuscaLexicalSqlite(fabrica), RepositorioTrechosSqlite(fabrica), embedder,
                             SqliteVecStore(fabrica) if embedder else None, reranker)

    def buscar(pergunta):
        r = rec.recuperar(pergunta, k=K, modo=modo)
        return [{"arquivo": t.caminho_relativo, "dispositivo": t.dispositivo, "texto": t.texto,
                 "subdispositivos": t.subdispositivos, "trecho_id": t.id, "revogado": t.revogado} for t in r.trechos]
    return buscar


def estagio_recuperacao(rotulo, sistemas, conjunto, limite_s):
    destino = EXECUCOES / rotulo
    destino.mkdir(parents=True, exist_ok=True)
    itens = carregar_golden(conjunto)
    inicio = time.perf_counter()
    for sistema in sistemas:
        arquivo = destino / f"recuperacao_{sistema}.jsonl"
        feitos = _jsonl_existente(arquivo)
        pendentes = [i for i in itens if i["id"] not in feitos]
        if not pendentes:
            print(f"[OK] {sistema}: {len(feitos)} perguntas já avaliadas")
            continue
        buscar = recuperador_v1() if sistema == "v1" else recuperador_v2(sistema)
        with arquivo.open("a", encoding="utf-8", newline="\n") as f:
            for it in pendentes:
                if limite_s and time.perf_counter() - inicio > limite_s:
                    print("[PARCIAL] limite de tempo; execute novamente para continuar")
                    return 3
                t0 = time.perf_counter()
                resultados = buscar(it["pergunta"])
                registro = {"id": it["id"], "ms": int((time.perf_counter() - t0) * 1000),
                            "recuperados": [{**r, "texto": r["texto"][:1500]} for r in resultados]}
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        print(f"[OK] {sistema}: {len(pendentes)} novas perguntas")
    for nome in ("embedder", "reranker"):
        modelo = getattr(recuperador_v2, nome, None)
        if modelo:
            modelo.liberar()
    return 0


def media(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 4) if valores else None


def estagio_relatorio(rotulo, conjunto):
    destino = EXECUCOES / rotulo
    itens = {i["id"]: i for i in carregar_golden(conjunto)}
    relatorio = {"rotulo": rotulo, "conjunto": conjunto, "perguntas": len(itens), "recuperacao": {}}
    for sistema in SISTEMAS:
        regs = _jsonl_existente(destino / f"recuperacao_{sistema}.jsonl")
        if not regs:
            continue
        por_tipo, geral, latencias = defaultdict(list), [], []
        for iid, reg in regs.items():
            it = itens.get(iid)
            if not it or not it["fontes_esperadas"]:
                continue  # perguntas de ausência não entram nas métricas de recuperação
            fontes = [Fonte(f["documento"], f["dispositivo"], f["evidencia"]) for f in it["fontes_esperadas"]]
            recs = [TrechoAvaliado(r["arquivo"], r["dispositivo"], r["texto"], r.get("subdispositivos") or [])
                    for r in reg["recuperados"]]
            m = avaliar_recuperacao(recs, fontes)
            # F2: as fontes são documentos inteiros; o sinal é a recuperação do documento
            if it["tipo"] == "F2":
                m = {k.replace("recall_documento", "recall"): v for k, v in m.items() if "documento" in k}
            m["revogados_no_top5"] = sum(1 for r in reg["recuperados"][:5] if r.get("revogado"))
            por_tipo[it["tipo"]].append(m)
            geral.append(m) if it["tipo"] != "F2" else None
            latencias.append(reg["ms"])
        chaves = ["recall@1", "recall@3", "recall@5", "recall@10", "precision@5", "mrr", "ndcg@10",
                  "recall_documento@5"]
        relatorio["recuperacao"][sistema] = {
            "geral_sem_F2": {c: media([m.get(c) for m in geral]) for c in chaves},
            "por_tipo": {t: {"n": len(ms), **{c: media([m.get(c) for m in ms]) for c in ("recall@5", "mrr",
                                                                                          "ndcg@10")}}
                         for t, ms in sorted(por_tipo.items())},
            "latencia_ms": {"p50": percentil(latencias, 50), "p95": percentil(latencias, 95)},
            "revogados_no_top5_media": media([m["revogados_no_top5"] for ms in por_tipo.values() for m in ms]),
            "perguntas_avaliadas": sum(len(v) for v in por_tipo.values()),
        }
    respostas = destino / "respostas_resumo.json"
    if respostas.exists():
        relatorio["respostas"] = json.loads(respostas.read_text(encoding="utf-8"))
    (destino / "relatorio.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = [f"{'sistema':16} R@1    R@5    R@10   MRR    nDCG@10 P@5    p50ms  p95ms"]
    for s, r in relatorio["recuperacao"].items():
        g = r["geral_sem_F2"]
        linhas.append(f"{s:16} {g['recall@1']:.3f}  {g['recall@5']:.3f}  {g['recall@10']:.3f}  {g['mrr']:.3f}  "
                      f"{g['ndcg@10']:.3f}   {g['precision@5']:.3f}  {r['latencia_ms']['p50']:<6} "
                      f"{r['latencia_ms']['p95']}")
    print("\n".join(linhas))
    return 0


# Piso de regressão = valor medido em 2026-11-16 (BM25, sintético sem OCR: R@10 0,697; MRR 0,544) menos margem.
# Não é meta de qualidade (as metas valem para o sistema completo; ver docs/AVALIACAO.md).
PISO_CI = {"recall@10": 0.65, "mrr": 0.50}


def estagio_ci():
    """Avaliação reduzida e determinística para o CI (RNF-12): sem GPU, sem modelos, sem rede.
    Indexa corpus/sintetico só com FTS5 num banco temporário e mede a recuperação BM25."""
    import shutil

    from app.application.ingestao.indexador import IndexarCorpus
    from app.application.recuperacao.hibrida import RecuperadorHibrido
    from app.infrastructure.extratores.adaptador import extensoes_suportadas, extrair
    from app.infrastructure.fonte_arquivos import listar, sha256
    from app.infrastructure.sqlite.busca import BuscaLexicalSqlite, RepositorioTrechosSqlite
    from app.infrastructure.sqlite.conexao import conectar, migrar
    from app.infrastructure.sqlite.repositorio_indexacao import RepositorioIndexacaoSqlite

    pasta = RAIZ / "data" / "cache" / "ci_avaliacao"
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    banco = pasta / "ci.db"
    conn = conectar(banco)
    migrar(conn)
    conn.close()

    def fabrica():
        return conectar(banco)

    corpus = RAIZ / "corpus"
    arquivos = [a for a in listar(corpus, extensoes_suportadas()) if a.relativo.startswith("sintetico/")]
    t0 = time.perf_counter()
    r = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256, None, None
                      ).executar(str(corpus), arquivos)
    print(f"Indexação FTS: {r.novos} documentos, {r.trechos} trechos, {time.perf_counter() - t0:.1f} s")
    rec = RecuperadorHibrido(BuscaLexicalSqlite(fabrica), RepositorioTrechosSqlite(fabrica))
    itens = [i for i in carregar_golden("todos") if i["tipo"] != "F2" and i["fontes_esperadas"]
             and all(f["documento"].startswith("sintetico/") for f in i["fontes_esperadas"])]
    metricas = []
    for it in itens:
        trechos = rec.recuperar(it["pergunta"], k=K, modo="bm25").trechos
        recs = [TrechoAvaliado(t.caminho_relativo, t.dispositivo, t.texto, t.subdispositivos) for t in trechos]
        fontes = [Fonte(f["documento"], f["dispositivo"], f["evidencia"]) for f in it["fontes_esperadas"]]
        metricas.append(avaliar_recuperacao(recs, fontes))
    resultado = {c: media([m[c] for m in metricas]) for c in ("recall@1", "recall@5", "recall@10", "mrr", "ndcg@10")}
    print(f"Perguntas: {len(itens)} | " + " | ".join(f"{k} {v}" for k, v in resultado.items()))
    falhas = [f"{k} {resultado[k]} < {piso}" for k, piso in PISO_CI.items() if resultado[k] < piso]
    if falhas:
        print("[ERRO] Regressão na recuperação: " + "; ".join(falhas))
        return 1
    print("[OK] Recuperação acima do piso do CI")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("ci", "--ci"):
        return estagio_ci()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("estagio", choices=["recuperacao", "relatorio"])
    p.add_argument("--rotulo", default="fase5")
    p.add_argument("--sistemas", default=",".join(SISTEMAS))
    p.add_argument("--conjunto", default="todos", choices=["validacao", "teste", "todos"])
    p.add_argument("--max-minutos", type=float, default=None)
    a = p.parse_args()
    if a.estagio == "recuperacao":
        return estagio_recuperacao(a.rotulo, a.sistemas.split(","), a.conjunto,
                                   a.max_minutos * 60 if a.max_minutos else None)
    return estagio_relatorio(a.rotulo, a.conjunto)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
