"""IndexarCorpus de ponta a ponta (RF-05): SQLite real + sqlite-vec + embedder falso determinístico."""
import hashlib
import math

import pytest

pytest.importorskip("sqlite_vec")

from app.application.ingestao.indexador import IndexarCorpus, origem_por_caminho  # noqa: E402
from app.domain.documentos import CorpusOrigem  # noqa: E402
from app.infrastructure.extratores.adaptador import extensoes_suportadas, extrair  # noqa: E402
from app.infrastructure.fonte_arquivos import listar, sha256  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar, migrar  # noqa: E402
from app.infrastructure.sqlite.repositorio_indexacao import RepositorioIndexacaoSqlite  # noqa: E402
from app.infrastructure.sqlite.vetores import SqliteVecStore  # noqa: E402


class EmbedderFalso:
    """Vetor determinístico por bag-of-words com hashing: textos iguais → vetores iguais."""
    dimensao = 1024

    def __init__(self):
        self.chamadas = 0

    def embed(self, textos):
        self.chamadas += 1
        saida = []
        for t in textos:
            v = [0.0] * 1024
            for palavra in t.lower().split():
                v[int(hashlib.md5(palavra.encode()).hexdigest(), 16) % 1024] += 1.0  # noqa: S324 - não criptográfico
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            saida.append([x / n for x in v])
        return saida


LEI = """LEI Nº 77.777, DE 2 DE JANEIRO DE 2030
Dispõe sobre testes de indexação.
Art. 1º Esta Lei trata de prorrogação de contratos de limpeza.
Art. 2º A vigência máxima é de dez anos.
"""
CONTRATO = """CONTRATO Nº 001/2030
CLÁUSULA PRIMEIRA – DO OBJETO
1.1. Serviços de vigilância patrimonial armada.
CLÁUSULA SEGUNDA – DA VIGÊNCIA
2.1. O prazo de vigência deste contrato é de 12 (doze) meses, com início em 01/01/2030 e término em 31/12/2030.
"""


@pytest.fixture()
def ambiente(tmp_path):
    raiz = tmp_path / "corpus"
    (raiz / "publico").mkdir(parents=True)
    (raiz / "sintetico").mkdir()
    (raiz / "outros").mkdir()
    (raiz / "publico" / "lei.txt").write_text(LEI, encoding="utf-8")
    (raiz / "sintetico" / "contrato.txt").write_text(CONTRATO, encoding="utf-8")
    banco = tmp_path / "sadgd.db"
    conn = conectar(banco)
    migrar(conn)
    conn.close()

    def fabrica():
        return conectar(banco)

    embedder = EmbedderFalso()
    caso = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256, embedder,
                         SqliteVecStore(fabrica), modelo="falso")

    def indexar():
        return caso.executar(str(raiz), listar(raiz, extensoes_suportadas(), excluir=()))

    return raiz, fabrica, indexar, embedder


def test_primeira_indexacao_grava_documentos_trechos_metadados_e_vetores(ambiente):
    raiz, fabrica, indexar, _ = ambiente
    r = indexar()
    assert (r.encontrados, r.novos, r.erros) == (2, 2, 0)
    assert r.trechos == r.vetores and r.trechos >= 5
    conn = fabrica()
    docs = {d["caminho_relativo"]: d for d in conn.execute("SELECT * FROM documentos")}
    assert docs["publico/lei.txt"]["corpus_origem"] == "publico"
    assert docs["publico/lei.txt"]["tipo_documental"] == "lei" and docs["publico/lei.txt"]["numero"] == "77.777"
    assert docs["sintetico/contrato.txt"]["vigencia_fim"] == "2030-12-31"
    assert docs["sintetico/contrato.txt"]["modelo_embedding"] == "falso"
    norma = conn.execute("SELECT especie, nivel, situacao FROM normas").fetchone()
    assert tuple(norma) == ("lei", 2, "vigente")
    disp = [r[0] for r in conn.execute("SELECT dispositivo FROM trechos ORDER BY documento_id, ordem")]
    assert "art. 2º" in disp and "cláusula segunda" in disp
    assert conn.execute("SELECT count(*) FROM trechos_fts WHERE trechos_fts MATCH 'vigilancia'").fetchone()[0] == 1
    conn.close()


def test_reindexar_sem_mudancas_nao_processa_nada(ambiente):
    _, _, indexar, embedder = ambiente
    indexar()
    chamadas = embedder.chamadas
    r = indexar()
    assert (r.novos, r.alterados, r.inalterados, r.trechos) == (0, 0, 2, 0)
    assert embedder.chamadas == chamadas


def test_arquivo_novo_alterado_e_removido(ambiente):
    raiz, fabrica, indexar, embedder = ambiente
    indexar()
    (raiz / "outros" / "nota.txt").write_text("Nota técnica sobre jardinagem e paisagismo.\n", encoding="utf-8")
    (raiz / "publico" / "lei.txt").write_text(LEI + "Art. 3º Dispositivo novo sobre teletrabalho.\n",
                                              encoding="utf-8")
    (raiz / "sintetico" / "contrato.txt").unlink()
    r = indexar()
    assert (r.novos, r.alterados, r.removidos) == (1, 1, 1)
    conn = fabrica()
    origem = conn.execute("SELECT corpus_origem FROM documentos WHERE caminho_relativo='outros/nota.txt'").fetchone()
    assert origem[0] == "real"  # fora de publico/sintetico: origem mais restritiva
    assert conn.execute("SELECT count(*) FROM trechos_fts WHERE trechos_fts MATCH 'vigilancia'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM trechos").fetchone()[0] == conn.execute(
        "SELECT count(*) FROM trechos_vec").fetchone()[0]
    conn.close()
    vetor = embedder.embed(["Nota técnica sobre jardinagem e paisagismo."])[0]
    melhor = SqliteVecStore(fabrica).buscar(vetor, 1)[0]
    conn = fabrica()
    texto = conn.execute("SELECT texto FROM trechos WHERE id = ?", (melhor.trecho_id,)).fetchone()[0]
    conn.close()
    assert "jardinagem" in texto and melhor.pontuacao > 0.9


def test_documento_gravado_sem_vetores_e_reprocessado(ambiente):
    """Interrupção entre gravar o documento e gravar os vetores não pode deixá-lo sem embeddings para sempre."""
    raiz, fabrica, _, embedder = ambiente
    sem_vetores = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256, None,
                                None, modelo="")
    sem_vetores.executar(str(raiz), listar(raiz, extensoes_suportadas(), excluir=()))
    conn = fabrica()
    assert conn.execute("SELECT count(*) FROM trechos_vec").fetchone()[0] == 0
    conn.close()
    com_vetores = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256,
                                embedder, SqliteVecStore(fabrica), modelo="falso")
    r = com_vetores.executar(str(raiz), listar(raiz, extensoes_suportadas(), excluir=()))
    assert r.alterados == 2 and r.vetores == r.trechos > 0
    assert com_vetores.executar(str(raiz), listar(raiz, extensoes_suportadas(), excluir=())).inalterados == 2


def test_limite_de_tempo_interrompe_sem_remover_arquivos_nao_vistos(ambiente):
    raiz, fabrica, indexar, embedder = ambiente
    indexar()
    (raiz / "outros" / "a.txt").write_text("Documento novo A sobre diárias.\n", encoding="utf-8")
    caso = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256, embedder,
                         SqliteVecStore(fabrica), modelo="falso")
    r = caso.executar(str(raiz), listar(raiz, extensoes_suportadas(), excluir=()), limite_segundos=0)
    assert r.interrompido and r.removidos == 0
    conn = fabrica()
    assert conn.execute("SELECT count(*) FROM documentos").fetchone()[0] >= 2  # nada foi apagado
    conn.close()
    r2 = caso.executar(str(raiz), listar(raiz, extensoes_suportadas(), excluir=()))
    assert not r2.interrompido and r2.novos == 1 and r2.vetores == r2.trechos


def test_origem_por_caminho():
    assert origem_por_caminho("publico/federal/lei/x.htm", CorpusOrigem.REAL) is CorpusOrigem.PUBLICO
    assert origem_por_caminho("sintetico/P01/x.docx", CorpusOrigem.REAL) is CorpusOrigem.SINTETICO
    assert origem_por_caminho("contratos/x.pdf", CorpusOrigem.REAL) is CorpusOrigem.REAL


def test_indexacao_parcial_de_um_arquivo_enviado_nao_remove_o_resto(ambiente):
    raiz, fabrica, indexar, embedder = ambiente
    indexar()
    enviado = raiz / "enviados" / "oficio.txt"
    enviado.parent.mkdir()
    enviado.write_text("Ofício sobre manutenção de elevadores do prédio-sede.\n", encoding="utf-8")
    caso = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), lambda c: extrair(c, ocr=None), sha256, embedder,
                         SqliteVecStore(fabrica), modelo="falso")
    so_ele = [a for a in listar(raiz, extensoes_suportadas(), excluir=()) if a.relativo == "enviados/oficio.txt"]
    r = caso.executar(str(raiz), so_ele, parcial=True)
    assert (r.novos, r.removidos) == (1, 0)
    conn = fabrica()
    assert conn.execute("SELECT count(*) FROM documentos WHERE status != 'REMOVIDO'").fetchone()[0] == 3
    assert conn.execute("SELECT corpus_origem FROM documentos WHERE caminho_relativo = 'enviados/oficio.txt'"
                        ).fetchone()[0] == "real"  # envio do usuário: origem mais restritiva (LGPD)
    conn.close()


def test_sem_modelo_local_nao_ha_vetores_no_inicio_e_nada_e_baixado(tmp_path, monkeypatch):
    from app.infrastructure.modelos import embeddings

    monkeypatch.setattr(embeddings, "PASTA_LOCAL", tmp_path / "vazio")
    assert embeddings.modelo_local_disponivel() is False  # o início do servidor indexa só o texto
    (tmp_path / "vazio").mkdir()
    (tmp_path / "vazio" / "model.safetensors").write_bytes(b"x")
    assert embeddings.modelo_local_disponivel() is True
