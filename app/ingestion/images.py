"""Preparação de imagens para OCR: páginas de PDF digitalizado e arquivos de imagem.

Somente leitura dos originais; as imagens intermediárias são gravadas em data\\cache e
apagadas ao final pelo chamador.
"""
from PIL import Image, ImageDraw, ImageFont, ImageSequence

MIN_WIDTH = 1400  # imagens pequenas são ampliadas para melhorar o reconhecimento
MAX_SIDE = 9000  # o OCR do Windows aceita até 10.000 px por lado


def prepare(image):
    image = image.convert("L")
    w, h = image.size
    if w < MIN_WIDTH:
        factor = min(2.5, MIN_WIDTH / max(w, 1))
        image = image.resize((int(w * factor), int(h * factor)), Image.LANCZOS)
    if max(image.size) > MAX_SIDE:
        factor = MAX_SIDE / max(image.size)
        image = image.resize((int(image.width * factor), int(image.height * factor)), Image.LANCZOS)
    return image


def image_frames(path, max_pages):
    """Páginas de um arquivo de imagem (TIFF pode ter várias)."""
    with Image.open(path) as img:
        for number, frame in enumerate(ImageSequence.Iterator(img), start=1):
            if number > max_pages:
                break
            yield number, prepare(frame.copy())


def image_page_count(path):
    with Image.open(path) as img:
        return getattr(img, "n_frames", 1)


def pdf_pages(path, page_numbers, dpi):
    """Renderiza as páginas indicadas (1 = primeira) de um PDF."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        for number in page_numbers:
            page = pdf[number - 1]
            try:
                yield number, prepare(page.render(scale=dpi / 72).to_pil())
            finally:
                page.close()
    finally:
        pdf.close()


def sample_image(lines):
    """Imagem com texto conhecido, usada no teste de OCR do painel."""
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default(size=34)
    img = Image.new("RGB", (1600, 90 + 70 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((40, 40 + 70 * i), line, fill="black", font=font)
    return img
