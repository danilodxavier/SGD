"""Métricas determinísticas de resposta (ADR-011): exatidão por resposta-chave, classificação e alucinação numérica.

Alucinação numérica: qualquer número, data, valor ou identificador numérico presente na resposta que não esteja
em nenhum trecho citado nem na pergunta. É um indicador conservador e reprodutível (sem LLM-juiz) adequado a
perguntas factuais sobre contratos e normas, onde os fatos críticos são numéricos.
"""
import re

from app.application.avaliacao.metricas import normalizar

RE_NUMERO = re.compile(r"\d[\d.,/-]*\d|\d")
RE_ROTULO = re.compile(r"\[?T\d+\]?")


def contem_chaves(resposta: str, chaves) -> bool | None:
    if not chaves:
        return None
    texto = normalizar(resposta)
    return all(normalizar(c) in texto for c in chaves)


MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
                                     "setembro", "outubro", "novembro", "dezembro"], start=1)}
RE_DATA_EXTENSO = re.compile(r"\b(\d{1,2})\s*(?:º|°|o)?\s+de\s+([a-zç]+)\s+de\s+(\d{4})\b", re.I)
RE_ATO_COM_ANO = re.compile(r"^(\d[\d.]*)/(\d{4})$")  # "8.666/1993"


def _datas_numericas(texto: str) -> str:
    """'20 de junho de 2025' → '20/06/2025' (compara datas como datas, não como números soltos)."""
    def trocar(m):
        mes = MESES.get(normalizar(m.group(2)))
        return f"{int(m.group(1)):02d}/{mes:02d}/{m.group(3)}" if mes else m.group(0)
    return RE_DATA_EXTENSO.sub(trocar, texto)


def _numeros(texto: str) -> set[str]:
    return {n.strip(".,-/") for n in RE_NUMERO.findall(RE_ROTULO.sub(" ", _datas_numericas(texto)))}


def numeros_nao_suportados(resposta: str, textos_citados, pergunta: str = "") -> list[str]:
    base = _numeros(" ".join(textos_citados)) | _numeros(pergunta)
    base_compacta = {re.sub(r"\D", "", n) for n in base}
    componentes = base | {parte for n in base for parte in n.split("/")}  # "21/06/1993" fornece "1993"
    faltando = []
    for n in sorted(_numeros(resposta)):
        if len(re.sub(r"\D", "", n)) < 2:
            continue  # dígitos isolados ("1", "2") são ambíguos (enumerações)
        if n in base or re.sub(r"\D", "", n) in base_compacta:
            continue
        ato = RE_ATO_COM_ANO.match(n)  # "Lei nº 8.666/1993" ≡ "Lei nº 8.666, de ... de 1993"
        if ato and ato.group(1) in componentes and ato.group(2) in componentes:
            continue
        faltando.append(n)
    return faltando


def classificacao_correta(esperada: str, obtida: str) -> bool:
    if esperada in ("fato", "inferencia"):
        return obtida in ("fato", "inferencia")
    return esperada == obtida
