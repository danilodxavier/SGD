from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.core.database import get_conn
from app.indexing.indexer import run_index
from app.ingestion import extractor, ocr
from app.ingestion.images import sample_image
from app.services import checklist
from app.services.questions import MSG_OCR, answer_question
from tests.sample_docs import PORTARIA_DIGITALIZADA
from tests.test_checklist import CHECKLIST
from tests.helpers import logged_client

HEADERS = {"X-Requested-With": "AgenteDocumental"}


class FakeEngine:
    """Mecanismo determinístico: devolve o texto da portaria fictícia para cada imagem."""

    name = "fake"
    label = "OCR de teste"

    def __init__(self):
        self.images = []

    def available(self, refresh=False):
        return True, "teste"

    def recognize(self, paths):
        for p in paths:
            assert Path(p).exists() and Image.open(p).mode == "L"
            self.images.append(Path(p))
        return [ocr.OcrPage("\n".join(PORTARIA_DIGITALIZADA)) for _ in paths]


@pytest.fixture()
def fake(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(ocr, "get_engine", lambda refresh=False: engine)
    return engine


def _portaria(root):
    return root / "Contratos" / "034-2022" / "Portaria_Fiscal_digitalizada.pdf"


# ---------- extração ----------

def test_pdf_digitalizado_sem_ocr(docs_dir):
    result = extractor.extract(_portaria(docs_dir), None)
    assert result.status == extractor.STATUS_ESCANEADO
    assert "Ative o OCR" in result.error


def test_pdf_digitalizado_com_ocr(docs_dir, db):
    engine = FakeEngine()
    result = extractor.extract(_portaria(docs_dir), engine)
    assert result.status == extractor.STATUS_OCR
    assert result.ocr_engine == "fake" and result.ocr_pages == 1
    assert result.segments[0].page == 1
    assert "fiscal" in result.full_text and "034/2022" in result.full_text


def test_pdf_com_texto_nao_passa_por_ocr(docs_dir, db):
    engine = FakeEngine()
    result = extractor.extract(docs_dir / "Contratos" / "034-2022" / "Contrato_034_2022.pdf", engine)
    assert result.status == extractor.STATUS_TEXTO and engine.images == []


def test_imagem_e_tiff_de_varias_paginas(tmp_path, db):
    engine = FakeEngine()
    png = tmp_path / "foto.png"
    sample_image(["texto"]).save(png)
    assert extractor.extract(png, engine).status == extractor.STATUS_OCR
    tif = tmp_path / "digitalizado.tif"
    frames = [sample_image(["pagina 1"]), sample_image(["pagina 2"])]
    frames[0].save(tif, save_all=True, append_images=frames[1:])
    result = extractor.extract(tif, engine)
    assert result.status == extractor.STATUS_OCR and [s.page for s in result.segments] == [1, 2]


def test_imagem_invalida(docs_dir, db):
    result = extractor.extract(docs_dir / "Outros" / "foto_documento.png", FakeEngine())
    assert result.status == extractor.STATUS_CORROMPIDO


def test_imagens_temporarias_removidas(docs_dir, db):
    engine = FakeEngine()
    extractor.extract(_portaria(docs_dir), engine)
    assert engine.images and not any(p.exists() for p in engine.images)
    cache = settings.data_dir / "cache"
    assert not any(cache.glob("ocr_*"))


def test_originais_preservados(docs_dir, db):
    path = _portaria(docs_dir)
    before = (path.stat().st_mtime, path.read_bytes())
    extractor.extract(path, FakeEngine())
    assert (path.stat().st_mtime, path.read_bytes()) == before


# ---------- indexação e uso das evidências ----------

def test_ativar_ocr_reprocessa_somente_digitalizados(indexed, fake):
    with get_conn() as conn:
        status = conn.execute("SELECT status FROM documents WHERE filename LIKE 'Portaria%'").fetchone()[0]
    assert status == extractor.STATUS_ESCANEADO

    result = run_index()  # mesmos arquivos; agora com OCR disponível
    assert result["ocr"] == 1
    assert result["unchanged"] == 9  # portaria e imagem sem texto foram reprocessadas
    with get_conn() as conn:
        row = conn.execute("SELECT status, ocr, ocr_pages, contract_ref FROM documents "
                           "WHERE filename LIKE 'Portaria%'").fetchone()
    assert (row["status"], row["ocr"], row["ocr_pages"], row["contract_ref"]) == ("COM_OCR", "fake", 1, "034/2022")

    again = run_index()  # OCR já aplicado: nada a reprocessar
    assert again["unchanged"] == 11 and again["ocr"] == 0


def test_checklist_com_portaria_lida_por_ocr(indexed, fake):
    run_index()
    c = checklist.create("OCR", CHECKLIST, "034/2022")
    items = {i["position"]: i for i in checklist.run(c["checklist"]["id"], today=date(2026, 10, 14))["items"]}
    portaria = items[6]
    assert portaria["status"] == "ATENDIDO"
    assert portaria["confidence"] == "media"
    assert "OCR" in portaria["justification"]
    assert portaria["evidences"][0]["filename"] == "Portaria_Fiscal_digitalizada.pdf"


def test_resposta_avisa_fonte_ocr(indexed, fake):
    run_index()
    res = answer_question("Quem é o fiscal do contrato 034/2022?")
    assert any(s["ocr"] for s in res["sources"])
    assert MSG_OCR in res["warnings"]
    assert res["confidence"] != "alta"


# ---------- configuração e API ----------

def test_configuracao_pelo_painel(db):
    from app.core.database import set_setting

    assert ocr.current_config()["enabled"] is False  # desativado no conftest
    set_setting("ocr_enabled", "true")
    set_setting("ocr_engine", "tesseract")
    assert ocr.current_config() == {"enabled": True, "engine": "tesseract"}


def test_api_ocr(indexed):
    with logged_client() as client:
        st = client.get("/api/ocr").json()
        assert {e["name"] for e in st["engines"]} == {"windows", "tesseract"}
        r = client.post("/api/ocr", json={"enabled": True, "engine": "auto"}, headers=HEADERS)
        assert r.status_code == 200 and r.json()["enabled"] is True
        assert client.post("/api/ocr", json={"enabled": True, "engine": "xyz"}, headers=HEADERS).status_code == 400
        assert client.post("/api/index", json={"retry_ocr": True}, headers=HEADERS).status_code in (200, 409)


# ---------- mecanismo real (somente se disponível nesta máquina) ----------

windows_ok = ocr.WindowsOcrEngine().available()[0]


@pytest.mark.skipif(not windows_ok, reason="OCR do Windows com pt-BR indisponível")
def test_ocr_real_do_windows(docs_dir, db):
    result = extractor.extract(_portaria(docs_dir), ocr.ENGINES["windows"])
    assert result.status == extractor.STATUS_OCR
    text = result.full_text.lower()
    assert "fiscal" in text and "034/2022" in text and "alfa" in text


@pytest.mark.skipif(not windows_ok, reason="OCR do Windows com pt-BR indisponível")
def test_botao_testar_ocr(db, monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", True)
    result = ocr.run_test()
    assert result["ok"], result
