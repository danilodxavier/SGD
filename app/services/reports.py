"""Relatórios: resultado da consulta, inventário documental, checklist, documentos ausentes,
conflitos e contratos identificados. Todo conteúdo vem do índice local, com fonte."""
import re
from collections import Counter
from datetime import datetime

from app.checklist import organizer
from app.checklist.matcher import (
    AUSENTE, NAO_IDENTIFICADO, PARCIAL, STATUS_LABELS, VENCIDO,
)
from app.contracts.items import load_items
from app.core.config import settings
from app.core.database import get_conn, get_documents_root
from app.core.logging import get_logger
from app.retrieval.search import documents_for_contract
from app.services import checklist as checklist_service
from app.services import documents as documents_service
from app.services.questions import MSG_CONFLITO, MSG_INFERENCIA, Answerer, answer_question
from app.services.report_writers import FORMATS, Report, Section, Table, render

log = get_logger("reports")

REPORTS = {
    "consulta": {"title": "Resultado da consulta", "params": ["question"],
                 "description": "Resposta a uma pergunta, com conflitos, trechos e fontes."},
    "inventario": {"title": "Inventário documental", "params": [],
                   "description": "Todos os documentos do diretório, com tipo, status e contrato relacionado."},
    "checklist": {"title": "Checklist", "params": ["checklist_id"],
                  "description": "Atendimento de cada item, evidências e organização virtual dos documentos."},
    "ausentes": {"title": "Documentos ausentes", "params": ["checklist_id?"],
                 "description": "Itens de checklist sem documento, vencidos ou incompletos e arquivos que saíram do diretório."},
    "conflitos": {"title": "Conflitos documentais", "params": [],
                  "description": "Informações divergentes entre documentos de um mesmo contrato e alterações por aditivos."},
    "contratos": {"title": "Contratos identificados", "params": [],
                  "description": "Dados de cada contrato e sua situação após os termos aditivos."},
}
REPORT_EXTENSIONS = set(FORMATS) | {"txt"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-.]+$")

# campos analisados por contrato: (grupo de coleta, rótulo, campo extraído)
CONTRACT_FIELDS = [
    ("valor", "Valor", "valor"),
    ("vigencia", "Início da vigência", "vigencia_inicio"),
    ("vigencia", "Término da vigência", "vigencia_fim"),
    ("contratada", "Contratada", "contratada"),
    ("contratada", "CNPJ da contratada", "cnpj"),
    ("processo", "Processo", "processo"),
]


class ReportError(ValueError):
    """Erro de parâmetros com mensagem para o usuário."""


def _where(page):
    return str(page) if page else "—"


def _br_datetime(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return iso or ""


CONFIDENCE = {"alta": "alta", "media": "média", "baixa": "baixa"}


def _root_meta():
    return [("Diretório documental", get_documents_root())]


# ---------------------------------------------------------------- consulta

def build_consulta(question=None, **_):
    question = (question or "").strip()
    if len(question) < 3:
        raise ReportError("Informe a pergunta para gerar o relatório da consulta.")
    res = answer_question(question)
    sections = [Section("Resposta", paragraphs=[res["answer"]] + ([res["note"]] if res.get("note") else []))]
    if res["conflicts"]:
        sections.append(Section(
            "Conflito identificado",
            paragraphs=["Os documentos apresentam valores divergentes. É necessária conferência documental."],
            table=Table(["Documento", "Página", "Valor", "Trecho"],
                        [[c["filename"], _where(c["page"]), c["value"], c.get("excerpt") or ""]
                         for c in res["conflicts"]], [2.2, 0.6, 1.2, 5])))
    if res["passages"]:
        sections.append(Section("Trechos dos documentos", table=Table(
            ["Documento", "Página", "Seção", "Trecho"],
            [[p["filename"], _where(p["page"]), p.get("section") or "", p["text"]] for p in res["passages"]],
            [2, 0.6, 1.6, 6])))
    sections.append(Section(
        "Fontes",
        paragraphs=[] if res["sources"] else ["Nenhuma fonte: a informação não foi localizada nos documentos."],
        table=Table(["Documento", "Página", "Seção", "Trecho"],
                    [[s["filename"], _where(s["page"]), s.get("section") or "", s.get("excerpt") or ""]
                     for s in res["sources"]], [2, 0.6, 1.6, 6]) if res["sources"] else None))
    ai = res.get("ai") or {}
    engine = (f"IA local ({ai['model']}) — resposta validada nos trechos" if ai.get("validated")
              else "Mecanismo local (regras e busca nos documentos)")
    meta = [("Pergunta", question), ("Tipo de resposta", res["kind_label"]), ("Confiança", res["confidence"]),
            ("Mecanismo", engine)]
    if res.get("warnings"):
        sections[0].paragraphs += res["warnings"]
    if res.get("contract"):
        meta.append(("Contrato", res["contract"]))
    return Report("consulta", "Resultado da consulta", "Resposta fundamentada exclusivamente nos documentos locais.",
                  meta + _root_meta(), sections, primary=len(sections) - 1,
                  data={"pergunta": question, **res})


# ---------------------------------------------------------------- inventário

def build_inventario(**_):
    docs = documents_service.list_documents(limit=1_000_000)["items"]
    by_status = Counter(d["status_label"] for d in docs)
    by_type = Counter(d["doc_type_label"] for d in docs)
    rows = [[
        d["filename"], str(_folder(d["relative_path"])), d["doc_type_label"] + (f" ({d['ordinal']}º)" if d["ordinal"] else ""),
        d["status_label"], d["contract_ref"] or "", d["pages"] or "", round((d["size"] or 0) / 1024, 1),
        _br_datetime(d["modified_at"]), d["error"] or "",
    ] for d in docs]
    sections = [
        Section("Resumo por status", table=Table(["Status", "Quantidade"], sorted(by_status.items()), [3, 1])),
        Section("Resumo por tipo de documento", table=Table(["Tipo", "Quantidade"], sorted(by_type.items()), [3, 1])),
        Section("Documentos", table=Table(
            ["Arquivo", "Pasta", "Tipo", "Status", "Contrato", "Páginas", "Tamanho (KB)", "Modificado em", "Observação"],
            rows, [2.6, 2, 1.4, 1.5, 0.9, 0.6, 0.8, 1.3, 2.4])),
    ]
    return Report("inventario", "Inventário documental", f"{len(docs)} documento(s) no diretório.",
                  _root_meta(), sections, landscape=True, primary=2,
                  data={"documentos": docs, "por_status": by_status, "por_tipo": by_type})


def _folder(relative_path):
    parts = re.split(r"[\\/]", relative_path or "")
    return "\\".join(parts[:-1]) or "."


# ---------------------------------------------------------------- checklist

def _evidence_text(ev):
    parts = [ev["filename"]] + ([f"pág. {ev['page']}"] if ev.get("page") else []) + ([ev["note"]] if ev.get("note") else [])
    return " — ".join(parts)


def build_checklist(checklist_id=None, **_):
    if not checklist_id:
        raise ReportError("Selecione o checklist.")
    data = checklist_service.get(int(checklist_id))
    if data is None:
        raise ReportError("Checklist não encontrado.")
    c = data["checklist"]
    org = organizer.organize(data["items"])
    sections = []
    if not c.get("last_run_at"):
        sections.append(Section("Situação", paragraphs=["O checklist ainda não foi executado."]))
    sections.append(Section("Resumo", table=Table(
        ["Status", "Quantidade"], [[STATUS_LABELS[k], v] for k, v in data["summary"].items()], [3, 1])))
    sections.append(Section("Itens", table=Table(
        ["Item", "Grupo", "Requisito", "Prioridade", "Status", "Confiança", "Justificativa", "Evidências"],
        [[f"{i['position']:02d}", i["category"] or "", i["description"], i["priority"],
          STATUS_LABELS.get(i["status"], "NÃO AVALIADO"), CONFIDENCE.get(i["confidence"], ""), i["justification"] or "",
          "\n".join(_evidence_text(ev) for ev in i["evidences"])] for i in data["items"]],
        [0.5, 1.3, 2.2, 0.8, 1.2, 0.8, 4.2, 3.2])))
    bullets = [f"{f['name']}: " + "; ".join(f"{d['filename']} (itens {', '.join(d['items'])})" for d in f["documents"])
               for f in org["folders"]]
    sections.append(Section(
        "Organização virtual dos documentos",
        paragraphs=["Agrupamento lógico para atendimento do checklist. Nenhum arquivo foi copiado, movido ou renomeado."
                    if bullets else "Nenhum documento comprova itens deste checklist."],
        bullets=bullets))
    for title, key in (("Itens sem documento", "without_documents"), ("Itens a conferir", "to_review")):
        if org[key]:
            sections.append(Section(title, bullets=[
                f"ITEM {i['position']:02d} — {i['description']} ({STATUS_LABELS[i['status']]})" for i in org[key]]))
    meta = [("Checklist", c["name"]), ("Contrato", c.get("contract_ref") or "todos os documentos"),
            ("Avaliado em", _br_datetime(c.get("last_run_at")) or "não avaliado"),
            ("Itens", str(len(data["items"])))]
    primary = next(i for i, s in enumerate(sections) if s.title == "Itens")
    return Report("checklist", f"Checklist — {c['name']}", "Atendimento dos requisitos com base nos documentos locais.",
                  meta + _root_meta(), sections, landscape=True, primary=primary,
                  data={**data, "organizacao": org})


# ---------------------------------------------------------------- ausentes

def build_ausentes(checklist_id=None, **_):
    if checklist_id:
        found = checklist_service.get(int(checklist_id))
        if found is None:
            raise ReportError("Checklist não encontrado.")
        checklists = [found]
    else:
        checklists = [checklist_service.get(c["id"]) for c in checklist_service.list_all()]

    def rows(statuses):
        out = []
        for data in checklists:
            c = data["checklist"]
            for i in data["items"]:
                if i["status"] in statuses:
                    out.append([c["name"], c.get("contract_ref") or "", f"{i['position']:02d}", i["description"],
                                STATUS_LABELS[i["status"]], i["justification"] or ""])
        return out

    columns = ["Checklist", "Contrato", "Item", "Requisito", "Status", "Justificativa"]
    widths = [1.6, 0.9, 0.5, 2.4, 1.3, 5]
    removed = documents_service.list_documents(status="REMOVIDO", limit=1_000_000)["items"]
    not_run = [d["checklist"]["name"] for d in checklists if not d["checklist"].get("last_run_at")]
    sections = [
        Section("Documentos ausentes", table=Table(columns, rows({AUSENTE, NAO_IDENTIFICADO}), widths)),
        Section("Documentos vencidos ou incompletos", table=Table(columns, rows({VENCIDO, PARCIAL}), widths)),
        Section("Arquivos que deixaram o diretório documental", table=Table(
            ["Arquivo", "Pasta", "Tipo", "Contrato", "Registrado em"],
            [[d["filename"], _folder(d["relative_path"]), d["doc_type_label"], d["contract_ref"] or "",
              _br_datetime(d["indexed_at"])] for d in removed], [2.5, 2.5, 1.5, 1, 1.5])),
    ]
    if not checklists:
        sections.insert(0, Section("Observação", paragraphs=["Nenhum checklist cadastrado."]))
    elif not_run:
        sections.insert(0, Section("Observação", paragraphs=[
            "Checklists ainda não executados (sem resultado): " + ", ".join(not_run) + "."]))
    scope = checklists[0]["checklist"]["name"] if checklist_id else "todos os checklists"
    return Report("ausentes", "Documentos ausentes",
                  "Pendências identificadas nos checklists e arquivos que não estão mais no diretório.",
                  [("Abrangência", scope)] + _root_meta(), sections, landscape=True,
                  primary=next(i for i, s in enumerate(sections) if s.title == "Documentos ausentes"))


# ---------------------------------------------------------------- análise por contrato

def contract_refs(conn):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT contract_ref FROM documents WHERE contract_ref IS NOT NULL AND status != 'REMOVIDO' "
        "ORDER BY contract_ref")]


def analyze_contract(conn, ref):
    """Conflitos, alterações por aditivo e valor vigente de cada campo de um contrato."""
    answerer = Answerer(conn, "")
    answerer.ref = ref
    answerer.doc_ids = documents_for_contract(conn, ref)
    collected = {}
    result = {"conflicts": [], "changes": [], "current": {}}
    for group, label, field in CONTRACT_FIELDS:
        if group not in collected:
            collected[group] = answerer.collect(group)
        evs = [e for e in collected[group] if e.field == field]
        if field == "valor":
            evs = [e for e in evs if e.qualifier == "global"]
        if not evs:
            continue
        situation, base, latest = answerer.resolve(evs)
        if situation == "conflito":
            result["conflicts"] += [{"field": label, "evidence": e} for e in base]
        elif situation == "alterado":
            result["changes"].append({"field": label, "base": base, "latest": latest})
            result["current"][field] = latest
        else:
            result["current"][field] = evs[0]
    return result


def build_conflitos(**_):
    conflict_rows, change_rows = [], []
    with get_conn() as conn:
        for ref in contract_refs(conn):
            analysis = analyze_contract(conn, ref)
            for c in analysis["conflicts"]:
                e = c["evidence"]
                conflict_rows.append([ref, c["field"], e.filename, _where(e.page), e.value, e.excerpt])
            for ch in analysis["changes"]:
                original = "; ".join(sorted({f"{e.value} ({e.filename})" for e in ch["base"]})) or "—"
                latest = ch["latest"]
                change_rows.append([ref, ch["field"], original, latest.filename, latest.value])
    paragraphs = [MSG_CONFLITO, "Nenhuma informação foi escolhida automaticamente: confira as fontes listadas."] \
        if conflict_rows else ["Nenhum conflito identificado entre os documentos dos contratos."]
    sections = [
        Section("Conflitos identificados", paragraphs=paragraphs, table=Table(
            ["Contrato", "Campo", "Documento", "Página", "Valor", "Trecho"], conflict_rows,
            [0.9, 1.3, 2.2, 0.6, 1.3, 5]) if conflict_rows else None),
        Section("Alterações registradas em termos aditivos",
                paragraphs=[f"Valores alterados por documento posterior. {MSG_INFERENCIA}"] if change_rows
                else ["Nenhuma alteração por termo aditivo identificada."],
                table=Table(["Contrato", "Campo", "Valor original", "Documento posterior", "Novo valor"],
                            change_rows, [0.9, 1.3, 3, 2.4, 1.3]) if change_rows else None),
    ]
    return Report("conflitos", "Conflitos documentais", "Divergências entre documentos de um mesmo contrato.",
                  _root_meta(), sections, landscape=True, primary=0,
                  data={"conflitos": [dict(zip(["contrato", "campo", "documento", "pagina", "valor", "trecho"], r))
                                      for r in conflict_rows],
                        "alteracoes": [dict(zip(["contrato", "campo", "valor_original", "documento", "novo_valor"], r))
                                       for r in change_rows]})


# ---------------------------------------------------------------- contratos

def build_contratos(**_):
    contracts = documents_service.list_contracts()
    first = {}
    for c in sorted(contracts, key=lambda c: c["source_document_id"]):
        first.setdefault(c["contract_number"], c)
    base_rows, status_rows, item_rows, data = [], [], [], []
    with get_conn() as conn:
        for ref, c in sorted(first.items()):
            for items in load_items(conn, ref, documents_for_contract(conn, ref)).values():
                item_rows += [[ref, i["item_number"] or "", i["description"], i["unit"] or "", i["quantity"] or "",
                               i["unit_value"] or "", i["total_value"] or "", f"{i['filename']} ({i['location']})"]
                              for i in items]
            analysis = analyze_contract(conn, ref)
            current = analysis["current"]
            ids = documents_for_contract(conn, ref)
            amendments = conn.execute(
                f"SELECT filename, ordinal FROM documents WHERE doc_type = 'ADITIVO' AND status != 'REMOVIDO' "
                f"AND id IN ({','.join('?' * len(ids))}) ORDER BY ordinal, filename", ids).fetchall() if ids else []
            conflicts = sorted({x["field"] for x in analysis["conflicts"]})
            changed = {ch["field"] for ch in analysis["changes"]}
            end = current.get("vigencia_fim")
            value = current.get("valor")
            base_rows.append([
                ref, c["process_number"] or "", c["contractor"] or "", c["cnpj"] or "", c["object"] or "",
                c["value"] or "", f"{c['start_date'] or '?'} a {c['end_date'] or '?'}" + (f" ({c['term']})" if c["term"] else ""),
                c["signature_date"] or "", c["filename"],
            ])
            status_rows.append([
                ref,
                "divergente" if "Término da vigência" in conflicts else
                (f"{end.value}" + (" (por aditivo)" if "Término da vigência" in changed else "") if end else "não identificado"),
                "divergente" if "Valor" in conflicts else
                (f"{value.value}" + (" (por aditivo)" if "Valor" in changed else "") if value else "não identificado"),
                "\n".join(f"{a['ordinal']}º — {a['filename']}" if a["ordinal"] else a["filename"] for a in amendments)
                or "nenhum",
                ", ".join(conflicts) or "nenhuma",
            ])
            data.append({**c, "termino_atual": end.value if end else None, "valor_atual": value.value if value else None,
                         "aditivos": [a["filename"] for a in amendments], "divergencias": conflicts})
    sections = [
        Section("Contratos", table=Table(
            ["Contrato", "Processo", "Contratada", "CNPJ", "Objeto", "Valor original", "Vigência original",
             "Assinatura", "Fonte"], base_rows, [0.8, 1.5, 1.8, 1.4, 3.4, 1.1, 1.6, 0.9, 1.8])),
        Section("Situação após termos aditivos",
                paragraphs=["Valores marcados “por aditivo” consideram o documento mais recente localizado. "
                            f"{MSG_INFERENCIA} Campos “divergentes” constam do relatório de conflitos."],
                table=Table(["Contrato", "Término da vigência", "Valor global", "Termos aditivos", "Divergências"],
                            status_rows, [0.9, 1.6, 1.6, 3, 2])),
        Section("Itens contratados", table=Table(
            ["Contrato", "Item", "Descrição", "Unidade", "Quantidade", "Valor unitário", "Valor total", "Fonte"],
            item_rows, [0.8, 0.5, 3, 0.8, 0.8, 1.1, 1.1, 2.2])),
    ]
    return Report("contratos", "Contratos identificados", f"{len(first)} contrato(s) identificado(s).",
                  _root_meta(), sections, landscape=True, primary=0, data={"contratos": data})


BUILDERS = {
    "consulta": build_consulta,
    "inventario": build_inventario,
    "checklist": build_checklist,
    "ausentes": build_ausentes,
    "conflitos": build_conflitos,
    "contratos": build_contratos,
}


# ---------------------------------------------------------------- geração e arquivos

def generate(kind, fmt, **params):
    """Gera o relatório, salva uma cópia em data\\reports e devolve (nome, conteúdo, tipo)."""
    if kind not in BUILDERS:
        raise ReportError("Relatório desconhecido.")
    fmt = (fmt or "").lower()
    if fmt not in FORMATS:
        raise ReportError("Formato não suportado. Use PDF, DOCX, XLSX, CSV ou JSON.")
    report = BUILDERS[kind](**params)
    content = render(report, fmt)
    suffix = ""
    if kind == "checklist":
        suffix = "_" + re.sub(r"[^A-Za-z0-9]+", "_", report.title.split("—", 1)[-1]).strip("_")[:40]
    filename = f"{kind}{suffix}_{datetime.now():%Y%m%d_%H%M%S}.{fmt}"
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / filename).write_bytes(content)
    log.info("Relatório gerado: %s", filename)
    return filename, content, FORMATS[fmt]


def list_files():
    folder = settings.reports_dir
    if not folder.exists():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lstrip(".").lower() in REPORT_EXTENSIONS]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size,
             "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")} for p in files]


def file_path(name):
    """Caminho de um relatório salvo, aceitando apenas nomes simples dentro de data\\reports."""
    if not SAFE_NAME.match(name or "") or name.startswith("."):
        return None
    path = (settings.reports_dir / name).resolve()
    if path.parent != settings.reports_dir.resolve() or not path.is_file():
        return None
    return path


def media_type(path):
    return FORMATS.get(path.suffix.lstrip(".").lower(), "text/plain; charset=utf-8")
