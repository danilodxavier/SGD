"""Cache semântico de perguntas (prompt mestre §5; Fase 10) — TDD.

Reaproveita a resposta de uma pergunta equivalente, mas NUNCA entre perguntas com identificadores diferentes
(nº de contrato, lei, ano, valor) e nunca depois que o acervo ou a memória de decisões mudou."""
import pytest

from app.application.cache_semantico import CacheSemantico, identificadores, normalizar
from tests.sadgd.test_decisoes import EmbedderFalso

pytest.importorskip("sqlite_vec")


def test_normalizacao_e_identificadores():
    assert normalizar("  Qual o VALOR do contrato?? ") == "qual o valor do contrato"
    assert identificadores("Contrato nº 012/2023, Lei 14.133 e R$ 1.200,00") == {"012/2023", "14.133", "1.200,00"}
    assert identificadores("Qual o objeto?") == set()


@pytest.fixture()
def cache(db):
    from app.core.config import settings
    from app.infrastructure.sqlite.cache_semantico import RepositorioCacheSqlite
    from app.infrastructure.sqlite.conexao import conectar

    return CacheSemantico(RepositorioCacheSqlite(lambda: conectar(settings.database_path)), EmbedderFalso(),
                          limiar=0.8)


def test_reaproveita_pergunta_igual_ou_parafraseada_na_mesma_versao(cache):
    cache.gravar("Qual o valor global do Contrato nº 012/2023?", {"resposta": "R$ 1.200.000,00"}, "v1")
    assert cache.buscar("qual o valor global do contrato nº 012/2023", "v1")["resposta"] == "R$ 1.200.000,00"
    assert cache.buscar("Qual é o valor global do Contrato nº 012/2023?", "v1") is not None  # paráfrase próxima


def test_nunca_mistura_identificadores_diferentes(cache):
    cache.gravar("Qual o valor global do Contrato nº 012/2023?", {"resposta": "R$ 1.200.000,00"}, "v1")
    assert cache.buscar("Qual o valor global do Contrato nº 044/2023?", "v1") is None
    assert cache.buscar("Qual o valor global do contrato?", "v1") is None  # sem o número: outra pergunta


def test_mudanca_no_acervo_invalida(cache):
    cache.gravar("Qual o valor global do Contrato nº 012/2023?", {"resposta": "R$ 1.200.000,00"}, "v1")
    assert cache.buscar("Qual o valor global do Contrato nº 012/2023?", "v2") is None


def test_pergunta_sem_relacao_nao_reaproveita(cache):
    cache.gravar("Qual o valor global do Contrato nº 012/2023?", {"resposta": "x"}, "v1")
    assert cache.buscar("Quem assina a portaria de teletrabalho?", "v1") is None
