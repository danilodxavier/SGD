"""Relatórios do checklist em CSV, TXT e JSON (PDF, DOCX e XLSX ficam para a fase 11)."""
import csv
import io
import json

from app.checklist.matcher import STATUS_LABELS
from app.services.report_writers import safe_cell

FORMATS = {
    "csv": "text/csv; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "json": "application/json; charset=utf-8",
}


def _evidence_text(ev):
    parts = [ev["filename"]]
    if ev.get("page"):
        parts.append(f"pág. {ev['page']}")
    if ev.get("section"):
        parts.append(ev["section"])
    if ev.get("note"):
        parts.append(ev["note"])
    return " — ".join(parts)


def to_csv(data):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")  # ponto e vírgula: abre corretamente no Excel em pt-BR
    writer.writerow(["Item", "Grupo", "Requisito", "Prioridade", "Status", "Confiança", "Justificativa",
                     "Documentos", "Evidências"])
    for item in data["items"]:
        evs = item["evidences"]
        writer.writerow(safe_cell(v) for v in [
            f"{item['position']:02d}", item["category"] or "", item["description"], item["priority"],
            STATUS_LABELS.get(item["status"], item["status"] or "NÃO AVALIADO"), item["confidence"] or "",
            item["justification"] or "",
            " | ".join(dict.fromkeys(ev["filename"] for ev in evs)),
            " | ".join(_evidence_text(ev) for ev in evs),
        ])
    return ("﻿" + out.getvalue()).encode("utf-8")  # BOM para o Excel reconhecer UTF-8


def to_txt(data):
    c = data["checklist"]
    lines = [f"CHECKLIST: {c['name']}"]
    if c.get("contract_ref"):
        lines.append(f"Contrato: {c['contract_ref']}")
    lines.append(f"Avaliado em: {c.get('last_run_at') or 'não avaliado'}")
    lines.append("Resumo: " + ", ".join(f"{STATUS_LABELS.get(k, k)}: {v}" for k, v in data["summary"].items()))
    for item in data["items"]:
        lines += ["", f"ITEM {item['position']:02d}", item["description"]]
        if item["category"]:
            lines.append(f"Grupo: {item['category']}")
        lines.append(f"STATUS: {STATUS_LABELS.get(item['status'], 'NÃO AVALIADO')}")
        if item["confidence"]:
            lines.append(f"Confiança: {item['confidence']}")
        if item["justification"]:
            lines.append(f"Justificativa: {item['justification']}")
        evs = item["evidences"]
        if evs:
            lines.append("")
            lines.append("Documento:" if len(evs) == 1 else "Documentos:")
            lines += [ev["filename"] for ev in {ev["filename"]: ev for ev in evs}.values()]
            lines.append("")
            lines.append("Evidência:")
            lines += [_evidence_text(ev) for ev in evs]

    org = data.get("organization")
    if org:
        if org["folders"]:
            lines += ["", "ORGANIZAÇÃO VIRTUAL DOS DOCUMENTOS (os arquivos originais não foram movidos)", "CHECKLIST"]
        for folder in org["folders"]:
            lines.append(f"├── {folder['name']}")
            lines += [f"│   └── {d['filename']}  (itens {', '.join(d['items'])})" for d in folder["documents"]]
        for title, key in (("Itens sem documento", "without_documents"), ("Itens a conferir", "to_review")):
            if org[key]:
                lines += ["", f"{title}:"] + [f"  ITEM {i['position']:02d} — {i['description']} "
                                               f"({STATUS_LABELS.get(i['status'], i['status'])})" for i in org[key]]
    return "\n".join(lines).encode("utf-8")


def to_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def render(data, fmt):
    return {"csv": to_csv, "txt": to_txt, "json": to_json}[fmt](data)
