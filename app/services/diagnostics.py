"""Verificações de ambiente usadas pelo painel e por scripts\\diagnostico.py."""
import importlib
import importlib.util
import os
import platform
import shutil
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path

from app.core.config import BASE_DIR, settings

OK, WARNING, ERRO = "OK", "WARNING", "ERRO"


def _check(name, level, message):
    return {"name": name, "level": level, "message": message}


def _version(module):
    try:
        mod = importlib.import_module(module)
        return getattr(mod, "__version__", "instalado")
    except Exception:
        return None


def run_checks(documents_root=None, check_port=True):
    checks = []

    system = platform.system()
    checks.append(_check("Windows", OK if system == "Windows" else WARNING, platform.platform()))

    py = sys.version_info
    checks.append(_check("Python", OK if py >= (3, 10) else ERRO, sys.version.split()[0]))

    pip_ok = importlib.util.find_spec("pip") is not None
    checks.append(_check("pip", OK if pip_ok else WARNING, "disponível" if pip_ok else "não encontrado"))

    in_venv = sys.prefix != sys.base_prefix
    checks.append(_check("venv", OK if in_venv else WARNING,
                         sys.prefix if in_venv else "Executando fora do ambiente virtual (.venv)"))

    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        conn.close()
        checks.append(_check("SQLite", OK, f"{sqlite3.sqlite_version} com FTS5"))
    except Exception as exc:
        checks.append(_check("SQLite", ERRO, f"FTS5 indisponível: {exc}"))

    root = documents_root
    if root is None:
        try:
            from app.core.database import get_documents_root
            root = get_documents_root()
        except Exception:
            root = settings.documents_root
    root_path = Path(root)
    if root_path.is_dir():
        checks.append(_check("diretório documental", OK, str(root_path)))
        readable = os.access(root_path, os.R_OK)
        checks.append(_check("permissão de leitura", OK if readable else ERRO, str(root_path)))
    else:
        checks.append(_check("diretório documental", WARNING,
                             f"{root_path} não existe. Defina o diretório no painel (Configurações)."))

    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.data_dir, delete=True):
            pass
        checks.append(_check("permissão de escrita", OK, str(settings.data_dir)))
    except Exception as exc:
        checks.append(_check("permissão de escrita", ERRO, f"{settings.data_dir}: {exc}"))

    free_gb = shutil.disk_usage(BASE_DIR).free / 1024 ** 3
    checks.append(_check("espaço em disco", OK if free_gb >= 1 else WARNING, f"{free_gb:.1f} GB livres"))

    for name, module in (("FastAPI", "fastapi"), ("Uvicorn", "uvicorn")):
        v = _version(module)
        checks.append(_check(name, OK if v else ERRO, v or "não instalado"))

    libs = {"PDF (pypdf)": "pypdf", "DOCX (python-docx)": "docx", "XLSX (openpyxl)": "openpyxl",
            "DOC/PPT (olefile)": "olefile", "XLS (xlrd)": "xlrd"}
    missing = [label for label, module in libs.items() if not _version(module)]
    checks.append(_check("bibliotecas de documentos", ERRO if missing else OK,
                         "faltando: " + ", ".join(missing) if missing else
                         "PDF, DOC, DOCX, RTF, ODT, XLS, XLSX, ODS, PPT, PPTX, TXT, CSV, MD"))

    try:
        from app.ingestion import ocr

        st = ocr.status(refresh=True)
        if not st["enabled"]:
            checks.append(_check("OCR", WARNING, "Desativado. Documentos digitalizados não terão texto."))
        elif st["active"]:
            engine = next(e for e in st["engines"] if e["name"] == st["active"])
            checks.append(_check("OCR", OK, f"{engine['label']} — {engine['message']}"))
        else:
            reasons = "; ".join(f"{e['label']}: {e['message']}" for e in st["engines"])
            checks.append(_check("OCR", WARNING, f"Nenhum mecanismo disponível ({reasons})"))
    except Exception as exc:
        checks.append(_check("OCR", WARNING, f"Não foi possível verificar o OCR: {exc}"))
    try:
        from app.core import auth
        from app.core.database import init_db

        init_db()  # garante as tabelas mais recentes em bancos criados por versões anteriores
        users = auth.list_users()
        admins = [u for u in users if u["is_admin"] and u["active"]]
        if not users:
            checks.append(_check("usuários", WARNING, "Nenhum usuário cadastrado. Abra http://127.0.0.1:8000 neste "
                                                    "computador para criar o primeiro administrador."))
        elif not admins:
            checks.append(_check("usuários", ERRO, "Nenhum administrador ativo. Use usuarios.bat para reativar ou "
                                                 "criar um administrador."))
        else:
            checks.append(_check("usuários", OK, f"{len(users)} usuário(s), {len(admins)} administrador(es) ativo(s)"))
    except Exception as exc:
        checks.append(_check("usuários", WARNING, f"Não foi possível verificar: {exc}"))
    if settings.network_mode:
        detail = f"rede ({settings.app_host}), faixas autorizadas: {', '.join(settings.allowed_clients)}"
        checks.append(_check("acesso", OK if settings.https else WARNING,
                             detail + ("" if settings.https else " — sem HTTPS: senhas trafegam sem criptografia")))
        if settings.https:
            missing = [f for f in (settings.ssl_certfile, settings.ssl_keyfile) if not Path(f).is_file()]
            if missing:
                checks.append(_check("certificado HTTPS", ERRO, "arquivo não encontrado: " + ", ".join(missing)))
    else:
        checks.append(_check("acesso", OK, "somente este computador (127.0.0.1)"))
    if not _version("pypdfium2"):
        checks.append(_check("OCR de PDF", ERRO, "pypdfium2 não instalado. Execute instalar.bat."))

    try:
        from app.core.database import get_conn, init_db
        init_db()
        with get_conn() as conn:
            result = conn.execute("PRAGMA quick_check").fetchone()[0]
        checks.append(_check("banco de dados", OK if result == "ok" else ERRO, f"{settings.database_path} ({result})"))
    except Exception as exc:
        checks.append(_check("banco de dados", ERRO, str(exc)))

    checks.extend(checks_sadgd())

    if check_port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            in_use = s.connect_ex((settings.app_host, settings.app_port)) == 0
        checks.append(_check(f"porta {settings.app_port}", WARNING if in_use else OK,
                             "em uso (o painel pode já estar em execução)" if in_use else "livre"))
    return checks


def _dentro_do_projeto(caminho):
    try:
        Path(caminho).resolve().relative_to(BASE_DIR)
        return True
    except ValueError:
        return False


def checks_sadgd(gpu=True, ollama=True):
    """Verificações da infraestrutura SAD-GD (Fase 3): ADR-001, 004, 006, 007, 009, 010."""
    checks = []

    # RNF-03: caches e dados de IA dentro do projeto
    variaveis = ("HF_HOME", "TORCH_HOME", "PHOENIX_WORKING_DIR")
    fora = [f"{v}={os.environ.get(v)}" for v in variaveis if not _dentro_do_projeto(os.environ.get(v, "/"))]
    for caminho in (settings.database_path, settings.data_dir, settings.ollama_models):
        if not _dentro_do_projeto(caminho):
            fora.append(str(caminho))
    checks.append(_check("pastas no projeto", WARNING if fora else OK,
                         "fora do projeto: " + ", ".join(fora) if fora else "caches, modelos e dados em subpastas"))

    desligadas = [v for v, esperado in (("HF_HUB_DISABLE_TELEMETRY", "1"), ("RAGAS_DO_NOT_TRACK", "true"),
                                        ("PHOENIX_TELEMETRY_ENABLED", "false"), ("LANGSMITH_TRACING", "false"))
                  if os.environ.get(v, "").lower() != esperado]
    checks.append(_check("telemetria de terceiros", WARNING if desligadas else OK,
                         "ativa em: " + ", ".join(desligadas) if desligadas else "desativada"))

    try:
        from app.infrastructure.sqlite.conexao import conectar

        conn = conectar(settings.database_path)
        try:
            versao_vec = conn.execute("SELECT vec_version()").fetchone()[0]
            migracoes = [r[0] for r in conn.execute("SELECT versao FROM schema_migrations ORDER BY versao")]
        finally:
            conn.close()
        checks.append(_check("sqlite-vec", OK, versao_vec))
        checks.append(_check("migrações SAD-GD", OK if migracoes else ERRO,
                             ", ".join(migracoes) or "nenhuma aplicada — execute instalar.bat"))
    except Exception as exc:
        checks.append(_check("sqlite-vec", ERRO, f"{exc}"))

    for nome, modulo in (("LangGraph", "langgraph"), ("sentence-transformers", "sentence_transformers"),
                         ("RAGAS", "ragas"), ("Arize Phoenix", "phoenix")):
        v = _version(modulo)
        nivel = ERRO if modulo in ("langgraph", "sentence_transformers") else WARNING
        checks.append(_check(nome, OK if v else nivel, v or "não instalado"))

    if gpu:
        try:
            from app.infrastructure.modelos.thread_principal import executar

            versao, placa = executar(_gpu_torch)  # torch só na thread principal (ver thread_principal.py)
            if placa:
                checks.append(_check("GPU (torch)", OK, f"{versao} — {placa}"))
            else:
                checks.append(_check("GPU (torch)", WARNING, f"{versao} — sem CUDA; embeddings na CPU"))
        except Exception as exc:
            checks.append(_check("GPU (torch)", ERRO, f"torch indisponível: {exc}"))

    if ollama:
        import json
        import urllib.request

        if not settings.ollama_exe.is_file():
            checks.append(_check("Ollama", WARNING, "não instalado em ferramentas\\ollama"))
        else:
            try:
                with urllib.request.urlopen(f"{settings.ollama_url}/api/tags", timeout=3) as r:  # noqa: S310
                    modelos = [m["name"] for m in json.load(r).get("models", [])]
                ok = any(m.split(":")[0] == settings.llm_modelo_padrao for m in modelos)
                checks.append(_check("Ollama", OK if ok else WARNING,
                                     f"em execução; modelos: {', '.join(modelos) or 'nenhum'}"
                                     + ("" if ok else f" — falta {settings.llm_modelo_padrao}")))
            except Exception:
                checks.append(_check("Ollama", WARNING, "instalado, mas parado (start.bat o inicia)"))

    tesseract = Path(settings.tesseract_cmd) if settings.tesseract_cmd else None
    if tesseract and tesseract.is_file():
        idiomas = tesseract.parent / "tessdata" / f"{settings.tesseract_lang}.traineddata"
        checks.append(_check("Tesseract", OK if idiomas.is_file() else WARNING,
                             f"{tesseract}" + ("" if idiomas.is_file() else f" — falta {idiomas.name}")))
    else:
        checks.append(_check("Tesseract", WARNING, "não encontrado em ferramentas\\tesseract"))

    checks.append(_check("GitHub CLI", OK if shutil.which("gh") else WARNING,
                         "instalado" if shutil.which("gh") else "não instalado (CI/Projects dependem dele)"))
    return checks


def _gpu_torch():
    import torch

    return torch.__version__, (torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
