"""Indexação pela linha de comando.

    python scripts\\indexar.py              indexação incremental do diretório configurado
    python scripts\\indexar.py --forcar     reprocessa todos os arquivos
    python scripts\\indexar.py --raiz D:\\X indexa outro diretório (e o salva como padrão)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_documents_root, init_db, set_setting  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.indexing.indexer import IndexBusy, IndexRootError, run_index  # noqa: E402
from app.ingestion.scanner import check_root  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Indexa o diretório documental.")
    parser.add_argument("--forcar", action="store_true", help="reprocessa todos os arquivos")
    parser.add_argument("--raiz", help="diretório documental a indexar")
    args = parser.parse_args()

    setup_logging()
    init_db()
    if args.raiz:
        ok, message = check_root(args.raiz)
        if not ok:
            print(f"[ERRO] {message}")
            return 1
        set_setting("documents_root", str(Path(args.raiz).resolve()))

    print(f"Diretório documental: {get_documents_root()}")
    try:
        r = run_index(force=args.forcar)
    except (IndexRootError, IndexBusy) as exc:
        print(f"[ERRO] {exc}")
        return 1
    except Exception:
        print("[ERRO] Falha na indexação. Consulte data\\logs\\app.log.")
        return 1
    print(f"Arquivos encontrados: {r['found']}")
    print(f"Arquivos novos: {r['new']}")
    print(f"Arquivos alterados: {r['changed']}")
    print(f"Arquivos inalterados: {r['unchanged']}")
    print(f"Arquivos removidos: {r['removed']}")
    print(f"Documentos com OCR: {r['ocr']}")
    print(f"Erros: {r['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
