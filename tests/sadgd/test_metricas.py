"""Métricas de avaliação (ADR-011) — TDD com valores calculados à mão."""
import math

import pytest

from app.application.avaliacao.metricas import (
    Fonte,
    TrechoAvaliado,
    avaliar_recuperacao,
    julgar,
    ndcg_em_k,
    normalizar,
    percentil,
    reciprocal_rank,
)

LEI = "publico/federal/lei/lei14133_2021.htm"


def tr(arquivo, dispositivo=None, texto="", subs=()):
    return TrechoAvaliado(arquivo, dispositivo, texto, list(subs))


def test_normalizacao_ignora_acentos_caixa_e_espacos():
    assert normalizar("  É  dispensável\na LICITAÇÃO ") == "e dispensavel a licitacao"


def test_julgamento_graduado():
    fonte = Fonte(LEI, "art. 75", "É dispensável a licitação")
    assert julgar(tr(LEI, "art. 75", "Art. 75. É dispensável a licitação:"), [fonte]) == (2, 0)
    assert julgar(tr(LEI, "art. 75, III a VIII", "III - para ..."), [fonte]) == (2, 0)  # pedaço do mesmo artigo
    assert julgar(tr(LEI, "art. 74", "É inexigível a licitação"), [fonte]) == (1, None)  # mesmo documento
    assert julgar(tr("outro.htm", "art. 75", "É dispensável a licitação"), [fonte]) == (0, None)
    # sem dispositivo esperado, vale a evidência literal
    so_evidencia = Fonte("sintetico/x.docx", None, "término em 28/02/2025")
    assert julgar(tr("sintetico/x.docx", None, "... passando o término em 28/02/2025."), [so_evidencia]) == (2, 0)


def test_artigo_75_nao_casa_com_artigo_7():
    assert julgar(tr(LEI, "art. 7º", "x"), [Fonte(LEI, "art. 75", None)])[0] == 1
    assert julgar(tr(LEI, "art. 75-A", "x"), [Fonte(LEI, "art. 75", None)])[0] == 1


def test_reciprocal_rank_e_ndcg():
    assert reciprocal_rank([0, 1, 2, 2]) == pytest.approx(1 / 3)
    assert reciprocal_rank([0, 0]) == 0.0
    # graus [2, 0, 1]; ideal com 1 fonte: [2]
    dcg = (2 ** 2 - 1) / math.log2(2) + 0 + (2 ** 1 - 1) / math.log2(4)
    idcg = (2 ** 2 - 1) / math.log2(2)
    assert ndcg_em_k([2, 0, 1], k=3, n_fontes=1) == pytest.approx(min(1.0, dcg / idcg))


def test_avaliar_recuperacao_conta_fontes_distintas():
    fontes = [Fonte("a.docx", "cláusula segunda", None), Fonte("b.pdf", None, "rescindido")]
    recuperados = [tr("a.docx", "cláusula primeira"), tr("a.docx", "cláusula segunda"), tr("c.txt"),
                   tr("b.pdf", None, "Fica rescindido o contrato")]
    m = avaliar_recuperacao(recuperados, fontes, ks=(1, 3, 5))
    assert m["recall@1"] == 0.0 and m["recall@3"] == 0.5 and m["recall@5"] == 1.0
    assert m["precision@3"] == pytest.approx(1 / 3)
    assert m["mrr"] == pytest.approx(1 / 2)
    assert m["recall_documento@1"] == 0.5  # a.docx já aparece em 1º lugar


def test_percentil_nearest_rank():
    assert percentil([10, 20, 30, 40], 50) == 20
    assert percentil([10, 20, 30, 40], 95) == 40
    assert percentil([], 50) is None
