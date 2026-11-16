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


def _numeros(texto: str) -> set[str]:
    return {n.strip(".,-/") for n in RE_NUMERO.findall(RE_ROTULO.sub(" ", texto))}


def numeros_nao_suportados(resposta: str, textos_citados, pergunta: str = "") -> list[str]:
    base = _numeros(" ".join(textos_citados)) | _numeros(pergunta)
    base_compacta = {re.sub(r"\D", "", n) for n in base}
    faltando = []
    for n in sorted(_numeros(resposta)):
        if len(re.sub(r"\D", "", n)) < 2:
            continue  # dígitos isolados ("1", "2") são ambíguos (enumerações)
        if n not in base and re.sub(r"\D", "", n) not in base_compacta:
            faltando.append(n)
    return faltando


def classificacao_correta(esperada: str, obtida: str) -> bool:
    if esperada in ("fato", "inferencia"):
        return obtida in ("fato", "inferencia")
    return esperada == obtida
