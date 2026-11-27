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
from app.application.portas import RespostaLLM
from app.application.respostas.f1 import montar_contexto, partes_prompt
from app.domain import confianca as conf
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
                 "máximo 3 afirmações, 2 fundamentos, 2 riscos, 2 alternativas e 2 lacunas, cada texto com uma frase "
                 "curta; \"raciocinio\" com até 15 palavras.")
# Teto de tokens do parecer: com 900, o JSON completo (≈ 850 tokens no acervo real) era cortado e a 2ª tentativa
# custava outra geração inteira (≈ 80 s). O pedido mais enxuto reduz a saída; o teto maior evita a repetição.
MIN_TOKENS_PARECER = 1200
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
    d["confianca"] = 0.0  # calculada pelo sistema no Parecer (a declarada pelo modelo vai para confianca_modelo)
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
    confianca_modelo: float | None = None  # autoavaliação do LLM (auditoria); dados["confianca"] é do sistema
    criterio_confianca: list = field(default_factory=list)

    def __post_init__(self):
        """Confiança do parecer calculada pelo sistema a partir das afirmações que sobreviveram à verificação."""
        afirmacoes = self.dados.get("afirmacoes") or []
        c = conf.calcular_parecer(valido=self.valido_reparado, afirmacoes=len(afirmacoes),
                                  citacoes_distintas=len({x for a in afirmacoes for x in a.get("citacoes", [])}),
                                  afirmacoes_removidas=self.afirmacoes_removidas, tentativas=self.tentativas)
        self.dados["confianca"] = c.valor if c.valor is not None else 0.0  # o schema exige número
        self.criterio_confianca = list(c.criterio)


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


# Orçamento do contexto comum da F2 (ficha + linha do tempo + trechos), em caracteres. O modelo local tem
# num_ctx 8192 e o texto real rende ≈ 2,3 caracteres/token: com ≈ 17 mil caracteres (7.500 tokens), prompt + resposta
# passavam do limite, o JSON do especialista era cortado (2ª tentativa) e o deslocamento do contexto anulava o cache
# de prefixo do relator (decisão real: 334 s). 8.500 caracteres + regras + papel + resposta cabem com folga.
MAX_CHARS_CONTEXTO_F2 = 8500
MAX_CHARS_EXTRA_F2 = 3000  # ficha + linha do tempo + precedentes (o restante do orçamento fica para os trechos)
MIN_TRECHOS_F2 = 4
MAX_CHARS_PARECERES = 3500  # pareceres compactados enviados ao relator (vários especialistas)


def cortar_linhas(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto
    corte = texto.rfind("\n", 0, limite)
    return texto[:corte if corte > 0 else limite].rstrip() + "\n[…]"


def ajustar_contexto(pergunta, trechos, contexto_extra="", contexto_max_chars=0,
                     max_chars=MAX_CHARS_CONTEXTO_F2) -> tuple[list, str]:
    """Mantém o contexto comum da F2 dentro do orçamento: os trechos entram na ordem recebida (origem da ficha,
    depois os mais relevantes da busca) até o limite, com um mínimo de MIN_TRECHOS_F2. O extra já chega limitado
    (a linha do tempo é cortada antes, preservando ficha e precedentes)."""
    extra = contexto_extra or ""
    usados, total = [], len(extra)
    for t in trechos:
        tamanho = len(montar_contexto([t], pergunta, contexto_max_chars)) + 2
        if len(usados) >= MIN_TRECHOS_F2 and total + tamanho > max_chars:
            break
        usados.append(t)
        total += tamanho
    return usados, extra


def contexto_compartilhado(pergunta, trechos, contexto_extra="", contexto_max_chars=0) -> list:
    """Início IDÊNTICO das mensagens de todos os especialistas e do relator (regras comuns + pergunta + ficha/linha
    do tempo + trechos): o Ollama lê esse bloco uma vez e as chamadas seguintes reaproveitam o cache de prefixo. As
    instruções de cada papel vêm depois. Medição (decisão real): o relator relia ≈ 5.600 tokens (≈ 40 s)."""
    regras, _ = partes_prompt("relator", versao=2)
    return [
        {"role": "system", "content": regras + "\n\nVocê integra o colegiado do SAD-GD. O contexto vem primeiro; "
                                               "as instruções do seu papel e o formato da resposta vêm na última "
                                               "mensagem."},
        {"role": "user", "content": f"PERGUNTA: {pergunta}\n\n{contexto_extra}\n\n"
                                    f"TRECHOS:\n{montar_contexto(trechos, pergunta, contexto_max_chars)}"},
    ]


def executar_especialista(llm, agente, pergunta, trechos, contexto_extra="", contexto_max_chars=0) -> Parecer:
    meta = _meta(agente)
    _, papel = partes_prompt(agente)
    mensagens = contexto_compartilhado(pergunta, trechos, contexto_extra, contexto_max_chars) + [
        {"role": "user", "content": papel + "\n\n" + ORDEM_PARECER}]
    r, tentativas = _chat_json(llm, mensagens, max(int(meta.get("max_tokens", 800)), MIN_TOKENS_PARECER),
                               float(meta.get("temperatura", 0)))
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
                   + (antes - len(reparado["afirmacoes"])), r.tokens_entrada, r.tokens_saida, r.latencia_ms, tentativas,
                   confianca_modelo=_declarada(bruto))


def _declarada(dados):
    """Autoavaliação do modelo (só auditoria); None se omitida ou inválida."""
    try:
        return max(0.0, min(1.0, float(dados["confianca"])))
    except (KeyError, TypeError, ValueError):
        return None


# níveis de compactação dos pareceres para o relator: (parecer, recomendação, afirmações, texto da afirmação,
# riscos, alternativas, lacunas, mitigação)
NIVEIS_COMPACTACAO = [(600, 300, 6, 250, 4, 3, 3, True), (300, 200, 2, 200, 2, 2, 2, False),
                      (200, 150, 1, 150, 1, 1, 1, False)]


def _compactar(p: Parecer, nivel: int = 0):
    d = p.dados
    parecer, recom, n_afirm, t_afirm, n_risco, n_alt, n_lac, mitigacao = NIVEIS_COMPACTACAO[nivel]
    return {"agente": p.agente, "parecer": d["parecer"][:parecer], "recomendacao": d.get("recomendacao", "")[:recom],
            "afirmacoes": [{"texto": a["texto"][:t_afirm], "citacoes": a["citacoes"], "tipo": a["tipo"]}
                           for a in d["afirmacoes"][:n_afirm]],
            "riscos": [{k: v for k, v in r.items() if mitigacao or k != "mitigacao"} for r in d["riscos"][:n_risco]],
            "alternativas": d["alternativas"][:n_alt], "lacunas": d["lacunas"][:n_lac], "confianca": d["confianca"]}


def pareceres_para_relator(pareceres) -> list:
    """Pareceres válidos compactados no nível mais detalhado que cabe em MAX_CHARS_PARECERES (vários especialistas
    somados ao contexto comum passariam do num_ctx do modelo local)."""
    validos = [p for p in pareceres if p.dados.get("parecer")]
    for nivel in range(len(NIVEIS_COMPACTACAO)):
        compactos = [_compactar(p, nivel) for p in validos]
        if len(json.dumps(compactos, ensure_ascii=False)) <= MAX_CHARS_PARECERES:
            break
    return compactos


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


def parecer_unico(pareceres) -> Parecer | None:
    """O único parecer da decisão, se válido e com ao menos uma afirmação citada (senão, o relator é chamado)."""
    if len(pareceres) != 1:
        return None
    p = pareceres[0]
    return p if p.valido_reparado and p.dados.get("parecer") and p.dados.get("afirmacoes") else None


def sintese_de_parecer_unico(p: Parecer) -> dict:
    """Síntese montada sem LLM a partir de um único parecer (rodada 13): com um só especialista não há consensos
    nem divergências a consolidar, e a 2ª chamada ao modelo custava ≈ 35 s só para reorganizar o parecer. Usa só o
    que o especialista escreveu (afirmações já verificadas); o resto passa pelas mesmas salvaguardas do relator."""
    d = p.dados
    linhas = [d["parecer"].strip()] + [
        f"- {a['texto'].strip().rstrip('.')} [{', '.join(a['citacoes'])}]." for a in d["afirmacoes"]]
    fontes = list(dict.fromkeys([c for a in d["afirmacoes"] for c in a["citacoes"]]
                                + [f["trecho"] for f in d.get("fundamentacao_legal", [])]))
    return {"resposta": "\n".join(x for x in linhas if x), "recomendacao": d.get("recomendacao") or "",
            "consensos": [], "divergencias": [], "alternativas": list(d.get("alternativas", [])),
            "riscos": list(d.get("riscos", [])), "lacunas": list(d.get("lacunas", [])), "fontes": fontes,
            "classificacao": "inferencia", "confianca": p.confianca_modelo}


def relatar_f2(llm, pergunta, trechos, pareceres, contexto_extra="", precedentes=(),
               contexto_max_chars=0) -> RespostaF2:
    unico = parecer_unico(pareceres)
    if unico is not None:  # um só especialista: síntese sem 2ª chamada ao modelo
        sintese = sintese_de_parecer_unico(unico)
        r, tentativas = RespostaLLM(json.dumps(sintese, ensure_ascii=False), "parecer-unico", 0, 0, 0,
                                    json=sintese), 1
    else:
        validos = pareceres_para_relator(pareceres)
        _, papel = partes_prompt("relator", versao=2)
        mensagens = contexto_compartilhado(pergunta, trechos, contexto_extra, contexto_max_chars) + [
            {"role": "user", "content": papel + "\n\n" + ORDEM_RELATOR + "\n\nPARECERES VERIFICADOS:\n"
                                        + json.dumps(validos, ensure_ascii=False)}]
        r, tentativas = _chat_json(llm, mensagens, 1200, 0.1)
    d = r.json if r is not None and isinstance(r.json, dict) else {}
    if r is None:
        d = {"resposta": FALHA_RELATOR, "classificacao": "inferencia"}
    por_rotulo = {t.rotulo: t for t in trechos}
    citados = [c for c in dict.fromkeys(list(map(_rotulo, d.get("fontes") or [])) +
                                        [f"T{n}" for n in re.findall(r"\bT(\d+)\b", str(d.get("resposta", "")))])
               if c in por_rotulo]
    fontes = [por_rotulo[c] for c in citados]
    d["aviso"] = AVISO_DECISAO  # obrigatório: o sistema sugere, a gestão decide
    d["fontes"] = citados
    if d.get("classificacao") not in ("fato", "inferencia", "conflito", "ausencia"):
        d["classificacao"] = "inferencia"
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
    obs += ["relator_dispensado_parecer_unico"] if unico is not None else []
    v = verificar(d["resposta"], fontes, pergunta)
    if not v.aprovada:  # remove frases sem suporte da síntese
        restantes = [f for f in re.split(r"(?<=[.!?])\s+", d["resposta"]) if f.strip() and f.strip() not in
                     v.frases_reprovadas]
        d["resposta"] = " ".join(restantes)
        obs.append("verificador_frases_removidas_no_relator")
    # confiança calculada pelo sistema em `completar` (a declarada pelo modelo vai para confianca_modelo)
    origem = completar(d, trechos, pareceres, precedentes, frases_removidas=not v.aprovada,
                       relator_nova_tentativa=r is not None and tentativas > 1, relator_falhou=r is None)
    obs += [f"rf20_{campo}_{o}" for campo, o in origem.items() if o != "modelo" and campo not in ("aviso", "confianca")]
    erros = _validar_schema({k: d[k] for k in _schema("relator.v2.json")["properties"] if k in d},
                            _schema("relator.v2.json"))
    return RespostaF2(d["resposta"] + f"\n\n{AVISO_DECISAO}", d, fontes, pareceres, not erros and r is not None, v,
                      r.tokens_entrada if r else 0, r.tokens_saida if r else 0, r.latencia_ms if r else 0,
                      obs + ([f"relator_schema: {erros[0]}"] if erros else []))
