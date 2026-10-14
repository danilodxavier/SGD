"""Scripts de linha de comando (indexar, diagnóstico, backup) e desempenho da indexação."""
import os
import subprocess
import sys
import time
import zipfile

from app.core.config import BASE_DIR
from app.indexing.indexer import run_index
from app.retrieval.search import search
from app.core.database import get_conn, set_setting


def _run(script, tmp_path, *args):
    env = {**os.environ, "DATA_DIR": str(tmp_path / "data"), "DATABASE_PATH": str(tmp_path / "data" / "cli.db"),
           "OCR_ENABLED": "false", "AUTO_INDEX": "false", "AI_PROVIDER": "local", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(BASE_DIR / "scripts" / script), *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, timeout=300)


def test_indexar_pela_linha_de_comando(docs_dir, tmp_path):
    r = _run("indexar.py", tmp_path, "--raiz", str(docs_dir))
    assert r.returncode == 0, r.stderr
    assert "Arquivos encontrados: 11" in r.stdout and "Arquivos novos: 11" in r.stdout
    again = _run("indexar.py", tmp_path)
    assert "Arquivos inalterados: 11" in again.stdout
    assert _run("indexar.py", tmp_path, "--raiz", str(tmp_path / "nao_existe")).returncode == 1


def test_diagnostico(docs_dir, tmp_path):
    _run("indexar.py", tmp_path, "--raiz", str(docs_dir))
    r = _run("diagnostico.py", tmp_path)
    for name in ("Windows", "Python", "SQLite", "diretório documental", "FastAPI", "Uvicorn", "banco de dados",
                 "porta"):
        assert name in r.stdout
    assert "[ERRO]" not in r.stdout and r.returncode == 0, r.stdout


def test_backup_sem_documentos_originais(docs_dir, tmp_path):
    _run("indexar.py", tmp_path, "--raiz", str(docs_dir))
    r = _run("backup.py", tmp_path)
    assert r.returncode == 0, r.stderr
    backups = list((tmp_path / "data" / "backups").glob("backup_*.zip"))
    assert len(backups) == 1
    names = zipfile.ZipFile(backups[0]).namelist()
    assert "database/cli.db" in names
    assert not any(n.endswith((".pdf", ".docx", ".xlsx")) for n in names)  # originais ficam fora do backup


def test_verificacao_de_aceitacao(tmp_path):
    r = _run("aceitacao.py", tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "23 de 23 critérios atendidos" in r.stdout


def test_desempenho_indexacao_incremental_e_busca(db, tmp_path):
    root = tmp_path / "volume"
    root.mkdir()
    for i in range(300):
        (root / f"doc_{i:03d}.txt").write_text(
            f"Processo nº 23188.{i:06d}/2024-01. Relatório mensal de fiscalização número {i}. "
            "Serviços de manutenção predial executados conforme cronograma." * 5, encoding="utf-8")
    set_setting("documents_root", str(root))
    start = time.time()
    assert run_index()["new"] == 300
    first = time.time() - start
    start = time.time()
    assert run_index()["unchanged"] == 300
    incremental = time.time() - start
    start = time.time()
    with get_conn() as conn:
        assert search(conn, "23188.000150/2024-01")
    query = time.time() - start
    assert first < 60 and incremental < 5 and query < 1, (first, incremental, query)
