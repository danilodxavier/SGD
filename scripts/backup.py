"""Backup de banco (com usuários), índice, configurações e relatórios.

    python scripts\\backup.py                                  grava em data\\backups
    python scripts\\backup.py --destino "D:\\...\\BACKUP"       grava na pasta indicada
    python scripts\\backup.py --destino "D:\\...\\BACKUP" --manter 30   e mantém só os 30 mais recentes

Os documentos originais NÃO são incluídos: eles permanecem no diretório do usuário.
O banco é copiado de forma consistente mesmo com o painel em uso.
"""
import argparse
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402
from app.core.logging import get_logger, setup_logging  # noqa: E402

log = get_logger("backup")


def create_backup(destination):
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"backup_{datetime.now():%Y%m%d_%H%M%S}.zip"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.data_dir) as tmp, \
            zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        if settings.database_path.exists():
            copy = Path(tmp) / settings.database_path.name
            src = sqlite3.connect(str(settings.database_path))
            dst = sqlite3.connect(str(copy))
            src.backup(dst)  # cópia consistente mesmo com o painel em execução
            dst.close()
            src.close()
            zf.write(copy, f"database/{settings.database_path.name}")
        for folder in ("index", "reports"):
            for path in (settings.data_dir / folder).rglob("*"):
                if path.is_file() and path.name != ".gitkeep":
                    zf.write(path, f"{folder}/{path.relative_to(settings.data_dir / folder)}")
        for name in (".env", ".env.example"):
            if (BASE_DIR / name).exists():
                zf.write(BASE_DIR / name, f"config/{name}")
    return target


def prune(destination, keep):
    """Apaga os backups mais antigos além dos `keep` mais recentes (somente arquivos backup_*.zip)."""
    backups = sorted(destination.glob("backup_*.zip"), key=lambda p: p.name, reverse=True)
    removed = []
    for old in backups[keep:]:
        old.unlink()
        removed.append(old.name)
    return removed


def main():
    parser = argparse.ArgumentParser(description="Cria um backup do Agente de Inteligência Documental.")
    parser.add_argument("--destino", help="pasta onde o backup será gravado (padrão: data\\backups)")
    parser.add_argument("--manter", type=int, default=0,
                        help="quantidade de backups a manter na pasta de destino (0 = manter todos)")
    args = parser.parse_args()
    setup_logging()
    destination = Path(args.destino) if args.destino else settings.backups_dir
    try:
        target = create_backup(destination)
    except OSError as exc:
        log.error("Falha no backup em %s: %s", destination, exc)
        print(f"[ERRO] Não foi possível gravar o backup em {destination}: {exc}")
        return 1
    print(f"[OK] Backup criado: {target} ({target.stat().st_size / 1024:.0f} KB)")
    log.info("Backup criado: %s", target)
    if args.manter > 0:
        for name in prune(destination, args.manter):
            print(f"     Backup antigo removido: {name}")
            log.info("Backup antigo removido: %s", name)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
