import os
import time

from app.core.database import get_conn
from app.indexing.duplicates import find_duplicates
from app.indexing.indexer import run_index
from app.retrieval.search import documents_for_contract, search
from app.services.questions import AUSENCIA, CONFLITO, FATO, INFERENCIA, TRECHOS, answer_question


# ---------- indexação ----------

def test_indexacao_inicial(indexed):
    r = indexed["result"]
    assert r["found"] == 11
    assert r["new"] == 11
    assert r["errors"] == 1  # arquivo corrompido


def test_indexacao_incremental_nao_reprocessa(indexed):
    again = run_index()
    assert again["unchanged"] == 11 and again["new"] == 0 and again["changed"] == 0


def test_indexacao_detecta_alteracao_e_remocao(indexed):
    root = indexed["root"]
    nota = root / "Outros" / "anotacoes.txt"
    nota.write_text("Conteúdo alterado.", encoding="utf-8")
    future = time.time() + 5
    os.utime(nota, (future, future))
    (root / "Outros" / "foto_documento.png").unlink()
    result = run_index()
    assert result["changed"] == 1
    assert result["removed"] == 1


def test_documentos_originais_preservados(indexed):
    root = indexed["root"]
    before = {p: p.stat().st_mtime for p in root.rglob("*") if p.is_file()}
    run_index(force=True)
    after = {p: p.stat().st_mtime for p in root.rglob("*") if p.is_file()}
    assert before == after


# ---------- busca ----------

def test_busca_por_cnpj_e_por_numero(indexed):
    with get_conn() as conn:
        hits = search(conn, "12.345.678/0001-90")
        assert any(h["filename"] == "Contrato_034_2022.pdf" for h in hits)
        assert search(conn, "12345678000190")
        ids = documents_for_contract(conn, "034/2022")
        files = {r["filename"] for r in conn.execute(
            f"SELECT filename FROM documents WHERE id IN ({','.join('?' * len(ids))})", ids)}
    assert {"Contrato_034_2022.pdf", "1_Termo_Aditivo_034_2022.docx", "Planilha_Itens_034_2022.xlsx",
            "Resumo_contrato_034.txt"} <= files
    assert "anotacoes.txt" not in files


def test_busca_ignora_acentos(indexed):
    with get_conn() as conn:
        assert search(conn, "vigencia prorrogacao")


def test_duplicidade(indexed):
    with get_conn() as conn:
        groups = find_duplicates(conn)["identical"]
    assert len(groups) == 1
    assert {d["filename"] for d in groups[0]} == {"Contrato_034_2022.pdf", "Copia_Contrato.pdf"}


# ---------- perguntas ----------

def test_encerramento_considera_aditivo(indexed):
    res = answer_question("Quando encerra o contrato 034/2022?")
    assert res["kind"] == INFERENCIA
    assert "28/02/2024" in res["answer"] and "28/02/2023" in res["answer"]
    assert any(s["filename"] == "1_Termo_Aditivo_034_2022.docx" for s in res["sources"])


def test_valor_conflitante(indexed):
    res = answer_question("Qual o valor do contrato 034/2022?")
    assert res["kind"] == CONFLITO
    values = {c["value"] for c in res["conflicts"]}
    assert {"R$ 120.000,00", "R$ 100.000,00"} <= values


def test_contratada_e_cnpj(indexed):
    res = answer_question("Quem é a contratada do contrato 034/2022?")
    assert res["kind"] == FATO
    assert "ALFA SERVIÇOS DE LIMPEZA LTDA" in res["answer"]
    res = answer_question("Qual o CNPJ da contratada?")  # sem número: único contrato identificado
    assert res["kind"] == FATO and "12.345.678/0001-90" in res["answer"]
    assert res["note"]


def test_objeto_com_fonte_e_pagina(indexed):
    res = answer_question("Qual é o objeto do contrato 034/2022?")
    assert res["kind"] == FATO
    assert "limpeza e conservação predial" in res["answer"]
    assert res["sources"][0]["page"] == 1


def test_aditivos(indexed):
    res = answer_question("Quais termos aditivos existem no contrato 034/2022?")
    assert res["kind"] == FATO and "1_Termo_Aditivo_034_2022.docx" in res["answer"]
    res = answer_question("Qual foi o último aditivo do contrato 034/2022?")
    assert "1º Termo Aditivo" in res["answer"] and "28/02/2024" in res["answer"]


def test_itens(indexed):
    res = answer_question("Quais são os itens do contrato 034/2022?")
    assert res["kind"] == FATO
    assert "Item 1 — Servente de limpeza — 4 posto — valor unitário R$ 1.800,00 — valor total R$ 7.200,00" \
        in res["answer"]
    assert res["sources"][0]["filename"] == "Planilha_Itens_034_2022.xlsx"


def test_informacao_ausente(indexed):
    res = answer_question("Qual a forma de pagamento do contrato 034/2022?")
    assert res["kind"] == AUSENCIA
    assert res["answer"] == "Não localizei essa informação nos documentos disponibilizados."
    assert res["sources"] == []


def test_contrato_inexistente(indexed):
    res = answer_question("Qual o valor do contrato 999/2030?")
    assert res["kind"] == AUSENCIA and "999/2030" in res["answer"]


def test_pergunta_livre_com_trechos(indexed):
    res = answer_question("manutenção do ar-condicionado do bloco B")
    assert res["kind"] == TRECHOS
    assert res["sources"]
