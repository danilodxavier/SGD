"""Verificador de fontes (SAD-072, RF-17) — TDD com os erros reais observados na Fase 5/6."""
from app.application.agentes.verificador import verificar
from app.application.recuperacao.regras import TrechoRecuperado


def tr(id_, texto, titulo="PRIMEIRO TERMO ADITIVO AO CONTRATO Nº 044/2023", revogado=False, situacao=None):
    return TrechoRecuperado(id_, 1, texto, "x.docx", "sintetico/x.docx", titulo, "cláusula segunda", 1, "aditivo",
                            "sintetico", "2025-08-15", revogado, situacao)


ADITIVO = tr(1, "2.1. O término da vigência passa de 31/08/2025 para 31/08/2026.")


def test_resposta_suportada_e_aprovada():
    v = verificar("O contrato vigora até 31/08/2026 [T1].", [ADITIVO], "Até quando vigora o Contrato nº 044/2023?")
    assert v.aprovada and not v.problemas


def test_data_inventada_e_reprovada_com_a_frase():
    # caso real T124: "termina em 28/08/2026" quando o aditivo diz 31/08/2026
    v = verificar("O Contrato nº 044/2023 foi prorrogado. Ele termina em 28/08/2026 [T1].", [ADITIVO],
                  "Até quando vigora o Contrato nº 044/2023?")
    assert not v.aprovada
    assert v.problemas[0].tipo == "numero_sem_suporte" and "28/08/2026" in v.problemas[0].detalhe
    assert v.frases_reprovadas == ["Ele termina em 28/08/2026 [T1]."]


def test_afirma_vigencia_de_norma_revogada():
    # caso real V049: "O Decreto nº 7.892/2013 continua vigente" com nota "Revogado pelo Decreto nº 11.462"
    decreto = tr(2, "DECRETO Nº 7.892, DE 23 DE JANEIRO DE 2013\n(Revogado pelo Decreto nº 11.462, de 2023)",
                 titulo="DECRETO Nº 7.892, DE 23 DE JANEIRO DE 2013", situacao="revogada")
    v = verificar("O Decreto nº 7.892/2013 continua vigente [T2].", [decreto],
                  "O Decreto nº 7.892/2013 continua vigente?")
    assert not v.aprovada and v.problemas[0].tipo == "vigencia_contraria_a_fonte"


def test_frase_que_afirma_e_nega_vigencia():
    # caso real V038: "ainda está vigente, pois foi revogado pelo Decreto ..."
    decreto = tr(3, "Fica revogado o Decreto nº 1.410, de 18 de abril de 2023.", titulo="DECRETO Nº 2.087/2025")
    v = verificar("O Decreto Nº 1.410/2023 ainda está vigente, pois foi revogado pelo Decreto Nº 2.087/2025 [T3].",
                  [decreto], "O Decreto nº 1.410/2023 ainda está vigente?")
    assert not v.aprovada and any(p.tipo == "afirmacao_contraditoria" for p in v.problemas)


def test_negacao_de_vigencia_nao_e_problema():
    decreto = tr(4, "Fica revogado o Decreto nº 1.410, de 18 de abril de 2023.", titulo="DECRETO Nº 2.087/2025")
    v = verificar("O Decreto nº 1.410/2023 não está mais vigente: foi revogado pelo Decreto nº 2.087/2025 [T4].",
                  [decreto], "O Decreto nº 1.410/2023 ainda está vigente?")
    assert v.aprovada


def test_mensagem_de_ausencia_e_aprovada_sem_citacao():
    v = verificar("Não localizei essa informação nos documentos disponibilizados.", [], "x")
    assert v.aprovada
