"""Detecção determinística de contradições (RF-09).

Para cada contrato, o valor VIGENTE de cada campo vem da cadeia autorizada (contrato → termos aditivos, em ordem
cronológica). Qualquer outro documento que DECLARE um valor diferente para o mesmo campo do mesmo contrato gera
uma contradição (origem = documento que fixou o valor vigente; destino = documento divergente). O sistema não
escolhe o valor "certo": apresenta as duas fontes para conferência.
"""
import re
from dataclasses import dataclass

from app.application.linha_do_tempo.referencias import chave_documento, encontrar_referencias

DATA = r"(\d{2}/\d{2}/\d{4})"
MOEDA = r"(R\$\s?[\d.]+,\d{2})"
AUTORIZADOS = {"contrato", "aditivo"}

# valor fixado pelo próprio contrato
VALOR_CONTRATO = re.compile(r"valor global do contrato (?:é|e) de " + MOEDA, re.I)
FIM_CONTRATO = re.compile(r"t[ée]rmino em " + DATA, re.I)
# valor alterado por aditivo
VALOR_ADITIVO = re.compile(r"valor global do contrato passa de " + MOEDA + r" para " + MOEDA, re.I)
FIM_ADITIVO = [re.compile(r"(?:t[ée]rmino|vig[êe]ncia)[^.]{0,60}?de " + DATA + r" para " + DATA, re.I),
               re.compile(r"vig[êe]ncia passa a encerrar-se em " + DATA, re.I)]
# valor declarado por outros documentos
VALOR_DECLARADO = re.compile(r"valor global de " + MOEDA, re.I)
FIM_DECLARADO = re.compile(r"vig[êe]ncia do contrato n[º°o]\.?\s*[\d/]+ encerra-se em " + DATA, re.I)


@dataclass(frozen=True)
class Contradicao:
    origem: int
    destino: int
    campo: str
    valor_vigente: str
    valor_declarado: str
    trecho_origem: int
    trecho_destino: int


def _norm_moeda(v):
    return v.replace("R$", "R$ ").replace("  ", " ").strip()


def _contrato_referido(d, por_chave):
    for _, texto in d.trechos:
        for ref in encontrar_referencias(texto):
            if ref.chave[0] == "contrato" and ref.chave in por_chave:
                return por_chave[ref.chave]
    return None


def detectar_contradicoes(documentos):
    por_chave = {}
    for d in documentos:
        chave = chave_documento(d.tipo, d.numero)
        if chave and chave[0] == "contrato":
            por_chave[chave] = d
    vigentes = {}  # (contrato_id, campo) -> (valor, doc_id, trecho_id)
    for c in por_chave.values():
        for tid, texto in c.trechos:
            if m := VALOR_CONTRATO.search(texto):
                vigentes.setdefault((c.id, "valor_global"), (_norm_moeda(m.group(1)), c.id, tid))
            if m := FIM_CONTRATO.search(texto):
                vigentes.setdefault((c.id, "vigencia_fim"), (m.group(1), c.id, tid))
    for a in sorted((d for d in documentos if d.tipo == "aditivo"), key=lambda d: d.data):
        c = _contrato_referido(a, por_chave)
        if not c:
            continue
        for tid, texto in a.trechos:
            if m := VALOR_ADITIVO.search(texto):
                vigentes[(c.id, "valor_global")] = (_norm_moeda(m.group(2)), a.id, tid)
            for padrao in FIM_ADITIVO:
                if m := padrao.search(texto):
                    vigentes[(c.id, "vigencia_fim")] = (m.groups()[-1], a.id, tid)
                    break
    achadas = []
    for d in documentos:
        if d.tipo in AUTORIZADOS:
            continue
        c = _contrato_referido(d, por_chave)
        if not c:
            continue
        for tid, texto in d.trechos:
            for campo, padrao in (("valor_global", VALOR_DECLARADO), ("vigencia_fim", FIM_DECLARADO)):
                m = padrao.search(texto)
                if not m or (c.id, campo) not in vigentes:
                    continue
                valor = _norm_moeda(m.group(1)) if campo == "valor_global" else m.group(1)
                vigente, origem, trecho_origem = vigentes[(c.id, campo)]
                if valor != vigente:
                    achadas.append(Contradicao(origem, d.id, campo, vigente, valor, trecho_origem, tid))
    return achadas
