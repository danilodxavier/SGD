"""API da linha do tempo (SAD-063): autenticação, cronologia, relações com evidência e fases."""
import pytest

pytest.importorskip("sqlite_vec")

from app.application.linha_do_tempo.contradicoes import detectar_contradicoes  # noqa: E402
from app.application.linha_do_tempo.grafo import agrupar, classificar_relacoes  # noqa: E402
from app.application.linha_do_tempo.vigencia import revogacoes_por_relacao  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite  # noqa: E402
from tests.helpers import anonymous_client, logged_client  # noqa: E402

DOCS = [
    ("contrato.txt", "contrato", "012/2023", "2023-03-01", "CONTRATO Nº 012/2023\nO valor global do contrato é de "
     "R$ 1.200.000,00.\nInício em 01/03/2023 e término em 29/02/2024."),
    ("suspensao.txt", "ordem_suspensao", "004/2023", "2023-10-10", "Fica suspensa a execução do Contrato nº 012/2023."),
    ("reinicio.txt", "ordem_reinicio", "005/2023", "2023-12-04", "Fica retomada a execução do Contrato nº 012/2023."),
    ("relatorio.txt", "relatorio_fiscalizacao", "007/2024", "2024-03-08", "O Contrato nº 012/2023, de valor global de "
     "R$ 1.250.000,00, foi executado."),
]


@pytest.fixture()
def grafo(db):
    conn = conectar(settings.database_path)
    for i, (arq, tipo, numero, data, texto) in enumerate(DOCS, start=1):
        conn.execute("INSERT INTO documentos (id, caminho, caminho_relativo, status, corpus_origem, tipo_documental, "
                     "numero, data_documento, titulo) VALUES (?,?,?,?,?,?,?,?,?)",
                     (i, arq, f"sintetico/{arq}", "COM_TEXTO", "sintetico", tipo, numero, data, f"{tipo} {numero}"))
        conn.execute("INSERT INTO trechos (id, documento_id, ordem, texto) VALUES (?,?,1,?)", (i * 10, i, texto))
    conn.commit()
    conn.close()
    repo = RepositorioGrafoSqlite(lambda: conectar(settings.database_path, vetores=False))
    docs = repo.carregar()
    relacoes = classificar_relacoes(docs, detectar_contradicoes(docs))
    repo.salvar(agrupar(docs, relacoes), relacoes, revogacoes_por_relacao(relacoes), {d.id: d.titulo for d in docs})
    return repo


def test_exige_login(grafo):
    with anonymous_client() as c:
        assert c.get("/api/sadgd/processos").status_code == 401


def test_linha_do_tempo_por_documento(grafo):
    with logged_client() as c:
        processos = c.get("/api/sadgd/processos").json()
        assert processos[0]["chave"] == "012/2023" and processos[0]["documentos"] == 4
        r = c.get("/api/sadgd/linha-do-tempo", params={"documento_id": 1})
        assert r.status_code == 200
        tl = r.json()
    assert [e["documento_id"] for e in tl["eventos"]] == [1, 2, 3, 4]
    tipos = {(x["origem"], x["destino"]): x["tipo"] for x in tl["relacoes"]}
    assert tipos[(1, 2)] == "ruptura" and tipos[(2, 3)] == "retomada" and tipos[(1, 4)] == "contradicao"
    assert all(x["evidencia"]["texto"] for x in tl["relacoes"])  # toda relação com evidência
    assert [f["nome"] for f in tl["fases"]] == ["Execução", "Interrupção", "Execução retomada"]
    assert tl["inconsistencias"] and "contradição" in tl["inconsistencias"][0]


def test_conflitos_do_grafo_para_o_respondedor(grafo):
    conflitos = grafo.entre({1, 4})
    assert len(conflitos) == 1 and conflitos[0].campo == "valor_global"
    assert (conflitos[0].valor_vigente, conflitos[0].valor_declarado) == ("R$ 1.200.000,00", "R$ 1.250.000,00")


def test_parametros_obrigatorios_e_inexistentes(grafo):
    with logged_client() as c:
        assert c.get("/api/sadgd/linha-do-tempo").status_code == 422
        assert c.get("/api/sadgd/linha-do-tempo", params={"processo_id": 9999}).status_code == 404
