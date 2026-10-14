"""Restaura um backup criado por scripts\\backup.py.

    python scripts\\restaurar.py --arquivo "D:\\...\\BACKUP\\backup_20261014_120000.zip"
    python scripts\\restaurar.py --arquivo ... --com-configuracao   também restaura o .env do backup

O servidor precisa estar parado (stop.bat). Antes de substituir, o banco atual é guardado como
documents.db.antes_restauracao_AAAAMMDD_HHMMSS na mesma pasta, permitindo desfazer.
"""
import argparse
import json
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402
from app.core.logging import get_logger, setup_logging  # noqa: E402

log = get_logger("restaurar")


def server_running():
    try:
        info = json.loads(settings.pid_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    from app.__main__ import _alive

    return _alive(info["pid"])


def main():
    parser = argparse.ArgumentParser(description="Restaura um backup do Agente de Inteligência Documental.")
    parser.add_argument("--arquivo", required=True, help="arquivo backup_*.zip a restaurar")
    parser.add_argument("--com-configuracao", action="store_true", help="também restaura o arquivo .env")
    args = parser.parse_args()
    setup_logging()

    source = Path(args.arquivo)
    if not source.is_file():
        print(f"[ERRO] Arquivo não encontrado: {source}")
        return 1
    if server_running():
        print("[ERRO] O sistema está em execução. Rode stop.bat e tente novamente.")
        return 1
    db_name = settings.database_path.name
    with zipfile.ZipFile(source) as zf:
        names = zf.namelist()
        if f"database/{db_name}" not in names:
            print("[ERRO] O arquivo não é um backup válido deste sistema (banco de dados ausente).")
            return 1
        tmp_db = settings.database_path.with_suffix(".restaurando")
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(f"database/{db_name}") as src, open(tmp_db, "wb") as dst:
            shutil.copyfileobj(src, dst)
        check = sqlite3.connect(str(tmp_db))
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        check.close()
        if result != "ok":
            tmp_db.unlink(missing_ok=True)
            print(f"[ERRO] O banco dentro do backup está danificado ({result}). Nada foi alterado.")
            return 1

        stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
        if settings.database_path.exists():
            saved = settings.database_path.with_name(f"{db_name}.antes_restauracao_{stamp}")
            shutil.copy2(settings.database_path, saved)
            print(f"     Banco atual guardado em: {saved}")
        for extra in ("-wal", "-shm"):  # arquivos auxiliares do SQLite do banco antigo
            Path(str(settings.database_path) + extra).unlink(missing_ok=True)
        tmp_db.replace(settings.database_path)

        for name in names:
            for folder in ("index/", "reports/"):
                if name.startswith(folder) and not name.endswith("/"):
                    target = settings.data_dir / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        if args.com_configuracao and "config/.env" in names:
            env = BASE_DIR / ".env"
            if env.exists():
                shutil.copy2(env, BASE_DIR / f".env.antes_restauracao_{stamp}")
            with zf.open("config/.env") as src, open(env, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print("     Arquivo .env restaurado.")
    log.info("Backup restaurado: %s", source)
    print(f"[OK] Backup restaurado: {source.name}. Inicie o sistema com start.bat.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
