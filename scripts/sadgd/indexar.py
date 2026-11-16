"""Indexação SAD-GD (Fase 4): extração, chunking estrutural, metadados, FTS5 e embeddings bge-m3 no sadgd.db.

Uso: python scripts/sadgd/indexar.py [--raiz corpus] [--forcar] [--sem-embeddings] [--cpu]
"""
import argparse
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROJETO))

from app.core.config import settings  # noqa: E402  (define HF_HOME etc. antes de importar torch)
from app.core.database import init_db  # noqa: E402
from app.domain.documentos import CorpusOrigem  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--raiz", default=None, help="pasta documental (padrão: DOCUMENTS_ROOT do .env)")
    p.add_argument("--forcar", action="store_true", help="reprocessa todos os arquivos")
    p.add_argument("--sem-embeddings", action="store_true", help="apenas FTS (sem vetores)")
    p.add_argument("--cpu", action="store_true", help="gera embeddings na CPU")
    p.add_argument("--max-minutos", type=float, default=None,
                   help="encerra de forma limpa após N minutos; a próxima execução continua de onde parou")
    a = p.parse_args(argv)

    from app.application.ingestao.indexador import IndexarCorpus
    from app.infrastructure.extratores.adaptador import extensoes_suportadas, extrair
    from app.infrastructure.fonte_arquivos import listar, sha256
    from app.infrastructure.sqlite.conexao import conectar
    from app.infrastructure.sqlite.repositorio_indexacao import RepositorioIndexacaoSqlite
    from app.infrastructure.sqlite.vetores import SqliteVecStore

    init_db()
    raiz = Path(a.raiz or settings.documents_root)
    if not raiz.is_absolute():
        raiz = (RAIZ_PROJETO / raiz).resolve()
    if not raiz.is_dir():
        print(f"[ERRO] Pasta documental inexistente: {raiz}")
        return 1

    def fabrica():
        return conectar(settings.database_path)

    embedder = None
    if not a.sem_embeddings:
        from app.infrastructure.modelos.embeddings import BgeM3Embedder

        embedder = BgeM3Embedder(dispositivo="cpu" if a.cpu else None)
    caso = IndexarCorpus(RepositorioIndexacaoSqlite(fabrica), extrair, sha256, embedder,
                         SqliteVecStore(fabrica) if embedder else None,
                         origem_padrao=CorpusOrigem(settings.corpus_origem),
                         modelo=embedder.nome_modelo if embedder else "")
    arquivos = listar(raiz, extensoes_suportadas())
    print(f"Indexando {len(arquivos)} arquivo(s) de {raiz} ...")
    r = caso.executar(str(raiz), arquivos, forcar=a.forcar,
                      limite_segundos=a.max_minutos * 60 if a.max_minutos else None)
    if embedder:
        embedder.liberar()
    print(f"Arquivos encontrados: {r.encontrados}\nArquivos novos: {r.novos}\nArquivos alterados: {r.alterados}\n"
          f"Arquivos inalterados: {r.inalterados}\nRemovidos: {r.removidos}\nErros: {r.erros}\n"
          f"Trechos gravados: {r.trechos}\nVetores gravados: {r.vetores}\nTempo: {r.segundos} s")
    for arquivo, motivo in r.falhas:
        print(f"  [FALHA] {arquivo}: {motivo}")
    if r.interrompido:
        print("[PARCIAL] Limite de tempo atingido; execute novamente para continuar.")
        return 3
    return 0 if not r.falhas else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
