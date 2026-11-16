"""Varredura somente leitura da pasta documental e hash SHA-256 (documentos originais nunca são alterados)."""
import hashlib
from pathlib import Path

from app.application.ingestao.indexador import ArquivoFonte

IGNORAR_NOMES = {"thumbs.db", "desktop.ini", ".ds_store", "gabarito.json", "manifesto.csv",
                 "coleta_publico_falhas.csv"}


def listar(raiz: Path, extensoes) -> list[ArquivoFonte]:
    raiz = Path(raiz)
    extensoes = {e.lower() for e in extensoes}
    arquivos = []
    for caminho in sorted(raiz.rglob("*")):
        if not caminho.is_file() or caminho.suffix.lower() not in extensoes:
            continue
        nome = caminho.name.lower()
        if nome in IGNORAR_NOMES or nome.startswith(("~$", ".")):
            continue
        info = caminho.stat()
        arquivos.append(ArquivoFonte(caminho.resolve(), caminho.relative_to(raiz).as_posix(), info.st_size,
                                     info.st_mtime))
    return arquivos


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with Path(caminho).open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()
