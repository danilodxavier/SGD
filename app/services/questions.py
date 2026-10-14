"""Respostas a perguntas em linguagem natural, fundamentadas exclusivamente nos documentos.

Cada resposta é classificada como:
- FATO_DOCUMENTAL: valor encontrado de forma explícita e sem divergência;
- INFERENCIA: conclusão que decorre da relação entre documentos (ex.: aditivo posterior);
- CONFLITO: documentos equivalentes apresentam valores divergentes;
- AUSENCIA: a informação não foi localizada;
- TRECHOS: não há resposta estruturada, mas há trechos pertinentes para conferência.
"""
import re
from collections import defaultdict
from dataclasses import dataclass

from app.contracts.extractor import VIGENCIA_FIELDS, extract, parse_contract_ref
from app.contracts.items import describe, load_items
from app.core.database import get_conn
from app.core.logging import get_logger
from app.core.text import excerpt, flatten, fold
from app.indexing.metadata import DOC_TYPE_LABELS
from app.retrieval.citations import dedupe_sources, source
from app.retrieval.search import documents_for_contract, query_terms, run_fts, search

log = get_logger("questions")

FATO, INFERENCIA, CONFLITO, AUSENCIA, TRECHOS = "FATO_DOCUMENTAL", "INFERENCIA", "CONFLITO", "AUSENCIA", "TRECHOS"
KIND_LABELS = {
    FATO: "Fato documental",
    INFERENCIA: "Inferência documental",
    CONFLITO: "Conflito",
    AUSENCIA: "Informação ausente",
    TRECHOS: "Trechos localizados",
}
MSG_AUSENTE = "Não localizei essa informação nos documentos disponibilizados."
MSG_CONFLITO = ("Foram identificadas informações divergentes entre os documentos. "
                "A aplicação apresenta as fontes e os respectivos conteúdos para conferência.")
MSG_INFERENCIA = "Esta conclusão decorre da relação entre os documentos localizados."
MSG_OCR = ("Parte das fontes foi lida por OCR (reconhecimento de texto em documento digitalizado); "
           "confira os valores no documento original.")
AMENDING = {"ADITIVO", "APOSTILAMENTO"}

# Ordem importa: intenções mais específicas primeiro.
INTENTS = [
    ("comprova_vigencia", ["comprova"]),
    ("relacionados", ["relacionad", "vinculad"]),
    ("valor_atualizado", ["valor atualizado", "valor atual"]),
    ("valor", ["valor", "quanto custa", "quanto custou", "preco"]),
    ("cnpj", ["cnpj"]),
    ("contratada", ["contratada", "fornecedor", "empresa contratada"]),
    ("objeto", ["objeto", "do que se trata"]),
    ("assinatura", ["assinatura", "assinado", "assinou", "celebrado", "firmado"]),
    ("encerramento", ["encerra", "termino", "terminar", "vence", "vencimento", "ate quando", "fim da vigencia",
                      "finaliza"]),
    ("inicio", ["inicio da vigencia", "inicia", "comecou", "comeca"]),
    ("ultimo_aditivo", ["ultimo aditivo", "ultimo termo aditivo"]),
    ("aditivos", ["aditivo"]),
    ("vigencia", ["vigencia", "prazo de vigencia", "prazo do contrato", "vigente"]),
    ("itens", ["itens", "item "]),
    ("clausula", ["pagamento", "obrigac", "penalidade", "sancoes", "sancao", "multa", "reajust", "repactua",
                  "rescis", "fiscaliza", "garantia contratual", "dotacao"]),
    ("processo", ["processo"]),
]

CLAUSE_TOPICS = {
    "pagamento": ["pagamento"],
    "obrigacoes": ["obrigac"],
    "penalidades": ["penalidade", "sanc", "multa", "infrac"],
    "reajuste": ["reajust"],
    "repactuacao": ["repactua"],
    "rescisao": ["rescis", "extinc"],
    "fiscalizacao": ["fiscaliza"],
    "garantia": ["garantia"],
    "dotacao": ["dotac", "orcamentar"],
}

FIELD_GROUPS = {
    "vigencia": (["vigencia", "vigorara", "prorrog*", "termino", "encerra*", "vencimento"], VIGENCIA_FIELDS),
    "valor": (["valor"], ("valor",)),
    "objeto": (["objeto"], ("objeto",)),
    "contratada": (["contratada"], ("contratada", "cnpj")),
    "assinatura": (["assinad*", "assinatura", "celebrad*", "firmad*", "janeiro", "fevereiro", "marco", "abril",
                    "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
                   ("assinatura",)),
    "processo": (["processo"], ("processo",)),
}
CONFIDENCE_LABEL = {"alta": "alta", "media": "média", "baixa": "baixa"}


@dataclass
class Evidence:
    field: str
    value: str
    key: str
    qualifier: str
    confidence: str
    document_id: int
    filename: str
    doc_type: str
    ordinal: int
    modified_at: str
    contract_ref: str | None
    page: int | None
    section: str | None
    excerpt: str

    @property
    def amending(self):
        return self.doc_type in AMENDING

    def as_source(self):
        return source(self.document_id, self.filename, self.page, self.section, self.excerpt, self.doc_type)


def detect_intent(question):
    folded = " " + fold(question) + " "
    for intent, keywords in INTENTS:
        if any(k in folded for k in keywords):
            return intent
    return None


def _quote(e):
    page = f", pág. {e.page}" if e.page else ""
    return f"“{e.filename}”{page}"


def _describe(e):
    if e.doc_type == "ADITIVO" and e.ordinal:
        return f"o {e.ordinal}º Termo Aditivo ({_quote(e)})"
    label = DOC_TYPE_LABELS.get(e.doc_type)
    if label and e.doc_type not in ("OUTRO", "PLANILHA"):
        return f"o documento {_quote(e)} ({label.lower()})"
    return f"o documento {_quote(e)}"


def _cite(evs):
    seen, parts = set(), []
    for e in evs:
        if e.document_id not in seen:
            seen.add(e.document_id)
            parts.append(_quote(e))
    if len(parts) == 1:
        return f"conforme o documento {parts[0]}"
    return "conforme os documentos " + ", ".join(parts[:-1]) + " e " + parts[-1]


def _amend_order(e):
    return (e.ordinal or 0, e.modified_at or "")


def _confidence(evs):
    return "alta" if all(e.confidence == "alta" for e in evs) else "media"


class Answerer:
    def __init__(self, conn, question):
        self.conn = conn
        self.question = question.strip()
        self.ref = None
        self.doc_ids = None
        self.label = "contrato"
        self.note = None

    # ---------- infraestrutura ----------
    def result(self, kind, answer, confidence="baixa", evidences=(), conflicts=None, passages=None, sources=None):
        srcs = dedupe_sources(list(sources or []) + [e.as_source() for e in evidences])
        ocr_ids = self._ocr_documents({s["document_id"] for s in srcs})
        warnings = []
        for s in srcs:
            s["ocr"] = s["document_id"] in ocr_ids
        if ocr_ids:
            warnings.append(MSG_OCR)
            if confidence == "alta":
                confidence = "media"
        return {
            "kind": kind,
            "kind_label": KIND_LABELS[kind],
            "answer": answer,
            "confidence": CONFIDENCE_LABEL.get(confidence, confidence),
            "sources": srcs,
            "conflicts": conflicts or [],
            "passages": passages or [],
            "warnings": warnings,
        }

    def _ocr_documents(self, ids):
        if not ids:
            return set()
        return {r[0] for r in self.conn.execute(
            f"SELECT id FROM documents WHERE status = 'COM_OCR' AND id IN ({','.join('?' * len(ids))})", list(ids))}

    def absent(self, message=MSG_AUSENTE):
        return self.result(AUSENCIA, message, "alta")

    def conflict(self, evs, field_label):
        rows = [{"document_id": e.document_id, "filename": e.filename, "page": e.page, "value": e.value,
                 "doc_type": e.doc_type, "excerpt": e.excerpt} for e in evs]
        text = f"{MSG_CONFLITO}\n\nCampo: {field_label}. É necessária conferência documental."
        return self.result(CONFLITO, text, "baixa", evs, conflicts=rows)

    def collect(self, group, fields=None):
        terms, group_fields = FIELD_GROUPS[group]
        fields = fields or group_fields
        rows = run_fts(self.conn, " OR ".join(terms), self.doc_ids, limit=500)
        # cópias idênticas (mesmo hash) não são citadas como fontes adicionais
        first_by_hash = {}
        for row in rows:
            if row["hash"]:
                first_by_hash[row["hash"]] = min(first_by_hash.get(row["hash"], row["document_id"]), row["document_id"])
        rows = [r for r in rows if not r["hash"] or first_by_hash[r["hash"]] == r["document_id"]]
        evidences, seen = [], set()
        for row in rows:
            flat, matches = extract(row["text"], fields)
            for m in matches:
                k = (row["document_id"], m.field, m.key, m.qualifier)
                if k in seen:
                    continue
                seen.add(k)
                evidences.append(Evidence(
                    m.field, m.value, m.key, m.qualifier, m.confidence, row["document_id"], row["filename"],
                    row["doc_type"], row["ordinal"] or 0, row["modified_at"], row["contract_ref"], row["page"],
                    row["section"], excerpt(flat, m.start, m.end),
                ))
        return evidences

    def resolve(self, evs):
        """Classifica um conjunto de evidências do mesmo campo.

        Retorna (situação, base, mais_recente), em que situação é 'unico', 'alterado' ou 'conflito'.
        """
        base = [e for e in evs if not e.amending]
        amend = [e for e in evs if e.amending]
        if len({e.key for e in evs}) == 1:
            return "unico", evs, None
        if len({e.key for e in base}) > 1:
            return "conflito", base, None
        if amend:
            top = max(_amend_order(e) for e in amend)
            latest = [e for e in amend if _amend_order(e) == top]
            if len({e.key for e in latest}) > 1:
                return "conflito", latest, None
            return "alterado", base, latest[0]
        return "conflito", evs, None

    def multiple_contracts(self, evs, field_label):
        by_contract = defaultdict(list)
        for e in evs:
            by_contract[e.contract_ref or "sem número identificado"].append(e)
        if len(by_contract) <= 1:
            return None
        lines = [f"Foram localizados registros de {field_label} em documentos de contratos diferentes:"]
        for ref, items in sorted(by_contract.items()):
            values = ", ".join(sorted({i.value for i in items}))
            lines.append(f"• Contrato {ref}: {values} ({_cite(items).replace('conforme ', '')})")
        lines.append("Informe o número do contrato na pergunta (ex.: 034/2022) para uma resposta precisa.")
        return self.result(TRECHOS, "\n".join(lines), "media", evs)

    # ---------- execução ----------
    def run(self):
        if len(self.question) < 3:
            return self.result(AUSENCIA, "Digite uma pergunta para pesquisar nos documentos.", "alta")
        intent = detect_intent(self.question)
        self.ref = parse_contract_ref(self.question)
        if self.ref:
            self.doc_ids = documents_for_contract(self.conn, self.ref)
            if not self.doc_ids:
                res = self.absent(f"Não localizei o Contrato nº {self.ref} nos documentos disponibilizados.")
                return self.finish(res, intent)
            self.label = f"Contrato nº {self.ref}"
        elif intent:
            refs = [r[0] for r in self.conn.execute(
                "SELECT DISTINCT contract_ref FROM documents WHERE contract_ref IS NOT NULL AND status != 'REMOVIDO'")]
            if len(refs) == 1:
                self.ref = refs[0]
                self.doc_ids = documents_for_contract(self.conn, self.ref)
                self.label = f"Contrato nº {self.ref}"
                self.note = (f"Como a pergunta não informa o número do contrato, foi considerado o único contrato "
                             f"identificado nos documentos (Contrato nº {self.ref}).")

        handler = getattr(self, f"h_{intent}", None) if intent else None
        res = handler() if handler else self.h_generic()
        return self.finish(res, intent)

    def finish(self, res, intent):
        res["intent"] = intent
        res["contract"] = self.ref
        res["note"] = self.note
        return res

    # ---------- intenções ----------
    def h_encerramento(self):
        evs = [e for e in self.collect("vigencia") if e.field == "vigencia_fim"]
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, "término de vigência")):
            return multi
        situation, base, latest = self.resolve(evs)
        if situation == "unico":
            return self.result(FATO, f"A vigência do {self.label} encerra-se em {evs[0].value}, {_cite(evs)}.",
                               _confidence(evs), evs)
        if situation == "alterado":
            parts = []
            if base:
                parts.append(f"De acordo com {_cite(base).replace('conforme ', '')}, a vigência do {self.label} "
                             f"terminaria em {base[0].value}.")
            parts.append(f"Entretanto, {_describe(latest)} registra término em {latest.value}. "
                         f"Considerando o documento mais recente localizado, o encerramento previsto é "
                         f"{latest.value}.")
            parts.append(MSG_INFERENCIA)
            return self.result(INFERENCIA, " ".join(parts), "media", [latest] + base)
        return self.conflict(base, "término da vigência")

    def h_inicio(self):
        evs = [e for e in self.collect("vigencia") if e.field == "vigencia_inicio"]
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, "início de vigência")):
            return multi
        base = [e for e in evs if not e.amending] or evs
        if len({e.key for e in base}) > 1:
            return self.conflict(base, "início da vigência")
        return self.result(FATO, f"A vigência do {self.label} inicia-se em {base[0].value}, {_cite(base)}.",
                           _confidence(base), base)

    def h_vigencia(self):
        evs = self.collect("vigencia")
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, "vigência")):
            return multi
        base = [e for e in evs if not e.amending]
        amend = sorted((e for e in evs if e.amending), key=_amend_order)
        by_field = {f: [e for e in base if e.field == f and not e.qualifier] for f in VIGENCIA_FIELDS}
        for f, label in (("vigencia_inicio", "início da vigência"), ("vigencia_fim", "término da vigência"),
                         ("vigencia_prazo", "prazo de vigência")):
            if len({e.key for e in by_field[f]}) > 1:
                return self.conflict(by_field[f], label)

        used = []
        pieces = []
        if by_field["vigencia_prazo"]:
            pieces.append(f"vigência de {by_field['vigencia_prazo'][0].value}")
            used += by_field["vigencia_prazo"]
        if by_field["vigencia_inicio"]:
            pieces.append(f"iniciando-se em {by_field['vigencia_inicio'][0].value}")
            used += by_field["vigencia_inicio"]
        if by_field["vigencia_fim"]:
            pieces.append(f"encerrando-se em {by_field['vigencia_fim'][0].value}")
            used += by_field["vigencia_fim"]

        text = ""
        if pieces:
            joined = pieces[0] if len(pieces) == 1 else ", ".join(pieces[:-1]) + " e " + pieces[-1]
            text = f"O {self.label} foi celebrado com {joined}, {_cite(used)}."
        ends = [e for e in amend if e.field == "vigencia_fim"]
        if ends:
            changes = "; ".join(f"{_describe(e)} registra término em {e.value}" for e in ends)
            text = (text + " " if text else "") + f"Há registro de alteração da vigência: {changes}. "
            text += f"Considerando o documento mais recente, o término previsto é {ends[-1].value}. {MSG_INFERENCIA}"
            return self.result(INFERENCIA, text.strip(), "media", used + ends)
        if not text:
            return self.absent()
        return self.result(FATO, text, _confidence(used), used)

    def _values(self):
        evs = self.collect("valor")
        if not evs:
            return None, []
        qualifiers = {e.qualifier for e in evs}
        qualifier = "global" if "global" in qualifiers else sorted(qualifiers)[0]
        return qualifier, [e for e in evs if e.qualifier == qualifier]

    def h_valor(self, updated=False):
        qualifier, evs = self._values()
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, f"valor {qualifier}")):
            return multi
        situation, base, latest = self.resolve(evs)
        label = f"valor {qualifier}"
        if situation == "unico":
            base_docs = [e for e in evs if not e.amending]
            text = f"O {label} do {self.label} é de {evs[0].value}, {_cite(evs)}."
            if updated and base_docs and not any(e.amending for e in evs):
                text += (" Não localizei termos aditivos ou apostilamentos que alterem esse valor "
                         "nos documentos disponibilizados.")
            return self.result(FATO, text, _confidence(evs), evs)
        if situation == "alterado":
            parts = []
            if base:
                parts.append(f"O {label} originalmente registrado para o {self.label} é de {base[0].value}, "
                             f"{_cite(base)}.")
            parts.append(f"Entretanto, {_describe(latest)} registra {label} de {latest.value}.")
            parts.append(f"Considerando o documento mais recente localizado, o valor atualizado é {latest.value}.")
            parts.append(MSG_INFERENCIA)
            return self.result(INFERENCIA, " ".join(parts), "media", [latest] + base)
        return self.conflict(base, label)

    def h_valor_atualizado(self):
        return self.h_valor(updated=True)

    def h_objeto(self):
        evs = self.collect("objeto")
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, "objeto")):
            return multi
        evs.sort(key=lambda e: (e.amending, e.confidence != "alta"))
        best = evs[0]
        obj = best.value.rstrip(".")
        return self.result(FATO, f"O objeto do {self.label} é {obj}, {_cite([best])}.",
                           _confidence([best]), [best] + evs[1:3])

    def _contractor(self):
        evs = self.collect("contratada")
        names = [e for e in evs if e.field == "contratada"]
        cnpjs = [e for e in evs if e.field == "cnpj"]
        return names, cnpjs

    def h_contratada(self):
        names, cnpjs = self._contractor()
        if not names:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(names, "contratada")):
            return multi
        names.sort(key=lambda e: e.confidence != "alta")
        if len({e.key for e in names}) > 1 and len({e.key for e in cnpjs}) != 1:
            return self.conflict(names, "contratada")
        best = names[0]
        text = f"A contratada do {self.label} é {best.value}"
        cnpj = next((c for c in cnpjs if c.document_id == best.document_id), None)
        if cnpj:
            text += f", inscrita no CNPJ sob o nº {cnpj.value}"
        text += f", {_cite([best])}."
        evidence = [best] + ([cnpj] if cnpj else [])
        return self.result(FATO, text, _confidence(evidence), evidence)

    def h_cnpj(self):
        names, cnpjs = self._contractor()
        if not cnpjs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(cnpjs, "CNPJ da contratada")):
            return multi
        if len({e.key for e in cnpjs}) > 1:
            return self.conflict(cnpjs, "CNPJ da contratada")
        best = cnpjs[0]
        name = next((n for n in names if n.document_id == best.document_id), None)
        who = f" ({name.value})" if name else ""
        return self.result(FATO, f"O CNPJ da contratada{who} é {best.value}, {_cite(cnpjs)}.",
                           _confidence(cnpjs), cnpjs + ([name] if name else []))

    def h_assinatura(self):
        evs = [e for e in self.collect("assinatura") if not e.amending]
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, "data de assinatura")):
            return multi
        explicit = [e for e in evs if e.qualifier != "fecho"]
        chosen = explicit or evs
        if len({e.key for e in chosen}) > 1:
            return self.conflict(chosen, "data de assinatura")
        e = chosen[0]
        if explicit:
            text = f"O {self.label} foi assinado em {e.value}, {_cite(chosen)}."
        else:
            text = (f"O documento {_quote(e)} está datado de {e.value} (data registrada no fecho do documento, "
                    f"junto ao local de assinatura).")
        return self.result(FATO, text, _confidence(chosen), chosen)

    def h_processo(self):
        evs = self.collect("processo")
        if not evs:
            return self.absent()
        if self.ref is None and (multi := self.multiple_contracts(evs, "número de processo")):
            return multi
        if len({e.key for e in evs}) > 1:
            return self.conflict(evs, "número do processo")
        return self.result(FATO, f"O {self.label} está vinculado ao Processo nº {evs[0].value}, {_cite(evs)}.",
                           _confidence(evs), evs)

    def _documents(self, where="", params=()):
        sql = ("SELECT id, filename, doc_type, ordinal, modified_at, contract_ref, pages FROM documents "
               "WHERE status != 'REMOVIDO'")
        if self.doc_ids is not None:
            if not self.doc_ids:
                return []
            sql += f" AND id IN ({','.join('?' * len(self.doc_ids))})"
            params = (*self.doc_ids, *params)
        return [dict(r) for r in self.conn.execute(sql + where, params)]

    def _doc_source(self, d):
        return source(d["id"], d["filename"], None, None, None, d["doc_type"])

    def h_aditivos(self):
        docs = sorted(self._documents(" AND doc_type = 'ADITIVO'"), key=lambda d: (d["ordinal"] or 99, d["modified_at"]))
        if not docs:
            return self.absent(f"Não localizei termos aditivos relacionados ao {self.label} nos documentos "
                               f"disponibilizados.")
        lines = [f"Foi localizado 1 termo aditivo relacionado ao {self.label}:" if len(docs) == 1 else
                 f"Foram localizados {len(docs)} termos aditivos relacionados ao {self.label}:"]
        for d in docs:
            order = f"{d['ordinal']}º Termo Aditivo — " if d["ordinal"] else ""
            ref = f" (Contrato {d['contract_ref']})" if self.ref is None and d["contract_ref"] else ""
            lines.append(f"• {order}“{d['filename']}”{ref}")
        return self.result(FATO, "\n".join(lines), "alta", sources=[self._doc_source(d) for d in docs])

    def h_ultimo_aditivo(self):
        docs = self._documents(" AND doc_type = 'ADITIVO'")
        if not docs:
            return self.absent(f"Não localizei termos aditivos relacionados ao {self.label} nos documentos "
                               f"disponibilizados.")
        by_ordinal = all(d["ordinal"] for d in docs)
        last = max(docs, key=lambda d: (d["ordinal"] or 0, d["modified_at"] or ""))
        order = f"o {last['ordinal']}º Termo Aditivo" if last["ordinal"] else "o termo aditivo"
        text = f"O último termo aditivo localizado para o {self.label} é {order}, documento “{last['filename']}”."
        saved = self.doc_ids
        self.doc_ids = [last["id"]]
        changes = [e for e in self.collect("vigencia") if e.field == "vigencia_fim"]
        values = [e for e in self.collect("valor") if e.qualifier == "global"]
        self.doc_ids = saved
        details = []
        if changes:
            details.append(f"término da vigência em {changes[0].value}")
        if values:
            details.append(f"valor global de {values[0].value}")
        if details:
            text += " Ele registra " + " e ".join(details) + "."
        kind = FATO
        if not by_ordinal:
            text += (" A ordem foi definida pela data de modificação dos arquivos, pois nem todos os aditivos "
                     f"indicam sua numeração. {MSG_INFERENCIA}")
            kind = INFERENCIA
        return self.result(kind, text, "alta" if by_ordinal else "media", changes[:1] + values[:1],
                           sources=[self._doc_source(last)])

    def h_relacionados(self):
        if self.ref is None:
            refs = [r[0] for r in self.conn.execute(
                "SELECT DISTINCT contract_ref FROM documents WHERE contract_ref IS NOT NULL AND status != 'REMOVIDO' "
                "ORDER BY contract_ref")]
            if not refs:
                return self.absent("Não identifiquei números de contrato nos documentos disponibilizados.")
            return self.result(TRECHOS, "Informe o número do contrato para listar os documentos relacionados. "
                                        "Contratos identificados: " + ", ".join(refs) + ".", "alta")
        docs = self._documents()
        groups = defaultdict(list)
        for d in docs:
            groups[DOC_TYPE_LABELS.get(d["doc_type"], "Outro")].append(d)
        lines = [f"Localizei {len(docs)} documento{'s' if len(docs) > 1 else ''} que menciona{'m' if len(docs) > 1 else ''} "
                 f"o {self.label}:"]
        for label in sorted(groups):
            lines.append(f"{label}:")
            lines += [f"  • “{d['filename']}”" for d in sorted(groups[label], key=lambda d: (d["ordinal"], d["filename"]))]
        lines.append("Critério: menção ao número do contrato no conteúdo ou no nome do arquivo.")
        return self.result(FATO, "\n".join(lines), "alta", sources=[self._doc_source(d) for d in docs])

    def h_comprova_vigencia(self):
        evs = self.collect("vigencia")
        if not evs:
            return self.absent()
        docs = []
        for e in evs:
            if e.document_id not in [d.document_id for d in docs]:
                docs.append(e)
        lines = [f"Os seguintes documentos contêm informações sobre a vigência do {self.label}:"]
        for e in docs:
            fields = sorted({x.field for x in evs if x.document_id == e.document_id})
            what = ", ".join({"vigencia_inicio": "início", "vigencia_fim": "término",
                              "vigencia_prazo": "prazo"}[f] for f in fields)
            lines.append(f"• {_quote(e)} — {what}")
        return self.result(FATO, "\n".join(lines), _confidence(evs), evs)

    def h_itens(self):
        groups = load_items(self.conn, self.ref, self.doc_ids)
        if groups:
            # o mesmo conteúdo salvo em vários formatos (ex.: DOC e ODT) é listado uma única vez
            distinct = {}
            for items in groups.values():
                key = tuple(describe(i) for i in items)
                distinct.setdefault(key, []).append(items)
            lines, sources = [], []
            for same in distinct.values():
                items, first = same[0], same[0][0]
                n = len(items)
                lines.append(f"Identifiquei {n} {'item' if n == 1 else 'itens'} em “{first['filename']}” "
                             f"({first['location']}):")
                lines += [f"• {describe(i)}" for i in items[:50]]
                if n > 50:
                    lines.append(f"• … e mais {n - 50} itens (consulte o documento).")
                if len(same) > 1:
                    lines.append("  A mesma relação consta de: " + ", ".join(f"“{o[0]['filename']}”" for o in same[1:])
                                 + ".")
                for other in same:
                    o = other[0]
                    sources.append(source(o["source_document_id"], o["filename"], None, o["location"], None,
                                          o["doc_type"]))
            if len(distinct) > 1:
                lines.append("Há relações de itens diferentes entre os documentos; confira qual está vigente.")
            return self.result(FATO, "\n".join(lines), "alta" if len(distinct) == 1 else "media", sources=sources)
        rows = run_fts(self.conn, 'item* OR quantidade OR qtd OR "valor unitario" OR unidade', self.doc_ids, limit=40)
        rows.sort(key=lambda r: (" | " not in r["text"], r["score"]))
        rows = [r for r in rows if " | " in r["text"] or re.search(r"\bitem\b", fold(r["text"]))][:3]
        if not rows:
            return self.absent()
        files = sorted({r["filename"] for r in rows})
        text = (f"Localizei a relação de itens do {self.label} em " + ", ".join(f"“{f}”" for f in files) +
                ". Os dados abaixo foram transcritos diretamente do documento, para conferência.")
        passages = [{"document_id": r["document_id"], "filename": r["filename"], "page": r["page"],
                     "section": r["section"], "text": r["text"]} for r in rows]
        sources = [source(r["document_id"], r["filename"], r["page"], r["section"], None, r["doc_type"]) for r in rows]
        return self.result(TRECHOS, text, "media", passages=passages, sources=sources)

    def h_clausula(self):
        """Transcreve a cláusula do tema perguntado (pagamento, penalidades, rescisão...), sem paráfrase."""
        folded = fold(self.question)
        topic = next((t for t, stems in CLAUSE_TOPICS.items() if any(s in folded for s in stems)), None)
        stems = CLAUSE_TOPICS.get(topic, [])
        rows = run_fts(self.conn, " OR ".join(f"{s}*" for s in stems), self.doc_ids, limit=200) if stems else []
        rows = [r for r in rows if r["section"] and any(s in fold(r["section"]) for s in stems)]
        if not rows:
            return self.h_generic()
        # um documento por conteúdo (cópias idênticas fora), contratos antes de aditivos
        by_doc, hashes = {}, set()
        for r in sorted(rows, key=lambda r: (r["doc_type"] != "CONTRATO", r["document_id"], r["chunk_id"])):
            if r["document_id"] not in by_doc and r["hash"] in hashes:
                continue
            hashes.add(r["hash"])
            by_doc.setdefault(r["document_id"], []).append(r)
        parts, sources = [], []
        for chunks in list(by_doc.values())[:3]:
            first = chunks[0]
            text = flatten("\n".join(c["text"] for c in chunks))
            if text.startswith(first["section"]):  # o título já é citado fora das aspas
                text = text[len(first["section"]):].strip()
            text = text[:1500]
            page = f", pág. {first['page']}" if first["page"] else ""
            parts.append(f"Conforme “{first['section']}” do documento “{first['filename']}”{page}:\n«{text}»")
            sources.append(source(first["document_id"], first["filename"], first["page"], first["section"],
                                  excerpt(text, 0, 0, 200), first["doc_type"]))
        if self.ref is None and len({c[0]["contract_ref"] for c in by_doc.values()}) > 1:
            parts.append("Há cláusulas de contratos diferentes; informe o número do contrato para restringir.")
        return self.result(FATO, "\n\n".join(parts), "alta", sources=sources)

    def h_generic(self):
        extra = {"contrato"} if self.ref else set()
        if self.ref:
            extra |= {fold(p) for p in re.split(r"[/\-]", self.ref)} | {self.ref, str(int(self.ref.split("/")[0]))}
        terms = [t for t in query_terms(self.question, extra) if fold(t) not in extra]
        if not terms:
            return self.absent()
        results = search(self.conn, self.question, limit=5, doc_ids=self.doc_ids, terms=terms)
        if not results:
            return self.absent()
        docs = {r["document_id"] for r in results}
        found = (f"{len(results)} trecho{'s' if len(results) > 1 else ''} em {len(docs)} "
                 f"documento{'s' if len(docs) > 1 else ''}")
        text = (f"Não identifiquei uma resposta estruturada para essa pergunta, mas localizei {found} que "
                f"trata{'m' if len(results) > 1 else ''} do assunto. Confira os trechos e as fontes abaixo.")
        passages = [{"document_id": r["document_id"], "filename": r["filename"], "page": r["page"],
                     "section": r["section"], "text": r["excerpt"]} for r in results]
        sources = [source(r["document_id"], r["filename"], r["page"], r["section"], r["excerpt"], r["doc_type"])
                   for r in results]
        return self.result(TRECHOS, text, "media" if results[0]["coverage"] >= 0.99 else "baixa",
                           passages=passages, sources=sources)


class AnswerProvider:
    """Interface para provedores de resposta (local, OpenAI, LLM local)."""

    name = "base"

    def answer(self, question):
        raise NotImplementedError


class LocalDocumentAnswerProvider(AnswerProvider):
    """Responde apenas com base no índice local, sem serviços externos."""

    name = "local"

    def answer(self, question):
        with get_conn() as conn:
            return Answerer(conn, question).run()


def get_provider():
    from app.services import llm  # importações tardias: os provedores de IA dependem deste módulo

    config = llm.current_config()
    if config["provider"] == "llm_local":
        from app.services.ai_provider import LocalLLMAnswerProvider

        return LocalLLMAnswerProvider(config)
    return LocalDocumentAnswerProvider()


def answer_question(question, username=None):
    provider = get_provider()
    res = provider.answer(question)
    res.setdefault("ai", None)
    res["provider"] = provider.name
    ai = res["ai"] or {}
    log.info("Consulta%s: intenção=%s contrato=%s resultado=%s fontes=%d provedor=%s ia=%s",
             f" de {username}" if username else "", res.get("intent"),
             res.get("contract"), res["kind"], len(res["sources"]), provider.name,
             "validada" if ai.get("validated") else ("descartada" if ai.get("used") else "não usada"))
    return res
