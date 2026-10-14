"""Respostas redigidas por um LLM local, com validação contra os trechos dos documentos.

Fluxo:
1. o mecanismo local responde primeiro (regras, conflitos, inferências);
2. os trechos pertinentes são numerados [F1], [F2]... e enviados ao LLM junto com a análise local;
3. a resposta do LLM só é aceita se: citar apenas trechos existentes; toda data, valor, CNPJ, nº de
   contrato e demais números constarem dos trechos; e, havendo conflito, apresentar todos os valores;
4. caso contrário (ou se a IA estiver indisponível), vale a resposta do mecanismo local, com aviso.
"""
import re
import time
from dataclasses import dataclass

from app.contracts.extractor import CNPJ, MONEY, P_CONTRACT, P_DATE, P_REF_LOOSE, money_key, normalize_contract, parse_date
from app.core.config import settings
from app.core.database import get_conn
from app.core.logging import get_logger
from app.core.text import flatten, fold
from app.retrieval.citations import source
from app.retrieval.search import documents_for_contract, query_terms, search
from app.services import llm
from app.services.questions import (
    AUSENCIA, CONFLITO, FATO, INFERENCIA, KIND_LABELS, MSG_AUSENTE, AnswerProvider, Answerer,
)

log = get_logger("ai")

RESPOSTA_IA = "RESPOSTA_IA"
KIND_LABELS.setdefault(RESPOSTA_IA, "Resposta redigida por IA (validada)")
MAX_PASSAGE_CHARS = 1500

SYSTEM_PROMPT = """Você é um assistente de análise documental de contratos administrativos. Responda em português do Brasil.
REGRAS OBRIGATÓRIAS:
1. Use EXCLUSIVAMENTE as informações dos trechos fornecidos. Não use conhecimento externo, jurídico ou geral.
2. Toda afirmação factual deve terminar com a citação do trecho entre colchetes, por exemplo [F2]. Use apenas os identificadores fornecidos.
3. Não invente nem calcule datas, valores, números, nomes ou cláusulas. Copie-os exatamente como aparecem nos trechos.
4. Se a resposta não estiver nos trechos, responda apenas: "Não localizei essa informação nos documentos disponibilizados."
5. Se os trechos apresentarem informações divergentes, não escolha uma delas: apresente cada valor com sua fonte e diga que é necessária conferência documental.
6. Quando um documento posterior (como um termo aditivo) alterar outro, informe ambos e deixe claro que se trata de interpretação da relação entre os documentos.
7. Seja claro, objetivo e profissional, em até 6 frases, sem títulos nem listas longas."""

P_MONEY = re.compile(MONEY)
P_CNPJ = re.compile(CNPJ)
P_NUMBER = re.compile(r"\d[\d.,/\-]*\d|\d")
P_CITATION = re.compile(r"\[F(\d+)\]")


@dataclass
class Passage:
    ref: int
    document_id: int
    filename: str
    page: int | None
    section: str | None
    text: str
    doc_type: str | None = None


# ---------------------------------------------------------------- contexto

def build_passages(conn, question, local):
    """Trechos citados pela resposta local + trechos mais relevantes da busca."""
    items, seen = [], set()

    def add(document_id, filename, page, section, text, doc_type):
        text = flatten(text)[:MAX_PASSAGE_CHARS]
        key = (document_id, text[:120])
        if text and key not in seen and len(items) < settings.llm_max_passages:
            seen.add(key)
            items.append(Passage(len(items) + 1, document_id, filename, page, section, text, doc_type))

    for s in local["sources"]:
        if s.get("excerpt"):
            add(s["document_id"], s["filename"], s.get("page"), s.get("section"), s["excerpt"], s.get("doc_type"))
    for p in local.get("passages", []):
        add(p["document_id"], p["filename"], p.get("page"), p.get("section"), p["text"], None)

    doc_ids = documents_for_contract(conn, local["contract"]) if local.get("contract") else None
    extra = {"contrato"} if local.get("contract") else set()
    terms = [t for t in query_terms(question, extra) if fold(t) not in extra]
    if terms:
        for r in search(conn, question, limit=settings.llm_max_passages, doc_ids=doc_ids, terms=terms,
                        min_coverage=0.5):
            add(r["document_id"], r["filename"], r["page"], r["section"], r["text"], r["doc_type"])
    return items


def build_messages(question, local, passages):
    preliminary = f"Classificação: {local['kind_label']}\n{local['answer']}"
    if local.get("conflicts"):
        preliminary += "\nValores divergentes: " + "; ".join(
            f"{c['value']} ({c['filename']})" for c in local["conflicts"])
    blocks = []
    for p in passages:
        where = " | ".join(x for x in (f"Documento: {p.filename}", f"Página: {p.page}" if p.page else None,
                                       f"Seção: {p.section}" if p.section else None) if x)
        blocks.append(f"[F{p.ref}] {where}\n{p.text}")
    user = (f"PERGUNTA: {question}\n\n"
            "ANÁLISE PRELIMINAR DO SISTEMA (baseada em regras; use-a como orientação, mas fundamente tudo nos "
            f"trechos):\n{preliminary}\n\nTRECHOS:\n" + "\n\n".join(blocks))
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


# ---------------------------------------------------------------- validação

def _facts(text):
    """Fatos verificáveis de um texto: datas, valores, CNPJs, nº de contrato e demais números."""
    folded = fold(text)
    dates = {parse_date(m.group(1))[1] for m in P_DATE.finditer(folded) if parse_date(m.group(1))}
    money = {money_key(m.group(1)) for m in P_MONEY.finditer(folded)}
    cnpjs = {re.sub(r"\D", "", m.group()) for m in P_CNPJ.finditer(folded)}
    contracts = {normalize_contract(m.group(1), m.group(2)) for m in P_CONTRACT.finditer(folded)}
    contracts |= {normalize_contract(m.group(1), m.group(2)) for m in P_REF_LOOSE.finditer(folded)}
    numbers = set()
    for m in P_NUMBER.finditer(text):
        for part in re.split(r"[.,/\-]", m.group()):
            if len(part) >= 3:
                numbers.add(part.lstrip("0") or "0")
    return {"dates": dates, "money": money, "cnpjs": cnpjs, "contracts": contracts, "numbers": numbers}


def validate(answer, passages, question, local):
    """Lista de motivos para rejeitar a resposta do LLM (vazia = aprovada)."""
    reasons = []
    refs = {p.ref for p in passages}
    cited = {int(n) for n in P_CITATION.findall(answer)}
    absent = "nao localizei" in fold(answer)
    if cited - refs:
        reasons.append("citou trechos inexistentes")
    if not absent and not cited:
        reasons.append("resposta sem citação das fontes")
    if absent and local["kind"] in (FATO, INFERENCIA, CONFLITO):
        reasons.append("não reconheceu informação que consta dos documentos")

    context = _facts(" ".join(p.text for p in passages) + " " + question)
    found = _facts(P_CITATION.sub(" ", answer))
    labels = {"dates": "data", "money": "valor", "cnpjs": "CNPJ", "contracts": "nº de contrato", "numbers": "número"}
    for kind, label in labels.items():
        missing = found[kind] - context[kind]
        if kind == "numbers":  # anos e números que fazem parte de datas/valores já conferidos
            missing = {n for n in missing if not any(n in d.replace("-", "") for d in context["dates"])}
        if missing:
            reasons.append(f"{label} sem respaldo nos trechos: {', '.join(sorted(missing)[:3])}")

    if local["kind"] == CONFLITO:
        answer_money = found["money"]
        answer_dates = found["dates"]
        for c in local["conflicts"]:
            f = _facts(c["value"])
            if (f["money"] and not f["money"] <= answer_money) or (f["dates"] and not f["dates"] <= answer_dates):
                reasons.append("não apresentou todos os valores divergentes")
                break
    return reasons


# ---------------------------------------------------------------- provedor

class LocalLLMAnswerProvider(AnswerProvider):
    name = "llm_local"

    def __init__(self, config=None):
        self.config = config or llm.current_config()

    def answer(self, question):
        with get_conn() as conn:
            local = Answerer(conn, question).run()
            if local["kind"] == AUSENCIA:  # sem trechos, nada a redigir: a ausência é a resposta
                return local
            passages = build_passages(conn, question, local)
            if not passages:
                return local
            ocr_ids = {r[0] for r in conn.execute(
                f"SELECT id FROM documents WHERE status = 'COM_OCR' AND id IN "
                f"({','.join('?' * len({p.document_id for p in passages}))})",
                list({p.document_id for p in passages}))}

        model = self.config["model"]
        start = time.time()
        try:
            text = llm.chat(self.config["base_url"], model, build_messages(question, local, passages))
        except llm.LLMError as exc:
            log.warning("IA indisponível: %s", exc)
            local["warnings"].append(f"IA indisponível ({exc}). Exibida a resposta do mecanismo local.")
            local["ai"] = {"used": False, "model": model, "error": str(exc)}
            return local
        seconds = round(time.time() - start, 1)

        reasons = validate(text, passages, question, local)
        if reasons:
            log.info("Resposta da IA descartada (%s): %s", model, "; ".join(reasons))
            local["warnings"].append("A resposta redigida pela IA foi descartada na validação ("
                                     + "; ".join(reasons) + "). Exibida a resposta do mecanismo local.")
            local["ai"] = {"used": True, "validated": False, "model": model, "seconds": seconds,
                           "reasons": reasons, "rejected_answer": text}
            return local

        log.info("Resposta da IA validada (%s, %.1fs)", model, seconds)
        ai_info = {"used": True, "validated": True, "model": model, "seconds": seconds,
                   "local_answer": local["answer"]}
        if "nao localizei" in fold(text):
            # a IA considerou os trechos insuficientes: ausência, mantendo os trechos para conferência
            local["warnings"].append("A IA considerou que os trechos localizados não respondem à pergunta.")
            return {**local, "kind": AUSENCIA, "kind_label": KIND_LABELS[AUSENCIA], "answer": MSG_AUSENTE,
                    "confidence": "média", "sources": [], "ai": ai_info}
        order = []
        for n in P_CITATION.findall(text):
            if int(n) not in order:
                order.append(int(n))
        renumber = {old: new for new, old in enumerate(order, start=1)}
        text = P_CITATION.sub(lambda m: f"[{renumber[int(m.group(1))]}]", text)
        by_ref = {p.ref: p for p in passages}
        sources = []
        for old in order:
            p = by_ref[old]
            s = source(p.document_id, p.filename, p.page, p.section, p.text[:500], p.doc_type)
            s.update(ref=renumber[old], ocr=p.document_id in ocr_ids)
            sources.append(s)

        kind = local["kind"] if local["kind"] in (FATO, INFERENCIA, CONFLITO) else RESPOSTA_IA
        confidence = local["confidence"] if kind != RESPOSTA_IA else "média"
        if any(s["ocr"] for s in sources) and confidence == "alta":
            confidence = "média"
        return {**local, "kind": kind, "kind_label": KIND_LABELS[kind], "answer": text, "confidence": confidence,
                "sources": sources or local["sources"], "passages": [], "ai": ai_info}
