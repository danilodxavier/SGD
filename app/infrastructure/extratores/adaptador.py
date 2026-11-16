"""Adaptador de extração (ADR-007): HTML legal próprio + leitores da v1 (PDF, DOCX, DOC, XLSX, ODT, RTF, PPT, TXT…)
com OCR para páginas digitalizadas. Devolve páginas prontas para o chunking estrutural."""
from dataclasses import dataclass, field
from pathlib import Path

from app.application.ingestao.chunking import Pagina
from app.infrastructure.extratores.html_legal import extrair_texto

EXTENSOES_HTML = {".htm", ".html"}


@dataclass
class ResultadoExtracao:
    status: str
    paginas: list = field(default_factory=list)
    num_paginas: int | None = None
    erro: str | None = None
    motor_ocr: str | None = None
    paginas_ocr: int = 0


def extensoes_suportadas():
    from app.ingestion import extractor

    return sorted(set(extractor.supported_extensions()) | EXTENSOES_HTML | extractor.IMAGE_EXTENSIONS)


def extrair(caminho: Path, ocr="auto") -> ResultadoExtracao:
    from app.ingestion import extractor

    if caminho.suffix.lower() in EXTENSOES_HTML:
        try:
            texto = extrair_texto(caminho.read_bytes())
        except OSError as exc:
            return ResultadoExtracao(extractor.STATUS_CORROMPIDO, erro=f"Não foi possível ler o arquivo: {exc}")
        if len(texto.strip()) < 20:
            return ResultadoExtracao(extractor.STATUS_SEM_TEXTO, erro="Documento sem texto extraível.")
        return ResultadoExtracao(extractor.STATUS_TEXTO, [Pagina(texto, None)], None)

    r = extractor.extract(caminho, ocr_engine=ocr)
    por_pagina = {}
    for seg in r.segments:
        por_pagina.setdefault(seg.page, []).append(seg.text.rstrip("\n"))
    paginas = [Pagina("\n".join(textos) + "\n", numero) for numero, textos in
               sorted(por_pagina.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))]
    return ResultadoExtracao(r.status, paginas, r.pages, r.error, r.ocr_engine, r.ocr_pages)
