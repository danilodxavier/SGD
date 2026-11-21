"""Grafo documental (Fase 6): referências, classificação de relações, contradições, agrupamento e vigência — TDD."""
from datetime import date

from app.application.linha_do_tempo.contradicoes import detectar_contradicoes
from app.application.linha_do_tempo.grafo import DocGrafo, agrupar, classificar_relacoes, linha_do_tempo
from app.application.linha_do_tempo.referencias import chave_documento, encontrar_referencias
from app.application.linha_do_tempo.vigencia import revogacoes_por_relacao


def doc(id_, tipo, numero, data, *trechos, origem="sintetico"):
    return DocGrafo(id_, tipo, numero, date.fromisoformat(data), f"{tipo.upper()} Nº {numero}", origem,
                    [(id_ * 100 + i, t) for i, t in enumerate(trechos)])


# ----------------------------------------------------------------- referências
def test_referencias_normalizadas():
    texto = ("Fica revogado o Decreto nº 1.410, de 18 de abril de 2023, e a Lei no 8.666, de 21 de junho de 1993. "
             "Ver Contrato nº 012/2023, Portaria nº 010/2023, Lei Complementar nº 101 e Decreto-Lei nº 4.657. "
             "Revogam-se os arts. 1º a 47-A da Lei nº 12.462, de 4 de agosto de 2011.")
    refs = encontrar_referencias(texto)
    chaves = [r.chave for r in refs]
    assert chaves == [("decreto", "1410"), ("lei", "8666"), ("contrato", "012/2023"), ("portaria", "010/2023"),
                      ("lei_complementar", "101"), ("decreto_lei", "4657"), ("lei", "12462")]
    assert [r.parcial for r in refs] == [False] * 6 + [True]  # "arts. 1º a 47-A da Lei" → revogação parcial
    # caso real (Lei 14.230/2021): "dispositivos e seção da Lei nº 8.429" também é parcial
    assert encontrar_referencias("Ficam revogados os seguintes dispositivos e seção da Lei nº 8.429, de 2 de junho "
                                 "de 1992:")[0].parcial
    assert encontrar_referencias("Revogam-se os §§ 2º e 3º do art. 10 da Lei nº 6.938, de 1981")[0].parcial


def test_chave_do_documento():
    assert chave_documento("decreto", "1.410/2023") == ("decreto", "1410")
    assert chave_documento("lei", "14.133") == ("lei", "14133")
    assert chave_documento("contrato", "012/2023") == ("contrato", "012/2023")
    assert chave_documento("portaria_designacao", "112/2024") == ("portaria", "112/2024")
    assert chave_documento("aditivo", "1º TA ao Contrato 012/2023") is None  # aditivo não é referido por número


# ----------------------------------------------------------------- classificação
CONTRATO = doc(1, "contrato", "012/2023", "2023-03-01", "CONTRATO Nº 012/2023\nO valor global do contrato é de "
               "R$ 1.200.000,00, para todo o período.\nO prazo de vigência é de 12 meses, com início em 01/03/2023 e "
               "término em 29/02/2024.")
ADITIVO = doc(2, "aditivo", "1º TA ao Contrato 012/2023", "2024-02-20", "Fica prorrogada a vigência do Contrato nº "
              "012/2023 por 12 meses, passando o término de 29/02/2024 para 28/02/2025.")
NOTIF = doc(3, "notificacao", "023/2024", "2024-10-02", "Notificamos a empresa pelas faltas no Contrato nº 012/2023.")
RESC = doc(4, "termo_rescisao", None, "2024-11-18", "Considerando a Notificação nº 023/2024 e a ausência de defesa, "
           "fica rescindido unilateralmente o Contrato nº 012/2023.")
SUSP = doc(5, "ordem_suspensao", "004/2024", "2024-04-01", "Fica suspensa a execução do Contrato nº 012/2023.")
REIN = doc(6, "ordem_reinicio", "005/2024", "2024-05-15", "Fica retomada a execução do Contrato nº 012/2023.")
REL = doc(7, "relatorio_fiscalizacao", "007/2024", "2024-03-08", "O Contrato nº 012/2023, de valor global de "
          "R$ 1.250.000,00, foi executado regularmente.")
APOST = doc(8, "apostilamento", "001/2024", "2024-06-01", "Registra-se o reajuste de 3,9% pelo IPCA.\nPara fins de "
            "registro, a vigência do Contrato nº 012/2023 encerra-se em 30/03/2025.")
DOCS = [CONTRATO, ADITIVO, NOTIF, RESC, SUSP, REIN, REL, APOST]


def rotulos(relacoes):
    return {(r.origem, r.destino): r.tipo for r in relacoes}


def test_classificacao_por_marcadores_e_tipo_documental():
    r = rotulos(classificar_relacoes(DOCS))
    assert r[(1, 2)] == "aditivo"
    assert r[(1, 3)] == "continuacao"
    assert r[(3, 4)] == "continuacao"  # "Considerando a Notificação"
    assert r[(1, 4)] == "ruptura"  # "fica rescindido ... o Contrato"
    assert r[(1, 5)] == "ruptura"
    assert r[(5, 6)] == "retomada"  # retomada aponta para a interrupção, não para o contrato
    assert r[(1, 8)] == "alteracao"  # apostilamento de reajuste
    assert (1, 6) not in r


def test_contradicoes_contra_a_cadeia_contrato_aditivos():
    contradicoes = detectar_contradicoes(DOCS)
    pares = {(c.origem, c.destino, c.campo): (c.valor_vigente, c.valor_declarado) for c in contradicoes}
    assert pares[(1, 7, "valor_global")] == ("R$ 1.200.000,00", "R$ 1.250.000,00")
    assert pares[(2, 8, "vigencia_fim")] == ("28/02/2025", "30/03/2025")  # vigente vem do aditivo
    assert len(pares) == 2  # o aditivo não "contradiz" o contrato: ele altera


def test_contradicao_prevalece_sobre_continuacao_no_mesmo_par():
    r = rotulos(classificar_relacoes(DOCS, detectar_contradicoes(DOCS)))
    assert r[(1, 7)] == "contradicao"


def test_normas_revogacao_alteracao_substituicao_regulamenta_fundamenta():
    lei = doc(10, "lei", "11.205/2022", "2022-11-23", "LEI Nº 11.205\nArt. 1º Compras sustentáveis.")
    p1 = doc(11, "portaria", "010/2023", "2023-02-14", "Art. 2º O fiscal atestará em 5 dias.")
    p2 = doc(12, "portaria", "025/2024", "2024-05-06", "Art. 1º O inciso II do art. 2º da Portaria nº 010/2023 passa "
             "a vigorar com a seguinte redação: 3 dias.")
    p3 = doc(13, "portaria", "040/2025", "2025-03-10", "Art. 3º Ficam revogadas a Portaria nº 010/2023 e a Portaria "
             "nº 025/2024.")
    in3 = doc(14, "instrucao_normativa", "03/2025", "2025-04-02", "Art. 1º Esta Instrução Normativa substitui "
              "integralmente a Portaria nº 010/2023.")
    d1 = doc(15, "decreto", "1.410/2023", "2023-04-18", "Art. 1º Este Decreto regulamenta a Lei nº 11.205, de 23 de "
             "novembro de 2022.")
    ori = doc(16, "orientacao", "02/2024", "2024-01-15", "Art. 1º A prorrogação observará o art. 107 da Lei nº 11.205.")
    r = rotulos(classificar_relacoes([lei, p1, p2, p3, in3, d1, ori]))
    assert r[(11, 12)] == "alteracao" and r[(11, 13)] == "revogacao" and r[(12, 13)] == "revogacao"
    assert r[(11, 14)] == "substituicao" and r[(10, 15)] == "regulamenta" and r[(10, 16)] == "fundamenta"


def test_marcador_explicito_vence_rotulo_padrao_no_mesmo_par():
    p = doc(60, "portaria", "062/2023", "2023-03-10", "Art. 1º Horário.")
    ori = doc(61, "orientacao", "12/2024", "2024-06-01", "Orienta a aplicação da Portaria nº 062/2023.",
              "Art. 1º A aplicação da Portaria nº 062/2023 observará a Lei nº 9.784.")
    r = {(x.origem, x.destino): x.tipo for x in classificar_relacoes([p, ori])}
    assert r[(60, 61)] == "continuacao"


def test_sequencia_do_mesmo_processo_sem_referencia_explicita():
    despacho = doc(20, "despacho", "233/2024", "2024-05-14", "PROCESSO SEGEP-PRO-2024/00081\nAutorizo o pregão.")
    contrato = doc(21, "contrato", "081/2024", "2024-07-01", "PROCESSO Nº SEGEP-PRO-2024/00081\nCONTRATO Nº 081/2024\n"
                   "Com fundamento na Lei nº 14.133, de 1º de abril de 2021.")
    lei = doc(22, "lei", "14.133/2021", "2021-04-01", "Art. 1º Normas gerais.", origem="publico")
    rel = [r for r in classificar_relacoes([despacho, contrato, lei]) if (r.origem, r.destino) == (20, 21)]
    assert rel and rel[0].tipo == "continuacao" and rel[0].confianca < 0.8  # inferência mais fraca


def test_agrupamento_e_linha_do_tempo_com_fases():
    relacoes = classificar_relacoes(DOCS, detectar_contradicoes(DOCS))
    grupos = agrupar(DOCS, relacoes)
    assert len(grupos) == 1 and grupos[0].chave == ("contrato", "012/2023")
    tl = linha_do_tempo(grupos[0], DOCS, relacoes)
    assert [e.documento for e in tl.eventos] == [1, 2, 7, 5, 6, 8, 3, 4]  # ordem cronológica
    assert [f.nome for f in tl.fases] == ["Execução", "Interrupção", "Execução retomada", "Extinção"]
    assert any("contradição" in i for i in tl.inconsistencias)


def test_anotacoes_de_compilacao_invertem_a_direcao():
    """Textos compilados oficiais anotam na voz passiva: "(Revogado pela Lei nº X)" significa que X revogou."""
    lei14133 = doc(40, "lei", "14.133/2021", "2021-04-01", "LEI Nº 14.133\nArt. 1º Normas gerais.")
    lei14230 = doc(41, "lei", "14.230/2021", "2021-10-25", "LEI Nº 14.230\nArt. 1º Altera a improbidade.")
    lei8666 = doc(42, "lei", "8.666/1993", "1993-06-21",
                  "LEI No 8.666, DE 21 DE JUNHO DE 1993\n(Revogada pela Lei nº 14.133, de 2021)",
                  "Art. 24. [REVOGADO] É dispensável a licitação: (Vide Lei nº 14.133, de 2021)")
    lei8429 = doc(43, "lei", "8.429/1992", "1992-06-02", "LEI Nº 8.429",
                  "Art. 1º O sistema de responsabilização. (Redação dada pela Lei nº 14.230, de 2021)",
                  "Art. 3º [REVOGADO] (Revogado pela Lei nº 14.230, de 2021)")
    rels = {(r.origem, r.destino): r for r in classificar_relacoes([lei14133, lei14230, lei8666, lei8429])}
    assert rels[(42, 40)].tipo == "revogacao" and not rels[(42, 40)].parcial  # nota no cabeçalho: ato inteiro
    assert (40, 42) not in rels  # nunca "a 8.666 revoga a 14.133"
    # notas em dispositivos (redação dada + revogado pela mesma lei): alteração parcial, nunca revogação total
    assert rels[(43, 41)].tipo == "alteracao"
    assert set(revogacoes_por_relacao(list(rels.values()))) == {42}


def test_marcador_de_outra_frase_ou_tag_revogado_nao_contamina():
    """Casos reais: '[REVOGADO]' é tag do extrator; marcador de outra frase não vale para a referência."""
    lei = doc(50, "lei", "11.107/2005", "2005-04-06", "Art. 1º Consórcios.")
    lei2 = doc(51, "lei", "13.709/2018", "2018-08-14", "Art. 1º LGPD.")
    dec = doc(52, "decreto", "9.373/2018", "2018-05-11",
              "Art. 8º-B. [REVOGADO] Excetuam-se da hipótese prevista no § 6º do art. 13 da Lei nº 11.107, de 2005.",
              "§ 4º A intimação será substituída por intimação eletrônica. Aplica-se a Lei nº 13.709, de 2018.")
    r = {(x.origem, x.destino): x.tipo for x in classificar_relacoes([lei, lei2, dec])}
    assert r[(50, 52)] == "fundamenta" and r[(51, 52)] == "fundamenta"


def test_revogacao_parcial_com_alteracao_e_alteracao():
    lei8429 = doc(70, "lei", "8.429/1992", "1992-06-02", "Art. 1º Improbidade.")
    lei14230 = doc(71, "lei", "14.230/2021", "2021-10-25",
                   "Art. 1º A Lei nº 8.429, de 2 de junho de 1992, passa a vigorar com as seguintes alterações:",
                   "Art. 4º Ficam revogados os seguintes dispositivos e seção da Lei nº 8.429, de 2 de junho de 1992:")
    rels = classificar_relacoes([lei8429, lei14230])
    assert {(r.origem, r.destino): r.tipo for r in rels}[(70, 71)] == "alteracao"
    assert revogacoes_por_relacao(rels) == {}


def test_revogacao_total_atualiza_vigencia_mas_parcial_nao():
    total = classificar_relacoes([doc(30, "decreto", "7.892/2013", "2013-01-23", "Art. 1º Texto."),
                                  doc(31, "decreto", "11.462/2023", "2023-03-31", "Art. 33. Fica revogado o "
                                      "Decreto nº 7.892, de 23 de janeiro de 2013.")])
    parcial = classificar_relacoes([doc(32, "lei", "12.462/2011", "2011-08-04", "Art. 1º RDC."),
                                    doc(33, "lei", "14.133/2021", "2021-04-01", "Art. 193. Revogam-se os arts. 1º a "
                                        "47-A da Lei nº 12.462, de 4 de agosto de 2011.")])
    assert set(revogacoes_por_relacao(total)) == {30}
    assert revogacoes_por_relacao(parcial) == {}


def test_contrato_que_cita_lei_e_fundamentacao_e_nao_une_processos():
    # caso real da Fase 8: contratos citando a Lei 14.133 caíam no mesmo processo de todas as normas
    lei = doc(1, "lei", "14.133/2021", "2021-04-01", "LEI Nº 14.133, DE 1º DE ABRIL DE 2021\nLicitações e contratos.")
    ti = doc(2, "contrato", "031/2023", "2023-02-01", "CONTRATO Nº 031/2023\nRegido pela Lei nº 14.133, de 1º de "
             "abril de 2021. Poderá ser rescindido conforme a Lei nº 14.133, de 1º de abril de 2021.")
    limpeza = doc(3, "contrato", "012/2023", "2023-03-01", "CONTRATO Nº 012/2023\nAplica-se a Lei nº 14.133, de 1º "
                  "de abril de 2021.")
    relacoes = classificar_relacoes([lei, ti, limpeza])
    r = rotulos(relacoes)
    assert r[(1, 2)] == "fundamenta" and r[(1, 3)] == "fundamenta"  # nem ruptura, nem continuação
    grupos = agrupar([lei, ti, limpeza], relacoes)
    assert not any({2, 3} <= set(g.documentos) for g in grupos)


def test_documentos_sem_data_nao_quebram_o_grafo_e_aditivo_datado_prevalece():
    """Regressão (acervo real, 2026-11-20): documentos reais podem vir sem data; a ordenação dos aditivos
    comparava None com date. Aditivo sem data fica com prioridade mínima: o datado define a vigência."""
    sem_data = DocGrafo(9, "aditivo", "2º TA ao Contrato 012/2023", None, "2º TA", "real",
                        [(900, "Fica prorrogada a vigência do Contrato nº 012/2023, passando o término para "
                               "31/12/2030.")])
    docs = [CONTRATO, ADITIVO, sem_data, NOTIF, RESC, SUSP, REIN, REL, APOST]
    contradicoes = detectar_contradicoes(docs)
    pares = {(c.origem, c.destino, c.campo): c.valor_vigente for c in contradicoes}
    assert pares[(2, 8, "vigencia_fim")] == "28/02/2025"  # o aditivo datado prevalece sobre o sem data
    relacoes = classificar_relacoes(docs, contradicoes)
    grupos = agrupar(docs, relacoes)
    assert any(9 in g.documentos for g in grupos)
    for g in grupos:
        linha_do_tempo(g, docs, relacoes)


def test_copias_da_mesma_norma_sem_relacao_formam_um_unico_grupo():
    """Regressão (acervo real, 2026-11-20): a mesma lei em dois arquivos, um deles ligado a outros documentos e o
    outro isolado, gerava dois grupos com a mesma chave e violava UNIQUE(tipo, chave) ao salvar o grafo."""
    lei = doc(20, "lei", "14.133", "2021-04-01", "LEI Nº 14.133, DE 1º DE ABRIL DE 2021. Lei de Licitações.")
    copia = doc(21, "lei", "14.133", "2021-04-01", "LEI Nº 14.133, DE 1º DE ABRIL DE 2021 (compilada).")
    parecer = doc(22, "parecer_juridico", "010/2024", "2024-05-01", "Nos termos da Lei nº 14.133, de 2021, opina-se.")
    docs = [lei, copia, parecer]
    grupos = agrupar(docs, classificar_relacoes(docs))
    chaves = [g.chave for g in grupos]
    assert len(chaves) == len(set(chaves))
    assert sorted(i for g in grupos if 20 in g.documentos for i in g.documentos) == [20, 21]
    assert sorted(i for g in grupos for i in g.documentos) == [20, 21, 22]  # nenhum documento perdido


def test_documento_que_cita_dois_contratos_nao_funde_os_processos():
    """Regressão (acervo real, 2026-11-20): portarias/relatórios que citam vários contratos encadeavam processos
    distintos (1.279 documentos de 15 contratos num único grupo). Dois contratos diferentes nunca se fundem."""
    outro = doc(30, "contrato", "031/2023", "2023-05-01", "CONTRATO Nº 031/2023\nO valor global do contrato é de "
                "R$ 500.000,00.")
    aditivo_outro = doc(31, "aditivo", "1º TA ao Contrato 031/2023", "2024-04-20", "Fica prorrogada a vigência do "
                        "Contrato nº 031/2023 por 12 meses.")
    portaria = doc(32, "portaria", "200/2024", "2024-01-10", "Designa fiscais para o Contrato nº 012/2023 e para o "
                   "Contrato nº 031/2023.")
    docs = [CONTRATO, ADITIVO, outro, aditivo_outro, portaria]
    grupos = {g.chave: sorted(g.documentos) for g in agrupar(docs, classificar_relacoes(docs))}
    assert {1, 2} <= set(grupos[("contrato", "012/2023")])
    assert {30, 31} <= set(grupos[("contrato", "031/2023")])
    assert not set(grupos[("contrato", "012/2023")]) & set(grupos[("contrato", "031/2023")])
    assert sum(32 in g for g in grupos.values()) == 1  # a portaria fica em um único processo
