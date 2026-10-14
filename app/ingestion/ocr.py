"""Reconhecimento óptico de caracteres (OCR), sempre local.

Mecanismos:
- windows: OCR nativo do Windows 10/11 (Windows.Media.Ocr), acionado via PowerShell; não exige instalação.
- tesseract: Tesseract OCR, se instalado pela TI (tesseract.exe + idioma "por").

O mecanismo é escolhido em Configurações (padrão "auto": Windows, depois Tesseract).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("ocr")

ENGINE_CHOICES = ("auto", "windows", "tesseract")
WINDOWS_SCRIPT = Path(__file__).with_name("ocr_windows.ps1")
TESSERACT_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
PROBE_TTL = 300  # segundos
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class OcrError(Exception):
    """Falha do mecanismo de OCR (mensagem compreensível)."""


@dataclass
class OcrPage:
    text: str
    error: str | None = None


class WindowsOcrEngine:
    name = "windows"
    label = "OCR do Windows"

    def __init__(self):
        self._probe = None  # (instante, idiomas, mensagem de erro)

    def _powershell(self):
        return shutil.which("powershell.exe") or shutil.which("powershell")

    def _run(self, env, timeout):
        script = WINDOWS_SCRIPT.read_text(encoding="utf-8")
        # -Command (e não -File): o script é da própria aplicação e não depende da política de execução
        return subprocess.run(
            [self._powershell(), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, **env}, timeout=timeout, creationflags=NO_WINDOW,
        )

    def languages(self, refresh=False):
        if self._probe and not refresh and time.time() - self._probe[0] < PROBE_TTL:
            return self._probe[1], self._probe[2]
        langs, error = [], None
        if sys.platform != "win32" or not self._powershell():
            error = "Disponível somente no Windows com PowerShell."
        else:
            try:
                r = self._run({"AGENTE_OCR_PROBE": "1"}, timeout=60)
                if r.returncode == 0:
                    langs = json.loads(r.stdout.strip() or "[]")
                    langs = [langs] if isinstance(langs, str) else langs
                else:
                    error = "O mecanismo de OCR do Windows não respondeu."
                    log.warning("Sonda do OCR do Windows falhou: %s", r.stderr[:500])
            except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
                error = "O mecanismo de OCR do Windows não respondeu."
                log.warning("Sonda do OCR do Windows falhou: %r", exc)
        self._probe = (time.time(), langs, error)
        return langs, error

    def available(self, refresh=False):
        langs, error = self.languages(refresh)
        if error:
            return False, error
        wanted = settings.ocr_language.lower()
        if not any(lang.lower() == wanted for lang in langs):
            return False, (f"Idioma {settings.ocr_language} não instalado para OCR (disponíveis: "
                           f"{', '.join(langs) or 'nenhum'}). Instale em Configurações do Windows > Hora e idioma > "
                           "Idioma e região.")
        return True, f"Idioma {settings.ocr_language}"

    def recognize(self, image_paths):
        work = Path(image_paths[0]).parent
        list_file = work / f"lista_{uuid.uuid4().hex}.txt"
        out_file = work / f"saida_{uuid.uuid4().hex}.json"
        list_file.write_text("\n".join(str(p) for p in image_paths), encoding="utf-8")
        try:
            r = self._run({"AGENTE_OCR_LIST": str(list_file), "AGENTE_OCR_OUT": str(out_file),
                           "AGENTE_OCR_LANG": settings.ocr_language}, timeout=60 + 30 * len(image_paths))
            if r.returncode != 0 or not out_file.exists():
                log.warning("OCR do Windows falhou: %s", r.stderr[:1000])
                raise OcrError("O OCR do Windows não conseguiu processar as imagens.")
            items = json.loads(out_file.read_text(encoding="utf-8-sig"))
        except subprocess.TimeoutExpired as exc:
            raise OcrError("O OCR do Windows excedeu o tempo limite.") from exc
        finally:
            list_file.unlink(missing_ok=True)
            out_file.unlink(missing_ok=True)
        items = [items] if isinstance(items, dict) else items
        by_path = {i["path"]: i for i in items}
        pages = []
        for p in image_paths:
            item = by_path.get(str(p), {"lines": [], "error": "sem resultado"})
            lines = item.get("lines") or []
            lines = [lines] if isinstance(lines, str) else lines
            pages.append(OcrPage("\n".join(lines), item.get("error")))
        return pages


class TesseractEngine:
    name = "tesseract"
    label = "Tesseract OCR"

    def command(self):
        if settings.tesseract_cmd:
            return settings.tesseract_cmd if Path(settings.tesseract_cmd).exists() else None
        return shutil.which("tesseract") or (str(TESSERACT_DEFAULT) if TESSERACT_DEFAULT.exists() else None)

    def available(self, refresh=False):
        cmd = self.command()
        if not cmd:
            return False, "Tesseract não instalado (opcional)."
        try:
            r = subprocess.run([cmd, "--list-langs"], capture_output=True, text=True, timeout=30,
                               creationflags=NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            return False, "Tesseract encontrado, mas não respondeu."
        langs = (r.stdout + r.stderr).split()
        if settings.tesseract_lang not in langs:
            return False, f"Tesseract sem o idioma “{settings.tesseract_lang}” instalado."
        return True, f"{cmd} (idioma {settings.tesseract_lang})"

    def recognize(self, image_paths):
        pages = []
        for p in image_paths:
            try:
                r = subprocess.run([self.command(), str(p), "stdout", "-l", settings.tesseract_lang, "--psm", "3"],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=180, creationflags=NO_WINDOW)
                pages.append(OcrPage(r.stdout, None if r.returncode == 0 else r.stderr[:300]))
            except (OSError, subprocess.TimeoutExpired) as exc:
                pages.append(OcrPage("", str(exc)))
        return pages


ENGINES = {"windows": WindowsOcrEngine(), "tesseract": TesseractEngine()}


def current_config():
    """Configuração efetiva: o painel prevalece sobre o .env."""
    from app.core.database import get_setting

    enabled = get_setting("ocr_enabled")
    engine = get_setting("ocr_engine") or settings.ocr_engine
    return {
        "enabled": settings.ocr_enabled if enabled is None else enabled == "true",
        "engine": engine if engine in ENGINE_CHOICES else "auto",
    }


def get_engine(refresh=False):
    """Mecanismo ativo, ou None se o OCR estiver desativado ou indisponível."""
    cfg = current_config()
    if not cfg["enabled"]:
        return None
    names = ["windows", "tesseract"] if cfg["engine"] == "auto" else [cfg["engine"]]
    for name in names:
        if ENGINES[name].available(refresh)[0]:
            return ENGINES[name]
    return None


def status(refresh=False):
    cfg = current_config()
    engines = []
    for name, engine in ENGINES.items():
        ok, message = engine.available(refresh)
        engines.append({"name": name, "label": engine.label, "available": ok, "message": message})
    active = get_engine() if cfg["enabled"] else None
    return {**cfg, "active": active.name if active else None,
            "active_label": active.label if active else None, "engines": engines,
            "language": settings.ocr_language, "dpi": settings.ocr_dpi, "max_pages": settings.ocr_max_pages}


def work_dir():
    path = settings.data_dir / "cache" / f"ocr_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def recognize_images(engine, numbered_images):
    """Recebe [(nº da página, imagem PIL)] e devolve {nº da página: OcrPage}."""
    numbered_images = list(numbered_images)
    if not numbered_images:
        return {}
    folder = work_dir()
    try:
        paths = []
        for number, image in numbered_images:
            p = folder / f"pagina_{number:04d}.png"
            image.save(p)
            paths.append(p)
        pages = engine.recognize(paths)
        return {number: page for (number, _), page in zip(numbered_images, pages)}
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def run_test():
    """Reconhece uma imagem gerada com texto conhecido (botão “Testar OCR” do painel)."""
    from app.core.text import fold
    from app.ingestion.images import sample_image

    engine = get_engine(refresh=True)
    if engine is None:
        return {"ok": False, "engine": None, "text": "", "message": "OCR desativado ou nenhum mecanismo disponível."}
    expected = ["Teste de OCR do Agente Documental", "Contrato nº 034/2022 — Vigência até 28/02/2024"]
    start = time.time()
    try:
        page = recognize_images(engine, [(1, sample_image(expected))])[1]
    except OcrError as exc:
        return {"ok": False, "engine": engine.label, "text": "", "message": str(exc)}
    words = ["teste", "ocr", "contrato", "034/2022", "vigencia", "28/02/2024"]
    found = sum(w in fold(page.text) for w in words)
    ok = found >= len(words) - 1
    return {"ok": ok, "engine": engine.label, "text": page.text, "seconds": round(time.time() - start, 1),
            "message": f"{found} de {len(words)} palavras de controle reconhecidas."}
