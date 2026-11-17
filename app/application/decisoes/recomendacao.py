"""SAD-081 — Recomendação F2 completa e fundamentada (RF-20).

Seis elementos obrigatórios: alternativas, riscos, base legal, precedentes, confiança e o aviso "o sistema sugere".
Regras determinísticas (nunca inventam conteúdo):
  - precedentes vêm SEMPRE da memória de decisões (o LLM não pode criar precedente);
  - base legal vem das fundamentações dos pareceres verificados (trecho no contexto) ou, na falta delas, dos trechos
    normativos recuperados; norma revogada não fundamenta — vai para o histórico (RF-14); ordem pela hierarquia;
  - alternativas e riscos ausentes na síntese são completados com os dos pareceres;
  - elemento sem conteúdo possível é declarado como lacuna (ausência explícita, nunca preenchimento inventado);
  - a confiança declarada é limitada por evidência (sem base legal, sem pareceres válidos, frases removidas).
"""
from app.domain.normas import EspecieNormativa

NIVEL = {e.codigo: e.nivel for e in EspecieNormativa} | {"decreto_lei": 2}
ELEMENTOS = ("alternativas", "riscos", "base_legal", "precedentes", "confianca", "aviso")
LACUNAS = {
    "alternativas": "Os pareceres não apresentaram alternativas fundamentadas nos documentos.",
    "riscos": "Os pareceres não identificaram riscos fundamentados nos documentos.",
    "base_legal": "Não localizei base legal vigente nos trechos recuperados.",
    "precedentes": "Não há decisões anteriores semelhantes registradas na memória de decisões.",
}
TETO_SEM_BASE_LEGAL, TETO_SEM_PARECER, TETO_FRASES_REMOVIDAS = 0.5, 0.4, 0.6


def _vigente(t):
    return not t.revogado and (t.situacao_norma or "vigente") != "revogada"


def base_legal(trechos, pareceres):
    """(vigentes, historico): entradas {norma, dispositivo, trecho, vigente, nivel}, vigentes pela hierarquia."""
    por_rotulo = {t.rotulo: t for t in trechos}
    itens = {}

    def incluir(t, norma, dispositivo):
        chave = (norma.strip().lower(), (dispositivo or "").strip().lower())
        if chave not in itens:
            itens[chave] = {"norma": norma.strip(), "dispositivo": (dispositivo or "").strip(), "trecho": t.rotulo,
                            "vigente": _vigente(t), "nivel": NIVEL.get(t.tipo_documental or "", 6)}

    for p in pareceres:
        if not p.valido_reparado:
            continue
        for f in p.dados.get("fundamentacao_legal") or []:
            t = por_rotulo.get(f.get("trecho"))
            if t is not None and (t.tipo_documental in NIVEL):
                incluir(t, f.get("norma") or t.titulo or "", f.get("dispositivo") or t.dispositivo)
    if not itens:  # nenhum especialista fundamentou: usa as normas recuperadas para a pergunta
        for t in trechos:
            if t.tipo_documental in NIVEL:
                incluir(t, t.titulo or "", t.dispositivo)
    todos = sorted(itens.values(), key=lambda i: (i["nivel"], i["norma"]))
    return [i for i in todos if i["vigente"]][:6], [i for i in todos if not i["vigente"]]


def _dos_pareceres(pareceres, campo, chave_unica, limite=3):
    vistos, saida = set(), []
    for p in pareceres:
        if not p.valido_reparado:
            continue
        for item in p.dados.get(campo) or []:
            k = str(item.get(chave_unica, "")).strip().lower()
            if k and k not in vistos:
                vistos.add(k)
                saida.append({**item, "agente": p.agente})
    return saida[:limite]


def completar(d, trechos, pareceres, precedentes, frases_removidas=False):
    """Completa a saída do relator in place. Retorna {elemento: 'modelo'|'sistema'|'lacuna'}."""
    origem = {}
    lacunas = list(d.get("lacunas") or [])
    for campo, chave in (("alternativas", "descricao"), ("riscos", "descricao")):
        if d.get(campo):
            origem[campo] = "modelo"
        else:
            d[campo] = _dos_pareceres(pareceres, campo, chave)
            origem[campo] = "sistema" if d[campo] else "lacuna"
    vigentes, historico = base_legal(trechos, pareceres)
    d["base_legal"], d["normas_no_historico"] = vigentes, historico
    origem["base_legal"] = "sistema" if vigentes else "lacuna"
    d["precedentes"] = [p.resumo() for p in precedentes]
    origem["precedentes"] = "sistema" if precedentes else "lacuna"
    for campo in ("alternativas", "riscos", "base_legal", "precedentes"):
        if origem[campo] == "lacuna" and LACUNAS[campo] not in lacunas:
            lacunas.append(LACUNAS[campo])
    d["lacunas"] = lacunas
    teto = 1.0
    if not vigentes:
        teto = min(teto, TETO_SEM_BASE_LEGAL)
    if not any(p.valido_reparado and p.dados.get("parecer") for p in pareceres):
        teto = min(teto, TETO_SEM_PARECER)
    if frases_removidas:
        teto = min(teto, TETO_FRASES_REMOVIDAS)
    d["confianca"] = round(min(float(d.get("confianca") or 0.0), teto), 3)
    origem["confianca"] = "modelo" if teto == 1.0 else "sistema"
    origem["aviso"] = "sistema"
    if precedentes and any(p.decisao.avaliacao_resultado.value == "negativo" for p in precedentes):
        alerta = "Há precedente com resultado negativo: avaliar o que deu errado antes de repetir a solução."
        if alerta not in d["lacunas"]:
            d.setdefault("alertas", []).append(alerta)
    return origem


def elementos_rf20(d):
    """Presença dos 6 elementos: presente (com conteúdo), declarado (ausência explícita em lacunas) ou ausente."""
    estado = {}
    lacunas = " ".join(d.get("lacunas") or [])
    for campo in ("alternativas", "riscos", "base_legal", "precedentes"):
        estado[campo] = "presente" if d.get(campo) else ("declarado" if LACUNAS[campo] in lacunas else "ausente")
    estado["confianca"] = "presente" if isinstance(d.get("confianca"), (int, float)) else "ausente"
    estado["aviso"] = "presente" if d.get("aviso") else "ausente"
    return estado
