"""Roteador (SAD-070, RF-15, ADR-004): decide a rota e os especialistas com o menor custo seguro.

Regras determinísticas primeiro (custo zero); o LLM pequeno só é consultado quando as regras não decidem
(`ambiguo=True`). Limites da matriz de acionamento (docs/agentes/README.md): F1 simples → nenhum especialista;
F1 complexa → até 2; F2 → gestor público + até 3. Nunca todos.
"""
import re
import unicodedata
from dataclasses import dataclass, field

DECISAO = re.compile(
    r"\b(devo|deveria|devemos|posso|podemos|pode prosseguir|e recomendavel|recomenda\w*|vale a pena|"
    r"qual (?:e )?a melhor|como devo|convem|melhor alternativa|e possivel .{0,40}\bou\b|"
    r"autorizar|aprovar|decidir)\b")
HISTORIA = re.compile(
    r"\b(ainda esta|esta vigente|vigente|continua vigente|em vigor|revog\w*|substitu\w*|alterad\w*|apos o|"
    r"historic\w*|o que mudou|ultimo|retomad\w*|suspens\w*|paralis\w*|interrup\w*|houve|atualmente|"
    r"quais .{0,30}(leis|hipoteses|sancoes)|reajuste)\b")
ANALISE = re.compile(r"^(e|sao) (legal|ilegal|licit\w*|permitid\w*|possivel|obrigatori\w*|nul\w*)\b|"
                     r"\b(cabe|cabem|admite-se|exige-se|e necessario)\b")
MATRIZ = {
    "fiscal_contrato": r"vigencia|prazo|aditiv|prorrog|penalidad|medica|entrega|fiscaliz|reajust|fatura|"
                       r"contratad|execucao|obra",
    "advogado": r"clausula|obrigac|direito|rescis|rescind|notifica|responsabilid|litigi|sanca",
    "procurador_estado": r"legal|ilegal|constitucion|competencia|nulidad|parecer juridico|risco juridico|"
                         r"\blei\b|decreto|norma",
    "controlador_geral": r"conformidad|irregular|\btce\b|\btcu\b|\bcgu\b|improbidad|auditori|controle|"
                         r"divergen|pagament",
    "analista_administrativo": r"instruc|documento|fluxo|tramit|prazo processual|checklist|designa|"
                               r"servidor|retom|turma",
    "analista_orcamentario_financeiro": r"orcament|dotac|empenh|\blrf\b|custo|impacto financeiro|reequilibri|"
                                        r"valor|pagar|pagament|fatura",
    "especialista_licitacoes": r"licita|pregao|dispensa|inexigib|\betp\b|termo de referencia|edital|"
                               r"\bata\b|contratar novamente|nova contratac|pesquisa de preco|sustentabil",
}
RE_CONTRATO = re.compile(r"contrato\s+n[º°o]\.?\s*([\d/]+)", re.I)


@dataclass
class DecisaoRota:
    rota: str  # F1_simples | F1_complexa | F2
    agentes: list = field(default_factory=list)
    consultas_busca: list = field(default_factory=list)
    filtros: dict = field(default_factory=dict)
    justificativa: str = ""
    metodo: str = "regras"
    ambiguo: bool = False


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def _pontuar(texto):
    return {agente: len(re.findall(padrao, texto)) for agente, padrao in MATRIZ.items()}


def rotear(pergunta: str) -> DecisaoRota:
    texto = _norm(pergunta)
    filtros = {}
    if m := RE_CONTRATO.search(pergunta):
        filtros["contrato"] = m.group(1).rstrip(".")
    pontos = _pontuar(texto)
    if DECISAO.search(texto):
        candidatos = sorted((a for a, p in pontos.items() if p > 0), key=lambda a: (-pontos[a], a))
        agentes = ["gestor_publico"] + candidatos[:3]
        return DecisaoRota("F2", agentes, [pergunta], filtros, "pedido de orientação para decidir")
    if HISTORIA.search(texto) or ANALISE.search(texto):
        candidatos = sorted((a for a, p in pontos.items() if p > 0), key=lambda a: (-pontos[a], a))[:2]
        motivo = ("análise de legalidade/cabimento" if ANALISE.search(texto)
                  else "pergunta sobre histórico, vigência ou relação entre documentos")
        return DecisaoRota("F1_complexa", candidatos, [pergunta], filtros, motivo)
    ambiguo = len(texto.split()) > 25 and not re.match(r"^(qual|quais|quando|quem|onde|o que|em que|a |o )", texto)
    return DecisaoRota("F1_simples", [], [pergunta], filtros, "fato pontual", ambiguo=ambiguo)
