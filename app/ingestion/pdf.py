"""Leitura de PDF com texto (pypdf), página a página."""
from pypdf import PdfReader

from app.ingestion.extractor import ExtractionError, Segment


def extract(path):
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise ExtractionError("O PDF está protegido por senha.")
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError("O PDF está protegido e não pôde ser aberto.") from exc

    segments = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            segments.append(Segment(text, page=number))
    return segments, len(reader.pages)
