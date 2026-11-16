"""Métricas determinísticas de resposta (ADR-011) — TDD."""
from app.application.avaliacao.metricas_resposta import (
    classificacao_correta,
    contem_chaves,
    numeros_nao_suportados,
)


def test_chaves_ignoram_caixa_acentos_e_espacos():
    assert contem_chaves("O valor global é de R$ 1.200.000,00 [T11].", ["R$ 1.200.000,00"])
    assert contem_chaves("Vigência de 01/03/2023 a 29/02/2024.", ["01/03/2023", "29/02/2024"])
    assert not contem_chaves("Vigência de 01/03/2023.", ["01/03/2023", "29/02/2024"])
    assert contem_chaves("qualquer coisa", []) is None  # sem chave definida: não avaliado


def test_numeros_nao_suportados_detectam_alucinacao_numerica():
    citados = ["3.1. O valor global do contrato é de R$ 1.200.000,00, para todo o período."]
    assert numeros_nao_suportados("O valor é R$ 1.200.000,00 [T11].", citados, "Qual o valor?") == []
    assert numeros_nao_suportados("O valor é R$ 1.300.000,00 [T11].", citados, "Qual o valor?") == ["1.300.000,00"]
    # números da própria pergunta e rótulos de citação não contam
    assert numeros_nao_suportados("O Contrato nº 012/2023 vale R$ 1.200.000,00 [T11].", citados,
                                  "Qual o valor do Contrato nº 012/2023?") == []


def test_formatos_equivalentes_nao_sao_alucinacao_mas_datas_erradas_sim():
    # caso real T090: "Lei nº 8.666/1993" = "Lei nº 8.666, de 21 de junho de 1993"
    citados = ["II - a Lei nº 8.666, de 21 de junho de 1993, a Lei nº 10.520, de 17 de julho de 2002"]
    assert numeros_nao_suportados("Revogou a Lei nº 8.666/1993 e a Lei nº 10.520/2002 [T1].", citados) == []
    # datas por extenso são comparadas como datas
    assert numeros_nao_suportados("Vigora até 24 de agosto de 2025.", ["passa a encerrar-se em 24/08/2025"]) == []
    # caso real T109: a resposta inventa "20 de junho de 2025" (o texto tem 20/06/2024 e 24/08/2025) → alucinação
    citados = ["A vigência passa a encerrar-se em 24/08/2025.", "Capital, 20 de junho de 2024."]
    assert numeros_nao_suportados("Vige até 20 de junho de 2025 [T1].", citados) == ["20/06/2025"]


def test_classificacao():
    assert classificacao_correta("fato", "fato") and classificacao_correta("fato", "inferencia")
    assert classificacao_correta("conflito", "conflito") and not classificacao_correta("conflito", "fato")
    assert classificacao_correta("ausencia", "ausencia") and not classificacao_correta("ausencia", "fato")
    assert not classificacao_correta("fato", "ausencia")
