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
    monkeypatch.setattr(settings, "ai_provider", "local")  # testes de IA usam um servidor simulado
    monkeypatch.setattr(settings, "ai_allow_remote", False)
    database.init_db()
    return settings.database_path


@pytest.fixture()
def indexed(db, docs_dir):
    from app.indexing.indexer import run_index

    database.set_setting("documents_root", str(docs_dir))
    result = run_index()
    return {"root": docs_dir, "result": result}
