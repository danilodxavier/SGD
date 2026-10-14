"""Avaliação de cada item do checklist contra os documentos indexados.

Princípio: um item só é ATENDIDO quando há documento que o comprove. Na falta de
evidência suficiente, o resultado é DÚVIDA ou NÃO IDENTIFICADO — nunca uma suposição.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.contracts.extractor import P_CLOSING, P_CNPJ, parse_contract_ref, validity_dates
from app.core.text import excerpt, flatten, fold
from app.ingestion.extractor import SEARCHABLE_STATUSES
from app.retrieval.citations import best_excerpt
from app.retrieval.search import coverage, documents_for_contract, fts_expression, query_terms, run_fts, search
from app.services.questions import Answerer

ATENDIDO = "ATENDIDO"
PARCIAL = "PARCIALMENTE_ATENDIDO"
AUSENTE = "AUSENTE"
DUVIDA = "DUVIDA"
DUPLICADO = "DUPLICADO"
VENCIDO = "VENCIDO"
INCOMPATIVEL = "INCOMPATIVEL"
NAO_IDENTIFICADO = "NAO_IDENTIFICADO"

STATUS_LABELS = {
    ATENDIDO: "ATENDIDO",
    PARCIAL: "PARCIALMENTE ATENDIDO",
    AUSENTE: "AUSENTE",
    DUVIDA: "DÚVIDA",
    DUPLICADO: "DUPLICADO",
    VENCIDO: "VENCIDO",
    INCOMPATIVEL: "INCOMPATÍVEL",
    NAO_IDENTIFICADO: "NÃO IDENTIFICADO",
}


@dataclass
class Rule:
    key: str
    label: str
    doc_types: set
    patterns: list


# Ordem importa: regras mais específicas primeiro ("nota fiscal" antes de "fiscal", "aditivo" antes de "contrato").
RULES = [
    Rule("aditivo", "termo aditivo", {"ADITIVO"}, [r"aditivo"]),
    Rule("apostilamento", "apostilamento", {"APOSTILAMENTO"}, [r"apostila"]),
    Rule("regularidade", "certidão de regularidade", {"CERTIDAO"},
         [r"certid", r"regularidade", r"\bfgts\b", r"\bcndt\b", r"\binss\b", r"\bcrf\b", r"debitos"]),
    Rule("fatura", "nota fiscal / fatura", {"FATURA"}, [r"nota\s+fiscal", r"\bfatura", r"\bnf-?e\b"]),
    Rule("relatorio", "relatório", {"RELATORIO"}, [r"relatorio"]),
    Rule("notificacao", "notificação", {"NOTIFICACAO"}, [r"notifica"]),
    Rule("fiscalizacao", "portaria de designação de fiscal", {"PORTARIA"}, [r"portaria", r"\bfiscal\b", r"fiscaliza"]),
    Rule("edital", "edital", {"EDITAL"}, [r"\bedital\b"]),
    Rule("termo_referencia", "termo de referência", {"TERMO_REFERENCIA"}, [r"termo\s+de\s+referencia"]),
    Rule("planilha", "planilha de itens", {"PLANILHA"}, [r"planilha", r"\bitens\b", r"relacao\s+de\s+itens"]),
    Rule("contrato", "termo de contrato", {"CONTRATO"}, [r"\bcontrato\b"]),
]

REGULARITY_PARTS = {
    "FGTS": [r"\bfgts\b", r"fundo\s+de\s+garantia", r"\bcrf\b"],
    "Trabalhista": [r"trabalhist", r"\bcndt\b"],
    "INSS / Previdenciária": [r"\binss\b", r"previdenci"],
    "Federal / Dívida Ativa da União": [r"receita\s+federal", r"tributos\s+federais", r"divida\s+ativa\s+da\s+uniao"],
    "Estadual": [r"estadua"],
    "Municipal": [r"municipa"],
}

# Palavras que descrevem a forma de apresentação, não o conteúdo exigido.
FILLER = set("""
apresentar apresentacao apresentado apresentada copia copias documento documentos comprovante comprovantes
comprovacao comprovar anexar anexo anexos original autenticada autenticado simples valido valida validos validas
vigente vigentes vigencia atualizado atualizada obrigatorio obrigatoria opcional houver assinado assinada assinados
assinadas assinatura assinaturas devidamente respectivo respectiva respectivos respectivas
""".split())
GENERIC = {"termo", "termos", "contrato", "contratos", "contratual", "servico", "servicos", "empresa", "contratada",
           "contratante", "processo"}
VIGENCY = re.compile(r"vigent|vigencia|em\s+vigor|\bvalido\b")
SIGNATURE = re.compile(r"assinad|assinatura")
SIGNED_EXPLICIT = re.compile(r"assinad[oa]\s+(?:eletronicamente|digitalmente)|documento\s+assinado|assinado\s+por")
SIGNED_MENTION = re.compile(r"\bassinad[oa]s?\b|\bassinaturas?\b")


@dataclass
class Evidence:
    document_id: int
    filename: str
    doc_type: str
    page: int | None = None
    section: str | None = None
    excerpt: str | None = None
    note: str = ""

    def as_dict(self):
        return dict(self.__dict__)


@dataclass
class Evaluation:
    status: str
    confidence: str
    justification: str
    evidences: list = field(default_factory=list)


def _names(docs, limit=4):
    names = [f"“{d['filename']}”" for d in docs[:limit]]
    more = f" e mais {len(docs) - limit}" if len(docs) > limit else ""
    return ", ".join(names) + more


def _plural(n, singular, plural):
    return singular if n == 1 else plural


class Matcher:
    def __init__(self, conn, contract_ref=None, today=None):
        self.conn = conn
        self.ref = contract_ref
        self.today = today or date.today()
        self.docs = {r["id"]: dict(r) for r in conn.execute(
            "SELECT id, filename, doc_type, status, hash, contract_ref, ordinal, modified_at FROM documents "
            "WHERE status != 'REMOVIDO' ORDER BY id")}
        self.scope = self._scope(contract_ref) if contract_ref else None
        self._text_cache = {}

    # ---------- apoio ----------
    def _scope(self, ref):
        """Documentos do contrato + documentos que citam o CNPJ da contratada (ex.: certidões)."""
        ids = set(documents_for_contract(self.conn, ref))
        cnpjs = {r[0] for r in self.conn.execute(
            "SELECT cnpj FROM contracts WHERE contract_number = ? AND cnpj IS NOT NULL", (ref,))}
        for cnpj in cnpjs:
            ids |= self._docs_with_phrase(cnpj)
        return ids

    def _docs_with_phrase(self, phrase):
        return {r[0] for r in self.conn.execute(
            "SELECT DISTINCT c.document_id FROM chunks_fts JOIN document_chunks c ON c.id = chunks_fts.rowid "
            "WHERE chunks_fts MATCH ?", ('"' + phrase.replace('"', '""') + '"',))}

    def _pool(self):
        return [d for i, d in self.docs.items() if self.scope is None or i in self.scope]

    def _chunks(self, document_id):
        return self.conn.execute(
            "SELECT text, page, section FROM document_chunks WHERE document_id = ? ORDER BY chunk_number",
            (document_id,)).fetchall()

    def _text(self, document_id):
        if document_id not in self._text_cache:
            self._text_cache[document_id] = "\n".join(c["text"] for c in self._chunks(document_id))
        return self._text_cache[document_id]

    def _evidence(self, d, terms=(), note=""):
        """Melhor trecho do documento para os termos; sem termos, o início do documento."""
        rows = run_fts(self.conn, fts_expression(list(terms)), [d["id"]], limit=1) if terms else []
        if rows:
            r = rows[0]
            return Evidence(d["id"], d["filename"], d["doc_type"], r["page"], r["section"],
                            best_excerpt(r["text"], terms), note)
        chunks = self._chunks(d["id"])
        if chunks:
            c = chunks[0]
            return Evidence(d["id"], d["filename"], d["doc_type"], c["page"], c["section"],
                            excerpt(flatten(c["text"]), 0, 0, 160), note)
        return Evidence(d["id"], d["filename"], d["doc_type"], note=note)

    def _dedupe(self, docs):
        """Mantém um arquivo por conteúdo idêntico e descreve as cópias."""
        first, copies = {}, []
        for d in docs:
            if d["hash"] and d["hash"] in first:
                copies.append((first[d["hash"]], d))
            else:
                first[d["hash"] or f"id{d['id']}"] = d
        unique = list(first.values())
        note = ""
        if copies:
            pairs = "; ".join(f"“{c['filename']}” é cópia idêntica de “{o['filename']}”" for o, c in copies)
            note = f" Observação: {pairs}."
        return unique, note

    # ---------- avaliação ----------
    def evaluate(self, description):
        folded = fold(description)
        rule = next((r for r in RULES if any(re.search(p, folded) for p in r.patterns)), None)
        terms = [t for t in query_terms(description) if fold(t) not in FILLER]
        if rule is None and not terms:
            return Evaluation(NAO_IDENTIFICADO, "baixa",
                              "Não foi possível interpretar o requisito. Descreva o documento esperado "
                              "(ex.: “Certidão de regularidade do FGTS”).")
        if rule is None:
            return self._free_text(description, terms)
        return self._by_rule(rule, description, folded, terms)

    def _scope_text(self):
        return f" vinculados ao Contrato nº {self.ref}" if self.ref else ""

    def _by_rule(self, rule, description, folded, terms):
        typed = [d for d in self._pool() if d["doc_type"] in rule.doc_types]
        if not typed:
            if self.scope is not None:
                outside = [d for i, d in self.docs.items() if i not in self.scope and d["doc_type"] in rule.doc_types]
                unreadable = [d for d in outside if d["status"] not in SEARCHABLE_STATUSES]
                outside = [d for d in outside if d["status"] in SEARCHABLE_STATUSES]
                if unreadable and not outside:
                    return Evaluation(
                        DUVIDA, "baixa",
                        f"Localizei {_names(unreadable)} pelo nome do arquivo, mas sem texto extraível "
                        f"(digitalizado); não foi possível verificar se pertence ao Contrato nº {self.ref}. "
                        "Ative o OCR ou confira o documento manualmente.",
                        [Evidence(d["id"], d["filename"], d["doc_type"]) for d in unreadable[:3]])
                if outside:
                    return Evaluation(
                        INCOMPATIVEL, "media",
                        f"Localizei {rule.label} apenas em documentos não vinculados ao Contrato nº {self.ref}: "
                        f"{_names(outside)}. Confira se algum deles se aplica a este contrato.",
                        [self._evidence(d) for d in outside[:3]])
            hits = search(self.conn, description, limit=3, doc_ids=self._scope_ids(), terms=terms, min_coverage=0.8) \
                if terms else []
            if hits:
                return Evaluation(
                    DUVIDA, "baixa",
                    f"Nenhum documento foi classificado como {rule.label}, mas há trechos que mencionam o requisito. "
                    "Confira se algum deles atende ao item.",
                    [Evidence(h["document_id"], h["filename"], h["doc_type"], h["page"], h["section"], h["excerpt"])
                     for h in hits])
            return Evaluation(AUSENTE, "media",
                              f"Não localizei {rule.label} nos documentos disponibilizados{self._scope_text()}.")

        # identificadores citados no item (nº de contrato, CNPJ) precisam constar do documento
        ref = parse_contract_ref(description)
        if ref and ref != self.ref:
            matching = set(documents_for_contract(self.conn, ref))
            filtered = [d for d in typed if d["id"] in matching]
            if not filtered:
                return Evaluation(INCOMPATIVEL, "media",
                                  f"Localizei {rule.label} ({_names(typed)}), mas nenhum menciona o Contrato nº {ref}.",
                                  [self._evidence(d) for d in typed[:3]])
            typed = filtered
        for m in P_CNPJ.finditer(folded):
            cnpj = description[m.start():m.end()]
            matching = self._docs_with_phrase(cnpj)
            filtered = [d for d in typed if d["id"] in matching]
            if not filtered:
                return Evaluation(INCOMPATIVEL, "media",
                                  f"Localizei {rule.label} ({_names(typed)}), mas nenhum menciona o CNPJ {cnpj}.",
                                  [self._evidence(d) for d in typed[:3]])
            typed = filtered

        readable = [d for d in typed if d["status"] in SEARCHABLE_STATUSES]
        if not readable:
            return Evaluation(DUVIDA, "baixa",
                              f"Localizei {_names(typed)} pelo nome do arquivo, mas sem texto extraível (provavelmente "
                              "digitalizado). Confira o documento manualmente.",
                              [Evidence(d["id"], d["filename"], d["doc_type"]) for d in typed[:3]])
        unique, copies_note = self._dedupe(readable)

        if rule.key == "regularidade":
            return self._regularity(unique, folded, copies_note)

        specific = [t for t in terms if fold(t) not in GENERIC
                    and not any(re.search(p, fold(t)) for p in rule.patterns)]
        if specific:
            about = [d for d in unique if coverage(specific, d["filename"] + "\n" + self._text(d["id"])) >= 0.99]
            if not about:
                return Evaluation(
                    DUVIDA, "baixa",
                    f"Localizei {rule.label} ({_names(unique)}), mas nenhum trata de "
                    f"“{' '.join(specific)}”. Confira se o documento atende ao item.",
                    [self._evidence(d) for d in unique[:3]])
            unique = about

        if rule.key == "contrato" and VIGENCY.search(folded):
            return self._vigency(unique, copies_note)
        if SIGNATURE.search(folded):
            return self._signature(unique, rule, copies_note)

        n = len(unique)
        return Evaluation(
            ATENDIDO, "alta",
            f"Localizei {n} {_plural(n, 'documento classificado', 'documentos classificados')} como {rule.label}: "
            f"{_names(unique)}.{copies_note}",
            [self._evidence(d, specific) for d in unique[:5]])

    def _scope_ids(self):
        return sorted(self.scope) if self.scope is not None else None

    def _regularity(self, docs, folded, copies_note):
        parts = [p for p, pats in REGULARITY_PARTS.items() if any(re.search(x, folded) for x in pats)]
        if not parts:
            parts = ["Regularidade"]
        missing, expired, valid, unknown, evidences = [], [], [], [], []
        for part in parts:
            pats = REGULARITY_PARTS.get(part)
            found = [d for d in docs if pats is None
                     or any(re.search(x, fold(d["filename"] + " " + self._text(d["id"])[:6000])) for x in pats)]
            if not found:
                missing.append(part)
                continue
            best = None  # (data de validade, documento, trecho)
            for d in found:
                dates = validity_dates(self._text(d["id"]))
                if dates:
                    top = max(dates)
                    if best is None or top[0] > best[0][0]:
                        best = (top, d)
            if best is None:
                unknown.append(part)
                evidences.append(self._evidence(found[0], note=f"{part}: validade não identificada no texto"))
                continue
            (iso, display, snippet), d = best
            ok = date.fromisoformat(iso) >= self.today
            (valid if ok else expired).append(f"{part} ({'válida' if ok else 'vencida'} — validade até {display})")
            evidences.append(Evidence(d["id"], d["filename"], d["doc_type"], None, None, snippet,
                                      f"{part}: validade até {display}"))

        found_text = "; ".join(valid + expired + [f"{p} (validade não identificada)" for p in unknown])
        if missing and len(missing) == len(parts):
            return Evaluation(AUSENTE, "media",
                              f"Não localizei certidão de regularidade referente a: {', '.join(missing)}"
                              f"{self._scope_text()}.", evidences)
        if missing:
            return Evaluation(PARCIAL, "media",
                              f"Localizei: {found_text}. Não localizei: {', '.join(missing)}.{copies_note}", evidences)
        if expired:
            return Evaluation(VENCIDO, "alta",
                              f"Há certidão com validade expirada em relação a {self.today:%d/%m/%Y}: {found_text}."
                              f"{copies_note}", evidences)
        if unknown:
            return Evaluation(ATENDIDO, "media",
                              f"Localizei: {found_text}. Confira a validade no documento original.{copies_note}",
                              evidences)
        return Evaluation(ATENDIDO, "alta", f"Localizei: {found_text}.{copies_note}", evidences)

    def _vigency(self, docs, copies_note):
        ref = self.ref
        if ref is None:
            refs = {d["contract_ref"] for d in docs if d["contract_ref"]}
            if len(refs) != 1:
                return Evaluation(DUVIDA, "baixa",
                                  "Há mais de um contrato nos documentos. Informe o número do contrato no checklist "
                                  "para verificar a vigência.", [self._evidence(d) for d in docs[:3]])
            ref = refs.pop()
        answerer = Answerer(self.conn, "")
        answerer.doc_ids = documents_for_contract(self.conn, ref)
        ends = [e for e in answerer.collect("vigencia") if e.field == "vigencia_fim"]
        if not ends:
            return Evaluation(DUVIDA, "baixa",
                              f"Localizei o Contrato nº {ref}, mas não identifiquei a data de término da vigência.",
                              [self._evidence(d) for d in docs[:2]])
        situation, base, latest = answerer.resolve(ends)
        if situation == "conflito":
            return Evaluation(DUVIDA, "baixa",
                              "Os documentos apresentam datas de término divergentes: "
                              + "; ".join(f"“{e.filename}”: {e.value}" for e in base) + ". É necessária conferência.",
                              [self._from_answer(e) for e in base])
        end = latest or ends[0]
        how = (f"conforme {end.filename}" if latest is None
               else f"considerando o termo aditivo mais recente (“{end.filename}”); esta conclusão decorre da "
                    "relação entre os documentos localizados")
        evidences = [self._from_answer(end)] + [self._from_answer(e) for e in base[:1] if latest is not None]
        confidence = "alta" if latest is None else "media"
        if date.fromisoformat(end.key) < self.today:
            return Evaluation(VENCIDO, confidence,
                              f"A vigência do Contrato nº {ref} encerrou-se em {end.value}, {how}.{copies_note}",
                              evidences)
        return Evaluation(ATENDIDO, confidence,
                          f"O Contrato nº {ref} está vigente até {end.value}, {how}.{copies_note}", evidences)

    @staticmethod
    def _from_answer(e):
        return Evidence(e.document_id, e.filename, e.doc_type, e.page, e.section, e.excerpt)

    def _signature(self, docs, rule, copies_note):
        explicit, mention, closing = [], [], []
        for d in docs:
            for c in self._chunks(d["id"]):
                flat = flatten(c["text"])
                f = fold(flat)
                for pattern, bucket in ((SIGNED_EXPLICIT, explicit), (SIGNED_MENTION, mention), (P_CLOSING, closing)):
                    m = pattern.search(f)
                    if m:
                        bucket.append(Evidence(d["id"], d["filename"], d["doc_type"], c["page"], c["section"],
                                               excerpt(flat, m.start(), m.end(), 140)))
                        break
        where = lambda e: f"“{e.filename}”" + (f", pág. {e.page}" if e.page else "")  # noqa: E731
        if explicit:
            e = explicit[0]
            return Evaluation(ATENDIDO, "alta", f"O documento {where(e)} registra assinatura expressa.{copies_note}",
                              explicit[:3])
        if closing:
            e = closing[0]
            return Evaluation(
                ATENDIDO, "media",
                f"O documento {where(e)} contém local e data de assinatura no fecho. A presença das assinaturas "
                f"deve ser conferida no original.{copies_note}", closing[:3])
        if mention:
            e = mention[0]
            return Evaluation(
                DUVIDA, "baixa",
                f"O documento {where(e)} menciona assinatura, mas não há evidência textual de que foi assinado. "
                f"Confira o original.{copies_note}", mention[:3])
        return Evaluation(PARCIAL, "media",
                          f"Localizei {rule.label} ({_names(docs)}), mas não identifiquei evidência textual de "
                          f"assinatura. Confira o original.{copies_note}",
                          [self._evidence(d) for d in docs[:3]])

    def _free_text(self, description, terms):
        pool = self._pool()
        by_name = [d for d in pool if coverage(terms, d["filename"].replace("_", " ")) >= 0.99]
        if by_name:
            unique, note = self._dedupe(by_name)
            return Evaluation(ATENDIDO, "media",
                              f"O nome do arquivo {_names(unique)} corresponde ao requisito. Confira o conteúdo.{note}",
                              [self._evidence(d, terms) for d in unique[:3]])
        hits = search(self.conn, description, limit=5, doc_ids=self._scope_ids(), terms=terms, min_coverage=0.5)
        evidences = [Evidence(h["document_id"], h["filename"], h["doc_type"], h["page"], h["section"], h["excerpt"])
                     for h in hits[:3]]
        if hits and hits[0]["coverage"] >= 0.99:
            return Evaluation(DUVIDA, "media",
                              "Localizei trechos que mencionam todos os termos do requisito, mas nenhum documento "
                              "específico para ele. Confira se os trechos abaixo atendem ao item.", evidences)
        if hits:
            return Evaluation(DUVIDA, "baixa",
                              "Localizei apenas menções parciais ao requisito. Confira os trechos abaixo.", evidences)
        return Evaluation(NAO_IDENTIFICADO, "baixa", "NÃO IDENTIFICADO NOS DOCUMENTOS: não localizei evidência "
                                                     "deste requisito nos documentos disponibilizados.")
