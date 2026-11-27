"""Confiança calculada pelo sistema (2026-11-25): mesmos critérios na ficha, no LLM e na decisão.

Casos reais que motivaram a mudança (consultas 6–8 da auditoria):
  - resposta correta e citada pelo LLM aparecia com 0% (o modelo omitiu o campo "confianca");
  - a mesma qualidade de resposta pela ficha aparecia com 90% (valor fixo);
  - a recusa correta aparecia com 30% (teto), e pela ficha com 70%.
"""
import json
import sqlite3

import pytest

from app.application.agentes.verificador import Problema, Verificacao
from app.application.fichas.consulta import ResponderPorFicha
from app.application.respostas.f1 import ResponderF1
from app.domain import confianca as conf
from app.domain.politicas import MENSAGEM_AUSENCIA
from tests.sadgd.test_fichas import FICHA, OUTRA, RepoFichas, RepoTrechos
from tests.sadgd.test_responder_f1 import TRECHOS, LLMFalso, saida


def aprova(*_):
    return Verificacao(True)


# ------------------------------------------------------------------------------------------------ domínio (escala)
def test_resposta_afirmativa_tem_base_por_caminho_e_criterio_explicado():
    ficha = conf.calcular("fato", "ficha", 2)
    llm = conf.calcular("fato", "llm", 2)
    assert (ficha.valor, llm.valor) == (0.90, 0.85)
    assert ficha.criterio[0].startswith("Base: fato extraído da ficha") and "90%" in ficha.criterio[0]
    assert any("aprovou todas as afirmações" in c for c in llm.criterio)


def test_descontos_por_sinais_verificaveis_e_limite_minimo():
    assert conf.calcular("fato", "llm", 1).valor == 0.80  # fonte única
    assert conf.calcular("fato", "llm", 2, ["verificador_detalhes_removidos"]).valor == 0.75
    assert conf.calcular("fato", "llm", 2, ["segunda_leitura_evidencias"]).valor == 0.75
    c = conf.calcular("fato", "llm", 1, ["verificador_nova_tentativa", "verificador_frases_removidas",
                                         "segunda_leitura_evidencias", "evidencias_contradizem_recusa"])
    assert c.valor == 0.35 and len(c.criterio) == 6  # base + 5 descontos, todos explicados
    assert conf.calcular("fato", "llm", 1, ["sem_verificador", "verificador_nova_tentativa",
                                            "verificador_frases_removidas"]).valor == conf.MINIMO
    assert conf.calcular("fato", "llm", 2, ["sinal_desconhecido", "ficha_do_contrato"]).valor == 0.85


def test_ausencia_e_conflito_nao_tem_percentual():
    busca = conf.calcular("ausencia", "llm", 0, trechos_examinados=8)
    inventario = conf.calcular("ausencia", "ficha", 0)
    conflito = conf.calcular("conflito", "llm", 2)
    assert busca.valor is inventario.valor is conflito.valor is None
    assert "8 trecho(s)" in busca.criterio[0] and "inventário" in inventario.criterio[0]
    assert "conferência documental" in conflito.criterio[0]


def test_candidatos_nao_sao_descontados_pelo_numero_de_fontes():
    assert conf.calcular("candidatos", "ficha", 1).valor == conf.calcular("candidatos", "ficha", 5).valor == 0.50


# --------------------------------------------------------------------------------------------------- F1 pelo LLM
def test_llm_que_omite_a_confianca_nao_gera_zero_por_cento():
    """Caso real (consulta 8): resposta certa, citada e aprovada; o modelo não preencheu "confianca"."""
    sem_campo = {k: v for k, v in saida().items() if k != "confianca"}
    r = ResponderF1(LLMFalso(sem_campo), verificador=aprova).responder("Qual o valor global?", TRECHOS)
    assert r.classificacao == "fato" and r.confianca == 0.65  # fato pelo LLM, uma fonte, sem a ficha como âncora
    assert r.confianca_modelo is None and r.trechos_examinados == 2


def test_autoavaliacao_do_modelo_nao_altera_a_confianca():
    alta = ResponderF1(LLMFalso(saida(confianca=1.0)), verificador=aprova).responder("Qual o valor?", TRECHOS)
    baixa = ResponderF1(LLMFalso(saida(confianca=0.1)), verificador=aprova).responder("Qual o valor?", TRECHOS)
    assert alta.confianca == baixa.confianca == 0.65
    assert (alta.confianca_modelo, baixa.confianca_modelo) == (1.0, 0.1)  # só registrada (auditoria)


def test_recusa_pelo_llm_mostra_o_alcance_da_busca_e_nao_um_teto_de_30():
    """Caso real (consulta 7): a recusa correta aparecia com "Confiança: 30%"."""
    llm = LLMFalso(saida(resposta="", fontes=[], classificacao="ausencia", confianca=1.0))
    r = ResponderF1(llm, verificador=aprova).responder("Qual o nome do cachorro do prefeito?", TRECHOS)
    assert r.resposta == MENSAGEM_AUSENCIA and r.confianca is None
    assert r.confianca_modelo == 1.0 and r.trechos_examinados == 2
    assert r.criterio_confianca == ["Sem evidência nos documentos (2 trecho(s) mais relevantes do acervo examinados)."]


def test_detalhe_reprovado_pelo_verificador_reduz_a_confianca_com_motivo():
    detalhe = "- O prazo é de 24 meses [T12]."

    def reprova_detalhe(texto, fontes, pergunta):
        return Verificacao(False, [Problema("numero", "24 não consta", detalhe)]) if detalhe in texto else \
            Verificacao(True)

    llm = LLMFalso(saida(detalhes=["O prazo é de 24 meses [T12].", "A vigência é de 12 meses [T12]."],
                         fontes=["T11", "T12"]))
    r = ResponderF1(llm, verificador=reprova_detalhe).responder("Qual o valor global?", TRECHOS)
    assert "verificador_detalhes_removidos" in r.observacoes
    assert r.confianca == 0.60 and any("removeu detalhes" in c for c in r.criterio_confianca)


def test_sem_verificador_a_confianca_cai_sem_poluir_as_observacoes():
    r = ResponderF1(LLMFalso(saida())).responder("Qual o valor global?", TRECHOS)
    assert r.confianca == 0.45 and "sem_verificador" not in r.observacoes


# ---------------------------------------------------------------------------------------------------------- ficha
def ficha(pergunta, fichas=(FICHA, OUTRA)):
    return ResponderPorFicha(RepoFichas(list(fichas)), RepoTrechos()).responder(pergunta)


def test_ficha_usa_a_mesma_escala_e_explica_o_calculo():
    r = ficha("Qual o objeto do contrato 012/2023?")
    assert r.classificacao == "fato" and r.confianca == 0.90  # objeto [T12] e contratada [T11]: duas fontes
    r2 = ficha("Qual o objeto do contrato 012/2023?")
    assert r2.criterio_confianca == r.criterio_confianca and r.criterio_confianca[0].startswith("Base: fato extraído")


def test_recusa_pela_ficha_tambem_nao_tem_percentual():
    r = ficha("Quem é o fiscal do contrato 099/2026?", (FICHA, OUTRA, {**OUTRA, "chave": "098/2026"}))
    if r is not None:  # inexistente: a ficha recusa sem percentual (antes: 70%)
        assert r.classificacao == "ausencia" and r.confianca is None


def test_numero_do_contrato_pelo_nome_da_contratada_responde_pela_ficha():
    """Caso real (consulta 8): "Qual o número do contrato com a <fornecedor>?" ia ao LLM (31 s)."""
    r = ficha("Qual o número do contrato com a Alfa?")
    assert r is not None and r.classificacao == "fato"
    assert "Número: 012/2023 [T11]" in r.resposta and "Contratada: ALFA SISTEMAS [T11]" in r.resposta
    assert r.confianca == 0.85  # a mesma fonte (T11) sustenta número e contratada


def test_numero_de_outro_documento_nao_e_confundido_com_o_do_contrato():
    assert ficha("Qual o número do processo do contrato da Alfa?") is None
    sem_numero = {**FICHA, "campos": {k: v for k, v in FICHA["campos"].items() if k != "numero"}}
    assert ficha("Qual o número do contrato com a Alfa?", (sem_numero, OUTRA)) is None  # o caminho completo procura


# ---------------------------------------------------------------------------------------------- F2 e pareceres
def test_f2_confianca_por_pareceres_base_legal_e_precedentes():
    completa = conf.calcular_f2(pareceres_validos=3, divergencias=0, base_legal_vigente=True, precedentes=1,
                                frases_removidas=False)
    assert completa.valor == 0.80
    dividida = conf.calcular_f2(pareceres_validos=3, divergencias=2, base_legal_vigente=True, precedentes=0,
                                frases_removidas=False)
    assert dividida.valor == 0.65 and len(dividida.criterio) == 3
    sem_lei = conf.calcular_f2(pareceres_validos=1, divergencias=0, base_legal_vigente=False, precedentes=1,
                               frases_removidas=False)
    assert sem_lei.valor == 0.5 and "Limitada a 50%" in sem_lei.criterio[-1]
    falhou = conf.calcular_f2(pareceres_validos=0, divergencias=0, base_legal_vigente=False, precedentes=0,
                              frases_removidas=False, relator_falhou=True)
    assert falhou.valor == 0.0


def test_parecer_de_especialista_pela_verificacao_das_afirmacoes():
    assert conf.calcular_parecer(valido=False, afirmacoes=3, citacoes_distintas=2, afirmacoes_removidas=0,
                                 tentativas=1).valor is None
    assert conf.calcular_parecer(valido=True, afirmacoes=0, citacoes_distintas=0, afirmacoes_removidas=0,
                                 tentativas=1).valor == 0.40
    assert conf.calcular_parecer(valido=True, afirmacoes=3, citacoes_distintas=3, afirmacoes_removidas=0,
                                 tentativas=1).valor == 0.75
    assert conf.calcular_parecer(valido=True, afirmacoes=2, citacoes_distintas=1, afirmacoes_removidas=1,
                                 tentativas=2).valor == 0.55


def test_parecer_ignora_a_autoavaliacao_do_modelo():
    from app.application.agentes.especialistas import Parecer

    dados = {"parecer": "x", "afirmacoes": [{"texto": "a", "citacoes": ["T1"]}, {"texto": "b", "citacoes": ["T2"]}],
             "confianca": 0.99}
    p = Parecer("fiscal_contrato", dados, True, True, confianca_modelo=0.99)
    assert p.dados["confianca"] == 0.75 and p.confianca_modelo == 0.99 and p.criterio_confianca


# ------------------------------------------------------------------------------------------------ API e auditoria
def test_api_expoe_criterio_e_alcance_e_esconde_a_autoavaliacao():
    from app.application.agentes.roteador import DecisaoRota
    from app.interfaces.api.perguntar import serializar

    r = ResponderF1(LLMFalso(saida(confianca=0.3)), verificador=aprova).responder("Qual o valor?", TRECHOS)
    payload = serializar({"decisao": DecisaoRota("F1_simples"), "resposta": r})
    assert payload["confianca"] == 0.65 and payload["criterio_confianca"] and payload["trechos_examinados"] == 2
    assert "confianca_modelo" not in json.dumps(payload)


def test_auditoria_grava_confianca_do_sistema_autoavaliacao_e_criterio(tmp_path):
    pytest.importorskip("sqlite_vec")
    from app.application.agentes.roteador import DecisaoRota
    from app.infrastructure.sqlite.auditoria import AuditoriaSqlite
    from app.infrastructure.sqlite.conexao import conectar, migrar

    caminho = tmp_path / "sadgd.db"
    conn = conectar(caminho)
    migrar(conn)
    conn.close()
    auditoria = AuditoriaSqlite(lambda: sqlite3.connect(caminho))
    cid = auditoria.iniciar(None, "pergunta")
    llm = LLMFalso(saida(resposta="", fontes=[], classificacao="ausencia", confianca=1.0))
    r = ResponderF1(llm, verificador=aprova).responder("pergunta", TRECHOS)
    auditoria.concluir(cid, {"decisao": DecisaoRota("F1_simples"), "resposta": r}, 100)
    conn = sqlite3.connect(caminho)
    linha = conn.execute("SELECT classificacao, confianca, confianca_modelo, criterio_confianca FROM consultas "
                         "WHERE id = ?", (cid,)).fetchone()
    conn.close()
    assert linha[:3] == ("ausencia", None, 1.0) and "Sem evidência" in json.loads(linha[3])[0]


# ------------------------------------------------------------------------------- recusa sem LLM (fora do acervo)
def _com_notas(*notas):
    from dataclasses import replace

    return [replace(t, pontuacao=n) for t, n in zip(TRECHOS, notas, strict=True)]


def test_pergunta_fora_do_acervo_e_recusada_sem_chamar_o_llm():
    """Caso real (consulta 7): 81 s e 3 leituras do LLM para recusar; nota máxima do reranker ≈ 0,002."""
    llm = LLMFalso(saida())
    r = ResponderF1(llm, verificador=aprova, limiar_relevancia=0.02).responder("Qual o nome do cachorro do prefeito?",
                                                                              _com_notas(0.0019, 0.0004))
    assert llm.mensagens is None  # o LLM não foi chamado
    assert r.resposta == MENSAGEM_AUSENCIA and r.confianca is None and r.trechos_examinados == 2
    assert r.observacoes == ["sem_trecho_relevante"] and r.lacunas


def test_um_trecho_relevante_basta_para_o_llm_ler_e_o_limiar_vem_desligado():
    llm = LLMFalso(saida())
    r = ResponderF1(llm, verificador=aprova, limiar_relevancia=0.02).responder("Qual o valor global?",
                                                                              _com_notas(0.66, 0.001))
    assert llm.mensagens is not None and r.classificacao == "fato"
    padrao = LLMFalso(saida())
    ResponderF1(padrao, verificador=aprova).responder("Qual o valor global?", _com_notas(0.0, 0.0))
    assert padrao.mensagens is not None  # sem limiar configurado (avaliações, testes): comportamento anterior


def test_numero_com_dois_contratos_do_mesmo_fornecedor_lista_os_dois_com_citacao():
    """Caso real: duas fichas casam com o nome do fornecedor — a ficha lista as duas (antes: LLM, 31 s)."""
    b = {**FICHA, "chave": "020/2024", "apelidos": [], "texto_busca": "ct 020-2024 alfa do brasil licencas",
         "campos": {"numero": {"valor": "020/2024", "trecho_id": 31}, "contratada": {"valor": "ALFA", "trecho_id": 31}}}
    r = ficha("Qual o número do contrato com a Alfa?", (FICHA, b, OUTRA))
    assert r is not None and r.resposta.startswith("Encontrei 2 contratos")
    assert "Contrato nº 012/2023 [T11]" in r.resposta and "Contrato nº 020/2024 [T31]" in r.resposta
    assert "varios_contratos" in r.observacoes and r.confianca == 0.85


def test_resposta_ancorada_na_ficha_nao_recebe_o_desconto_de_leitura_livre():
    """Rodada 18 (gabarito real, teste): ancorado na ficha, ≥ 80% de confiança acertou 96%; lendo só trechos, 46%."""
    ficha = "FICHA DO CONTRATO Nº 012/2023 (dados conferidos):\n- Valor global: R$ 1.200.000,00 [T11]"
    livre = ResponderF1(LLMFalso(saida()), verificador=aprova).responder("Qual o valor?", TRECHOS)
    ancorada = ResponderF1(LLMFalso(saida()), verificador=aprova).responder("Qual o valor?", TRECHOS, ficha=ficha)
    assert (livre.confianca, ancorada.confianca) == (0.65, 0.80)
    assert any("sem a ficha" in c for c in livre.criterio_confianca)
    assert not any("sem a ficha" in c for c in ancorada.criterio_confianca)
