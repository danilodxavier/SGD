"""Cadastro, execução, organização e exportação de checklists."""
import base64
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.checklist import organizer, report
from app.checklist.matcher import DUPLICADO, STATUS_LABELS, Matcher
from app.checklist.parser import item_key, parse
from app.contracts.extractor import parse_contract_ref
from app.core.config import settings
from app.core.database import get_conn
from app.core.logging import get_logger
from app.ingestion import extractor

log = get_logger("checklist")

UPLOAD_EXTENSIONS = {".txt", ".md", ".csv", ".docx", ".doc", ".rtf", ".odt", ".xlsx", ".xlsm", ".xls", ".ods", ".pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ChecklistError(ValueError):
    """Erro de validação com mensagem para o usuário."""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def normalize_contract(value):
    value = (value or "").strip()
    if not value:
        return None
    ref = parse_contract_ref(f"contrato {value}")
    if not ref:
        raise ChecklistError("Número de contrato inválido. Use o formato 034/2022.")
    return ref


def _validate(name, text):
    name = (name or "").strip()
    if not name:
        raise ChecklistError("Informe um nome para o checklist.")
    items = parse(text)
    if not items:
        raise ChecklistError("Nenhum item foi identificado. Informe um requisito por linha.")
    return name[:200], items


def _save_items(conn, checklist_id, items):
    conn.execute("DELETE FROM checklist_items WHERE checklist_id = ?", (checklist_id,))
    for it in items:
        conn.execute(
            "INSERT INTO checklist_items (checklist_id, position, category, description, requirement, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (checklist_id, it.position, it.category, it.description, it.requirement, it.priority),
        )


def create(name, text, contract_ref=None, created_by=None):
    name, items = _validate(name, text)
    ref = normalize_contract(contract_ref)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO checklist (name, created_at, updated_at, contract_ref, source_text, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, _now(), _now(), ref, text, created_by),
        )
        _save_items(conn, cur.lastrowid, items)
    log.info("Checklist criado: id=%s itens=%d", cur.lastrowid, len(items))
    return get(cur.lastrowid)


def update(checklist_id, name, text, contract_ref=None):
    name, items = _validate(name, text)
    ref = normalize_contract(contract_ref)
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM checklist WHERE id = ?", (checklist_id,)).fetchone():
            return None
        conn.execute("UPDATE checklist SET name = ?, contract_ref = ?, source_text = ?, updated_at = ?, "
                     "last_run_at = NULL WHERE id = ?", (name, ref, text, _now(), checklist_id))
        _save_items(conn, checklist_id, items)
    return get(checklist_id)


def delete(checklist_id):
    """Remove o checklist e seus resultados (dados da aplicação; nenhum documento é afetado)."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM checklist WHERE id = ?", (checklist_id,))
    return cur.rowcount > 0


def list_all():
    with get_conn() as conn:
        rows = conn.execute("SELECT c.id, c.name, c.contract_ref, c.created_at, c.updated_at, c.last_run_at, "
                            "c.created_by, u.name AS created_by_name FROM checklist c "
                            "LEFT JOIN users u ON u.id = c.created_by "
                            "ORDER BY COALESCE(c.updated_at, c.created_at) DESC").fetchall()
        out = []
        for r in rows:
            counts = Counter(s[0] for s in conn.execute(
                "SELECT status FROM checklist_items WHERE checklist_id = ?", (r["id"],)))
            out.append({**dict(r), "items": sum(counts.values()),
                        "summary": {k: v for k, v in counts.items() if k}})
    return out


def get(checklist_id):
    with get_conn() as conn:
        c = conn.execute("SELECT c.*, u.name AS created_by_name FROM checklist c "
                         "LEFT JOIN users u ON u.id = c.created_by WHERE c.id = ?", (checklist_id,)).fetchone()
        if not c:
            return None
        items = [dict(r) for r in conn.execute(
            "SELECT id, position, category, description, requirement, priority, status, confidence, justification, "
            "evaluated_at FROM checklist_items WHERE checklist_id = ? ORDER BY position", (checklist_id,))]
        by_item = {i["id"]: i for i in items}
        for i in items:
            i["evidences"] = []
            i["status_label"] = STATUS_LABELS.get(i["status"], "NÃO AVALIADO")
        for m in conn.execute(
                "SELECT m.checklist_item_id, m.document_id, m.page, m.section, m.evidence, m.justification, "
                "d.filename, d.doc_type FROM checklist_matches m JOIN checklist_items i ON i.id = m.checklist_item_id "
                "JOIN documents d ON d.id = m.document_id WHERE i.checklist_id = ? ORDER BY m.id", (checklist_id,)):
            by_item[m["checklist_item_id"]]["evidences"].append({
                "document_id": m["document_id"], "filename": m["filename"], "doc_type": m["doc_type"],
                "page": m["page"], "section": m["section"], "excerpt": m["evidence"], "note": m["justification"],
            })
    summary = Counter(i["status"] for i in items if i["status"])
    ordered = {k: summary[k] for k in STATUS_LABELS if summary.get(k)}
    return {"checklist": dict(c), "items": items, "summary": ordered, "status_labels": STATUS_LABELS}


def run(checklist_id, today=None):
    data = get(checklist_id)
    if data is None:
        return None
    with get_conn() as conn:
        matcher = Matcher(conn, data["checklist"]["contract_ref"], today=today)
        ocr_ids = {r[0] for r in conn.execute("SELECT id FROM documents WHERE status = 'COM_OCR'")}
        seen = {}
        for item in data["items"]:
            key = item_key(item["description"])
            if key in seen:
                result_status, confidence = DUPLICADO, "alta"
                justification = f"Requisito repetido do item {seen[key]:02d}; avaliado apenas uma vez."
                evidences = []
            else:
                seen[key] = item["position"]
                ev = matcher.evaluate(item["requirement"] or item["description"])
                result_status, confidence, justification, evidences = ev.status, ev.confidence, ev.justification, \
                    ev.evidences
                if any(e.document_id in ocr_ids for e in evidences):
                    justification += " Evidência lida por OCR (documento digitalizado): confira no original."
                    confidence = "media" if confidence == "alta" else confidence
            conn.execute("DELETE FROM checklist_matches WHERE checklist_item_id = ?", (item["id"],))
            seen_docs = set()
            for e in evidences:
                if (e.document_id, e.page) in seen_docs:
                    continue
                seen_docs.add((e.document_id, e.page))
                conn.execute(
                    "INSERT INTO checklist_matches (checklist_item_id, document_id, status, confidence, justification, "
                    "page, section, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (item["id"], e.document_id, result_status, confidence, e.note, e.page, e.section, e.excerpt),
                )
            conn.execute("UPDATE checklist_items SET status = ?, confidence = ?, justification = ?, evaluated_at = ? "
                         "WHERE id = ?", (result_status, confidence, justification, _now(), item["id"]))
        conn.execute("UPDATE checklist SET last_run_at = ? WHERE id = ?", (_now(), checklist_id))
    result = get(checklist_id)
    log.info("Checklist executado: id=%s resultado=%s", checklist_id, result["summary"])
    return result


def organization(checklist_id):
    data = get(checklist_id)
    return None if data is None else organizer.organize(data["items"])


def export(checklist_id, fmt):
    if fmt in ("pdf", "docx", "xlsx"):
        from app.services import reports  # importação tardia: reports depende deste módulo

        if get(checklist_id) is None:
            return None
        return reports.generate("checklist", fmt, checklist_id=checklist_id)
    if fmt not in report.FORMATS:
        raise ChecklistError("Formato não suportado. Use PDF, DOCX, XLSX, CSV, TXT ou JSON.")
    data = get(checklist_id)
    if data is None:
        return None
    data["organization"] = organizer.organize(data["items"])
    content = report.render(data, fmt)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", data["checklist"]["name"]).strip("_")[:40] or "checklist"
    filename = f"checklist_{checklist_id}_{slug}_{datetime.now():%Y%m%d_%H%M%S}.{fmt}"
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / filename).write_bytes(content)  # cópia em data\reports para rastreabilidade
    log.info("Relatório de checklist exportado: %s", filename)
    return filename, content, report.FORMATS[fmt]


def text_from_upload(filename, content_base64):
    """Extrai o texto de um arquivo enviado pelo painel para preencher o checklist."""
    ext = Path(filename or "").suffix.lower()
    if ext not in UPLOAD_EXTENSIONS:
        raise ChecklistError("Formato não suportado. Use TXT, MD, CSV, DOC, DOCX, RTF, ODT, XLS, XLSX, ODS ou PDF.")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except ValueError as exc:
        raise ChecklistError("Não foi possível ler o arquivo enviado.") from exc
    if len(data) > MAX_UPLOAD_BYTES:
        raise ChecklistError("Arquivo muito grande (limite de 10 MB).")
    cache = settings.data_dir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    temp = cache / f"checklist_{uuid.uuid4().hex}{ext}"
    try:
        temp.write_bytes(data)
        result = extractor.extract(temp)
    finally:
        temp.unlink(missing_ok=True)
    if result.status not in extractor.SEARCHABLE_STATUSES:
        raise ChecklistError(f"Não foi possível extrair o texto do arquivo. {result.error or ''}".strip())
    return result.full_text
