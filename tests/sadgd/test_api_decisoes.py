"""API da memória de decisões (SAD-082): perfis, auditoria, resultado e precedentes."""
import pytest

pytest.importorskip("sqlite_vec")

from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from app.interfaces.api import perguntar as api  # noqa: E402
from tests.helpers import HEADERS, logged_client  # noqa: E402
from tests.sadgd.test_decisoes import EmbedderFalso, RerankerFalso  # noqa: E402

DECISAO = {"titulo": "Prorrogação do contrato de vigilância", "decisao": "Prorrogar por 12 meses.",
           "data": "2025-07-30", "contexto": "Sem ocorrências.", "codigo": "DG-011/2025"}


@pytest.fixture()
def memoria_falsa(db, monkeypatch):
    from app.application.decisoes.memoria import MemoriaDecisoes
    from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite

    m = MemoriaDecisoes(RepositorioDecisoesSqlite(lambda: conectar(settings.database_path)), EmbedderFalso(),
                        RerankerFalso(), limiar_rerank=0.1)
    monkeypatch.setitem(api._componentes, "memoria", m)
    return m


def test_consulta_nao_registra_decisao(memoria_falsa):
    with logged_client("leitor.teste", "consulta") as c:
        assert c.post("/api/sadgd/decisoes", json=DECISAO, headers=HEADERS).status_code == 403
        assert c.get("/api/sadgd/decisoes").json() == []


def test_admin_registra_avalia_resultado_e_precedente_e_recuperado(memoria_falsa):
    with logged_client() as c:
        r = c.post("/api/sadgd/decisoes", json=DECISAO, headers=HEADERS)
        assert r.status_code == 201 and r.json()["avaliacao_resultado"] == "pendente"
        did = r.json()["id"]
        r = c.patch(f"/api/sadgd/decisoes/{did}/resultado", headers=HEADERS,
                    json={"resultado": "Execução regular.", "avaliacao_resultado": "positivo"})
        assert r.json()["avaliacao_resultado"] == "positivo"
        assert c.patch("/api/sadgd/decisoes/999/resultado", headers=HEADERS,
                       json={"resultado": "x x x", "avaliacao_resultado": "neutro"}).status_code == 404
        prec = c.get("/api/sadgd/precedentes", params={"pergunta": "prorrogar o contrato de vigilância"}).json()
        assert prec[0]["codigo"] == "DG-011/2025" and prec[0]["licao"].startswith("resultado positivo")
        assert c.post("/api/sadgd/decisoes", json={**DECISAO, "titulo": ""}, headers=HEADERS).status_code == 422
    conn = conectar(settings.database_path, vetores=False)
    acoes = [r[0] for r in conn.execute("SELECT acao FROM auditoria WHERE alvo = ?", (f"decisao:{did}",))]
    conn.close()
    assert acoes == ["registrar_decisao", "avaliar_resultado_decisao"]
