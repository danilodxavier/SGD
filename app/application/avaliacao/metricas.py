"""Métricas determinísticas de recuperação e utilidades (ADR-011).

Relevância graduada de um trecho para as fontes esperadas de uma pergunta:
  2 = mesmo documento E (mesmo dispositivo — inclusive pedaços "art. 75, III a VIII" — OU evidência literal no texto)
  1 = mesmo documento
  0 = outro documento
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fonte:
    arquivo: str  # caminho relativo à pasta do corpus (ex.: "publico/federal/lei/lei14133_2021.htm")
    dispositivo: str | None = None  # ex.: "art. 75", "cláusula segunda"
    evidencia: str | None = None  # trecho literal esperado no texto


@dataclass
class TrechoAvaliado:
    arquivo: str
    dispositivo: str | None
    texto: str
    subdispositivos: list = field(default_factory=list)


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return " ".join(texto.split())


def _mesmo_dispositivo(previsto: str | None, esperado: str) -> bool:
    if not previsto:
        return False
    base = normalizar(previsto)
    alvo = normalizar(esperado)
    # "art. 75" casa com "art. 75" e "art. 75, iii a viii", mas não com "art. 7" ou "art. 75-a"
    return base == alvo or re.match(re.escape(alvo) + r",\s", base) is not None


def julgar(trecho: TrechoAvaliado, fontes: list[Fonte]) -> tuple[int, int | None]:
    """(grau de relevância, índice da fonte atendida com grau 2 ou None)."""
    melhor = 0
    texto = None
    for i, f in enumerate(fontes):
        if trecho.arquivo != f.arquivo:
            continue
        melhor = max(melhor, 1)
        if f.dispositivo and (_mesmo_dispositivo(trecho.dispositivo, f.dispositivo)
                              or any(_mesmo_dispositivo(s, f.dispositivo) for s in trecho.subdispositivos)):
            return 2, i
        if f.evidencia:
            texto = texto if texto is not None else normalizar(trecho.texto)
            if normalizar(f.evidencia) in texto:
                return 2, i
    return melhor, None


def reciprocal_rank(graus) -> float:
    for posicao, g in enumerate(graus, start=1):
        if g == 2:
            return 1.0 / posicao
    return 0.0


def ndcg_em_k(graus, k: int, n_fontes: int) -> float:
    dcg = sum((2 ** g - 1) / math.log2(p + 1) for p, g in enumerate(graus[:k], start=1))
    ideal = sum((2 ** 2 - 1) / math.log2(p + 1) for p in range(1, min(k, max(n_fontes, 1)) + 1))
    return min(1.0, dcg / ideal) if ideal else 0.0


def avaliar_recuperacao(recuperados: list[TrechoAvaliado], fontes: list[Fonte], ks=(1, 3, 5, 10)) -> dict:
    julgados = [julgar(t, fontes) for t in recuperados]
    graus = [g for g, _ in julgados]
    arquivos_esperados = {f.arquivo for f in fontes}
    m = {"mrr": reciprocal_rank(graus)}
    for k in ks:
        topo = julgados[:k]
        atendidas = {i for g, i in topo if g == 2 and i is not None}
        m[f"recall@{k}"] = len(atendidas) / len(fontes) if fontes else 0.0
        m[f"precision@{k}"] = sum(1 for g, _ in topo if g == 2) / k
        docs = {t.arquivo for t in recuperados[:k]} & arquivos_esperados
        m[f"recall_documento@{k}"] = len(docs) / len(arquivos_esperados) if arquivos_esperados else 0.0
        m[f"ndcg@{k}"] = ndcg_em_k(graus, k, len(fontes))
    return m


def percentil(valores, p: float):
    """Percentil pelo método nearest-rank."""
    ordenados = sorted(valores)
    if not ordenados:
        return None
    return ordenados[max(0, math.ceil(p * len(ordenados) / 100) - 1)]
