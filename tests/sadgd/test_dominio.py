"""Regras de domínio puras do SAD-GD (TDD): hierarquia normativa, vigência, relações e política de envio externo."""
from datetime import date

import pytest

from app.domain.documentos import CorpusOrigem
from app.domain.normas import EspecieNormativa, Norma, SituacaoVigencia, fundamentacao_atual, prevalece
from app.domain.politicas import (
    AVISO_DECISAO,
    MENSAGEM_AUSENCIA,
    PoliticaEnvioExternoViolada,
    avaliar_envio_externo,
    exigir_envio_permitido,
)
from app.domain.relacoes import Relacao, TipoRelacao, ciclos_de_substituicao


def norma(id_, especie, ano, situacao=SituacaoVigencia.VIGENTE, inicio=None, fim=None):
    return Norma(documento_id=id_, especie=especie, numero=str(id_), ano=ano, situacao=situacao,
                 vigencia_inicio=inicio, vigencia_fim=fim)


class TestHierarquia:
    def test_niveis_seguem_a_piramide_normativa(self):
        ordem = [EspecieNormativa.CONSTITUICAO, EspecieNormativa.LEI, EspecieNormativa.DECRETO,
                 EspecieNormativa.INSTRUCAO_NORMATIVA, EspecieNormativa.ORIENTACAO]
        assert [e.nivel for e in ordem] == sorted(e.nivel for e in ordem)
        assert EspecieNormativa.LEI_COMPLEMENTAR.nivel == EspecieNormativa.LEI.nivel
        assert EspecieNormativa.PORTARIA.nivel == EspecieNormativa.INSTRUCAO_NORMATIVA.nivel
        assert EspecieNormativa.PARECER.nivel == EspecieNormativa.ORIENTACAO.nivel

    def test_norma_superior_prevalece(self):
        lei, decreto = norma(1, EspecieNormativa.LEI, 2021), norma(2, EspecieNormativa.DECRETO, 2023)
        resultado = prevalece(lei, decreto)
        assert resultado.vencedora is lei and resultado.criterio == "hierarquico"

    def test_mesmo_nivel_prevalece_a_posterior_como_inferencia(self):
        antiga, nova = norma(1, EspecieNormativa.DECRETO, 2019), norma(2, EspecieNormativa.DECRETO, 2024)
        resultado = prevalece(antiga, nova)
        assert resultado.vencedora is nova and resultado.criterio == "cronologico"
        assert resultado.inferencia is True

    def test_mesmo_nivel_e_mesmo_ano_nao_decide(self):
        a, b = norma(1, EspecieNormativa.DECRETO, 2024), norma(2, EspecieNormativa.DECRETO, 2024)
        assert prevalece(a, b).vencedora is None

    def test_norma_revogada_nunca_prevalece_sobre_vigente(self):
        lei_revogada = norma(1, EspecieNormativa.LEI, 1993, SituacaoVigencia.REVOGADA)
        decreto = norma(2, EspecieNormativa.DECRETO, 2023)
        assert prevalece(lei_revogada, decreto).vencedora is decreto


class TestVigencia:
    def test_revogada_sai_da_fundamentacao_atual_mas_fica_no_historico(self):
        vigente = norma(1, EspecieNormativa.LEI, 2021)
        revogada = norma(2, EspecieNormativa.LEI, 1993, SituacaoVigencia.REVOGADA)
        atual, historico = fundamentacao_atual([vigente, revogada], date(2026, 11, 16))
        assert atual == [vigente] and historico == [revogada]

    def test_vigencia_por_datas(self):
        futura = norma(1, EspecieNormativa.DECRETO, 2026, inicio=date(2027, 1, 1))
        expirada = norma(2, EspecieNormativa.DECRETO, 2020, fim=date(2022, 12, 31))
        assert not futura.vigente_em(date(2026, 11, 16))
        assert not expirada.vigente_em(date(2026, 11, 16))
        assert expirada.vigente_em(date(2021, 6, 1))

    def test_parcialmente_revogada_continua_na_fundamentacao(self):
        parcial = norma(1, EspecieNormativa.LEI, 2021, SituacaoVigencia.PARCIALMENTE_REVOGADA)
        atual, _ = fundamentacao_atual([parcial], date(2026, 11, 16))
        assert atual == [parcial]


class TestRelacoes:
    def test_oito_classes_avaliadas_e_duas_auxiliares(self):
        avaliadas = {t for t in TipoRelacao if t.avaliada}
        assert len(avaliadas) == 8
        assert {TipoRelacao.REGULAMENTA, TipoRelacao.FUNDAMENTA}.isdisjoint(avaliadas)

    @pytest.mark.parametrize("confianca", [-0.1, 1.5])
    def test_confianca_fora_do_intervalo_e_rejeitada(self, confianca):
        with pytest.raises(ValueError):
            Relacao(origem_id=1, destino_id=2, tipo=TipoRelacao.ADITIVO, confianca=confianca, evidencia_trecho_id=9)

    def test_relacao_exige_documentos_distintos_e_evidencia(self):
        with pytest.raises(ValueError):
            Relacao(origem_id=1, destino_id=1, tipo=TipoRelacao.ADITIVO, confianca=0.9, evidencia_trecho_id=9)
        with pytest.raises(ValueError):
            Relacao(origem_id=1, destino_id=2, tipo=TipoRelacao.ADITIVO, confianca=0.9, evidencia_trecho_id=None)

    def test_detecta_ciclo_de_revogacao(self):
        rel = [
            Relacao(1, 2, TipoRelacao.REVOGACAO, 0.9, 10),
            Relacao(2, 3, TipoRelacao.SUBSTITUICAO, 0.9, 11),
            Relacao(3, 1, TipoRelacao.REVOGACAO, 0.9, 12),
            Relacao(4, 5, TipoRelacao.ADITIVO, 0.9, 13),
        ]
        ciclos = ciclos_de_substituicao(rel)
        assert len(ciclos) == 1 and set(ciclos[0]) == {1, 2, 3}


class TestPoliticaEnvioExterno:
    def test_provedor_local_sempre_permitido(self):
        assert avaliar_envio_externo(remoto=False, permitido_na_config=False,
                                     origens={CorpusOrigem.REAL}, anonimizado=False).permitido

    def test_dados_reais_nunca_saem_da_maquina(self):
        decisao = avaliar_envio_externo(remoto=True, permitido_na_config=True,
                                        origens={CorpusOrigem.PUBLICO, CorpusOrigem.REAL}, anonimizado=True)
        assert not decisao.permitido and "real" in decisao.motivo

    def test_remoto_exige_autorizacao_e_anonimizacao(self):
        def envio(config, anonimizado):
            return avaliar_envio_externo(remoto=True, permitido_na_config=config, origens={CorpusOrigem.SINTETICO},
                                         anonimizado=anonimizado).permitido

        assert not envio(config=False, anonimizado=True)
        assert not envio(config=True, anonimizado=False)
        assert envio(config=True, anonimizado=True)

    def test_sem_origem_conhecida_e_bloqueado(self):
        decisao = avaliar_envio_externo(remoto=True, permitido_na_config=True, origens=set(), anonimizado=True)
        assert not decisao.permitido

    def test_exigir_lanca_excecao(self):
        with pytest.raises(PoliticaEnvioExternoViolada):
            exigir_envio_permitido(remoto=True, permitido_na_config=True, origens={CorpusOrigem.REAL}, anonimizado=True)


def test_mensagens_institucionais():
    assert MENSAGEM_AUSENCIA == "Não localizei essa informação nos documentos disponibilizados."
    assert "gestão" in AVISO_DECISAO
