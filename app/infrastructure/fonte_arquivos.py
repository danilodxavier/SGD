"""Varredura somente leitura da pasta documental e hash SHA-256 (documentos originais nunca são alterados)."""
import hashlib
from pathlib import Path

from app.application.ingestao.indexador import ArquivoFonte

IGNORAR_NOMES = {"thumbs.db", "desktop.ini", ".ds_store", "gabarito.json", "manifesto.csv",
                 "coleta_publico_falhas.csv"}


IGNORAR_PASTAS = {"$recycle.bin", "system volume information", "__pycache__", "node_modules"}


def pastas_da_aplicacao() -> list[Path]:
    """Pastas do próprio sistema que nunca são indexadas, mesmo se ficarem dentro da raiz documental
    (banco, cache, logs, relatórios, backups, modelos, ferramentas, ambiente Python)."""
    from app.core.config import BASE_DIR, settings

    return [Path(settings.data_dir), BASE_DIR / "BACKUP", BASE_DIR / "modelos",
            BASE_DIR / "ferramentas", BASE_DIR / ".venv", BASE_DIR / ".git"]


def listar(raiz: Path, extensoes, excluir=None) -> list[ArquivoFonte]:
    """Arquivos suportados abaixo da raiz, exceto ocultos, temporários do Office, pastas de sistema e as
    pastas da própria aplicação (`excluir`; padrão: `pastas_da_aplicacao()`)."""
    raiz = Path(raiz)
    extensoes = {e.lower() for e in extensoes}
    excluidas = [p.resolve() for p in (pastas_da_aplicacao() if excluir is None else excluir)]
    arquivos = []
    for caminho in sorted(raiz.rglob("*")):
        if not caminho.is_file() or caminho.suffix.lower() not in extensoes:
            continue
        nome = caminho.name.lower()
        if nome in IGNORAR_NOMES or nome.startswith(("~$", ".")):
            continue
        relativo = caminho.relative_to(raiz)
        if any(parte.startswith(".") or parte.lower() in IGNORAR_PASTAS for parte in relativo.parts[:-1]):
            continue
        absoluto = caminho.resolve()
        if any(absoluto.is_relative_to(p) for p in excluidas):
            continue
        info = caminho.stat()
        arquivos.append(ArquivoFonte(absoluto, relativo.as_posix(), info.st_size, info.st_mtime))
    return arquivos


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with Path(caminho).open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()
