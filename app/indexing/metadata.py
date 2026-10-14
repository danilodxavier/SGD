"""Classificação do tipo documental e metadados derivados do conteúdo."""
import mimetypes
import re

from app.contracts.extractor import find_contract_numbers
from app.core.text import fold

# Ordem importa: o primeiro padrão encontrado define o tipo.
DOC_TYPES = [
    ("ADITIVO", r"termo\s+aditivo|\baditivo\b"),
    ("APOSTILAMENTO", r"apostila"),
    ("PORTARIA", r"\bportaria\b"),
    ("NOTIFICACAO", r"notificac"),
    ("CERTIDAO", r"certid[ao]|\bcnd\b|\bfgts\b|regularidade"),
    ("FATURA", r"nota\s+fiscal|\bfatura\b|\bnf-?e\b"),
    ("RELATORIO", r"relatorio"),
    ("EDITAL", r"\bedital\b"),
    ("TERMO_REFERENCIA", r"termo\s+de\s+referencia"),
    ("PLANILHA", r"planilha|\bitens\b"),
    ("CONTRATO", r"\bcontrato\b"),
]

DOC_TYPE_LABELS = {
    "CONTRATO": "Contrato",
    "ADITIVO": "Termo Aditivo",
    "APOSTILAMENTO": "Apostilamento",
    "PORTARIA": "Portaria",
    "NOTIFICACAO": "Notificação",
    "CERTIDAO": "Certidão / Regularidade",
    "FATURA": "Fatura / Nota Fiscal",
    "RELATORIO": "Relatório",
    "EDITAL": "Edital",
    "TERMO_REFERENCIA": "Termo de Referência",
    "PLANILHA": "Planilha",
    "OUTRO": "Outro",
}

ORDINAL_WORDS = {
    "primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4, "quinto": 5,
    "sexto": 6, "setimo": 7, "oitavo": 8, "nono": 9, "decimo": 10,
}


def _name(filename):
    return fold(re.sub(r"[_\-.]+", " ", filename))


def classify(filename, head_text):
    name = _name(filename)
    head = fold(head_text[:300])  # só o título/abertura, para não confundir com menções no corpo
    for doc_type, pattern in DOC_TYPES:  # o nome do arquivo tem prioridade
        if re.search(pattern, name):
            return doc_type
    for doc_type, pattern in DOC_TYPES:
        if re.search(pattern, head):
            return doc_type
    return "OUTRO"


def amendment_ordinal(filename, head_text):
    """Número de ordem do termo aditivo (1º, 2º...), ou 0 se não identificado."""
    for source in (_name(filename), fold(head_text[:800])):
        m = re.search(r"(\d{1,2})\s*[º°o]?\s*(?:termo\s+)?(?:de\s+)?aditivo", source)
        if m:
            return int(m.group(1))
        m = re.search(rf"\b({'|'.join(ORDINAL_WORDS)})\s+termo\s+aditivo", source)
        if m:
            return ORDINAL_WORDS[m.group(1)]
    return 0


def primary_contract(filename, text):
    refs = find_contract_numbers(text[:20000])
    return refs[0] if refs else None


def mime_type(path):
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"
