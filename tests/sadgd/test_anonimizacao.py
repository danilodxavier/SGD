"""Anonimização LGPD (SAD-074, RF-25) e política de envio a provedores remotos (RNF-08) — TDD."""
import pytest

from app.application.agentes.politica_llm import LLMProtegido
from app.application.anonimizacao import anonimizar, restaurar
from app.application.portas import RespostaLLM
from app.domain.documentos import CorpusOrigem
from app.domain.politicas import PoliticaEnvioExternoViolada

TEXTO = ("Encaminhamos o requerimento do servidor Joaquim Pereira Lins, CPF 123.456.789-09, e-mail "
         "joaquim.lins@exemplo.vv.gov, telefone (99) 98877-1122, matrícula 204.551. Designar a servidora Ana Clara "
         "Moura Teles como fiscal. Assina: Henrique Bastos Lacerda, Secretário de Estado de Gestão Pública. "
         "Contrato com Brilho Serviços Gerais Ltda., CNPJ 41.258.763/0001-14, conforme a Lei nº 14.133.")


def test_mascara_dados_pessoais_e_preserva_dados_institucionais():
    anon, mapa = anonimizar(TEXTO)
    for dado in ("123.456.789-09", "joaquim.lins@exemplo.vv.gov", "(99) 98877-1122", "204.551", "Joaquim Pereira Lins",
                 "Ana Clara Moura Teles", "Henrique Bastos Lacerda"):
        assert dado not in anon, dado
    # pessoa jurídica, órgão, CNPJ e lei não são dados pessoais
    for mantido in ("Brilho Serviços Gerais Ltda.", "41.258.763/0001-14", "Secretário de Estado de Gestão Pública",
                    "Lei nº 14.133"):
        assert mantido in anon, mantido
    assert "[PESSOA_1]" in anon and "[CPF_1]" in anon and restaurar(anon, mapa) == TEXTO


def test_nome_nao_atravessa_quebra_de_linha_nem_usa_conector_maiusculo():
    # casos reais do corpus público: "Paulo Guedes\nEste Decreto..." e "Carlos De ..."
    anon, mapa = anonimizar("Paulo Guedes\nEste Decreto entra em vigor.")
    assert mapa == {"[PESSOA_1]": "Paulo Guedes"} and "Este Decreto" in anon
    _, mapa = anonimizar("Assinam Carlos De Souza e outros.")
    assert list(mapa.values()) == ["Carlos De Souza"]


def test_mesma_pessoa_recebe_o_mesmo_marcador():
    anon, _ = anonimizar("Joaquim Pereira Lins assinou. Depois, Joaquim Pereira Lins ratificou.")
    assert anon.count("[PESSOA_1]") == 2


class LLMRemotoFalso:
    nome, remoto = "remoto", True

    def __init__(self):
        self.recebido = None

    def chat(self, mensagens, **kw):
        self.recebido = mensagens
        return RespostaLLM("Resposta sobre [PESSOA_1].", "remoto", json={"resposta": "Fiscal: [PESSOA_1]"})


def test_remoto_com_dados_reais_e_bloqueado():
    llm = LLMProtegido(LLMRemotoFalso(), permitido_na_config=True, origens={CorpusOrigem.REAL})
    with pytest.raises(PoliticaEnvioExternoViolada):
        llm.chat([{"role": "user", "content": TEXTO}])


def test_remoto_com_corpus_academico_recebe_texto_anonimizado_e_resposta_e_restaurada():
    remoto = LLMRemotoFalso()
    llm = LLMProtegido(remoto, permitido_na_config=True, origens={CorpusOrigem.SINTETICO})
    r = llm.chat([{"role": "user", "content": TEXTO}])
    assert "Joaquim Pereira Lins" not in remoto.recebido[0]["content"]
    assert r.texto == "Resposta sobre Joaquim Pereira Lins." and r.json == {"resposta": "Fiscal: Joaquim Pereira Lins"}


def test_local_nao_e_alterado():
    class Local(LLMRemotoFalso):
        remoto = False

    local = Local()
    protegido = LLMProtegido(local, permitido_na_config=False, origens={CorpusOrigem.REAL})
    protegido.chat([{"role": "user", "content": TEXTO}])
    assert local.recebido[0]["content"] == TEXTO
