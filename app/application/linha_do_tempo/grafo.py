"""Grafo documental (SAD-060/061): classificação de relações por regras explicáveis, agrupamento e linha do tempo.

Convenção (igual ao gabarito): a relação liga ORIGEM → DESTINO, e o DESTINO contém a evidência e age sobre a origem
(o aditivo adita o contrato; a portaria posterior revoga a anterior; a ordem de reinício retoma a suspensão).

Regra principal: para cada referência a outro documento dentro de um trecho, vale o marcador mais próximo ANTES da
referência no mesmo trecho ("Fica revogado o Decreto nº…", "fica rescindido … o Contrato nº…"); "passa a vigorar"
logo DEPOIS da referência indica alteração. Regras de tipo documental complementam (aditivo, apostilamento).
"""
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.application.linha_do_tempo.referencias import chave_documento, encontrar_referencias

NORMATIVOS = {"constituicao", "lei", "lei_complementar", "decreto_lei", "decreto", "portaria", "portaria_designacao",
              "instrucao_normativa", "orientacao"}
INTERRUPCOES = {"ordem_suspensao", "termo_paralisacao", "denuncia_convenio"}
EXTINCOES = {"termo_rescisao"}
PRIORIDADE = ["contradicao", "revogacao", "substituicao", "ruptura", "retomada", "aditivo", "alteracao",
              "regulamenta", "fundamenta", "continuacao"]
MARCADORES = [  # (tipo, padrão sobre texto sem acentos e em minúsculas) — formas ativas
    ("revogacao", r"\brevoga(?:m)?(?:-se)?\b|\bfica(?:m)? revogad[oa]s?\b"),
    ("substituicao", r"\bsubstitu(?:i|em)\b|\bem substituicao\b"),
    ("retomada", r"\bretomad[oa]s?\b|\breinicio\b|\bretomar\b"),
    ("ruptura", r"\bsuspens[ao]\b|\bsuspend\w*|\brescind\w*|\brescisao\b|\bparalisad\w*|\bdenunciad\w*|\banulad\w*"),
    ("alteracao", r"\baltera\b|\balteram\b|\bapostilad\w*|\bnova redacao\b|\breajuste\b"),
    ("regulamenta", r"\bregulament(?:a|am)\b"),
    ("fundamenta", r"\bobservar(?:a|ao)\b|\bnos termos d|\bcom fundamento\b|\bfundamentos?\s*:"),
    ("continuacao", r"\bconsiderando\b|\bacolho\b|\borienta a aplicacao\b|\bnotificamos\b"),
]
APOS_REFERENCIA = re.compile(r"^[^.;]{0,120}?\bpassa(?:m)? a vigorar\b")
# Anotações de compilação oficiais: entre parênteses, na voz passiva, logo antes da referência
# ("(Revogado pela Lei nº X)", "(Redação dada pela Lei nº X)", "(Vide Lei nº X)") — o documento REFERIDO é quem age
ANOTACOES = [
    ("revogacao", re.compile(r"\(\s*revogad[oa]s?\s+(?:pel[oa]s?|por)\s*$")),
    ("alteracao", re.compile(r"\(\s*(?:redacao dada|incluid[oa]s?|acrescid[oa]s?|alterad[oa]s?|renumerad[oa]s?)"
                             r"\s+(?:pel[oa]s?|por)\s*$")),
    (None, re.compile(r"\(\s*(?:vide|regulamento|vigencia|veto)\b[^()]{0,25}$")),  # remissões: sem relação
]
RE_PROCESSO = re.compile(r"PROCESSO\s+(?:N[º°o]\.?\s*)?([A-Z][A-Z0-9-]*-\d{4}/\d+)", re.I)


@dataclass
class DocGrafo:
    id: int
    tipo: str
    numero: str | None
    data: date | None
    titulo: str | None
    corpus_origem: str
    trechos: list  # [(trecho_id, texto)]


@dataclass
class RelacaoGrafo:
    origem: int
    destino: int
    tipo: str
    confianca: float
    trecho_id: int
    justificativa: str
    parcial: bool = False


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


FIM_DE_FRASE = re.compile(r"(?:[.;:]\s+|\n)(?=\S)")
TAG_REVOGADO = re.compile(r"\[revogado\]")


def _marcador_antes(texto_norm, posicao):
    """Marcador mais próximo antes da referência, dentro da MESMA frase (a tag '[REVOGADO]' do extrator não conta)."""
    inicio_frase = 0
    for m in FIM_DE_FRASE.finditer(texto_norm, 0, posicao):
        if not re.search(r"\b(?:art|arts|n|inc|al|par)\.\s+$", texto_norm[max(0, m.start() - 5):m.end()]):
            inicio_frase = m.end()
    frase = TAG_REVOGADO.sub(lambda t: " " * len(t.group()), texto_norm[inicio_frase:posicao])
    melhor, pos_melhor = None, -1
    for tipo, padrao in MARCADORES:
        for m in re.finditer(padrao, frase):
            if m.start() > pos_melhor:
                melhor, pos_melhor = tipo, m.start()
    return melhor


def _classificar(destino, origem, texto, ref):
    if destino.tipo == "aditivo" and origem.tipo == "contrato":
        return "aditivo", 0.95, "termo aditivo do contrato"
    if origem.tipo in NORMATIVOS and destino.tipo not in NORMATIVOS:
        # contrato/aditivo/relatório não revoga nem altera lei: citar a norma é invocar sua base legal
        # (sem esta regra, "rescindido nos termos da Lei 14.133" virava ruptura e unia contratos às normas)
        return "fundamenta", 0.8, "documento não normativo cita ato normativo"
    norm = _sem_acento(texto)
    if APOS_REFERENCIA.search(norm[ref.fim:]):
        return "alteracao", 0.9, "'passa a vigorar' após a referência"
    marcador = _marcador_antes(norm, ref.inicio)
    if marcador:
        return marcador, 0.9, f"marcador '{marcador}' antes da referência"
    if destino.tipo == "apostilamento" and origem.tipo == "contrato":
        return "alteracao", 0.85, "apostilamento do contrato"
    if destino.tipo in NORMATIVOS and origem.tipo in NORMATIVOS:
        return "fundamenta", 0.7, "ato normativo que cita outro"
    return "continuacao", 0.75, "documento que se refere a outro anterior"


def _anotacao(texto_norm, posicao):
    """Tipo da nota de compilação imediatamente antes da referência; None = remissão sem relação;
    False = não é nota de compilação."""
    janela = texto_norm[max(0, posicao - 40):posicao]
    for tipo, padrao in ANOTACOES:
        if padrao.search(janela):
            return tipo
    return False


def _processos(d):
    return {m.group(1).upper() for _, t in d.trechos for m in RE_PROCESSO.finditer(t)}


def classificar_relacoes(documentos, contradicoes=()):
    por_chave = {}
    for d in documentos:
        chave = chave_documento(d.tipo, d.numero)
        if chave:
            por_chave.setdefault(chave, d)
    candidatas = defaultdict(list)  # (origem, destino) -> [RelacaoGrafo]
    for d in documentos:
        for indice, (tid, texto) in enumerate(d.trechos):
            norm = _sem_acento(texto)
            for ref in encontrar_referencias(texto):
                o = por_chave.get(ref.chave)
                if not o or o.id == d.id:
                    continue
                anotacao = _anotacao(norm, ref.inicio)
                if anotacao is not False:  # nota de compilação: inverte a direção (o referido age sobre este)
                    if anotacao:
                        cabecalho = indice == 0  # nota no cabeçalho do ato vale para o ato inteiro
                        candidatas[(d.id, o.id)].append(RelacaoGrafo(
                            d.id, o.id, anotacao, 0.9, tid, f"nota de compilação '{anotacao}' no ato afetado",
                            parcial=not cabecalho))
                    continue
                tipo, conf, motivo = _classificar(d, o, texto, ref)
                candidatas[(o.id, d.id)].append(RelacaoGrafo(o.id, d.id, tipo, conf, tid, motivo, ref.parcial))
    # rótulo com evidência explícita (marcador, tipo documental, nota) vence o rótulo atribuído por padrão;
    # revogação PARCIAL de um ato que o mesmo documento também altera é, no conjunto, uma alteração
    def ordem(r):
        prioridade = PRIORIDADE.index("alteracao") + 0.5 if r.tipo == "revogacao" and r.parcial else \
            PRIORIDADE.index(r.tipo)
        return r.confianca < 0.85, prioridade

    relacoes = {par: min(rs, key=ordem) for par, rs in candidatas.items()}

    # retomada aponta para a interrupção mais recente do mesmo contrato/convênio, não para o próprio instrumento
    por_id = {d.id: d for d in documentos}
    for (o, d), r in list(relacoes.items()):
        if r.tipo != "retomada":
            continue
        interrupcoes = [xd for (xo, xd), xr in relacoes.items() if xo == o and xr.tipo == "ruptura"
                        and por_id[xd].tipo in INTERRUPCOES and _antes(por_id[xd], por_id[d])]
        if interrupcoes:
            alvo = max(interrupcoes, key=lambda x: por_id[x].data or date.min)
            del relacoes[(o, d)]
            relacoes[(alvo, d)] = RelacaoGrafo(alvo, d, "retomada", r.confianca, r.trecho_id,
                                               "retomada da interrupção registrada anteriormente")

    for c in contradicoes:  # a contradição é a relação mais informativa para o par
        relacoes[(c.origem, c.destino)] = RelacaoGrafo(c.origem, c.destino, "contradicao", 0.95, c.trecho_destino,
                                                       f"{c.campo}: vigente {c.valor_vigente} × declarado "
                                                       f"{c.valor_declarado}")

    # documento sem referência explícita: continuação do documento anterior do mesmo processo administrativo
    com_entrada = {d for (_, d), r in relacoes.items() if r.tipo != "fundamenta"}  # base legal não liga processos
    por_processo = defaultdict(list)
    for d in documentos:
        for p in _processos(d):
            por_processo[p].append(d)
    for membros in por_processo.values():
        ordenados = sorted(membros, key=lambda x: (x.data or date.min, x.id))
        for anterior, atual in zip(ordenados, ordenados[1:], strict=False):
            if atual.id not in com_entrada and (anterior.id, atual.id) not in relacoes:
                relacoes[(anterior.id, atual.id)] = RelacaoGrafo(
                    anterior.id, atual.id, "continuacao", 0.6, atual.trechos[0][0] if atual.trechos else 0,
                    "mesmo processo administrativo, sem referência explícita (inferência)")
    return list(relacoes.values())


def _antes(a, b):
    return (a.data or date.min) <= (b.data or date.max)


@dataclass
class Grupo:
    chave: tuple
    documentos: list = field(default_factory=list)


def agrupar(documentos, relacoes):
    """Componentes conexos pelas relações (exceto 'fundamenta', que liga processos distintos à base legal)."""
    pai = {d.id: d.id for d in documentos}

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    # cada componente guarda os contratos que contém: um documento que cita dois contratos (portaria de fiscais,
    # relatório consolidado) não pode fundir processos distintos — no acervo real isso encadeava 15 contratos
    contratos_de = {}
    for d in documentos:
        if d.tipo == "contrato" and (chave := chave_documento(d.tipo, d.numero)):
            contratos_de[d.id] = {chave}
    tipo_de = {d.id: d.tipo for d in documentos}
    for r in relacoes:
        if r.tipo != "fundamenta" and r.origem in pai and r.destino in pai:
            a, b = raiz(r.origem), raiz(r.destino)
            ca, cb = contratos_de.get(a, set()), contratos_de.get(b, set())
            # contratos diferentes só se unem por SUBSTITUIÇÃO direta entre eles (novo contrato que substitui o
            # anterior); a simples menção a outro contrato, mesmo num documento-contrato, não funde processos
            direta = r.tipo == "substituicao" and tipo_de[r.origem] == tipo_de[r.destino] == "contrato"
            if a == b or (ca and cb and ca != cb and not direta):
                continue
            pai[a] = b
            if ca | cb:
                contratos_de[b] = ca | cb
    por_raiz = defaultdict(list)
    for d in documentos:
        por_raiz[raiz(d.id)].append(d)
    # componentes com a mesma chave (ex.: duas cópias da mesma lei, uma isolada) são o mesmo processo/tema
    por_chave = defaultdict(list)
    for membros in por_raiz.values():
        membros.sort(key=lambda d: (d.data or date.min, d.id))
        contratos = [d for d in membros if d.tipo == "contrato"]
        base = contratos[0] if contratos else membros[0]
        chave = chave_documento(base.tipo, base.numero) or ("tema", str(base.id))
        por_chave[("contrato", chave[1]) if contratos else ("tema", chave[0] + ":" + chave[1])] += membros
    grupos = [Grupo(chave, [d.id for d in sorted(membros, key=lambda d: (d.data or date.min, d.id))])
              for chave, membros in por_chave.items()]
    return sorted(grupos, key=lambda g: g.chave)


@dataclass
class Evento:
    documento: int
    data: date | None
    tipo_documental: str
    titulo: str | None


@dataclass
class Fase:
    nome: str
    inicio: date | None
    documentos: list = field(default_factory=list)


@dataclass
class LinhaDoTempo:
    grupo: tuple
    eventos: list
    relacoes: list
    fases: list
    inconsistencias: list


def linha_do_tempo(grupo, documentos, relacoes):
    por_id = {d.id: d for d in documentos}
    membros = sorted((por_id[i] for i in grupo.documentos), key=lambda d: (d.data or date.min, d.id))
    ids = set(grupo.documentos)
    rels = [r for r in relacoes if r.origem in ids and r.destino in ids]
    tipo_entrada = {}
    for r in rels:
        tipo_entrada.setdefault(r.destino, set()).add(r.tipo)
    fases, atual = [], Fase("Execução", membros[0].data if membros else None)
    for d in membros:
        entradas = tipo_entrada.get(d.id, set())
        nome = None
        if d.tipo in EXTINCOES or ("ruptura" in entradas and d.tipo not in INTERRUPCOES):
            nome = "Extinção"
        elif "ruptura" in entradas:
            nome = "Interrupção"
        elif "retomada" in entradas:
            nome = "Execução retomada"
        if nome and nome != atual.nome:
            fases.append(atual)
            atual = Fase(nome, d.data)
        atual.documentos.append(d.id)
    fases.append(atual)
    inconsistencias = [f"contradição entre documentos {r.origem} e {r.destino}: {r.justificativa}"
                       for r in rels if r.tipo == "contradicao"]
    inconsistencias += [f"documento {d.id} sem data" for d in membros if d.data is None]
    eventos = [Evento(d.id, d.data, d.tipo, d.titulo) for d in membros]
    return LinhaDoTempo(grupo.chave, eventos, rels, [f for f in fases if f.documentos], inconsistencias)
