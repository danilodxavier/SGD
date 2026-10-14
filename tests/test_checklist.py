import base64
import io
from datetime import date

import pytest
from docx import Document

from app.checklist.parser import parse
from app.services import checklist
from tests.helpers import logged_client

TODAY = date(2026, 10, 14)
HEADERS = {"X-Requested-With": "AgenteDocumental"}

CHECKLIST = """DOCUMENTOS CONTRATUAIS
1. Contrato assinado (obrigatório)
2. Termo aditivo de prorrogação
3. Termo aditivo de reajuste
4. Contrato vigente
5. Planilha de itens
6. Portaria de designação do fiscal
DOCUMENTOS DE REGULARIDADE
7. Certidão de regularidade do FGTS
8. Certidão negativa de débitos trabalhistas
9. Certidões FGTS, trabalhista e INSS
10. Garantia contratual (se houver)
11. Contrato 099/2023 assinado
12. Contrato assinado
"""


# ---------- interpretação ----------

def test_parser_numeracao_grupos_e_prioridade():
    items = parse(CHECKLIST)
    assert len(items) == 12
    assert items[0].description == "Contrato assinado"
    assert items[0].priority == "alta"
    assert items[0].category == "DOCUMENTOS CONTRATUAIS"
    assert items[6].category == "DOCUMENTOS DE REGULARIDADE"
    assert items[9].description == "Garantia contratual" and items[9].priority == "baixa"


def test_parser_marcadores_e_linhas_de_planilha():
    items = parse("Item | Descrição | Obrigatoriedade\n1 | Contrato assinado | Obrigatório\n- Portaria do fiscal\n"
                  "a) Nota fiscal\n[ ] Relatório mensal")
    assert [i.description for i in items] == ["Contrato assinado", "Portaria do fiscal", "Nota fiscal",
                                              "Relatório mensal"]
    assert items[0].priority == "alta"


def test_lista_simples_em_maiusculas_nao_vira_grupo():
    items = parse("CONTRATO ASSINADO\nCERTIDÃO DO FGTS")
    assert [i.description for i in items] == ["CONTRATO ASSINADO", "CERTIDÃO DO FGTS"]


# ---------- avaliação ----------

def _run(ref="034/2022"):
    c = checklist.create("Teste", CHECKLIST, ref)
    result = checklist.run(c["checklist"]["id"], today=TODAY)
    return result, {i["position"]: i for i in result["items"]}


def test_status_de_cada_item(indexed):
    _, items = _run()
    expected = {
        1: "ATENDIDO",              # fecho com local e data de assinatura
        2: "ATENDIDO",
        3: "DUVIDA",                # há aditivo, mas não trata de reajuste
        4: "VENCIDO",               # vigência prorrogada até 28/02/2024
        5: "ATENDIDO",
        6: "DUVIDA",                # portaria digitalizada, sem OCR não há como conferir
        7: "ATENDIDO",              # FGTS válido até 30/12/2030
        8: "VENCIDO",               # CNDT válida até 10/01/2023
        9: "PARCIALMENTE_ATENDIDO",  # falta INSS
        10: "NAO_IDENTIFICADO",
        11: "INCOMPATIVEL",         # nenhum contrato menciona 099/2023
        12: "DUPLICADO",
    }
    assert {k: v["status"] for k, v in items.items()} == expected


def test_evidencias_com_documento_e_pagina(indexed):
    _, items = _run()
    signed = items[1]
    assert signed["evidences"][0]["filename"] == "Contrato_034_2022.pdf"
    assert signed["evidences"][0]["page"] == 2
    assert "cópia idêntica" in signed["justification"]
    assert "28/02/2024" in items[4]["justification"]
    assert "INSS" in items[9]["justification"]
    assert items[10]["evidences"] == []
    assert "digitalizado" in items[6]["justification"]


def test_sem_contrato_avalia_todos_os_documentos(indexed):
    result, items = _run(ref=None)
    assert items[7]["status"] == "ATENDIDO"
    assert items[4]["status"] == "VENCIDO"  # único contrato nos documentos


def test_organizacao_virtual(indexed):
    result, _ = _run()
    org = checklist.organization(result["checklist"]["id"])
    folders = {f["name"]: [d["filename"] for d in f["documents"]] for f in org["folders"]}
    assert folders["01 — Contrato"] == ["Contrato_034_2022.pdf"]
    assert "Certidao_FGTS.txt" in folders["03 — Comprovação de Regularidade"]
    assert [i["position"] for i in org["without_documents"]] == [10]
    assert {i["position"] for i in org["to_review"]} == {3, 6, 11}


def test_exportacao_txt_e_csv(indexed, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    result, _ = _run()
    cid = result["checklist"]["id"]
    _, txt, _ = checklist.export(cid, "txt")
    text = txt.decode("utf-8")
    assert "ITEM 01\nContrato assinado" in text and "STATUS: ATENDIDO" in text
    assert "ORGANIZAÇÃO VIRTUAL" in text
    name, csv_bytes, _ = checklist.export(cid, "csv")
    assert csv_bytes.decode("utf-8-sig").startswith("Item;Grupo;Requisito")
    assert (tmp_path / "data" / "reports" / name).exists()


def test_validacoes(indexed):
    with pytest.raises(checklist.ChecklistError):
        checklist.create("", CHECKLIST)
    with pytest.raises(checklist.ChecklistError):
        checklist.create("Vazio", "   \n\n")
    with pytest.raises(checklist.ChecklistError):
        checklist.create("Contrato inválido", CHECKLIST, "abc")


def test_documentos_originais_preservados(indexed):
    root = indexed["root"]
    before = {p: (p.stat().st_mtime, p.stat().st_size) for p in root.rglob("*") if p.is_file()}
    _run()
    after = {p: (p.stat().st_mtime, p.stat().st_size) for p in root.rglob("*") if p.is_file()}
    assert before == after


# ---------- API ----------

@pytest.fixture()
def client(indexed):
    with logged_client() as c:
        yield c


def test_api_fluxo_completo(client):
    r = client.post("/api/checklists", json={"name": "API", "text": CHECKLIST, "contract_ref": "34/2022"},
                    headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    cid = data["checklist"]["id"]
    assert data["checklist"]["contract_ref"] == "034/2022"
    assert len(data["items"]) == 12

    run = client.post(f"/api/checklists/{cid}/run", headers=HEADERS).json()
    assert run["summary"]["ATENDIDO"] >= 4
    assert client.get("/api/checklists").json()[0]["id"] == cid
    assert client.get(f"/api/checklists/{cid}/organization").json()["folders"]

    exported = client.get(f"/api/checklists/{cid}/export", params={"format": "csv"})
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    assert client.get(f"/api/checklists/{cid}/export", params={"format": "exe"}).status_code == 400

    assert client.delete(f"/api/checklists/{cid}", headers=HEADERS).status_code == 200
    assert client.get(f"/api/checklists/{cid}").status_code == 404


def test_api_carrega_checklist_de_docx(client):
    doc = Document()
    for line in ("1. Contrato assinado", "2. Certidão do FGTS"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    r = client.post("/api/checklists/parse-file", headers=HEADERS,
                    json={"filename": "lista.docx", "content_base64": base64.b64encode(buf.getvalue()).decode()})
    assert r.status_code == 200
    assert "Certidão do FGTS" in r.json()["text"]
    bad = client.post("/api/checklists/parse-file", headers=HEADERS,
                      json={"filename": "virus.exe", "content_base64": "AAAA"})
    assert bad.status_code == 400
