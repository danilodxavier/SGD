"""Vigência a partir do grafo (SAD-062, RF-14): revogação total ou substituição integral de um ato normativo
retira sua vigência; revogação parcial ("arts. 1º a 47-A da Lei…") não. A evidência é a relação com trecho."""

TIPOS_QUE_REVOGAM = {"revogacao", "substituicao"}


def revogacoes_por_relacao(relacoes) -> dict:
    """documento revogado -> relação que o revogou (a primeira encontrada)."""
    revogados = {}
    for r in relacoes:
        if r.tipo in TIPOS_QUE_REVOGAM and not r.parcial:
            revogados.setdefault(r.origem, r)
    return revogados
