"""Extração de texto: escolhe o leitor conforme a extensão e classifica o resultado."""
from dataclasses import dataclass, field

from app.core.logging import get_logger

log = get_logger("ingestion")

STATUS_TEXTO = "COM_TEXTO"
STATUS_ESCANEADO = "ESCANEADO"
STATUS_OCR = "COM_OCR"
STATUS_SEM_TEXTO = "SEM_TEXTO"
STATUS_CORROMPIDO = "CORROMPIDO"
STATUS_NAO_SUPORTADO = "NAO_SUPORTADO"
STATUS_REMOVIDO = "REMOVIDO"

SEARCHABLE_STATUSES = (STATUS_TEXTO, STATUS_OCR)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
# Formatos previstos na especificação, com leitura planejada para fases futuras.


@dataclass
class Segment:
    text: str
    page: int | None = None
    section: str | None = None
    detect_headings: bool = True


@dataclass
class ExtractionResult:
    status: str
    segments: list = field(default_factory=list)
    pages: int | None = None
    error: str | None = None
    ocr_engine: str | None = None
    ocr_pages: int = 0

    @property
    def full_text(self):
        return "\n".join(s.text for s in self.segments)


class ExtractionError(Exception):
    """Erro com mensagem compreensível para o usuário final."""


def _readers():
    from app.ingestion import doc, docx, odf, pdf, pptx, rtf, text, xlsx

    return {
        ".pdf": pdf.extract,
        ".docx": docx.extract,
        ".doc": doc.extract,
        ".rtf": rtf.extract,
        ".odt": odf.extract_odt,
        ".xlsx": xlsx.extract,
        ".xlsm": xlsx.extract,
        ".xls": xlsx.extract_xls,
        ".ods": odf.extract_ods,
        ".pptx": pptx.extract,
        ".ppt": pptx.extract_ppt,
        ".txt": text.extract,
        ".md": text.extract,
        ".csv": text.extract_csv,
    }


def supported_extensions():
    return sorted(_readers())


AUTO = "auto"
MIN_PAGE_CHARS = 30  # página com menos texto que isso é tratada como digitalizada


def _ocr_engine(ocr_engine):
    if ocr_engine == AUTO:
        from app.ingestion import ocr

        return ocr.get_engine()
    return ocr_engine


def extract(path, ocr_engine=AUTO):
    """Extrai o texto do arquivo. `ocr_engine`: AUTO (configuração do painel), um mecanismo ou None."""
    ext = path.suffix.lower()
    readers = _readers()
    if ext in IMAGE_EXTENSIONS:
        return _extract_image(path, _ocr_engine(ocr_engine))
    if ext not in readers:
        return ExtractionResult(STATUS_NAO_SUPORTADO, error="Formato não suportado.")
    try:
        segments, pages = readers[ext](path)
    except ExtractionError as exc:
        log.warning("Falha ao ler %s: %s", path, exc)
        return ExtractionResult(STATUS_CORROMPIDO, error=str(exc))
    except Exception as exc:  # leitores de terceiros lançam exceções variadas
        log.warning("Falha ao ler %s: %r", path, exc)
        return ExtractionResult(STATUS_CORROMPIDO, error="O arquivo está protegido, corrompido ou em formato inválido.")

    segments = [s for s in segments if s.text and s.text.strip()]
    if ext == ".pdf" and pages:
        return _complete_pdf(path, segments, pages, ocr_engine)
    if not segments:
        return ExtractionResult(STATUS_SEM_TEXTO, pages=pages, error="Documento sem texto extraível.")
    return ExtractionResult(STATUS_TEXTO, segments, pages)


def _complete_pdf(path, segments, pages, engine):
    """Aplica OCR às páginas sem camada de texto (PDF digitalizado ou misto)."""
    from app.core.config import settings

    with_text = {s.page for s in segments if len("".join(s.text.split())) >= MIN_PAGE_CHARS}
    missing = [n for n in range(1, pages + 1) if n not in with_text]
    engine = _ocr_engine(engine) if missing else None  # só consulta o OCR se houver página digitalizada
    if not missing or engine is None:
        if segments:
            return ExtractionResult(STATUS_TEXTO, segments, pages)
        hint = "Ative o OCR em Configurações." if engine is None else ""
        return ExtractionResult(STATUS_ESCANEADO, pages=pages,
                                error=f"PDF sem camada de texto (provavelmente digitalizado). {hint}".strip())

    from app.ingestion import images, ocr

    targets = missing[: settings.ocr_max_pages]
    try:
        recognized = ocr.recognize_images(engine, images.pdf_pages(path, targets, settings.ocr_dpi))
    except Exception as exc:
        log.warning("OCR falhou em %s: %r", path, exc)
        if segments:
            return ExtractionResult(STATUS_TEXTO, segments, pages, error="Falha no OCR das páginas digitalizadas.")
        # sem registrar o mecanismo: o documento volta a ser tentado na próxima indexação
        return ExtractionResult(STATUS_ESCANEADO, pages=pages, error="PDF digitalizado: falha no OCR. Consulte os logs.")
    by_page = {s.page: s for s in segments}
    for number, page in recognized.items():
        if len("".join(page.text.split())) > len("".join(by_page.get(number, Segment("")).text.split())):
            by_page[number] = Segment(page.text, page=number)
    ocr_pages = sum(1 for n, p in recognized.items() if p.text.strip())
    merged = [by_page[n] for n in sorted(by_page) if by_page[n].text.strip()]
    note = None
    if len(missing) > len(targets):
        note = f"OCR aplicado às primeiras {len(targets)} páginas digitalizadas (limite OCR_MAX_PAGES)."
    if not merged:
        return ExtractionResult(STATUS_ESCANEADO, pages=pages, ocr_engine=engine.name,
                                error="PDF digitalizado: o OCR não reconheceu texto. Confira a qualidade da digitalização.")
    status = STATUS_OCR if ocr_pages else STATUS_TEXTO
    return ExtractionResult(status, merged, pages, error=note, ocr_engine=engine.name, ocr_pages=ocr_pages)


def _extract_image(path, engine):
    from app.core.config import settings

    if engine is None:
        return ExtractionResult(STATUS_SEM_TEXTO, error="Imagem sem texto extraível. Ative o OCR em Configurações.")
    from app.ingestion import images, ocr

    try:
        pages = images.image_page_count(path)
        recognized = ocr.recognize_images(engine, images.image_frames(path, settings.ocr_max_pages))
    except ocr.OcrError as exc:
        return ExtractionResult(STATUS_SEM_TEXTO, error=str(exc), ocr_engine=engine.name)
    except Exception as exc:  # Pillow lança exceções variadas para imagens inválidas
        log.warning("Imagem inválida %s: %r", path, exc)
        return ExtractionResult(STATUS_CORROMPIDO, error="A imagem está corrompida ou em formato inválido.")
    segments = [Segment(p.text, page=n if pages > 1 else None) for n, p in sorted(recognized.items()) if p.text.strip()]
    if not segments:
        return ExtractionResult(STATUS_SEM_TEXTO, pages=pages, ocr_engine=engine.name,
                                error="O OCR não reconheceu texto na imagem.")
    return ExtractionResult(STATUS_OCR, segments, pages, ocr_engine=engine.name, ocr_pages=len(segments))
