"""Gabarito automático do acervo REAL a partir das fichas de contrato (rodada 18, 2026-11-25).

Cada dado da ficha (número, contratada, CNPJ, objeto, fiscal, gestor, assinatura, valor, término da vigência) foi
conferido contra o trecho de onde veio na extração: vira uma pergunta com resposta esperada e documento esperado.
O conjunto é dividido por CONTRATO em validação (ajustes) e teste (medição final, nunca usado para ajustar).

Modos de execução:
  llm       — caminho de produção quando a ficha não responde sozinha (documentos-chave + ficha conferida no
              contexto + LLM + verificador);
  leitura   — teste de estresse: sem a ficha no contexto (o gabarito vem da ficha), só trechos + LLM;
  completo  — pipeline do servidor (ficha quando cobre).

Tudo fica em avaliacao/real/ (fora do Git). Na tela: só números e ids — nunca perguntas, respostas ou trechos reais.
Uso: python scripts/sadgd/avaliar_gabarito_fichas.py gerar
     python scripts/sadgd/avaliar_gabarito_fichas.py executar --modo llm --conjunto validacao --rodada r18 \
            [--max-minutos 4]
     python scripts/sadgd/avaliar_gabarito_fichas.py resumo --modo llm --conjunto validacao --rodada r18
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.fichas.agrupamento import chaves_no_texto, normalizar  # noqa: E402
from app.application.fichas.consulta import data_do_texto  # noqa: E402

PASTA = RAIZ / "avaliacao" / "real"
GABARITO = PASTA / "gabarito_fichas.jsonl"
VAZIAS = {"a", "o", "e", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "para", "por", "com", "sem",
          "que", "um", "uma", "ao", "aos", "as", "os", "ltda", "me", "epp", "eireli", "sa", "s", "servico", "servicos",
          "contrato", "contratada", "empresa"}

# campo → (modelos de pergunta, tipo de comparação). {n} = número do contrato
MODELOS = {
    "contratada": (["Qual empresa foi contratada no contrato {n}?", "Quem é a contratada do contrato {n}?"], "nome"),
    "cnpj_contratada": (["Qual o CNPJ da empresa contratada no contrato {n}?"], "cnpj"),
    "objeto": (["Qual o objeto do contrato {n}?", "Do que trata o contrato {n}?"], "texto"),
    "fiscal": (["Quem é o fiscal do contrato {n}?"], "nome"),
    "gestor": (["Quem é o gestor do contrato {n}?"], "nome"),
    "data_assinatura": (["Em que data foi assinado o contrato {n}?"], "data"),
    "valor_global": (["Qual o valor global do contrato {n}?"], "dinheiro"),
    "vigencia_atual_fim": (["Até quando vai a vigência do contrato {n}?"], "data"),
    "vigencia_fim": (["Até quando vai a vigência do contrato {n}?"], "data"),
}
RE_DINHEIRO = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


def _ler(caminho):
    return [json.loads(x) for x in open(caminho, encoding="utf-8")] if caminho.exists() else []


def _conjunto(chave):
    # divisão estável por contrato (não é uso criptográfico; trocar o hash mudaria os conjuntos já medidos)
    return "validacao" if int(hashlib.md5(chave.encode()).hexdigest(), 16) % 2 == 0 else "teste"  # noqa: S324


def _nome_curto(contratada):
    palavras = [p for p in re.findall(r"[a-z0-9]{4,}", normalizar(contratada)) if p not in VAZIAS]
    return palavras[0] if palavras else None


def gerar(_a):
    from app.core.config import settings
    from app.infrastructure.sqlite.conexao import conectar

    conn = conectar(settings.database_path, vetores=False)
    fichas = [(r[0], json.loads(r[1])) for r in conn.execute("SELECT chave, campos FROM fichas_contrato")]
    doc_do_trecho = dict(conn.execute("SELECT id, documento_id FROM trechos"))
    conn.close()
    itens = []
    for chave, campos in sorted(fichas):
        # a pergunta usa o nº do contrato (chave da pasta), como a equipe pergunta; o campo "numero" só entra no
        # gabarito quando confere com a chave (5 de 17 fichas tinham nº de processo ou de outro contrato)
        numero = chave
        if "numero" in campos and chave not in chaves_no_texto(str(campos["numero"]["valor"]), so_contrato=False):
            campos = {k: v for k, v in campos.items() if k != "numero"}
        for campo, (modelos, tipo) in MODELOS.items():
            if campo not in campos or (campo == "vigencia_fim" and "vigencia_atual_fim" in campos):
                continue
            item = campos[campo]
            for i, modelo in enumerate(modelos):
                itens.append({"id": f"G{len(itens) + 1:03d}", "contrato": chave, "conjunto": _conjunto(chave),
                              "campo": campo, "tipo": tipo, "pergunta": modelo.format(n=numero),
                              "esperado": str(item["valor"]), "trecho_esperado": item.get("trecho_id"),
                              "documento_esperado": doc_do_trecho.get(item.get("trecho_id")), "variante": i})
        nome = _nome_curto((campos.get("contratada") or {}).get("valor", ""))
        if nome and "numero" in campos:  # o número pelo nome do fornecedor (como a equipe pergunta)
            item = campos["numero"]
            itens.append({"id": f"G{len(itens) + 1:03d}", "contrato": chave, "conjunto": _conjunto(chave),
                          "campo": "numero", "tipo": "numero", "pergunta": f"Qual o número do contrato com a {nome}?",
                          "esperado": str(item["valor"]), "trecho_esperado": item.get("trecho_id"),
                          "documento_esperado": doc_do_trecho.get(item.get("trecho_id")), "variante": 0})
    PASTA.mkdir(parents=True, exist_ok=True)
    with open(GABARITO, "w", encoding="utf-8") as f:
        for it in itens:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    por = {c: sum(1 for i in itens if i["conjunto"] == c) for c in ("validacao", "teste")}
    print(f"[OK] {len(itens)} perguntas de {len(fichas)} fichas → {GABARITO.relative_to(RAIZ)} | {por}")
    return 0


# ------------------------------------------------------------------------------------------------- pontuação
def _datas(texto):
    t = normalizar(texto)
    achadas = set()
    for m in re.finditer(r"\b\d{1,2}[/.-]\d{1,2}[/.-]20\d{2}\b|\b\d{1,2}\s*(?:o|º)?\s*de\s+[a-z]+\s+de\s+20\d{2}\b", t):
        d = data_do_texto(m.group(0))
        if d:
            achadas.add(d)
    return achadas


def acertou(tipo, esperado, resposta) -> bool:
    r = normalizar(resposta)
    if tipo == "dinheiro":
        alvo = set(RE_DINHEIRO.findall(esperado))
        return bool(alvo) and bool(alvo & set(RE_DINHEIRO.findall(r)))
    if tipo == "cnpj":
        digitos = re.sub(r"\D", "", esperado)
        return len(digitos) >= 14 and digitos in re.sub(r"[.\-/\s]", "", r)
    if tipo == "data":
        alvo = _datas(esperado)
        return bool(alvo) and bool(alvo & _datas(r))
    if tipo == "numero":
        alvo = set(chaves_no_texto(esperado, so_contrato=False))
        return bool(alvo & set(chaves_no_texto(r, so_contrato=False))) or normalizar(esperado) in r
    termos = [p for p in re.findall(r"[a-z0-9]{3,}", normalizar(esperado)) if p not in VAZIAS]
    if not termos:
        return normalizar(esperado) in r
    presentes = sum(1 for p in termos if re.search(rf"\b{re.escape(p)}", r))
    if tipo == "nome" and not re.search(rf"\b{re.escape(termos[0])}\b", r):
        return False  # pessoa/empresa: o 1º nome tem de aparecer (sobrenomes comuns não bastam)
    return presentes / len(termos) >= (0.5 if tipo == "texto" else 0.6)


# ------------------------------------------------------------------------------------------------- execução
def _arquivo(a):
    return PASTA / f"gabarito_{a.rodada}_{a.modo}_{a.conjunto}.jsonl"


def executar(a):
    from app.core.config import settings

    if settings.ai_allow_remote or settings.llm_f2 != "local":
        print("[ERRO] Com documentos reais use AI_ALLOW_REMOTE=false e SADGD_LLM_F2=local no .env.")
        return 1
    itens = [i for i in _ler(GABARITO) if i["conjunto"] == a.conjunto]
    if a.limite:
        itens = itens[: a.limite]
    feitos = {r["id"] for r in _ler(_arquivo(a))}
    pendentes = [i for i in itens if i["id"] not in feitos]
    if not pendentes:
        print(f"[OK] {len(itens)} já executadas. Rode `resumo`.")
        return 0
    from app.interfaces.api import perguntar as api

    orq = api.construir_orquestrador()
    if a.modo in ("llm", "leitura"):
        orq._fichas = lambda _p: None  # a ficha não responde; a busca continua restrita ao contrato citado
    if a.modo == "leitura":
        orq._ficha_f1 = None  # teste de estresse: o LLM não recebe a ficha, só os trechos
    inicio, n = time.time(), 0
    with open(_arquivo(a), "a", encoding="utf-8") as saida:
        for it in pendentes:
            if a.max_minutos and time.time() - inicio > a.max_minutos * 60:
                break
            t = time.time()
            try:
                estado = orq.executar(it["pergunta"])
                d, erro = api.serializar(estado), None
                recuperados = list(dict.fromkeys(x.documento_id for x in estado.get("trechos", [])))
            except Exception as exc:  # noqa: BLE001 - a falha também é resultado
                d, erro, recuperados = {}, f"{type(exc).__name__}: {exc}"[:300], []
            resposta = d.get("resposta") or ""
            reg = {"contexto_ids": [x.id for x in estado.get("trechos", [])] if not erro else [],
                   "fontes_ids": [f["trecho_id"] for f in d.get("fontes", [])],
                   "id": it["id"], "campo": it["campo"], "ms": round((time.time() - t) * 1000), "erro": erro,
                   "rota": d.get("rota"), "ficha": d.get("ficha"), "classificacao": d.get("classificacao"),
                   "confianca": d.get("confianca"), "resposta": resposta,
                   "acerto": bool(resposta) and d.get("classificacao") != "ausencia"
                   and acertou(it["tipo"], it["esperado"], resposta),
                   "fonte_correta": it["documento_esperado"] in {f["documento_id"] for f in d.get("fontes", [])},
                   "recuperou_documento": it["documento_esperado"] in recuperados,
                   "tokens": d.get("tokens"), "observacoes": d.get("observacoes"), "tempos_ms": d.get("tempos_ms")}
            saida.write(json.dumps(reg, ensure_ascii=False) + "\n")
            saida.flush()
            n += 1
            print(f"  {reg['id']} {reg['campo']}: {'ok' if reg['acerto'] else 'ERRO'} {reg['ms'] / 1000:.1f} s",
                  flush=True)
    restantes = len(pendentes) - n
    print(f"[{'PARCIAL' if restantes else 'OK'}] {n} nesta rodada; faltam {restantes}.")
    return 3 if restantes else 0


def _p(valores, q):
    valores = sorted(valores)
    return valores[min(len(valores) - 1, int(round(q * (len(valores) - 1))))] if valores else None


def resumo(a):
    gab = {i["id"]: i for i in _ler(GABARITO)}
    res = [r for r in _ler(_arquivo(a)) if r["id"] in gab]
    if not res:
        print("[ERRO] nada executado.")
        return 1
    n = len(res)
    respondidas = [r for r in res if r["classificacao"] not in (None, "ausencia")]
    acertos = sum(r["acerto"] for r in res)
    ms = [r["ms"] for r in res]
    llm = [r["ms"] for r in res if not r.get("ficha")]
    tok = [((r.get("tokens") or {}).get("entrada") or 0) for r in res if not r.get("ficha")]
    saida = {
        "rodada": a.rodada, "modo": a.modo, "conjunto": a.conjunto, "n": n,
        "acuracia": round(acertos / n, 3),
        "precisao (acertos/respondidas)": round(acertos / len(respondidas), 3) if respondidas else None,
        "recusas": n - len(respondidas), "fonte_correta": round(sum(r["fonte_correta"] for r in res) / n, 3),
        "documento_recuperado": round(sum(r["recuperou_documento"] for r in res) / n, 3),
        "erros_execucao": sum(1 for r in res if r["erro"]),
        "via_ficha": sum(1 for r in res if r.get("ficha")),
        "latencia_s": {"p50": round(statistics.median(ms) / 1000, 1), "p95": round(_p(ms, 0.95) / 1000, 1)},
        "latencia_llm_s": {"p50": round(statistics.median(llm) / 1000, 1),
                           "media": round(statistics.mean(llm) / 1000, 1)} if llm else None,
        "tokens_entrada_media_llm": round(statistics.mean(tok)) if tok else None,
        "por_campo": {}, "calibracao": {},
        "erros_ids": {"recusa": [r["id"] for r in res if r["classificacao"] == "ausencia"],
                      "valor_errado_doc_recuperado": [r["id"] for r in res if not r["acerto"]
                                                      and r["classificacao"] != "ausencia"
                                                      and r["recuperou_documento"]],
                      "valor_errado_doc_nao_recuperado": [r["id"] for r in res if not r["acerto"]
                                                          and r["classificacao"] != "ausencia"
                                                          and not r["recuperou_documento"]]},
    }
    for campo in sorted({r["campo"] for r in res}):
        rs = [r for r in res if r["campo"] == campo]
        saida["por_campo"][campo] = f"{sum(r['acerto'] for r in rs)}/{len(rs)}"
    for faixa, (lo, hi) in {"<0.6": (0, 0.6), "0.6-0.8": (0.6, 0.8), ">=0.8": (0.8, 1.01)}.items():
        rs = [r for r in respondidas if isinstance(r["confianca"], (int, float)) and lo <= r["confianca"] < hi]
        if rs:
            saida["calibracao"][faixa] = {"n": len(rs), "acuracia": round(sum(r["acerto"] for r in rs) / len(rs), 3),
                                          "confianca_media": round(statistics.mean(r["confianca"] for r in rs), 3)}
    (PASTA / f"resumo_gabarito_{a.rodada}_{a.modo}_{a.conjunto}.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("acao", choices=["gerar", "executar", "resumo"])
    p.add_argument("--modo", choices=["llm", "leitura", "completo"], default="llm")
    p.add_argument("--conjunto", choices=["validacao", "teste"], default="validacao")
    p.add_argument("--rodada", default="r18")
    p.add_argument("--max-minutos", type=float, default=None)
    p.add_argument("--limite", type=int, default=None)
    a = p.parse_args()
    return {"gerar": gerar, "executar": executar, "resumo": resumo}[a.acao](a)


if __name__ == "__main__":
    sys.exit(main())
