"""Hierarquia normativa e vigência temporal (RF-14).

Constituição > Lei (ordinária/complementar) > Decreto > Instrução Normativa/Portaria > Orientação/Parecer.
Norma revogada não fundamenta decisão atual, mas permanece no histórico.
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum, StrEnum


class EspecieNormativa(Enum):
    CONSTITUICAO = ("constituicao", 1)
    LEI_COMPLEMENTAR = ("lei_complementar", 2)
    LEI = ("lei", 2)
    DECRETO = ("decreto", 3)
    INSTRUCAO_NORMATIVA = ("instrucao_normativa", 4)
    PORTARIA = ("portaria", 4)
    ORIENTACAO = ("orientacao", 5)
    PARECER = ("parecer", 5)

    def __init__(self, codigo, nivel):
        self.codigo = codigo
        self.nivel = nivel  # 1 = mais alto


class SituacaoVigencia(StrEnum):
    VIGENTE = "vigente"
    PARCIALMENTE_REVOGADA = "parcialmente_revogada"
    REVOGADA = "revogada"


@dataclass(frozen=True)
class Norma:
    documento_id: int
    especie: EspecieNormativa
    numero: str
    ano: int
    situacao: SituacaoVigencia = SituacaoVigencia.VIGENTE
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None

    def vigente_em(self, referencia: date) -> bool:
        if self.situacao is SituacaoVigencia.REVOGADA:
            return False
        if self.vigencia_inicio and referencia < self.vigencia_inicio:
            return False
        return not (self.vigencia_fim and referencia > self.vigencia_fim)


@dataclass(frozen=True)
class ResultadoPrevalencia:
    vencedora: Norma | None
    criterio: str  # hierarquico | cronologico | vigencia | indeterminado
    inferencia: bool


def prevalece(a: Norma, b: Norma, referencia: date | None = None) -> ResultadoPrevalencia:
    """Indica qual norma prevalece num conflito. Critério cronológico é sempre inferência documental."""
    referencia = referencia or date.today()
    va, vb = a.vigente_em(referencia), b.vigente_em(referencia)
    if va != vb:
        return ResultadoPrevalencia(a if va else b, "vigencia", False)
    if a.especie.nivel != b.especie.nivel:
        return ResultadoPrevalencia(a if a.especie.nivel < b.especie.nivel else b, "hierarquico", False)
    if a.ano != b.ano:
        return ResultadoPrevalencia(a if a.ano > b.ano else b, "cronologico", True)
    return ResultadoPrevalencia(None, "indeterminado", True)


def fundamentacao_atual(normas, referencia: date):
    """Separa normas utilizáveis como fundamento na data de referência das que ficam só no histórico."""
    atual, historico = [], []
    for n in normas:
        (atual if n.vigente_em(referencia) else historico).append(n)
    return atual, historico
