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

    pdf_version = _version("fpdf")
    if not pdf_version:
        checks.append(_check("relatórios PDF", ERRO, "fpdf2 não instalado. Execute instalar.bat."))
    else:
        from app.services.report_writers import unicode_font_available
        checks.append(_check("relatórios PDF", OK if unicode_font_available() else WARNING,
                             f"fpdf2 {pdf_version}" + ("" if unicode_font_available() else
                                                        " — fonte Arial não encontrada; símbolos especiais serão simplificados")))

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
        from app.services import llm

        ai = llm.status()
        if ai["provider"] != "llm_local":
            checks.append(_check("mecanismo de respostas", OK, "Local — somente documentos (sem IA)"))
        else:
            ready = ai["reachable"] and ai["model"] in ai["models"]
            checks.append(_check("mecanismo de respostas", OK if ready else WARNING,
                                 f"LLM local em {ai['base_url']}: {ai['message']}"
                                 + ("" if ready else " As respostas usarão o mecanismo local.")))
    except Exception as exc:
        checks.append(_check("mecanismo de respostas", WARNING, f"Não foi possível verificar: {exc}"))
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

    if check_port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            in_use = s.connect_ex((settings.app_host, settings.app_port)) == 0
        checks.append(_check(f"porta {settings.app_port}", WARNING if in_use else OK,
                             "em uso (o painel pode já estar em execução)" if in_use else "livre"))
    return checks
