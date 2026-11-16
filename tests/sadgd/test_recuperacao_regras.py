"""Regras puras da recuperação híbrida (SAD-050) — TDD: consulta FTS, RRF e filtro de vigência."""
from app.application.portas import ResultadoBusca
from app.application.recuperacao.regras import (
    TrechoRecuperado,
    consulta_fts,
    filtrar_vigencia,
    fundir_rrf,
    termos_da_pergunta,
)


def test_termos_removem_palavras_vazias_e_preservam_numeros():
    termos = termos_da_pergunta("Qual é o valor global do Contrato nº 012/2023 e o CNPJ 41.258.763/0001-14?")
    assert "012/2023" in termos and "41.258.763/0001-14" in termos
    assert "valor" in termos and "global" in termos and "contrato" in termos
    assert not {"qual", "é", "o", "do", "nº", "e"} & set(termos)


def test_consulta_fts_usa_prefixo_e_aspas():
    expr = consulta_fts(["prorrogação", "012/2023", "vigência"])
    assert '"prorrogação"*' in expr and '"012/2023"' in expr and " OR " in expr
    assert consulta_fts([]) is None


def test_rrf_combina_listas_e_favorece_consenso():
    bm25 = [ResultadoBusca(1, 9.0, "bm25"), ResultadoBusca(2, 8.0, "bm25"), ResultadoBusca(3, 7.0, "bm25")]
    denso = [ResultadoBusca(3, 0.9, "denso"), ResultadoBusca(1, 0.8, "denso"), ResultadoBusca(4, 0.7, "denso")]
    fundido = fundir_rrf([bm25, denso], k=60)
    ids = [r.trecho_id for r in fundido]
    assert ids[:2] == [1, 3]  # aparecem bem colocados nas duas listas
    assert set(ids) == {1, 2, 3, 4}
    assert all(r.fonte == "rrf" for r in fundido)
    assert abs(fundido[0].pontuacao - (1 / 61 + 1 / 62)) < 1e-9


def trecho(id_, revogado=False, situacao="vigente"):
    return TrechoRecuperado(id_, 10, "texto", "doc.htm", "publico/doc.htm", "Lei X", "art. 1º", None, "lei",
                            "publico", None, revogado, situacao)


def test_filtro_de_vigencia_remove_revogados_e_guarda_historico():
    itens = [trecho(1), trecho(2, revogado=True), trecho(3, situacao="revogada"), trecho(4, situacao=None)]
    atuais, historico = filtrar_vigencia(itens)
    assert [t.id for t in atuais] == [1, 4]
    assert [t.id for t in historico] == [2, 3]


def test_rotulo_de_citacao():
    assert trecho(42).rotulo == "T42"
