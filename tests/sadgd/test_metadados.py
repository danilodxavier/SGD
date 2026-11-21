"""Extração de metadados (SAD-044, RF-04) — TDD."""
from datetime import date

import pytest

from app.application.ingestao.metadados import extrair_metadados

AVISO = ("DOCUMENTO FICTÍCIO — corpus acadêmico SAD-GD.\n\nESTADO DE VALE VERDE\n"
         "SECRETARIA DE ESTADO DE GESTÃO PÚBLICA\n")


@pytest.mark.parametrize("titulo,tipo,numero", [
    ("CONTRATO Nº 012/2023", "contrato", "012/2023"),
    ("PRIMEIRO TERMO ADITIVO AO CONTRATO Nº 012/2023", "aditivo", "1º TA ao Contrato 012/2023"),
    ("SEGUNDO TERMO ADITIVO AO CONTRATO Nº 031/2023", "aditivo", "2º TA ao Contrato 031/2023"),
    ("APOSTILAMENTO Nº 001/2024 AO CONTRATO Nº 012/2023", "apostilamento", "001/2024"),
    ("NOTIFICAÇÃO Nº 023/2024 — CONTRATO Nº 012/2023", "notificacao", "023/2024"),
    ("TERMO DE RESCISÃO UNILATERAL DO CONTRATO Nº 012/2023", "termo_rescisao", None),
    ("ORDEM DE SUSPENSÃO Nº 004/2023 — CONTRATO Nº 031/2023", "ordem_suspensao", "004/2023"),
    ("ORDEM DE REINÍCIO Nº 005/2023 — CONTRATO Nº 031/2023", "ordem_reinicio", "005/2023"),
    ("RELATÓRIO DE FISCALIZAÇÃO Nº 007/2024 — CONTRATO Nº 044/2023", "relatorio_fiscalizacao", "007/2024"),
    ("PARECER JURÍDICO Nº 118/2024 — PROCESSO SEGEP-PRO-2024/00081", "parecer_juridico", "118/2024"),
    ("DECISÃO DA GESTÃO DG-004/2024 — PRORROGAÇÃO DO CONTRATO Nº 012/2023", "decisao_gestao", "DG-004/2024"),
    ("PORTARIA Nº 112/2024 — DESIGNAÇÃO DE FISCAL", "portaria_designacao", "112/2024"),
    ("PORTARIA Nº 010/2023, DE 14 DE FEVEREIRO DE 2023", "portaria", "010/2023"),
    ("INSTRUÇÃO NORMATIVA Nº 01/2022, DE 1º DE JUNHO DE 2022", "instrucao_normativa", "01/2022"),
    ("ORIENTAÇÃO NORMATIVA Nº 02/2024, DE 15 DE JANEIRO DE 2024", "orientacao", "02/2024"),
    ("TERMO DE DENÚNCIA DO CONVÊNIO Nº 007/2023", "denuncia_convenio", None),
    ("CONVÊNIO Nº 007/2023 — CAPACITAÇÃO DE SERVIDORES", "convenio", "007/2023"),
])
def test_tipo_e_numero_pelo_titulo(titulo, tipo, numero):
    m = extrair_metadados(AVISO + "\n" + titulo + "\n\nCorpo do documento.\n")
    assert (m.tipo_documental, m.numero) == (tipo, numero)
    assert m.orgao == "SEGEP/VV"


@pytest.mark.parametrize("titulo,tipo,numero,data", [
    ("LEI Nº 14.133, DE 1º DE ABRIL DE 2021", "lei", "14.133", date(2021, 4, 1)),
    ("LEI No 8.666, DE 21 DE JUNHO DE 1993.", "lei", "8.666", date(1993, 6, 21)),
    ("LEI COMPLEMENTAR Nº 101, DE 4 DE MAIO DE 2000", "lei_complementar", "101", date(2000, 5, 4)),
    ("DECRETO-LEI Nº 4.657, DE 4 DE SETEMBRO DE 1942.", "decreto_lei", "4.657", date(1942, 9, 4)),
    ("DECRETO Nº 11.462, DE 31 DE MARÇO DE 2023", "decreto", "11.462", date(2023, 3, 31)),
])
def test_atos_federais(titulo, tipo, numero, data):
    texto = f"Presidência da República\nCasa Civil\nSubchefia para Assuntos Jurídicos\n{titulo}\nMensagem de veto\n"
    m = extrair_metadados(texto)
    assert (m.tipo_documental, m.numero, m.data) == (tipo, numero, data)
    assert m.especie == tipo and m.nivel_hierarquico in (2, 3)
    assert m.orgao == "Presidência da República"


def test_constituicao():
    m = extrair_metadados("Presidência da República\nCONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1988\n")
    assert (m.tipo_documental, m.numero, m.nivel_hierarquico) == ("constituicao", "1988", 1)


def test_contrato_com_processo_vigencia_e_data():
    texto = (AVISO + "\nCONTRATO Nº 058/2023\n\nPROCESSO Nº SEGEP-PRO-2023/00058\n"
             "2.1. O prazo de vigência deste contrato é de 12 (doze) meses, com início em 01/07/2023 e término em "
             "30/06/2024, podendo ser prorrogado.\nCapital do Estado de Vale Verde, 29 de junho de 2023.\n")
    m = extrair_metadados(texto)
    assert m.processo == "SEGEP-PRO-2023/00058"
    assert (m.vigencia_inicio, m.vigencia_fim) == (date(2023, 7, 1), date(2024, 6, 30))
    assert m.data == date(2023, 7, 1)  # contrato: data de referência = início da vigência


def test_data_pelo_fecho_quando_titulo_nao_tem_data():
    m = extrair_metadados(AVISO + "\nNOTIFICAÇÃO Nº 023/2024 — CONTRATO Nº 012/2023\nTexto.\n"
                                  "Capital do Estado de Vale Verde, 2 de outubro de 2024.\n")
    assert m.data == date(2024, 10, 2)


def test_situacao_revogada_somente_com_evidencia_no_documento():
    vigente = extrair_metadados("LEI Nº 1.000, DE 2 DE JANEIRO DE 2000\nArt. 1º Texto.\n")
    assert vigente.situacao is None  # sem evidência, não presume
    revogada = extrair_metadados("LEI Nº 10.520, DE 17 DE JULHO DE 2002.\n"
                                 "(Revogada pela Lei nº 14.133, de 2021)\nArt. 1º Texto.\n")
    assert revogada.situacao == "revogada"
    assert "14.133" in revogada.evidencia_situacao


def test_nota_de_revogacao_de_artigo_nao_revoga_a_lei_inteira():
    # caso real: a Lei 12.462/2011 teve artigos revogados pela Lei 14.133/2021, mas não a lei inteira
    texto = ("LEI Nº 12.462, DE 4 DE AGOSTO DE 2011.\nInstitui o Regime Diferenciado de Contratações.\n"
             "Art. 1º [REVOGADO] É instituído o RDC. (Revogado pela Lei nº 14.133, de 2021)\nArt. 50. Texto.\n")
    m = extrair_metadados(texto)
    assert m.situacao is None


def test_documento_sem_titulo_reconhecivel():
    m = extrair_metadados("Anotações diversas sem identificação formal.\n")
    assert m.tipo_documental == "outro" and m.numero is None


# ------------------------------------------------- 2º nível: formatos do acervo real (A1, 2026-11-20)
# Cabeçalhos INVENTADOS no formato usual de documentos de execução contratual (nenhum dado real).
CABECALHO_REAL = "GOVERNO DO ESTADO\nSECRETARIA DE ESTADO\nCOORDENADORIA DE CONTRATOS\n"


@pytest.mark.parametrize("titulo,tipo,numero", [
    ("CONTRATO DE PRESTAÇÃO DE SERVIÇOS Nº 045/2022/SEXX", "contrato", "045/2022"),
    ("CONTRATO N.º 012/2023", "contrato", "012/2023"),
    ("2º TERMO ADITIVO AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS Nº 045/2022", "aditivo", "2º TA ao Contrato 045/2022"),
    ("TERMO ADITIVO Nº 03 AO CONTRATO Nº 045/2022", "aditivo", "3º TA ao Contrato 045/2022"),
    ("TERCEIRO TERMO ADITIVO", "aditivo", None),
    ("TERMO DE APOSTILAMENTO Nº 02/2024", "apostilamento", "02/2024"),
    ("NOTA DE EMPENHO", "nota_empenho", None),
    ("DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA", "nota_fiscal", None),
    ("NOTA FISCAL DE SERVIÇOS ELETRÔNICA - NFS-e", "nota_fiscal", None),
    ("ORDEM BANCÁRIA", "pagamento", None),
    ("NOTA DE LIQUIDAÇÃO", "pagamento", None),
    ("CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS", "certidao", None),
    ("Certificado de Regularidade do FGTS - CRF", "certidao", None),
    ("TERMO DE RECEBIMENTO DEFINITIVO", "termo_recebimento", None),
    ("ATESTADO DE RECEBIMENTO E EXECUÇÃO", "termo_recebimento", None),
    ("RELATÓRIO MENSAL DE FISCALIZAÇÃO", "relatorio_fiscalizacao", None),
    ("RELATÓRIO DE ATIVIDADES", "relatorio", None),
    ("PORTARIA Nº 345/2023/GAB", "portaria", "345/2023"),
    ("PROPOSTA COMERCIAL", "proposta", None),
    ("APÓLICE DE SEGURO GARANTIA", "garantia", None),
    ("OFÍCIO CIRCULAR Nº 15/2024/CC", "oficio", "15/2024"),
    ("TERMO DE REFERÊNCIA", "termo_referencia", None),
    ("ESTUDO TÉCNICO PRELIMINAR", "estudo_tecnico_preliminar", None),
    ("ATA DE REGISTRO DE PREÇOS Nº 010/2023", "ata_registro_precos", "010/2023"),
    ("EXTRATO DO CONTRATO Nº 045/2022", "extrato_publicacao", "045/2022"),
    ("DESPACHO", "despacho", None),
])
def test_segundo_nivel_formatos_reais(titulo, tipo, numero):
    m = extrair_metadados(CABECALHO_REAL + titulo + "\nCorpo do documento.\n")
    assert (m.tipo_documental, m.numero) == (tipo, numero)
    assert m.titulo


def test_mencao_ao_contrato_no_corpo_nao_vira_contrato():
    texto = CABECALHO_REAL + "Prezados,\nEncaminhamos a documentação referente ao Contrato nº 045/2022.\n"
    assert extrair_metadados(texto).tipo_documental == "outro"


@pytest.mark.parametrize("arquivo,extensao,tipo", [
    ("pasta/NE 2024NE000123.pdf", ".pdf", "nota_empenho"),
    ("pasta/Nota de empenho - março.pdf", ".pdf", "nota_empenho"),
    ("pasta/NF 1234 empresa.pdf", ".pdf", "nota_fiscal"),
    ("pasta/CND federal.pdf", ".pdf", "certidao"),
    ("pasta/Certidões.pdf", ".pdf", "certidao"),
    ("pasta/2º Termo Aditivo.pdf", ".pdf", "aditivo"),
    ("pasta/Apostilamento reajuste.pdf", ".pdf", "apostilamento"),
    ("pasta/Relatório do fiscal - jan.pdf", ".pdf", "relatorio_fiscalizacao"),
    ("pasta/OB 2024OB01234.pdf", ".pdf", "pagamento"),
    ("pasta/Processo de pagamento 03.pdf", ".pdf", "pagamento"),
    ("pasta/Controle de medições.xlsx", ".xlsx", "planilha"),
    ("pasta/digitalizado_0001.pdf", ".pdf", "outro"),
])
def test_nome_do_arquivo_quando_o_texto_nao_identifica(arquivo, extensao, tipo):
    m = extrair_metadados(CABECALHO_REAL + "texto sem título reconhecível\n", nome_arquivo=arquivo, extensao=extensao)
    assert m.tipo_documental == tipo


def test_texto_prevalece_sobre_o_nome_e_regras_estritas_prevalecem():
    m = extrair_metadados(AVISO + "\nCONTRATO Nº 012/2023\n", nome_arquivo="pasta/NF 99.pdf", extensao=".pdf")
    assert (m.tipo_documental, m.numero) == ("contrato", "012/2023")
    m = extrair_metadados(CABECALHO_REAL + "NOTA DE EMPENHO\n", nome_arquivo="pasta/contrato.pdf", extensao=".pdf")
    assert m.tipo_documental == "nota_empenho"
