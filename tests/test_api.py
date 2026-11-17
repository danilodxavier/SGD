"""API: saúde, painel, proteção CSRF/host, acervo de amostra (formatos reais) e mensagens de erro sem traceback."""
import pytest

from tests.helpers import anonymous_client, logged_client

HEADERS = {"X-Requested-With": "AgenteDocumental"}


@pytest.fixture()
def client(indexed):
    with logged_client() as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok", "documents_root": "ok", "index": "ok"}


def test_painel_servido(client):
    r = client.get("/")
    assert r.status_code == 200 and "SAD-GD" in r.text


def test_post_sem_cabecalho_e_bloqueado(client):
    r = client.post("/api/sadgd/perguntar", json={"pergunta": "teste de CSRF"})
    assert r.status_code == 403


def test_host_externo_bloqueado(indexed):
    with anonymous_client(base_url="http://exemplo.com") as c:
        assert c.get("/health").status_code == 403


def test_acervo_de_amostra_e_arquivo_original(client, indexed):
    resumo = indexed["result"]["resumo"]
    assert resumo["encontrados"] == 11 and resumo["erros"] >= 1  # o arquivo corrompido proposital
    docs = client.get("/api/sadgd/documentos").json()
    pdf = next(d for d in docs if d["caminho_relativo"].endswith("Contrato_034_2022.pdf"))
    assert pdf["trechos"] > 0
    r = client.get(f"/api/sadgd/documentos/{pdf['id']}/arquivo")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_config_rejeita_diretorio_inexistente(client):
    r = client.post("/api/config", json={"documents_root": r"Z:\nao\existe"}, headers=HEADERS)
    assert r.status_code == 400
    assert "não existe" in r.json()["detail"]


def test_painel_e_busca_no_acervo_de_amostra(client):
    p = client.get("/api/sadgd/painel").json()
    assert p["documentos"] >= 10 and p["trechos"] > 0
    assert client.get("/api/sadgd/busca", params={"q": "limpeza"}).json()["resultados"]


def test_erro_nao_expoe_traceback(client):
    r = client.get("/api/sadgd/trechos/999999")
    assert r.status_code == 404
    assert "Traceback" not in r.text
