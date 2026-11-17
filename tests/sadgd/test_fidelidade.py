"""Faithfulness com LLM-juiz (Fase 10): partes determinísticas (frases, corrupções, interpretação, κ)."""
from app.application.avaliacao.fidelidade import corromper, frases, interpretar, kappa
from app.domain.politicas import AVISO_DECISAO

RESPOSTA = ("O valor global do Contrato nº 044/2023 é R$ 2.340.000,00 [T11]. O contrato é vigente até 31/08/2026 "
            f"[T12].\n\n{AVISO_DECISAO}")


def test_frases_ignoram_aviso_e_citacoes_soltas():
    assert frases(RESPOSTA) == ["O valor global do Contrato nº 044/2023 é R$ 2.340.000,00 [T11].",
                                "O contrato é vigente até 31/08/2026 [T12]."]
    assert frases("Não localizei essa informação nos documentos disponibilizados.") == []


def test_corrupcoes_alteram_o_conteudo_e_nunca_os_rotulos_de_citacao():
    num = corromper(RESPOSTA, "numero", 1)
    assert num != RESPOSTA and "[T11]" in num and "[T12]" in num
    assert " não é " in corromper(RESPOSTA, "inversao", 1)
    inv = corromper(RESPOSTA, "invencao", 1)
    assert len(frases(inv)) == 3 and AVISO_DECISAO not in inv
    assert corromper("Sem números nem verbos-alvo", "numero", 1) is None


def test_interpretacao_conservadora():
    assert interpretar({"frases": [{"n": 1, "sustentada": True}, {"n": 2, "sustentada": "não"}]}, 3) == [
        True, False, False]  # a frase 3 não julgada conta como não sustentada
    assert interpretar(None, 2) == [False, False]


def test_kappa():
    assert kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert kappa([1, 0, 1, 0], [0, 1, 0, 1]) == -1.0
    assert kappa([], []) is None


def test_abreviacoes_juridicas_nao_quebram_a_frase():
    r = "A Constituição Federal, no art. 37, exige concurso. O art. 106, inciso I, da Lei nº 14.133 trata disso. [T9]"
    assert frases(r) == ["A Constituição Federal, no art. 37, exige concurso.",
                         "O art. 106, inciso I, da Lei nº 14.133 trata disso. [T9]"]
