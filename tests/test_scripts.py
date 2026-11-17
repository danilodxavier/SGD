"""Scripts de linha de comando (indexar, diagnóstico, backup) e desempenho da indexação."""
import os
import subprocess
import sys
import time
import zipfile

from app.core.config import BASE_DIR
from app.core.database import get_conn, set_setting


def _run(script, tmp_path, *args):
    env = {**os.environ, "DATA_DIR": str(tmp_path / "data"), "DATABASE_PATH": str(tmp_path / "data" / "cli.db"),
           "OCR_ENABLED": "false", "AUTO_INDEX": "false", "AI_PROVIDER": "local", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(BASE_DIR / "scripts" / script), *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, timeout=300)


def test_diagnostico(docs_dir, tmp_path):
    _run("sadgd/indexar.py", tmp_path, "--raiz", str(docs_dir), "--sem-embeddings")
    r = _run("diagnostico.py", tmp_path)
    for name in ("Windows", "Python", "SQLite", "diretório documental", "FastAPI", "Uvicorn", "banco de dados",
                 "porta"):
        assert name in r.stdout
    assert "[ERRO]" not in r.stdout and r.returncode == 0, r.stdout


def test_backup_sem_documentos_originais(docs_dir, tmp_path):
    _run("sadgd/indexar.py", tmp_path, "--raiz", str(docs_dir), "--sem-embeddings")
    r = _run("backup.py", tmp_path)
    assert r.returncode == 0, r.stderr
    backups = list((tmp_path / "data" / "backups").glob("backup_*.zip"))
    assert len(backups) == 1
    names = zipfile.ZipFile(backups[0]).namelist()
    assert "database/cli.db" in names
    assert not any(n.endswith((".pdf", ".docx", ".xlsx")) for n in names)  # originais ficam fora do backup

