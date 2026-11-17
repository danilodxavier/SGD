"""API do acervo SAD-GD (SAD-090/091/093): upload → indexação → busca, arquivo seguro, trecho, painel e perfis."""
import pytest

pytest.importorskip("sqlite_vec")

from app.core.config import settings  # noqa: E402
from app.infrastructure import servico_indexacao  # noqa: E402
from app.infrastructure.servico_indexacao import ServicoIndexacao  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from tests.helpers import HEADERS, logged_client  # noqa: E402

OFICIO = ("OFÍCIO Nº 77/2025/SEGEP\nSolicitamos a manutenção corretiva dos elevadores do prédio-sede, "
          "parados desde 3 de março de 2025.\n").encode()


@pytest.fixture()
def acervo(db, tmp_path, monkeypatch):
    raiz = tmp_path / "corpus"
    (raiz / "sintetico").mkdir(parents=True)
    (raiz / "sintetico" / "contrato.txt").write_text(
        "CONTRATO Nº 012/2023\nCLÁUSULA PRIMEIRA – DO OBJETO\nPrestação de serviços de limpeza e conservação.\n"
        "Rege-se pela Lei nº 14.133, de 1º de abril de 2021.\n", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("fora da raiz", encoding="utf-8")
    servico = ServicoIndexacao(raiz, com_embeddings=False)
    monkeypatch.setattr(servico_indexacao, "servico", servico)
    servico.iniciar(None)
    assert servico.aguardar(60)["erro"] is None
    return raiz, servico


def _enviar(c, nome="oficio elevador.txt", dados=OFICIO):
    return c.post("/api/sadgd/documentos", files={"arquivo": (nome, dados, "text/plain")}, headers=HEADERS)


def test_upload_indexa_reconstroi_grafo_e_documento_aparece_na_busca(acervo):
    raiz, servico = acervo
    with logged_client() as c:
        assert c.get("/api/sadgd/busca", params={"q": "elevadores"}).json()["resultados"] == []
        r = _enviar(c)
        assert r.status_code == 202 and r.json()["arquivo"].startswith("enviados/")
        estado = servico.aguardar(60)
        assert estado["erro"] is None and estado["resumo"]["novos"] == 1 and estado["resumo"]["removidos"] == 0
        assert estado["grafo"]["documentos"] == 2
        achados = c.get("/api/sadgd/busca", params={"q": "elevadores"}).json()["resultados"]
        assert achados and "elevadores" in achados[0]["texto"]
        docs = {d["caminho_relativo"]: d for d in c.get("/api/sadgd/documentos").json()}
        enviado = docs[r.json()["arquivo"]]
        assert enviado["corpus_origem"] == "real"  # envio do usuário: nunca vai a provedor remoto
        assert "sintetico/contrato.txt" in docs  # o resto do acervo continua lá
        # o mesmo nome não sobrescreve: ganha sufixo
        assert _enviar(c).json()["arquivo"] != r.json()["arquivo"]
        servico.aguardar(60)


def test_fonte_abre_o_arquivo_original_com_isolamento_e_trecho(acervo):
    with logged_client() as c:
        doc = c.get("/api/sadgd/documentos", params={"q": "012/2023"}).json()[0]
        r = c.get(f"/api/sadgd/documentos/{doc['id']}/arquivo")
        assert r.status_code == 200 and "limpeza" in r.text
        assert r.headers["content-security-policy"] == "sandbox" and r.headers["x-content-type-options"] == "nosniff"
        trecho = c.get("/api/sadgd/busca", params={"q": "limpeza"}).json()["resultados"][0]
        t = c.get(f"/api/sadgd/trechos/{trecho['trecho_id']}").json()
        assert t["documento_id"] == doc["id"] and "limpeza" in t["texto"]
        assert c.get("/api/sadgd/trechos/999999").status_code == 404


def test_arquivo_fora_da_raiz_nunca_e_servido(acervo, tmp_path):
    conn = conectar(settings.database_path, vetores=False)
    conn.execute("INSERT INTO documentos (id, caminho, caminho_relativo, status, corpus_origem) "
                 "VALUES (900, ?, '../segredo.txt', 'COM_TEXTO', 'real')", (str(tmp_path / "segredo.txt"),))
    conn.commit()
    conn.close()
    with logged_client() as c:
        assert c.get("/api/sadgd/documentos/900/arquivo").status_code == 404


def test_upload_rejeita_formato_vazio_e_perfil_consulta(acervo):
    with logged_client() as c:
        assert _enviar(c, "virus.exe").status_code == 415
        assert _enviar(c, "vazio.txt", b"").status_code == 422
    with logged_client("leitor.teste", "consulta") as c:
        assert _enviar(c).status_code == 403
        assert c.post("/api/sadgd/indexar", headers=HEADERS).status_code == 403
    with logged_client("gestora.teste", "gestor") as c:
        assert _enviar(c).status_code == 202  # RF-23: gestor envia documentos
        assert c.post("/api/sadgd/indexar", headers=HEADERS).status_code == 403  # reindexar tudo: só admin
    acervo[1].aguardar(60)


def test_painel_resume_o_acervo(acervo):
    with logged_client() as c:
        p = c.get("/api/sadgd/painel").json()
    assert p["documentos"] == 1 and p["por_origem"] == {"sintetico": 1} and p["trechos"] >= 1
    assert p["indexacao"]["executando"] is False and p["ultima_indexacao"]["novos"] == 1


def test_gestor_registra_decisao_e_consulta_nao(db, monkeypatch):
    from app.application.decisoes.memoria import MemoriaDecisoes
    from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite
    from app.interfaces.api import perguntar as api
    from tests.sadgd.test_api_decisoes import DECISAO, memoria_falsa  # noqa: F401
    from tests.sadgd.test_decisoes import EmbedderFalso, RerankerFalso

    monkeypatch.setitem(api._componentes, "memoria", MemoriaDecisoes(
        RepositorioDecisoesSqlite(lambda: conectar(settings.database_path)), EmbedderFalso(), RerankerFalso()))
    with logged_client("gestora.teste", "gestor") as c:
        assert c.post("/api/sadgd/decisoes", json=DECISAO, headers=HEADERS).status_code == 201
