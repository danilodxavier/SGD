"""API de perguntas (SAD-076) e auditoria de consultas (SAD-075): orquestrador falso, sem LLM nem modelos."""
import hashlib
import json

import pytest

pytest.importorskip("sqlite_vec")

from app.application.agentes.especialistas import Parecer, RespostaF2  # noqa: E402
from app.application.agentes.roteador import rotear  # noqa: E402
from app.application.recuperacao.regras import TrechoRecuperado  # noqa: E402
from app.application.respostas.f1 import RespostaF1  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from app.interfaces.api import perguntar as api  # noqa: E402
from tests.helpers import HEADERS, anonymous_client, logged_client  # noqa: E402
from tests.sadgd.test_api_linha_do_tempo import grafo  # noqa: E402, F401 - fixture reaproveitada

TRECHO = TrechoRecuperado(10, 1, "O valor global do contrato é de R$ 1.200.000,00.", "contrato.txt",
                          "sintetico/contrato.txt", "contrato 012/2023", "Cláusula 2ª", None, "contrato", "sintetico",
                          "2023-03-01", False, None)


class OrquestradorFalso:
    def __init__(self, tracer):
        self.tracer = tracer

    def executar(self, pergunta):
        decisao = rotear(pergunta)
        with self.tracer.span("rotear"):
            pass
        if decisao.rota == "F2":
            p = Parecer("gestor_publico", {"parecer": "Viável.", "confianca": 0.7}, True, True, tokens_entrada=100,
                        tokens_saida=20)
            r = RespostaF2("Recomenda-se prorrogar.", {"recomendacao": "Prorrogar", "confianca": 0.7}, [TRECHO], [p],
                           True, tokens_entrada=200, tokens_saida=40)
            return {"decisao": decisao, "resposta": r, "pareceres": [p], "tempos": [("relator", 5)]}
        r = RespostaF1("O valor global é R$ 1.200.000,00 [T10].", "respondida", 0.9, [TRECHO], tokens_entrada=300,
                       tokens_saida=30)
        return {"decisao": decisao, "resposta": r, "pareceres": [], "tempos": [("responder_f1", 7)]}


@pytest.fixture()
def falso(db, monkeypatch):
    monkeypatch.setitem(api._componentes, "fabrica_orquestrador", OrquestradorFalso)


def _linhas(sql):
    conn = conectar(settings.database_path, vetores=False)
    try:
        return [tuple(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def test_exige_login(falso):
    with anonymous_client() as c:
        assert c.post("/api/sadgd/perguntar", json={"pergunta": "Qual o valor?"}, headers=HEADERS).status_code == 401


def test_f1_responde_com_fontes_e_registra_auditoria_sem_texto_da_pergunta(falso):
    pergunta = "Qual o valor global do Contrato nº 012/2023?"
    with logged_client() as c:
        r = c.post("/api/sadgd/perguntar", json={"pergunta": pergunta}, headers=HEADERS)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["rota"].startswith("F1") and corpo["fontes"][0]["trecho_id"] == 10 and corpo["aviso"]
    cid = corpo["consulta_id"]
    (h, rota, tin, tout, lat), = _linhas(f"SELECT pergunta_hash, rota, tokens_entrada, tokens_saida, latencia_ms "
                                         f"FROM consultas WHERE id = {cid}")
    assert h == hashlib.sha256(pergunta.encode()).hexdigest() and rota == corpo["rota"] and (tin, tout) == (300, 30)
    assert lat is not None and _linhas(f"SELECT trecho_id FROM consulta_fontes WHERE consulta_id = {cid}") == [(10,)]
    assert _linhas(f"SELECT acao FROM auditoria WHERE alvo = 'consulta:{cid}'") == [("consulta",)]
    assert _linhas(f"SELECT no FROM spans WHERE consulta_id = {cid}") == [("rotear",)]
    assert pergunta not in json.dumps(_linhas("SELECT * FROM consultas"))  # LGPD: só o hash


def test_f2_devolve_pareceres_e_grava_pareceres(falso):
    with logged_client() as c:
        corpo = c.post("/api/sadgd/perguntar",
                       json={"pergunta": "Devemos prorrogar o Contrato nº 012/2023? Recomende a melhor decisão."},
                       headers=HEADERS).json()
    assert corpo["rota"] == "F2" and corpo["pareceres"][0]["agente"] == "gestor_publico" and corpo["confianca"] == 0.7
    assert _linhas(f"SELECT agente, valido FROM pareceres WHERE consulta_id = {corpo['consulta_id']}") == [
        ("gestor_publico", 1)]
    assert _linhas(f"SELECT tokens_entrada FROM consultas WHERE id = {corpo['consulta_id']}") == [(300,)]


def test_falha_do_orquestrador_vira_503_e_fica_auditada(db, monkeypatch):
    class Quebrado:
        def __init__(self, tracer):
            pass

        def executar(self, pergunta):
            raise RuntimeError("ollama fora")

    monkeypatch.setitem(api._componentes, "fabrica_orquestrador", Quebrado)
    with logged_client() as c:
        r = c.post("/api/sadgd/perguntar", json={"pergunta": "Qual o valor?"}, headers=HEADERS)
    assert r.status_code == 503 and "RuntimeError" in r.json()["detail"]
    assert _linhas("SELECT count(*) FROM consultas WHERE latencia_ms IS NOT NULL") == [(1,)]


def test_resumo_da_linha_do_tempo_para_f2(grafo):  # noqa: F811
    texto = grafo.resumo({1})
    assert texto.startswith("LINHA DO TEMPO") and "ruptura" in texto and "retomada" in texto
    assert texto.index("2023-03-01") < texto.index("2023-10-10") and grafo.resumo(set()) == ""


def test_cache_semantico_reaproveita_so_a_mesma_pergunta_e_audita(db, monkeypatch):
    chamadas = []

    class Contador(OrquestradorFalso):
        def executar(self, pergunta):
            chamadas.append(pergunta)
            return super().executar(pergunta)

    monkeypatch.setitem(api._componentes, "fabrica_orquestrador", Contador)
    pergunta = "Qual o valor global do Contrato nº 012/2023?"
    with logged_client() as c:
        primeira = c.post("/api/sadgd/perguntar", json={"pergunta": pergunta}, headers=HEADERS).json()
        segunda = c.post("/api/sadgd/perguntar", json={"pergunta": "  qual o valor global do contrato nº 012/2023 "},
                         headers=HEADERS).json()
        outra = c.post("/api/sadgd/perguntar", json={"pergunta": "Qual o valor global do Contrato nº 044/2023?"},
                       headers=HEADERS).json()
        sem = c.post("/api/sadgd/perguntar", json={"pergunta": pergunta, "usar_cache": False}, headers=HEADERS).json()
    assert (primeira["cache"], segunda["cache"], outra["cache"], sem["cache"]) == (False, True, False, False)
    assert len(chamadas) == 3 and segunda["resposta"] == primeira["resposta"]
    assert segunda["consulta_id"] != primeira["consulta_id"]  # toda consulta é auditada, mesmo vinda do cache
    assert _linhas(f"SELECT cache_hit, tokens_entrada FROM consultas WHERE id = {segunda['consulta_id']}") == [(1, 0)]
    assert _linhas(f"SELECT trecho_id FROM consulta_fontes WHERE consulta_id = {segunda['consulta_id']}") == [(10,)]


def test_construir_orquestrador_entrega_lista_de_trechos_ao_grafo(monkeypatch):
    """Regressão (Fase 11): o recuperador real devolve ResultadoRecuperacao; o orquestrador espera a lista de trechos.

    Os demais testes da API e o E2E substituem o orquestrador, por isso a montagem real nunca era exercitada."""
    from app.application.recuperacao.hibrida import ResultadoRecuperacao

    class RecuperadorReal:
        def recuperar(self, pergunta, k=8):
            return ResultadoRecuperacao(pergunta, [TRECHO][:k])

    monkeypatch.setitem(api._componentes, "recuperador", RecuperadorReal())
    monkeypatch.setitem(api._componentes, "memoria", object())
    orq = api.construir_orquestrador()
    trechos = orq._recuperar_no({"pergunta": "Qual o valor global do contrato 012/2023?"})["trechos"]
    assert isinstance(trechos, list) and trechos[0].id == TRECHO.id


def test_consulta_pela_fila_devolve_numero_na_hora_e_resultado_ao_dono(falso):
    import time

    with logged_client() as c:
        r = c.post("/api/sadgd/consultas", json={"pergunta": "Qual o valor global do Contrato nº 012/2023?",
                                                 "usar_cache": False}, headers=HEADERS)
        assert r.status_code == 202 and r.json()["estado"] in ("fila", "processando", "concluida")
        cid = r.json()["id"]
        for _ in range(200):
            s = c.get(f"/api/sadgd/consultas/{cid}").json()
            if s["estado"] in ("concluida", "erro"):
                break
            time.sleep(0.02)
    assert s["estado"] == "concluida" and s["resultado"]["rota"].startswith("F1")
    assert s["resultado"]["fontes"][0]["trecho_id"] == 10 and s["resultado"]["consulta_id"]
    with logged_client("outro.gestor", "consulta") as outro:
        assert outro.get(f"/api/sadgd/consultas/{cid}").status_code == 404


def test_linha_do_tempo_limitada_traz_os_eventos_mais_recentes(grafo):  # noqa: F811
    """Rodada 12: com limite de eventos, entram os mais recentes (antes, os mais antigos e os sem data)."""
    texto = grafo.resumo({1}, max_processos=1, max_eventos=2)
    assert "2024-03-08" in texto and "2023-12-04" in texto and "2023-03-01" not in texto
    assert texto.index("2023-12-04") < texto.index("2024-03-08")  # exibidos em ordem cronológica
