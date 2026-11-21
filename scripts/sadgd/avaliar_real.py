"""Avaliação do SAD-GD com documentos REAIS — tudo local; só métricas agregadas vão para a tela.

Protocolo (docs/AVALIACAO_REAL.md):
1. `modelo`   cria avaliacao/real/perguntas.csv (cabeçalho + exemplos fictícios) para a equipe preencher.
2. `executar` roda cada pergunta no pipeline real da API (mesma montagem de POST /api/sadgd/perguntar), com
              LLM local; retomável com --max-minutos. Respostas ficam em avaliacao/real/resultados.jsonl.
3. `revisao`  gera avaliacao/real/revisao.csv (pergunta, resposta, fontes) para o julgamento humano,
              preservando julgamentos já preenchidos.
4. `resumo`   imprime e grava (avaliacao/real/resumo.json) apenas números: recuperação do documento esperado,
              termos-chave, recusa correta, latência e, com o julgamento humano, exatidão e alucinação.

A pasta avaliacao/real/ está no .gitignore: perguntas, respostas e fontes reais nunca vão ao Git nem à nuvem.
Uso: python scripts/sadgd/avaliar_real.py modelo|executar|revisao|resumo [--max-minutos N] [--k 5]
"""
import argparse
import csv
import json
import statistics
import sys
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

PASTA = RAIZ / "avaliacao" / "real"
PERGUNTAS, RESULTADOS = PASTA / "perguntas.csv", PASTA / "resultados.jsonl"
REVISAO, RESUMO = PASTA / "revisao.csv", PASTA / "resumo.json"
CAMPOS = ["id", "pergunta", "tipo", "termos_esperados", "documento_esperado"]
TIPOS = {"fato", "ausencia", "linha_do_tempo", "conflito", "decisao"}
JULGAMENTOS = {"C": "correta", "P": "parcial", "I": "incorreta", "A": "alucinacao"}
AUSENCIA = "não localizei essa informação"


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def _ler_csv(caminho):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _gravar_csv(caminho, campos, linhas):
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:  # BOM: abre certo no Excel
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def _resultados():
    if not RESULTADOS.exists():
        return {}
    return {r["id"]: r for r in map(json.loads, RESULTADOS.read_text(encoding="utf-8").splitlines()) if r}


def modelo(_a):
    PASTA.mkdir(parents=True, exist_ok=True)
    if PERGUNTAS.exists():
        print(f"[OK] Já existe: {PERGUNTAS.relative_to(RAIZ)} (não sobrescrito)")
        return 0
    exemplos = [
        {"id": "R001", "pergunta": "Qual é o valor global do Contrato nº 000/0000?", "tipo": "fato",
         "termos_esperados": "R$ 0,00", "documento_esperado": "parte_do_nome_do_arquivo"},
        {"id": "R002", "pergunta": "Até quando vigora o Contrato nº 000/0000 após o último aditivo?",
         "tipo": "linha_do_tempo", "termos_esperados": "00/00/0000", "documento_esperado": "aditivo"},
        {"id": "R003", "pergunta": "Qual o número da nota de empenho do Contrato nº 000/0000?", "tipo": "ausencia",
         "termos_esperados": "", "documento_esperado": ""},
        {"id": "R004", "pergunta": "Devo prorrogar o Contrato nº 000/0000?", "tipo": "decisao",
         "termos_esperados": "", "documento_esperado": ""},
    ]
    _gravar_csv(PERGUNTAS, CAMPOS, exemplos)
    print(f"[OK] Modelo criado: {PERGUNTAS.relative_to(RAIZ)} — substitua os exemplos fictícios por perguntas reais.")
    return 0


def _validar(linhas):
    erros = []
    ids = [ln["id"].strip() for ln in linhas]
    if len(ids) != len(set(ids)):
        erros.append("ids repetidos")
    for ln in linhas:
        if ln.get("tipo", "").strip() not in TIPOS:
            erros.append(f"{ln.get('id')}: tipo deve ser um de {sorted(TIPOS)}")
        if "000/0000" in ln.get("pergunta", ""):
            erros.append(f"{ln.get('id')}: ainda é exemplo fictício")
    return erros


def executar(a):
    from app.core.config import settings

    if settings.ai_allow_remote or settings.llm_f2 != "local":
        print("[ERRO] Com documentos reais use AI_ALLOW_REMOTE=false e SADGD_LLM_F2=local no .env.")
        return 1
    linhas = _ler_csv(PERGUNTAS)
    erros = _validar(linhas)
    if erros:
        print("[ERRO] perguntas.csv: " + "; ".join(erros[:10]))
        return 1
    feitos = _resultados()
    pendentes = [ln for ln in linhas if ln["id"].strip() not in feitos]
    if not pendentes:
        print(f"[OK] {len(linhas)} perguntas já executadas. Rode `revisao` e `resumo`.")
        return 0

    from app.interfaces.api import perguntar as api

    orq, inicio, n = api.construir_orquestrador(), time.time(), 0
    with open(RESULTADOS, "a", encoding="utf-8") as saida:
        for ln in pendentes:
            if a.max_minutos and time.time() - inicio > a.max_minutos * 60:
                break
            t = time.time()
            try:
                estado = orq.executar(ln["pergunta"].strip())
                d, erro = api.serializar(estado), None
                recuperados = [{"arquivo": x.caminho_relativo, "pagina": x.pagina} for x in estado.get("trechos", [])]
            except Exception as exc:  # registra e segue: a falha também é resultado
                d, erro, recuperados = {}, f"{type(exc).__name__}: {exc}"[:300], []
            reg = {"id": ln["id"].strip(), "tipo": ln["tipo"].strip(), "ms": round((time.time() - t) * 1000),
                   "erro": erro, "rota": d.get("rota"), "agentes": d.get("agentes"),
                   "classificacao": d.get("classificacao") or (d.get("recomendacao") or {}).get("classificacao"),
                   "confianca": d.get("confianca"), "resposta": d.get("resposta"),
                   "recomendacao": (d.get("recomendacao") or {}).get("recomendacao"),
                   "elementos_rf20": d.get("elementos_rf20"), "valido": d.get("valido"),
                   "fontes": [{"arquivo": f["arquivo"], "pagina": f["pagina"]} for f in d.get("fontes", [])],
                   "recuperados": recuperados, "provedor_f2": d.get("provedor_f2")}
            saida.write(json.dumps(reg, ensure_ascii=False) + "\n")
            saida.flush()
            n += 1
            print(f"  {reg['id']}: {reg['rota'] or 'ERRO'} {reg['ms'] / 1000:.1f} s")  # sem conteúdo real na tela
    restantes = len(pendentes) - n
    print(f"[{'PARCIAL' if restantes else 'OK'}] {n} executadas nesta rodada; faltam {restantes}.")
    return 3 if restantes else 0


def revisao(_a):
    perguntas = {ln["id"].strip(): ln for ln in _ler_csv(PERGUNTAS)}
    res = _resultados()
    antigos = {ln["id"]: ln for ln in _ler_csv(REVISAO)} if REVISAO.exists() else {}
    linhas = []
    for i, p in perguntas.items():
        r = res.get(i)
        if not r:
            continue
        fontes = " | ".join(f"{f['arquivo']}" + (f" p.{f['pagina']}" if f.get("pagina") else "")
                            for f in r.get("fontes", []))
        resposta = (r.get("recomendacao") + " || " if r.get("recomendacao") else "") + (
            r.get("resposta") or r.get("erro") or "")
        linhas.append({"id": i, "tipo": p["tipo"], "pergunta": p["pergunta"], "termos_esperados": p["termos_esperados"],
                       "resposta": resposta, "classificacao": r.get("classificacao"),
                       "confianca": r.get("confianca"), "fontes": fontes,
                       "julgamento": (antigos.get(i) or {}).get("julgamento", ""),
                       "fontes_corretas": (antigos.get(i) or {}).get("fontes_corretas", ""),
                       "observacao": (antigos.get(i) or {}).get("observacao", "")})
    campos = ["id", "tipo", "pergunta", "termos_esperados", "resposta", "classificacao", "confianca", "fontes",
              "julgamento", "fontes_corretas", "observacao"]
    _gravar_csv(REVISAO, campos, linhas)
    print(f"[OK] {REVISAO.relative_to(RAIZ)} com {len(linhas)} respostas. Preencha 'julgamento' "
          f"(C=correta, P=parcial, I=incorreta, A=alucinação/afirmação sem suporte) e 'fontes_corretas' (S/N).")
    return 0


def _pct(xs):
    return round(sum(xs) / len(xs), 3) if xs else None


def resumo(a):
    perguntas = {ln["id"].strip(): ln for ln in _ler_csv(PERGUNTAS)}
    res = _resultados()
    julg = {ln["id"]: ln for ln in _ler_csv(REVISAO)} if REVISAO.exists() else {}
    feitos = [r for r in res.values() if r["id"] in perguntas]
    if not feitos:
        print("[ERRO] Nada executado ainda.")
        return 1
    rec_k, rec_fonte, termos, recusa, falsa_recusa, ms = [], [], [], [], [], []
    for r in feitos:
        p = perguntas[r["id"]]
        ms.append(r["ms"])
        doc = _norm(p.get("documento_esperado"))
        if doc:
            rec_k.append(any(doc in _norm(x["arquivo"]) for x in r["recuperados"][:a.k]))
            rec_fonte.append(any(doc in _norm(x["arquivo"]) for x in r["fontes"]))
        texto = _norm((r.get("recomendacao") or "") + " " + (r.get("resposta") or ""))
        esperados = [_norm(t) for t in (p.get("termos_esperados") or "").split("|") if t.strip()]
        if esperados:
            termos.append(all(t in texto for t in esperados))
        recusou = _norm(AUSENCIA) in texto  # o texto já está sem acentos
        if p["tipo"] == "ausencia":
            recusa.append(recusou)
        elif p["tipo"] != "decisao":
            falsa_recusa.append(recusou)
    js = [julg[r["id"]]["julgamento"].strip().upper()[:1] for r in feitos
          if r["id"] in julg and julg[r["id"]]["julgamento"].strip()[:1].upper() in JULGAMENTOS]
    fc = [julg[r["id"]]["fontes_corretas"].strip().upper()[:1] == "S" for r in feitos
          if r["id"] in julg and julg[r["id"]].get("fontes_corretas", "").strip()[:1].upper() in ("S", "N")]
    por_tipo = {}
    for r in feitos:
        por_tipo[r["tipo"]] = por_tipo.get(r["tipo"], 0) + 1
    f2 = [r for r in feitos if r["rota"] == "F2"]
    saida = {
        "perguntas": len(perguntas), "executadas": len(feitos), "por_tipo": por_tipo,
        "erros_execucao": sum(1 for r in feitos if r["erro"]),
        f"recall@{a.k}_documento_esperado": _pct(rec_k), "n_com_documento_esperado": len(rec_k),
        "documento_esperado_entre_fontes_citadas": _pct(rec_fonte),
        "termos_esperados_na_resposta": _pct(termos), "n_com_termos": len(termos),
        "recusa_correta (tipo ausencia)": _pct(recusa), "recusa_indevida (demais tipos)": _pct(falsa_recusa),
        "f2_validas": _pct([bool(r.get("valido")) for r in f2]),
        "f2_rf20_completo": _pct([bool(r.get("elementos_rf20")) and all(v in ("presente", "declarado") for v in
                                                                          r["elementos_rf20"].values()) for r in f2]),
        "f2_provedor_remoto": sum(1 for r in f2 if (r.get("provedor_f2") or {}).get("provedor", "local") != "local"),
        "latencia_s": {"p50": round(statistics.median(ms) / 1000, 1),
                       "p95": round(sorted(ms)[max(0, int(len(ms) * 0.95) - 1)] / 1000, 1)},
        "julgadas": len(js),
        "julgamento_humano": {v: _pct([j == k for j in js]) for k, v in JULGAMENTOS.items()} if js else None,
        "exatidao_humana (C + 0,5·P)": round((js.count("C") + 0.5 * js.count("P")) / len(js), 3) if js else None,
        "fontes_corretas_humano": _pct(fc),
    }
    RESUMO.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


AMOSTRA_TIPOS = PASTA / "amostra_tipos.csv"


def amostra_tipos(a):
    """Amostra estratificada (até --por-tipo documentos de cada tipo, semente fixa) para a equipe conferir o tipo."""
    import random
    import sqlite3

    from app.core.config import settings

    if AMOSTRA_TIPOS.exists():
        print(f"[OK] Já existe: {AMOSTRA_TIPOS.relative_to(RAIZ)} (não sobrescrito; apague para sortear de novo)")
        return 0
    conn = sqlite3.connect(str(settings.database_path))
    docs = conn.execute("SELECT id, caminho_relativo, tipo_documental, numero, titulo FROM documentos "
                        "WHERE status IN ('COM_TEXTO', 'COM_OCR')").fetchall()
    conn.close()
    por_tipo = {}
    for d in docs:
        por_tipo.setdefault(d[2], []).append(d)
    rnd, linhas = random.Random(20261120), []  # noqa: S311 - amostragem reprodutível, não criptografia
    for tipo in sorted(por_tipo):
        for d in rnd.sample(por_tipo[tipo], min(a.por_tipo, len(por_tipo[tipo]))):
            linhas.append({"documento_id": d[0], "arquivo": d[1], "tipo_atribuido": d[2],
                           "numero_atribuido": d[3] or "", "titulo_detectado": (d[4] or "")[:120],
                           "tipo_correto": "", "numero_correto": ""})
    PASTA.mkdir(parents=True, exist_ok=True)
    _gravar_csv(AMOSTRA_TIPOS, list(linhas[0].keys()), linhas)
    print(f"[OK] {AMOSTRA_TIPOS.relative_to(RAIZ)}: {len(linhas)} documentos de {len(por_tipo)} tipos. Preencha "
          f"'tipo_correto' (repita o tipo se estiver certo) e, se houver, 'numero_correto'.")
    return 0


def medir_tipos(_a):
    linhas = [ln for ln in _ler_csv(AMOSTRA_TIPOS) if ln.get("tipo_correto", "").strip()]
    if not linhas:
        print("[ERRO] Nenhuma linha conferida em amostra_tipos.csv")
        return 1
    por_tipo = {}
    for ln in linhas:
        por_tipo.setdefault(ln["tipo_atribuido"], []).append(_norm(ln["tipo_correto"]) == _norm(ln["tipo_atribuido"]))
    num = [_norm(ln["numero_correto"]) == _norm(ln["numero_atribuido"]) for ln in linhas
           if ln.get("numero_correto", "").strip()]
    saida = {"conferidos": len(linhas), "precisao_geral": _pct([x for v in por_tipo.values() for x in v]),
             "precisao_por_tipo": {t: {"n": len(v), "precisao": _pct(v)} for t, v in sorted(por_tipo.items())},
             "numero_correto": _pct(num), "n_numero_conferido": len(num)}
    (PASTA / "resumo_tipos.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("acao", choices=["modelo", "executar", "revisao", "resumo", "amostra-tipos", "medir-tipos"])
    p.add_argument("--max-minutos", type=float, default=None)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--por-tipo", type=int, default=8)
    a = p.parse_args()
    if a.acao in ("amostra-tipos", "medir-tipos"):
        if a.acao == "medir-tipos" and not AMOSTRA_TIPOS.exists():
            print("[ERRO] Gere a amostra primeiro: avaliar_real.py amostra-tipos")
            return 1
        return amostra_tipos(a) if a.acao == "amostra-tipos" else medir_tipos(a)
    if a.acao != "modelo" and not PERGUNTAS.exists():
        print("[ERRO] Crie primeiro as perguntas: python scripts/sadgd/avaliar_real.py modelo")
        return 1
    return {"modelo": modelo, "executar": executar, "revisao": revisao, "resumo": resumo}[a.acao](a)


if __name__ == "__main__":
    sys.exit(main())
