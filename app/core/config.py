"""Configurações da aplicação, lidas do arquivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# Caches e dados de bibliotecas de IA ficam dentro do projeto (ADR-001) e sem telemetria de terceiros (LGPD).
# Definidos antes de qualquer import de huggingface/torch/ragas/langchain.
_AMBIENTE_PADRAO = {
    "HF_HOME": BASE_DIR / "modelos" / "hf",
    "TORCH_HOME": BASE_DIR / "modelos" / "torch",
    "PHOENIX_WORKING_DIR": BASE_DIR / "data" / "observabilidade",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "RAGAS_DO_NOT_TRACK": "true",
    "LANGSMITH_TRACING": "false",
    "LANGCHAIN_TRACING_V2": "false",
    "PHOENIX_TELEMETRY_ENABLED": "false",
    "TOKENIZERS_PARALLELISM": "false",
    # transformers 5 + torch 2.14 + Python 3.15: a carga paralela de pesos causa "access violation" no Windows
    # (reproduzido em 2026-11-16, CPU e GPU); a carga sequencial funciona. Ver HABILIDADES.md.
    "HF_DEACTIVATE_ASYNC_LOAD": "1",
}
for _chave, _valor in _AMBIENTE_PADRAO.items():
    os.environ.setdefault(_chave, str(_valor))


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
        self.database_path = _path(os.getenv("DATABASE_PATH"), r"data\database\sadgd.db")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.auto_index = _bool(os.getenv("AUTO_INDEX"), True)
        self.ocr_enabled = _bool(os.getenv("OCR_ENABLED"), True)
        self.ocr_engine = os.getenv("OCR_ENGINE", "auto").strip().lower()
        self.ocr_language = os.getenv("OCR_LANGUAGE", "pt-BR").strip()
        self.ocr_dpi = int(os.getenv("OCR_DPI", "200"))
        self.ocr_max_pages = int(os.getenv("OCR_MAX_PAGES", "50"))
        tesseract_projeto = BASE_DIR / "ferramentas" / "tesseract" / "tesseract.exe"
        self.tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip() or (
            str(tesseract_projeto) if tesseract_projeto.is_file() else "")
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
        # SAD-GD (v2)
        self.corpus_origem = os.getenv("CORPUS_ORIGEM", "real").strip().lower()  # origem padrão (mais restritiva)
        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        self.ollama_exe = _path(os.getenv("OLLAMA_EXE"), r"ferramentas\ollama\ollama.exe")
        self.ollama_models = _path(os.getenv("OLLAMA_MODELS"), r"modelos\ollama")
        self.llm_modelo_padrao = os.getenv("LLM_MODELO_PADRAO", "sadgd-qwen2.5-7b").strip()
        self.observabilidade = os.getenv("OBSERVABILIDADE", "sqlite").strip().lower()  # sqlite | phoenix | nenhuma
        # F2 em provedor gratuito em nuvem (Fase 10/11; ADR-004): só corpus acadêmico, anonimizado, com reserva local.
        # Exige AI_ALLOW_REMOTE=true E SADGD_LLM_F2=gemini E a chave no .env (nunca no código ou no chat).
        self.llm_f2 = os.getenv("SADGD_LLM_F2", "local").strip().lower()  # local | gemini
        self.gemini_url = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/openai/").strip()
        self.gemini_modelo = os.getenv("GEMINI_MODELO", "gemini-2.5-flash").strip()
        self.gemini_extras = os.getenv("GEMINI_EXTRAS", '{"reasoning_effort": "none"}').strip()
        self.versao_sistema = "2.0.0.dev0"

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
