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


def test_pergunta(client):
    r = client.post("/api/ask", json={"question": "Qual o objeto do contrato 034/2022?"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["kind"] == "FATO_DOCUMENTAL"


def test_post_sem_cabecalho_e_bloqueado(client):
    r = client.post("/api/ask", json={"question": "teste"})
    assert r.status_code == 403


def test_host_externo_bloqueado(indexed):
    with anonymous_client(base_url="http://exemplo.com") as c:
        assert c.get("/health").status_code == 403


def test_documentos_e_arquivo(client):
    data = client.get("/api/documents").json()
    assert data["total"] == 11
    pdf = next(d for d in data["items"] if d["filename"] == "Contrato_034_2022.pdf")
    detail = client.get(f"/api/documents/{pdf['id']}").json()
    assert detail["chunks"] > 0
    r = client.get(f"/api/documents/{pdf['id']}/file")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_config_rejeita_diretorio_inexistente(client):
    r = client.post("/api/config", json={"documents_root": r"Z:\nao\existe"}, headers=HEADERS)
    assert r.status_code == 400
    assert "não existe" in r.json()["detail"]


def test_status_dashboard(client):
    data = client.get("/api/status").json()
    assert data["found"] == 11 and data["contracts"] == 1 and data["errors"] == 1


def test_busca(client):
    data = client.get("/api/search", params={"q": "limpeza"}).json()
    assert data["results"]


def test_erro_nao_expoe_traceback(client):
    r = client.get("/api/documents/999999")
    assert r.status_code == 404
    assert "Traceback" not in r.text
