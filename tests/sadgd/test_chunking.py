"""Chunking estrutural jurídico (SAD-043, RF-03) — escrito antes da implementação (TDD)."""
from app.application.ingestao.chunking import Pagina, dividir

LEI = """LEI Nº 99.999, DE 1º DE ABRIL DE 2030
Dispõe sobre testes.
CAPÍTULO I
DISPOSIÇÕES GERAIS
Art. 1º Esta Lei estabelece normas gerais.
Art. 2º Para os fins desta Lei, consideram-se:
I - órgão: unidade de atuação;
II – entidade: unidade com personalidade jurídica;
a) da administração direta;
b) da administração indireta;
§ 1º O disposto neste artigo aplica-se aos Estados.
§ 2º (Revogado).
Parágrafo único. Regulamento disporá sobre o tema.
CAPÍTULO II
DAS CONTRATAÇÕES
Seção I
Do Planejamento
Art. 10. A fase preparatória é caracterizada pelo planejamento.
Art. 75. É dispensável a licitação:
Art. 5º-A. Artigo incluído por lei posterior.
Art. 1.048. Artigo de numeração longa.
"""

CONTRATO = """CONTRATO Nº 012/2023
PROCESSO Nº SEGEP-PRO-2023/00012
O ESTADO, por meio da Secretaria, e a empresa X resolvem celebrar o presente contrato.
CLÁUSULA PRIMEIRA – DO OBJETO
1.1. O objeto é a limpeza predial.
CLÁUSULA SEGUNDA – DA VIGÊNCIA
2.1. A vigência é de 12 (doze) meses.
2.2. A prorrogação dependerá de justificativa.
CLÁUSULA DÉCIMA PRIMEIRA - DO FORO
11.1. Fica eleito o foro da Capital.
"""


def rotulos(trechos):
    return [t.dispositivo for t in trechos]


def test_artigos_viram_trechos_com_rotulo_e_caminho_hierarquico():
    trechos = dividir([Pagina(LEI, 1)])
    assert rotulos(trechos) == [None, "art. 1º", "art. 2º", "art. 10", "art. 75", "art. 5º-A", "art. 1.048"]
    art2 = trechos[2]
    assert art2.tipo_dispositivo == "artigo"
    assert art2.caminho == "CAPÍTULO I – DISPOSIÇÕES GERAIS > art. 2º"
    assert trechos[3].caminho == "CAPÍTULO II – DAS CONTRATAÇÕES > Seção I – Do Planejamento > art. 10"
    assert trechos[0].tipo_dispositivo == "preambulo"


def test_subdispositivos_sao_reconhecidos_dentro_do_artigo():
    art2 = dividir([Pagina(LEI, 1)])[2]
    assert art2.subdispositivos == ["art. 2º, I", "art. 2º, II", "art. 2º, II, a", "art. 2º, II, b",
                                    "art. 2º, § 1º", "art. 2º, § 2º", "art. 2º, parágrafo único"]


def test_texto_e_literal_e_offsets_apontam_para_o_original():
    texto = LEI
    for t in dividir([Pagina(texto, 1)]):
        assert texto[t.inicio:t.fim] == t.texto
    assert "Art. 2º Para os fins desta Lei" in dividir([Pagina(texto, 1)])[2].texto


def test_clausulas_e_itens_de_contrato():
    trechos = dividir([Pagina(CONTRATO, 1)])
    assert rotulos(trechos) == [None, "cláusula primeira", "cláusula segunda", "cláusula décima primeira"]
    assert trechos[2].subdispositivos == ["cláusula segunda, item 2.1", "cláusula segunda, item 2.2"]
    assert trechos[1].tipo_dispositivo == "clausula"


def test_artigo_longo_e_dividido_nos_subdispositivos_sem_ultrapassar_o_limite():
    incisos = "\n".join(f"{r} - hipótese de dispensa número {r} " + "x" * 300 for r in
                        ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"])
    texto = f"Art. 75. É dispensável a licitação:\n{incisos}\n"
    trechos = dividir([Pagina(texto, 1)], max_caracteres=1000)
    assert len(trechos) > 1
    assert all(len(t.texto) <= 1000 for t in trechos)
    assert trechos[0].dispositivo == "art. 75"
    assert trechos[1].dispositivo.startswith("art. 75, ")  # faixa de incisos: "art. 75, III a IV"
    assert all(t.contexto.startswith("Art. 75. É dispensável") for t in trechos)
    assert "".join(t.texto for t in trechos).replace("\n", "") == texto.replace("\n", "")


def test_paginas_sao_preservadas():
    p1 = "Art. 1º Primeiro artigo.\n"
    p2 = "Art. 2º Segundo artigo.\n"
    trechos = dividir([Pagina(p1, 1), Pagina(p2, 2)])
    assert [(t.dispositivo, t.pagina) for t in trechos] == [("art. 1º", 1), ("art. 2º", 2)]


def test_dispositivo_revogado_e_marcado():
    texto = "Art. 1º Vigente.\nArt. 2º [REVOGADO] Texto tachado na fonte oficial.\n"
    trechos = dividir([Pagina(texto, 1)])
    assert [t.revogado for t in trechos] == [False, True]


def test_texto_livre_e_dividido_por_paragrafos():
    paragrafos = [f"Parágrafo {i} " + "palavra " * 60 for i in range(10)]
    texto = "\n\n".join(paragrafos)
    trechos = dividir([Pagina(texto, 1)], max_caracteres=1200)
    assert len(trechos) >= 4
    assert all(t.tipo_dispositivo == "livre" and t.dispositivo is None for t in trechos)
    assert all(len(t.texto) <= 1200 for t in trechos)


def test_referencia_a_artigo_no_meio_da_frase_nao_abre_dispositivo():
    texto = "Art. 1º Aplica-se o disposto no\nArt. 5º da Lei nº 1.000 conforme citado.\n"
    # linha que começa com "Art. 5º da Lei" é citação, não um novo artigo deste documento
    trechos = dividir([Pagina(texto, 1)])
    assert rotulos(trechos) == ["art. 1º"]


def test_artigo_legitimo_que_comeca_com_da_dos_nao_e_confundido_com_citacao():
    # casos reais da Lei 9.784/1999 (art. 56) e da Lei 14.133/2021 (arts. 165 a 167)
    texto = ("Art. 56. Das decisões administrativas cabe recurso, em face de razões de legalidade.\n"
             "Art. 165. Dos atos da Administração decorrentes da aplicação desta Lei cabem:\n"
             "Art. 166. Da aplicação das sanções caberá recurso.\n"
             "Art. 167. Conforme o art. 5º do Decreto nº 9.999, aplica-se.\n")
    assert rotulos(dividir([Pagina(texto, 1)])) == ["art. 56", "art. 165", "art. 166", "art. 167"]
