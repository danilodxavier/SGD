"""Relações entre documentos do grafo documental (RF-11 a RF-13)."""
from dataclasses import dataclass
from enum import Enum


class TipoRelacao(Enum):
    CONTINUACAO = ("continuacao", True)
    ADITIVO = ("aditivo", True)
    ALTERACAO = ("alteracao", True)
    REVOGACAO = ("revogacao", True)
    SUBSTITUICAO = ("substituicao", True)
    RUPTURA = ("ruptura", True)
    CONTRADICAO = ("contradicao", True)
    RETOMADA = ("retomada", True)
    # auxiliares: registradas no grafo, fora das métricas de classificação (RF-12)
    REGULAMENTA = ("regulamenta", False)
    FUNDAMENTA = ("fundamenta", False)

    def __init__(self, codigo, avaliada):
        self.codigo = codigo
        self.avaliada = avaliada

    @classmethod
    def de_codigo(cls, codigo: str) -> "TipoRelacao":
        for tipo in cls:
            if tipo.codigo == codigo:
                return tipo
        raise ValueError(f"Tipo de relação desconhecido: {codigo}")


@dataclass(frozen=True)
class Relacao:
    origem_id: int
    destino_id: int
    tipo: TipoRelacao
    confianca: float
    evidencia_trecho_id: int | None
    metodo: str = "regra"  # regra | llm | manual

    def __post_init__(self):
        if self.origem_id == self.destino_id:
            raise ValueError("Uma relação liga documentos distintos.")
        if not 0.0 <= self.confianca <= 1.0:
            raise ValueError("Confiança deve estar entre 0 e 1.")
        if self.evidencia_trecho_id is None:
            raise ValueError("Toda relação precisa de trecho de evidência (nunca relação sem fonte).")


TIPOS_DE_SUBSTITUICAO = {TipoRelacao.REVOGACAO, TipoRelacao.SUBSTITUICAO}


def ciclos_de_substituicao(relacoes):
    """Ciclos de revogação/substituição (A revoga B que revoga A) são inconsistências para revisão humana."""
    grafo = {}
    for r in relacoes:
        if r.tipo in TIPOS_DE_SUBSTITUICAO:
            grafo.setdefault(r.origem_id, set()).add(r.destino_id)

    ciclos, vistos = [], set()

    def visitar(no, caminho, na_pilha):
        for prox in sorted(grafo.get(no, ())):
            if prox in na_pilha:
                ciclo = caminho[caminho.index(prox):]
                chave = frozenset(ciclo)
                if chave not in vistos:
                    vistos.add(chave)
                    ciclos.append(ciclo)
            else:
                visitar(prox, caminho + [prox], na_pilha | {prox})

    for inicio in sorted(grafo):
        visitar(inicio, [inicio], {inicio})
    return ciclos
