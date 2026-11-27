"""Confiança calculada pelo sistema (2026-11-25), com os mesmos critérios em todos os caminhos de resposta.

Antes, a confiança misturava três coisas não comparáveis: a autoavaliação do LLM (que o modelo local às vezes omite:
resposta correta e citada exibida com 0%), valores fixos da ficha do contrato (90%) e tetos das recusas (30% pelo LLM,
70% pela ficha). Agora ela mede o quanto a resposta AFIRMATIVA está sustentada por evidência verificável:

    confiança = base (classificação × caminho) − descontos por sinais registrados na auditoria

e cada fator vai para `criterio`, exibido ao usuário e gravado na auditoria. A autoavaliação do LLM não entra no
cálculo: fica só na auditoria (`confianca_modelo`).

Ausência e conflito não recebem percentual: não afirmam um fato. A recusa mostra o alcance da busca (trechos
examinados) e o conflito mostra as fontes divergentes para conferência.
"""
from dataclasses import dataclass

SEM_PERCENTUAL = frozenset({"ausencia", "conflito"})
MINIMO, MAXIMO = 0.30, 0.95

# base por caminho e classificação: a ficha é extração pré-processada e conferida (determinística no momento da
# pergunta); o LLM lê os trechos na hora — mesmo aprovado pelo verificador, fica um degrau abaixo
BASE = {
    ("ficha", "fato"): 0.90, ("ficha", "inferencia"): 0.75, ("ficha", "candidatos"): 0.50,
    ("llm", "fato"): 0.85, ("llm", "inferencia"): 0.70, ("llm", "candidatos"): 0.50,
}
ROTULO_BASE = {
    ("ficha", "fato"): "fato extraído da ficha do contrato, com citação",
    ("ficha", "inferencia"): "conclusão calculada a partir da ficha do contrato",
    ("ficha", "candidatos"): "documentos indicados para conferência",
    ("llm", "fato"): "fato lido nos trechos pelo modelo, com citação literal",
    ("llm", "inferencia"): "inferência do modelo a partir dos trechos citados",
    ("llm", "candidatos"): "documentos indicados para conferência",
}
# sinais (códigos das observações registradas na auditoria) → (desconto, descrição)
DESCONTOS = {
    "verificador_detalhes_removidos": (0.10, "o verificador removeu detalhes sem suporte nos trechos"),
    "verificador_nova_tentativa": (0.15, "a 1ª redação foi reprovada pelo verificador e reescrita"),
    "verificador_frases_removidas": (0.15, "o verificador removeu frases sem suporte"),
    "segunda_leitura_evidencias": (0.10, "a resposta só veio na 2ª leitura dos trechos (a 1ª recusou)"),
    "evidencias_contradizem_recusa": (0.05, "foi necessária uma 3ª leitura"),
    "citacoes_invalidas_descartadas": (0.05, "citações a trechos inexistentes foram descartadas"),
    "citacao_reparada": (0.05, "o sistema acrescentou a citação do trecho que contém um número da resposta"),
    "sem_verificador": (0.20, "resposta não conferida pelo verificador de fontes"),
    # rodada 18 (gabarito real): o LLM lendo só trechos acertou 48% com confiança ≥ 80%; ancorado na ficha conferida,
    # 95–97% — a faixa ≥ 80% fica para as respostas ancoradas
    "leitura_sem_ficha": (0.15, "leitura livre dos trechos, sem a ficha conferida do contrato como âncora"),
    "fonte_unica": (0.05, "uma única fonte citada"),
    "sem_fontes": (0.30, "nenhuma fonte citada"),
    "classificacao_automatica": (0.10, "relação baseada na classificação automática dos documentos"),
    "varios_contratos": (0.05, "mais de um contrato corresponde ao nome citado"),
    "pendencias_por_regra": (0.15, "pontos de atenção identificados por regras sobre as datas da ficha"),
}


@dataclass(frozen=True)
class Confianca:
    valor: float | None  # None: ausência ou conflito (não há fato afirmado)
    criterio: tuple[str, ...]


def _pct(v: float) -> str:
    return f"{round(v * 100)}%"


def calcular(classificacao: str, origem: str, n_fontes: int, sinais=(), trechos_examinados: int = 0) -> Confianca:
    """origem: "ficha" | "llm"; sinais: observações da resposta (as desconhecidas são ignoradas)."""
    if classificacao in SEM_PERCENTUAL:
        if classificacao == "conflito":
            return Confianca(None, ("Os documentos divergem sobre o fato perguntado: o sistema apresenta as fontes "
                                    "e não escolhe um valor — conferência documental necessária.",))
        alcance = (f"{trechos_examinados} trecho(s) mais relevantes do acervo examinados" if trechos_examinados
                   else "conferido no inventário das fichas de contrato")
        return Confianca(None, (f"Sem evidência nos documentos ({alcance}).",))
    chave = (origem, classificacao if (origem, classificacao) in BASE else "inferencia")
    valor = BASE[chave]
    criterio = [f"Base: {ROTULO_BASE[chave]} — {_pct(valor)}"]
    sinais = list(dict.fromkeys(sinais))
    if classificacao != "candidatos":  # candidatos: lista para conferência, não um fato sustentado por fontes
        if n_fontes == 0:
            sinais.append("sem_fontes")
        elif n_fontes == 1:
            sinais.append("fonte_unica")
    for s in sinais:
        if s in DESCONTOS:
            desconto, descricao = DESCONTOS[s]
            valor -= desconto
            criterio.append(f"−{_pct(desconto)}: {descricao}")
    if origem == "llm" and not any(s.startswith("verificador_") or s == "sem_verificador" for s in sinais):
        criterio.append("Verificador de fontes: aprovou todas as afirmações")
    valor = round(min(MAXIMO, max(MINIMO, valor)), 2)
    return Confianca(valor, tuple(criterio))


# ---------------------------------------------------------------------------------------------------- F2 (decisão)
BASE_F2_VARIOS, BASE_F2_UM = 0.80, 0.75
TETO_SEM_BASE_LEGAL, TETO_SEM_PARECER, TETO_FRASES_REMOVIDAS, TETO_RELATOR_FALHOU = 0.5, 0.4, 0.6, 0.0


def calcular_f2(*, pareceres_validos: int, divergencias: int, base_legal_vigente: bool, precedentes: int,
                frases_removidas: bool, relator_nova_tentativa: bool = False,
                relator_falhou: bool = False) -> Confianca:
    """Recomendação (F2): sustentação pelos pareceres verificados, base legal vigente e precedentes; tetos quando
    falta evidência essencial."""
    valor = BASE_F2_VARIOS if pareceres_validos >= 2 else BASE_F2_UM
    criterio = [f"Base: {pareceres_validos} parecer(es) válido(s) de especialistas — {_pct(valor)}"]
    for condicao, desconto, descricao in (
            (divergencias > 0, 0.10, "há divergências entre os especialistas"),
            (precedentes == 0, 0.05, "sem precedente da gestão na memória de decisões"),
            (relator_nova_tentativa, 0.05, "a síntese precisou de nova tentativa")):
        if condicao:
            valor -= desconto
            criterio.append(f"−{_pct(desconto)}: {descricao}")
    for condicao, teto, descricao in (
            (not base_legal_vigente, TETO_SEM_BASE_LEGAL, "sem base legal vigente nos trechos"),
            (pareceres_validos == 0, TETO_SEM_PARECER, "nenhum parecer válido"),
            (frases_removidas, TETO_FRASES_REMOVIDAS, "o verificador removeu frases da síntese"),
            (relator_falhou, TETO_RELATOR_FALHOU, "a síntese estruturada falhou")):
        if condicao and valor > teto:
            valor = teto
            criterio.append(f"Limitada a {_pct(teto)}: {descricao}")
    return Confianca(round(min(MAXIMO, max(0.0, valor)), 2), tuple(criterio))


def calcular_parecer(*, valido: bool, afirmacoes: int, citacoes_distintas: int, afirmacoes_removidas: int,
                     tentativas: int) -> Confianca:
    """Parecer de um especialista: afirmações que sobreviveram à verificação determinística."""
    if not valido:
        return Confianca(None, ("Parecer inválido: ignorado pelo relator.",))
    if afirmacoes == 0:
        return Confianca(0.40, ("Base: parecer sem afirmação sustentada por trecho — 40%",))
    valor, criterio = 0.75, [f"Base: {afirmacoes} afirmação(ões) verificada(s) com citação — 75%"]
    for condicao, desconto, descricao in (
            (citacoes_distintas == 1, 0.05, "uma única fonte citada"),
            (afirmacoes_removidas > 0, 0.10, f"{afirmacoes_removidas} afirmação(ões) sem suporte removida(s)"),
            (tentativas > 1, 0.05, "resposta refeita (JSON cortado na 1ª tentativa)")):
        if condicao:
            valor -= desconto
            criterio.append(f"−{_pct(desconto)}: {descricao}")
    return Confianca(round(max(MINIMO, valor), 2), tuple(criterio))


def aplicar(resposta, origem: str, trechos_examinados: int = 0, sinais_extras=()):
    """Preenche confianca, criterio_confianca e trechos_examinados de uma RespostaF1/RespostaFicha (in place)."""
    c = calcular(resposta.classificacao, origem, len(resposta.fontes), [*resposta.observacoes, *sinais_extras],
                 trechos_examinados)
    resposta.confianca, resposta.criterio_confianca = c.valor, list(c.criterio)
    resposta.trechos_examinados = trechos_examinados
    return resposta
