"""Cache semântico de perguntas e respostas (prompt mestre §5 — otimização de tokens; Fase 10).

Uma resposta é reaproveitada somente se:
  1. a versão do acervo/memória de decisões é a mesma (qualquer upload, reindexação ou decisão nova invalida);
  2. os IDENTIFICADORES da pergunta são idênticos (números de contrato, leis, anos, valores) — "contrato 012/2023"
     e "contrato 044/2023" têm embeddings quase iguais, mas nunca compartilham resposta;
  3. o texto normalizado é igual OU a similaridade de cosseno dos embeddings atinge o limiar (paráfrase).
"""
import re
import unicodedata
from collections.abc import Sequence
from typing import Protocol

from app.application.portas import EmbeddingPort

RE_IDENTIFICADOR = re.compile(r"\d+(?:[./,-]\d+)*")


def normalizar(pergunta: str) -> str:
    s = unicodedata.normalize("NFKC", pergunta).lower().strip()
    s = re.sub(r"[?!.;:]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def identificadores(pergunta: str) -> set:
    return set(RE_IDENTIFICADOR.findall(pergunta))


class RepositorioCachePort(Protocol):
    def exato(self, normalizada: str, versao: str) -> list[tuple[int, str, str]]: ...
    def similares(self, vetor: Sequence[float], k: int) -> list[tuple[int, float]]: ...
    def obter(self, ids: Sequence[int], versao: str) -> list[tuple[int, str, str]]: ...
    def gravar(self, normalizada: str, resposta: dict, versao: str, vetor: Sequence[float] | None) -> int: ...


class CacheSemantico:
    # 0,93 (bge-m3): o par de perguntas DIFERENTES mais parecido do golden set com os mesmos identificadores tem
    # cosseno 0,883 → margem de 0,05; reaproveita 7/10 paráfrases (scripts/sadgd/calibrar_cache.py)
    LIMIAR_PADRAO = 0.93

    def __init__(self, repo: RepositorioCachePort, embedder: EmbeddingPort | None = None, *,
                 limiar: float = LIMIAR_PADRAO):
        self.repo, self.embedder, self.limiar = repo, embedder, limiar

    def buscar(self, pergunta: str, versao: str) -> dict | None:
        normalizada, ids = normalizar(pergunta), identificadores(pergunta)
        for _, texto, resposta in self.repo.exato(normalizada, versao):
            if identificadores(texto) == ids:
                return resposta
        if not self.embedder:
            return None
        candidatos = [(i, s) for i, s in self.repo.similares(self.embedder.embed([normalizada])[0], 5)
                      if s >= self.limiar]
        por_id = {i: (texto, resposta) for i, texto, resposta in self.repo.obter([i for i, _ in candidatos], versao)}
        for i, _ in candidatos:
            if i in por_id and identificadores(por_id[i][0]) == ids:
                return por_id[i][1]
        return None

    def gravar(self, pergunta: str, resposta: dict, versao: str) -> int:
        normalizada = normalizar(pergunta)
        vetor = self.embedder.embed([normalizada])[0] if self.embedder else None
        return self.repo.gravar(normalizada, resposta, versao, vetor)
