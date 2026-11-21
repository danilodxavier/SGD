"""Abertura do documento junto dos trechos recuperados (acervo real, 2026-11-21).

A busca devolve recortes: cláusulas do meio de um contrato raramente repetem número, partes e objeto, e o modelo
recusava perguntas como "Qual o contrato do <fornecedor>?" (R05) com 8 trechos do contrato certo ("os trechos
não dizem o objeto"). Para os documentos mais relevantes, o contexto passa a levar também o início do documento e a
cláusula do objeto — texto literal, cortes marcados com "[…]", tamanho limitado para caber no contexto dos especialistas.
"""
import re
from dataclasses import replace
from typing import Protocol

RE_OBJETO = re.compile(r"\bobjeto\b", re.IGNORECASE)
CABECA, JANELA, RECUO = 500, 500, 100


class IniciaisPort(Protocol):
    def iniciais(self, documento_ids: list[int], ate_ordem: int = 4) -> dict: ...


def _corte(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + " […]"


def _janela_objeto(texto: str, inicio_busca: int = 0) -> str | None:
    m = RE_OBJETO.search(texto, inicio_busca)
    if not m:
        return None
    inicio = max(texto.rfind("\n", 0, m.start()) + 1, m.start() - RECUO)
    return ("[…] " if inicio > 0 else "") + _corte(texto[inicio:], JANELA)


def recorte_abertura(texto: str) -> str:
    """Início do documento e, se a palavra "objeto" vier depois dele, a janela da cláusula do objeto."""
    texto = texto.strip()
    if len(texto) <= CABECA + JANELA:
        return texto
    cabeca = texto[:CABECA].rsplit(" ", 1)[0]
    if RE_OBJETO.search(cabeca):
        return cabeca + " […]"
    janela = _janela_objeto(texto, CABECA)
    return cabeca + (" " + janela if janela else " […]")


def com_aberturas(trechos: list, repositorio: IniciaisPort, max_docs: int = 3) -> list:
    """Insere, antes do primeiro trecho de cada um dos `max_docs` documentos mais bem colocados SEM número na ficha,
    a abertura do documento (1º trecho recortado) e, se ela não trouxer o objeto, a cláusula do objeto entre os 4
    primeiros. Documento com número extraído já se identifica pela ficha: a abertura só custaria latência
    (acadêmico, 96% com número: p50 9,5 → 23 s sem ganho de exatidão; acervo real: 16% com número)."""
    sem_numero = [t.documento_id for t in trechos if not getattr(t, "numero", None)]
    docs = list(dict.fromkeys(sem_numero))[:max_docs]
    if not docs:
        return trechos
    iniciais = repositorio.iniciais(docs)
    presentes = {t.id for t in trechos}
    extras = {}
    for d in docs:
        lista = iniciais.get(d) or []
        if not lista:
            continue
        primeiro, selecionados = lista[0], []
        if primeiro.id not in presentes:
            selecionados.append(replace(primeiro, texto=recorte_abertura(primeiro.texto),
                                        dispositivo=primeiro.dispositivo or "abertura do documento"))
        if not RE_OBJETO.search(primeiro.texto):
            objeto = next((t for t in lista[1:] if RE_OBJETO.search(t.texto)), None)
            if objeto and objeto.id not in presentes:
                selecionados.append(replace(objeto, texto=_janela_objeto(objeto.texto) or objeto.texto))
        extras[d] = selecionados
    saida, vistos = [], set()
    for t in trechos:
        if t.documento_id in extras and t.documento_id not in vistos:
            saida.extend(extras[t.documento_id])
            vistos.add(t.documento_id)
        saida.append(t)
    return saida
