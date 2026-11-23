"""Valor do aditivo: o acréscimo/supressão não pode virar "valor atual" da ficha (erro visto em 2026-11-23)."""
import importlib.util
from pathlib import Path

from app.application.fichas.extracao import CAMPOS_ADITIVO, e_variacao, validar

TRECHO_ACRESCIMO = ("CLÁUSULA SEGUNDA – DO VALOR 2.1. Em decorrência do acréscimo, o valor mensal passa a ser de "
                    "R$ 114.950,00 e o valor global remanescente do período é acrescido de R$ 73.150,00.")
TRECHO_NOVO = "CLÁUSULA SEGUNDA – O valor global do contrato passa a ser de R$ 1.273.150,00."


def test_acrescimo_supressao_e_reducao_sao_variacao():
    assert e_variacao("R$ 73.150,00", TRECHO_ACRESCIMO)
    assert e_variacao("R$ 10.000,00", "Fica suprimido o valor de R$ 10.000,00 do contrato.")
    assert e_variacao("R$ 5.000,00", "com redução de R$ 5.000,00 no valor global")
    assert e_variacao("R$ 7.000,00", "acréscimo de 25%, equivalente a R$ 7.000,00")


def test_novo_valor_nao_e_variacao():
    assert not e_variacao("R$ 1.273.150,00", TRECHO_NOVO)
    assert not e_variacao("R$ 114.950,00", TRECHO_ACRESCIMO)  # "passa a ser de" é o novo valor mensal


def test_validar_recusa_acrescimo_como_valor_atual():
    trechos = [(8535, TRECHO_ACRESCIMO)]
    dados = {"valor_atual": {"valor": "R$ 73.150,00", "trecho": "T8535"}}
    assert validar(dados, trechos, CAMPOS_ADITIVO) == {}
    dados = {"valor_atual": {"valor": "R$ 1.273.150,00", "trecho": "T1"}}
    assert validar(dados, [(1, TRECHO_NOVO)], CAMPOS_ADITIVO)["valor_atual"]["trecho_id"] == 1


class _Repo:
    def __init__(self, fichas, trechos):
        self.fichas, self.trechos, self.salvas = fichas, trechos, []

    def todas(self):
        return self.fichas

    def trechos_do_documento(self, doc):
        return self.trechos.get(doc, [])

    def salvar(self, ficha):
        self.salvas.append(ficha)


def test_script_remove_so_o_valor_que_e_variacao():
    raiz = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("corrigir", raiz / "scripts" / "sadgd" / "corrigir_valor_atual.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    errada = {"campos": {"valor_global": {"valor": "R$ 1.200.000,00", "trecho_id": 1},
                         "valor_atual": {"valor": "R$ 73.150,00", "trecho_id": 8535},
                         "aditivo_valor": {"valor": "2024-08-05", "trecho_id": 8533, "documento_id": 7}}}
    certa = {"campos": {"valor_atual": {"valor": "R$ 1.273.150,00", "trecho_id": 9},
                        "aditivo_valor": {"valor": "2024", "trecho_id": 9, "documento_id": 8}}}
    repo = _Repo([errada, certa], {7: [(8535, TRECHO_ACRESCIMO)], 8: [(9, TRECHO_NOVO)]})
    assert mod.corrigir(repo)["variacao"] == 1 and repo.salvas == []  # simulação não grava
    r = mod.corrigir(repo, aplicar=True)
    assert r["variacao"] == 1 and repo.salvas == [errada]
    assert "valor_atual" not in errada["campos"] and "valor_global" in errada["campos"]
    assert "valor_atual" in certa["campos"]
