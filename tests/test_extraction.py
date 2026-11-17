from app.ingestion import extractor


def test_pdf_extrai_texto_por_pagina(docs_dir):
    result = extractor.extract(docs_dir / "Contratos" / "034-2022" / "Contrato_034_2022.pdf")
    assert result.status == extractor.STATUS_TEXTO
    assert result.pages == 2
    assert [s.page for s in result.segments] == [1, 2]
    assert "CLÁUSULA SEGUNDA" in result.segments[0].text
    assert "R$ 120.000,00" in result.segments[1].text


def test_docx_identifica_secoes(docs_dir):
    result = extractor.extract(docs_dir / "Contratos" / "034-2022" / "1_Termo_Aditivo_034_2022.docx")
    assert result.status == extractor.STATUS_TEXTO
    sections = [s.section for s in result.segments]
    assert "CLÁUSULA PRIMEIRA – DA PRORROGAÇÃO" in sections
    assert "28/02/2024" in result.full_text


def test_xlsx_le_planilha(docs_dir):
    result = extractor.extract(docs_dir / "Contratos" / "034-2022" / "Planilha_Itens_034_2022.xlsx")
    assert result.status == extractor.STATUS_TEXTO
    assert result.segments[0].section == "Planilha: Itens"
    assert "Servente de limpeza | posto | 4 | 1800 | 7200" in result.full_text


def test_txt(docs_dir):
    result = extractor.extract(docs_dir / "Contratos" / "034-2022" / "Resumo_contrato_034.txt")
    assert result.status == extractor.STATUS_TEXTO
    assert "R$ 100.000,00" in result.full_text


def test_arquivo_corrompido_nao_gera_excecao(docs_dir):
    result = extractor.extract(docs_dir / "Outros" / "arquivo_corrompido.pdf")
    assert result.status == extractor.STATUS_CORROMPIDO
    assert "Traceback" not in (result.error or "")


def test_imagem_sem_texto_aguarda_ocr(docs_dir):
    result = extractor.extract(docs_dir / "Outros" / "foto_documento.png", ocr_engine=None)
    assert result.status == extractor.STATUS_SEM_TEXTO
    assert "Ative o OCR" in result.error


def test_formato_nao_suportado(tmp_path):
    path = tmp_path / "desenho.dwg"
    path.write_bytes(b"x")
    assert extractor.extract(path).status == extractor.STATUS_NAO_SUPORTADO


def test_csv_com_ponto_e_virgula(tmp_path):
    path = tmp_path / "pagamentos.csv"
    path.write_text("Mês;Valor;Nota fiscal\nJaneiro;10.000,00;NF 123\n", encoding="utf-8")
    result = extractor.extract(path)
    assert result.status == extractor.STATUS_TEXTO
    assert "Janeiro | 10.000,00 | NF 123" in result.full_text


def test_txt_em_codificacao_do_windows_e_markdown(tmp_path):
    txt = tmp_path / "antigo.txt"
    txt.write_bytes("Vigência até 31/12/2025 — cláusula".encode("cp1252"))
    assert "Vigência até 31/12/2025" in extractor.extract(txt).full_text
    md = tmp_path / "notas.md"
    md.write_text("# Reunião\nPrazo de entrega: 30 dias", encoding="utf-8")
    assert "Prazo de entrega" in extractor.extract(md).full_text


def test_pdf_protegido_por_senha(docs_dir, tmp_path):
    from pypdf import PdfReader, PdfWriter

    source = docs_dir / "Contratos" / "034-2022" / "Contrato_034_2022.pdf"
    for user_password, expected in (("segredo", extractor.STATUS_CORROMPIDO), ("", extractor.STATUS_TEXTO)):
        writer = PdfWriter()
        for page in PdfReader(str(source)).pages:
            writer.add_page(page)
        writer.encrypt(user_password=user_password, owner_password="dono", algorithm="RC4-128")
        path = tmp_path / f"protegido_{bool(user_password)}.pdf"
        with open(path, "wb") as fh:
            writer.write(fh)
        result = extractor.extract(path, ocr_engine=None)
        assert result.status == expected, result.error
        if user_password:
            assert "senha" in result.error
