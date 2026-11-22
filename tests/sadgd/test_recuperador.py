"""RecuperadorHibrido de ponta a ponta: SQLite real (FTS5 + sqlite-vec), embedder e reranker falsos."""
import pytest

pytest.importorskip("sqlite_vec")

from app.application.ingestao.indexador import IndexarCorpus  # noqa: E402
from app.application.recuperacao.hibrida import RecuperadorHibrido  # noqa: E402
from app.infrastructure.extratores.adaptador import extensoes_suportadas, extrair  # noqa: E402
from app.infrastructure.fonte_arquivos import listar, sha256  # noqa: E402
from app.infrastructure.sqlite.busca import BuscaLexicalSqlite, RepositorioTrechosSqlite  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar, migrar  # noqa: E402
from app.infrastructure.sqlite.repositorio_indexacao import RepositorioIndexacaoSqlite  # noqa: E402
from app.infrastructure.sqlite.vetores import SqliteVecStore  # noqa: E402
from tests.sadgd.test_indexador import EmbedderFalso  # noqa: E402

LEI_ANTIGA = """LEI Nº 1.111, DE 2 DE JANEIRO DE 1990
Art. 1º [REVOGADO] A dispensa de licitação ocorre nos casos de emergência antiga.
Art. 2º Esta Lei trata de almoxarifado.
"""
LEI_NOVA = """LEI Nº 2.222, DE 2 DE JANEIRO DE 2030
Art. 75. É dispensável a licitação nos casos de emergência ou calamidade pública.
Art. 76. A alienação de bens imóveis dependerá de autorização legislativa.
"""


class RerankerTextoCurto:
    """Favorece textos mais curtos — basta para verificar que a reordenação é aplicada."""

    def pontuar(self, consulta, textos):
        return [-len(t) for t in textos]


class RerankerSobreposicao:
    """Pontua pela quantidade de palavras da pergunta presentes no texto (aproximação de um cross-encoder)."""

    def pontuar(self, consulta, textos):
        palavras = {p for p in consulta.lower().split() if len(p) > 3}
        return [sum(p in t.lower() for p in palavras) for t in textos]


@pytest.fixture()
def recuperador(tmp_path):
    raiz = tmp_path / "corpus" / "publico"
    raiz.mkdir(parents=True)
    (raiz / "antiga.txt").write_text(LEI_ANTIGA, encoding="utf-8")
    (raiz / "nova.txt").write_text(LEI_NOVA, encoding="utf-8")
    banco = tmp_path / "sadgd.db"
    conn = conectar(banco)
    migrar(conn)
    conn.close()

    def fabrica():
        return conectar(banco)

    embedder = EmbedderFalso()
    IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256, embedder,
                  SqliteVecStore(fabrica), modelo="falso").executar(str(raiz.parent), listar(raiz.parent,
                                                                                           extensoes_suportadas(),
                                                                                           excluir=()))

    def criar(reranker=None):
        return RecuperadorHibrido(BuscaLexicalSqlite(fabrica), RepositorioTrechosSqlite(fabrica), embedder,
                                  SqliteVecStore(fabrica), reranker)

    return criar


@pytest.mark.parametrize("modo", ["bm25", "denso", "hibrido", "hibrido_rerank"])
def test_todos_os_modos_encontram_o_dispositivo_vigente(recuperador, modo):
    r = recuperador(RerankerSobreposicao()).recuperar("dispensa de licitação em emergência", k=3, modo=modo)
    assert r.trechos, modo
    assert any(t.dispositivo == "art. 75" for t in r.trechos)
    assert all(not t.revogado for t in r.trechos)  # dispositivo tachado não fundamenta resposta atual


def test_revogado_vai_para_historico_e_pode_ser_incluido(recuperador):
    rec = recuperador()
    padrao = rec.recuperar("dispensa de licitação emergência antiga", k=5, modo="hibrido")
    assert any(t.revogado for t in padrao.historico)
    com_historico = rec.recuperar("dispensa de licitação emergência antiga", k=5, modo="hibrido",
                                  incluir_historico=True)
    assert any(t.revogado for t in com_historico.trechos)


def test_reranker_reordena_e_metadados_vem_completos(recuperador):
    r = recuperador(RerankerTextoCurto()).recuperar("lei almoxarifado alienação bens", k=4, modo="hibrido_rerank")
    tamanhos = [len(t.texto) for t in r.trechos]
    assert tamanhos == sorted(tamanhos)
    t = r.trechos[0]
    assert t.corpus_origem == "publico" and t.arquivo.endswith(".txt") and t.rotulo.startswith("T")
    assert "rerank" in r.tempos_ms


def test_modo_invalido(recuperador):
    with pytest.raises(ValueError):
        recuperador().recuperar("x", modo="magico")


def test_textos_identicos_de_copias_ocupam_uma_vaga_so():
    from app.application.recuperacao.hibrida import sem_duplicatas
    from app.application.recuperacao.regras import TrechoRecuperado

    def t(id_, texto):
        return TrechoRecuperado(id_, id_, texto, "a.pdf", f"p{id_}/a.pdf", None, None, None, None, "real", None,
                                False, None)
    saida = sem_duplicatas([t(1, "Cláusula 1. Objeto."), t(2, "Cláusula  1.\nObjeto."), t(3, "Cláusula 2. Prazo.")])
    assert [x.id for x in saida] == [1, 3]  # mantém a primeira (maior pontuação); espaços não contam


def test_escopo_do_contrato_mistura_contrato_e_reserva_do_acervo():
    from app.application.portas import ResultadoBusca
    from app.application.recuperacao.hibrida import RecuperadorHibrido
    from app.application.recuperacao.regras import TrechoRecuperado

    class Lexical:
        def buscar(self, expr, k):
            return [ResultadoBusca(i, 1.0 / i, "bm25") for i in range(1, 11)]

    class Repo:
        def obter(self, ids):
            return [TrechoRecuperado(i, i, f"texto distinto {i}", "a.pdf", f"p/{i}.pdf", None, None, None, None,
                                     "real", None, False, None) for i in ids]

    rec = RecuperadorHibrido(Lexical(), Repo())
    trechos = rec.recuperar("pergunta de teste", k=8, modo="bm25", documentos={6, 7, 8, 9, 10}).trechos
    ids = {t.id for t in trechos}
    assert {6, 7, 8, 9, 10} <= ids and len(ids - {6, 7, 8, 9, 10}) == 3  # 5 do contrato + 3 do acervo
    poucos = rec.recuperar("pergunta de teste", k=8, modo="bm25", documentos={10}).trechos
    assert [t.id for t in poucos] == list(range(1, 9))  # menos de 3 no escopo: acervo inteiro
