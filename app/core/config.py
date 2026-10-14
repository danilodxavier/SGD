"""Configurações da aplicação, lidas do arquivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _bool(value, default):
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "sim", "yes", "on")


# faixas de endereços de redes internas (RFC 1918) e o próprio computador
DEFAULT_ALLOWED_CLIENTS = "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"


def _list(value, default):
    return [item.strip() for item in (value if value is not None and value.strip() else default).split(",")
            if item.strip()]


def _path(value, default):
    path = Path((value or default).strip())
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


class Settings:
    def __init__(self):
        self.app_host = os.getenv("APP_HOST", "127.0.0.1").strip()
        self.app_port = int(os.getenv("APP_PORT", "8000"))
        # acesso pela rede (APP_HOST=0.0.0.0): computadores e nomes de acesso aceitos
        self.allowed_clients = _list(os.getenv("ALLOWED_CLIENTS"), DEFAULT_ALLOWED_CLIENTS)
        self.allowed_hosts = [h.lower() for h in _list(os.getenv("ALLOWED_HOSTS"), "")]
        self.session_hours = int(os.getenv("SESSION_HOURS", "8"))
        self.ssl_certfile = os.getenv("SSL_CERTFILE", "").strip()
        self.ssl_keyfile = os.getenv("SSL_KEYFILE", "").strip()
        self.documents_root = os.getenv("DOCUMENTS_ROOT", r"D:\Documentos").strip()
        self.database_path = _path(os.getenv("DATABASE_PATH"), r"data\database\documents.db")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.auto_index = _bool(os.getenv("AUTO_INDEX"), True)
        self.ocr_enabled = _bool(os.getenv("OCR_ENABLED"), True)
        self.ocr_engine = os.getenv("OCR_ENGINE", "auto").strip().lower()
        self.ocr_language = os.getenv("OCR_LANGUAGE", "pt-BR").strip()
        self.ocr_dpi = int(os.getenv("OCR_DPI", "200"))
        self.ocr_max_pages = int(os.getenv("OCR_MAX_PAGES", "50"))
        self.tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
        self.tesseract_lang = os.getenv("TESSERACT_LANG", "por").strip()
        self.ai_provider = os.getenv("AI_PROVIDER", "local").strip().lower()
        self.ai_key_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
        self.llm_base_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1").strip().rstrip("/")
        self.llm_model = os.getenv("LLM_MODEL", "").strip()
        self.llm_timeout = int(os.getenv("LLM_TIMEOUT", "120"))
        self.llm_max_passages = int(os.getenv("LLM_MAX_PASSAGES", "8"))
        # endereços fora desta máquina só com autorização expressa no .env (padrão: LOCAL ONLY)
        self.ai_allow_remote = _bool(os.getenv("AI_ALLOW_REMOTE"), False)
        self.data_dir = _path(os.getenv("DATA_DIR"), "data")

    @property
    def https(self):
        return bool(self.ssl_certfile and self.ssl_keyfile)

    @property
    def network_mode(self):
        return self.app_host not in ("127.0.0.1", "localhost", "::1")

    @property
    def logs_dir(self):
        return self.data_dir / "logs"

    @property
    def reports_dir(self):
        return self.data_dir / "reports"

    @property
    def backups_dir(self):
        return self.data_dir / "backups"

    @property
    def pid_file(self):
        return self.data_dir / "app.pid"


settings = Settings()
