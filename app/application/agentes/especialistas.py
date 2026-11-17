"""Especialistas e relator F2 (SAD-071/073): prompts versionados, saída JSON validada por schema, citações
restritas ao contexto e verificação determinística de cada afirmação (RF-16/17/18)."""
import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from app.application.agentes.verificador import suporte, verificar
from app.application.avaliacao.metricas_resposta import numeros_nao_suportados
from app.application.decisoes.recomendacao import completar
from app.application.respostas.f1 import carregar_prompt, montar_contexto
from app.domain.politicas import AVISO_DECISAO

AGENTES = Path(__file__).resolve().parent
ORDEM_PARECER = ("Responda SOMENTE com um objeto JSON com as chaves nesta ordem: \"parecer\" (texto até 600 "
                 "caracteres), \"afirmacoes\" (lista de {\"id\", \"texto\", \"tipo\": fato|inferencia, \"citacoes\": "
                 "[\"T<id>\"], \"raciocinio\"}), \"fundamentacao_legal\" (lista de {\"norma\", \"dispositivo\", "
                 "\"trecho\": \"T<id>\", \"vigente\": true|false}), \"riscos\" (lista de {\"descricao\", "
                 "\"probabilidade\": baixa|media|alta, \"impacto\": baixo|medio|alto, \"mitigacao\"}), "
                 "\"alternativas\" (lista de {\"descricao\", \"pros\": [\"...\"], \"contras\": [\"...\"]}), "
                 "\"recomendacao\", \"lacunas\", "
                 "\"conflitos\" (lista de {\"descricao\", \"trechos\"}), \"confianca\" (0 a 1). Seja conciso: no "
                 "máximo 4 afirmações, 3 fundamentos, 3 riscos, 2 alternativas e 3 lacunas, cada texto com uma frase.")
ORDEM_RELATOR = ("Modo F2. Responda SOMENTE com um objeto JSON com as chaves nesta ordem: \"resposta\" "
                 "(síntese com citações [T<id>] e, se houver, [P<id>] dos precedentes), \"recomendacao\" (1 a 2 "
                 "frases), \"consensos\" (lista de frases curtas, texto simples), "
                 "\"divergencias\" (lista de {\"tema\", \"posicoes\": [{\"agente\", "
                 "\"posicao\"}]}), \"alternativas\" (lista de {\"descricao\", \"pros\": [\"...\"], "
                 "\"contras\": [\"...\"]}), \"riscos\" (lista de {\"descricao\", \"probabilidade\": "
                 "baixa|media|alta, \"impacto\": baixo|medio|alto, \"mitigacao\"}), \"lacunas\", \"fontes\" "
                 "(lista de \"T<id>\"), \"classificacao\" (inferencia|conflito|ausencia), \"confianca\" (0 a 1). "
                 "Seja conciso: \"resposta\" até 900 caracteres e no máximo 3 itens por lista, cada um com uma "
                 "frase.")
NIVEIS_PROB = {"baixa", "media", "alta"}
SEM_ACENTO = str.maketrans("áâãéêíóôõú", "aaaeeiooou")
NIVEIS_IMP = {"baixo", "medio", "alto"}


@cache
def _schema(nome):
    return json.loads((AGENTES / "schemas" / nome).read_text(encoding="utf-8"))


@cache
def _meta(agente):
    texto = (AGENTES / "prompts" / f"{agente}.v1.md").read_text(encoding="utf-8")
    cabecalho = texto.split("---", 2)[1]
    return dict(linha.split(":", 1) for linha in cabecalho.strip().splitlines())


def _validar_schema(dados, schema):
    import jsonschema

    erros = sorted(jsonschema.Draft202012Validator(schema).iter_errors(dados), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '<raiz>'}: {e.message[:120]}" for e in erros]


def _rotulo(x):
    x = str(x).strip().strip("[]").strip()
    return f"T{x}" if x.isdigit() else x


def _nivel(valor, validos, padrao):
    v = str(valor or "").strip().lower().translate(SEM_ACENTO)
    return v if v in validos else padrao


def _consenso_em_frase(item):
    """Consenso deve ser texto; objetos {tema, posicoes:[{agente, posicao}]} viram uma frase sem perder conteúdo."""
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    tema = str(item.get("tema") or item.get("descricao") or "").strip()
    posicoes = [f"{p.get('agente', '')}: {p.get('posicao', '')}".strip(": ") for p in item.get("posicoes") or []
                if isinstance(p, dict)]
    return " — ".join(x for x in (tema, "; ".join(posicoes)) if x)


def _reparar_parecer(d, agente, rotulos):
    """Reparo mínimo de forma (nunca de conteúdo): tipos, listas ausentes, enums e citações fora do contexto."""
    d = dict(d) if isinstance(d, dict) else {}
    d["agente"] = agente
    d["parecer"] = str(d.get("parecer") or "")[:1200]
    for chave in ("afirmacoes", "fundamentacao_legal", "riscos", "alternativas", "lacunas", "conflitos"):
        d[chave] = d.get(chave) if isinstance(d.get(chave), list) else []
    try:
        d["confianca"] = max(0.0, min(1.0, float(d.get("confianca", 0))))
    except (TypeError, ValueError):
        d["confianca"] = 0.0
    afirmacoes = []
    for i, a in enumerate(d["afirmacoes"], start=1):
        if not isinstance(a, dict):
            continue
        citacoes = [c for c in map(_rotulo, a.get("citacoes") or []) if c in rotulos]
        if not citacoes:
            continue  # afirmação sem citação válida não entra (RF-17)
        afirmacoes.append({"id": str(a.get("id") or f"A{i}"), "texto": str(a.get("texto") or ""),
                           "tipo": a.get("tipo") if a.get("tipo") in ("fato", "inferencia") else "inferencia",
                           "citacoes": citacoes, "raciocinio": str(a.get("raciocinio") or "")})
    d["afirmacoes"] = afirmacoes
    d["fundamentacao_legal"] = [
        {"norma": str(f.get("norma") or ""), "dispositivo": str(f.get("dispositivo") or ""),
         "trecho": _rotulo(f.get("trecho")), "vigente": bool(f.get("vigente", True))}
        for f in d["fundamentacao_legal"] if isinstance(f, dict) and _rotulo(f.get("trecho")) in rotulos]
    d["riscos"] = [{"descricao": str(r.get("descricao") or ""),
                    "probabilidade": _nivel(r.get("probabilidade"), NIVEIS_PROB, "media"),
                    "impacto": _nivel(r.get("impacto"), NIVEIS_IMP, "medio"),
                    "mitigacao": str(r.get("mitigacao") or "")} for r in d["riscos"] if isinstance(r, dict)]
    d["alternativas"] = [{"descricao": str(a.get("descricao") or ""),
                          "pros": [str(x) for x in (a.get("pros") or [])] if isinstance(a.get("pros"), list) else
                          [str(a.get("pros"))], "contras": [str(x) for x in (a.get("contras") or [])]
                          if isinstance(a.get("contras"), list) else [str(a.get("contras"))]}
                         for a in d["alternativas"] if isinstance(a, dict)]
    d["lacunas"] = [str(x) for x in d["lacunas"]]
    d["conflitos"] = [{"descricao": str(c.get("descricao") or ""),
                       "trechos": [t for t in map(_rotulo, c.get("trechos") or []) if t in rotulos]}
                      for c in d["conflitos"] if isinstance(c, dict)]
    d["conflitos"] = [c for c in d["conflitos"] if len(c["trechos"]) >= 2]
    if "recomendacao" in d:
        d["recomendacao"] = str(d["recomendacao"] or "")
    return {k: v for k, v in d.items() if k in _schema("parecer_especialista.v1.json")["properties"]}


@dataclass
class Parecer:
    agente: str
    dados: dict
    valido_bruto: bool
    valido_reparado: bool
    erros_schema: list = field(default_factory=list)
    afirmacoes_removidas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    tentativas: int = 1


AVISO_CORTE = ("Sua resposta anterior foi cortada e não formou um JSON válido. Responda de novo, de forma bem "
               "mais concisa, com o objeto JSON completo.")
FALHA_RELATOR = ("Não foi possível consolidar os pareceres de forma estruturada; consulte os pareceres individuais "
                 "dos especialistas.")


def _chat_json(llm, mensagens, max_tokens, temperatura):
    """Chamada JSON tolerante a corte por limite de tokens: 1 nova tentativa mais concisa e com orçamento maior.
    Devolve (RespostaLLM | None, tentativas)."""
    try:
        return llm.chat(mensagens, max_tokens=max_tokens, temperatura=temperatura, json_livre=True), 1
    except RuntimeError:  # ErroLLM (JSON inválido/cortado) ou falha transitória do servidor
        pass
    try:
        return llm.chat(mensagens + [{"role": "user", "content": AVISO_CORTE}], max_tokens=int(max_tokens * 1.5),
                        temperatura=temperatura, json_livre=True), 2
    except RuntimeError:
        return None, 2


def executar_especialista(llm, agente, pergunta, trechos, contexto_extra="") -> Parecer:
    meta = _meta(agente)
    mensagens = [
        {"role": "system", "content": carregar_prompt(agente) + "\n\n" + ORDEM_PARECER},
        {"role": "user", "content": f"PERGUNTA: {pergunta}\n\n{contexto_extra}\n\n"
                                    f"TRECHOS:\n{montar_contexto(trechos)}"},
    ]
    r, tentativas = _chat_json(llm, mensagens, int(meta.get("max_tokens", 800)), float(meta.get("temperatura", 0)))
    if r is None:  # o especialista falhou: parecer vazio e inválido (o relator o ignora), sem derrubar o grafo
        return Parecer(agente, _reparar_parecer({}, agente, set()), False, False, ["sem_json_valido"], tentativas=2)
    bruto = r.json if isinstance(r.json, dict) else {}
    schema = _schema("parecer_especialista.v1.json")
    erros = _validar_schema({**bruto, "agente": agente}, schema)
    rotulos = {t.rotulo for t in trechos}
    reparado = _reparar_parecer(bruto, agente, rotulos)
    erros_rep = _validar_schema(reparado, schema)
    # verificação determinística de cada afirmação (números/datas dos trechos citados)
    por_rotulo = {t.rotulo: t for t in trechos}
    antes = len(reparado["afirmacoes"])
    reparado["afirmacoes"] = [
        a for a in reparado["afirmacoes"]
        if not numeros_nao_suportados(a["texto"], [suporte(por_rotulo[c]) for c in a["citacoes"]], pergunta)]
    return Parecer(agente, reparado, not erros, not erros_rep, erros or erros_rep,
                   (len([a for a in (bruto.get("afirmacoes") or []) if isinstance(a, dict)]) - antes)
                   + (antes - len(reparado["afirmacoes"])), r.tokens_entrada, r.tokens_saida, r.latencia_ms, tentativas)


def _compactar(p: Parecer):
    d = p.dados
    return {"agente": p.agente, "parecer": d["parecer"][:600], "recomendacao": d.get("recomendacao", "")[:300],
            "afirmacoes": [{"texto": a["texto"][:250], "citacoes": a["citacoes"], "tipo": a["tipo"]}
                           for a in d["afirmacoes"][:6]],
            "riscos": d["riscos"][:4], "alternativas": d["alternativas"][:3], "lacunas": d["lacunas"][:3],
            "confianca": d["confianca"]}


@dataclass
class RespostaF2:
    resposta: str
    dados: dict
    fontes: list
    pareceres: list
    valido: bool
    verificacao: object = None
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    observacoes: list = field(default_factory=list)


def relatar_f2(llm, pergunta, trechos, pareceres, contexto_extra="", precedentes=()) -> RespostaF2:
    validos = [_compactar(p) for p in pareceres if p.dados.get("parecer")]
    mensagens = [
        {"role": "system", "content": carregar_prompt("relator", versao=2) + "\n\n" + ORDEM_RELATOR},
        {"role": "user", "content": f"PERGUNTA: {pergunta}\n\n{contexto_extra}\n\nPARECERES VERIFICADOS:\n"
                                    f"{json.dumps(validos, ensure_ascii=False)}\n\n"
                                    f"TRECHOS:\n{montar_contexto(trechos)}"},
    ]
    r, tentativas = _chat_json(llm, mensagens, 1200, 0.1)
    d = r.json if r is not None and isinstance(r.json, dict) else {}
    if r is None:
        d = {"resposta": FALHA_RELATOR, "classificacao": "inferencia", "confianca": 0.0}
    por_rotulo = {t.rotulo: t for t in trechos}
    citados = [c for c in dict.fromkeys(list(map(_rotulo, d.get("fontes") or [])) +
                                        [f"T{n}" for n in re.findall(r"\bT(\d+)\b", str(d.get("resposta", "")))])
               if c in por_rotulo]
    fontes = [por_rotulo[c] for c in citados]
    d["aviso"] = AVISO_DECISAO  # obrigatório: o sistema sugere, a gestão decide
    d["fontes"] = citados
    if d.get("classificacao") not in ("fato", "inferencia", "conflito", "ausencia"):
        d["classificacao"] = "inferencia"
    try:
        d["confianca"] = max(0.0, min(1.0, float(d.get("confianca", 0))))
    except (TypeError, ValueError):
        d["confianca"] = 0.0
    for chave in ("consensos", "divergencias", "alternativas", "riscos", "lacunas"):
        d[chave] = d.get(chave) if isinstance(d.get(chave), list) else []
    # reparo de forma: consenso no formato das divergências ({"tema", "posicoes"}) → frase (Gemini, Fase 11)
    d["consensos"] = [_consenso_em_frase(c) for c in d["consensos"] if _consenso_em_frase(c)]
    for risco in d["riscos"]:  # reparo de forma: "médio"/"Alta" → "medio"/"alta"
        if isinstance(risco, dict):
            for campo in ("probabilidade", "impacto"):
                if isinstance(risco.get(campo), str):
                    risco[campo] = risco[campo].strip().lower().translate(SEM_ACENTO)
    d["resposta"] = str(d.get("resposta") or "")
    d["recomendacao"] = str(d.get("recomendacao") or "").strip() or "Ver síntese; os pareceres não convergiram " \
        "para uma medida única."
    for alt in d["alternativas"]:  # reparo de forma: prós/contras em texto → lista
        if isinstance(alt, dict):
            for campo in ("pros", "contras"):
                if isinstance(alt.get(campo), str):
                    alt[campo] = [alt[campo]] if alt[campo].strip() else []
    # reparo de forma: chaves extras inventadas pelo modelo (ex.: "fontes" dentro de uma alternativa) são descartadas
    permitidas = {"alternativas": ("descricao", "pros", "contras", "riscos"),
                  "riscos": ("descricao", "probabilidade", "impacto", "mitigacao"),
                  "divergencias": ("tema", "posicoes")}
    for campo, chaves in permitidas.items():
        d[campo] = [{k: v for k, v in item.items() if k in chaves} for item in d[campo] if isinstance(item, dict)]
    obs = ["relator_sem_json_valido"] if r is None else (["relator_nova_tentativa"] if tentativas > 1 else [])
    v = verificar(d["resposta"], fontes, pergunta)
    if not v.aprovada:  # remove frases sem suporte da síntese
        restantes = [f for f in re.split(r"(?<=[.!?])\s+", d["resposta"]) if f.strip() and f.strip() not in
                     v.frases_reprovadas]
        d["resposta"] = " ".join(restantes)
        d["confianca"] = min(d["confianca"], 0.6)
        obs.append("verificador_frases_removidas_no_relator")
    origem = completar(d, trechos, pareceres, precedentes, frases_removidas=not v.aprovada)
    obs += [f"rf20_{campo}_{o}" for campo, o in origem.items() if o != "modelo" and campo != "aviso"]
    erros = _validar_schema({k: d[k] for k in _schema("relator.v2.json")["properties"] if k in d},
                            _schema("relator.v2.json"))
    return RespostaF2(d["resposta"] + f"\n\n{AVISO_DECISAO}", d, fontes, pareceres, not erros and r is not None, v,
                      r.tokens_entrada if r else 0, r.tokens_saida if r else 0, r.latencia_ms if r else 0,
                      obs + ([f"relator_schema: {erros[0]}"] if erros else []))
