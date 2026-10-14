"""Configuração de logs em data\\logs\\app.log."""
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import settings

_configured = False


def setup_logging():
    global _configured
    if _configured:
        return
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("agente")
    logger.setLevel(settings.log_level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        settings.logs_dir / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    _configured = True


def get_logger(name):
    return logging.getLogger(f"agente.{name}")
