import pytest

from app.core import database
from app.core.config import settings
from tests import sample_docs


@pytest.fixture()
def docs_dir(tmp_path):
    return sample_docs.build(tmp_path / "documentos")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "test.db")
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")  # relatórios e cache fora do projeto
    monkeypatch.setattr(settings, "ocr_enabled", False)  # testes de OCR o ativam explicitamente
    # independente do .env da máquina (publicada na LAN, ex.: APP_HOST = IP da rede): testes rodam em modo local
    monkeypatch.setattr(settings, "app_host", "127.0.0.1")
    monkeypatch.setattr(settings, "allowed_hosts", [])
    monkeypatch.setattr(settings, "ssl_certfile", "")
    monkeypatch.setattr(settings, "ssl_keyfile", "")
    monkeypatch.setattr(settings, "ai_provider", "local")  # testes de IA usam um servidor simulado
    monkeypatch.setattr(settings, "ai_allow_remote", False)
    database.init_db()
    return settings.database_path


@pytest.fixture()
def indexed(db, docs_dir, monkeypatch):
    """Documentos de amostra (PDF, DOCX, XLSX, digitalizado, corrompido…) indexados pelo indexador do SAD-GD."""
    from app.infrastructure import servico_indexacao
    from app.infrastructure.servico_indexacao import ServicoIndexacao

    database.set_setting("documents_root", str(docs_dir))
    servico = ServicoIndexacao(docs_dir, com_embeddings=False)
    monkeypatch.setattr(servico_indexacao, "servico", servico)
    servico.iniciar(None)
    estado = servico.aguardar(120)
    assert estado["erro"] is None, estado["erro"]
    return {"root": docs_dir, "result": estado}
