"""SAD-080 — Memória de decisões e recuperação de precedentes (RF-19).

Busca híbrida como a dos trechos (ADR-005): BM25 sobre a decisão + vetores bge-m3 → RRF → reranker opcional.
Decisões do mesmo processo da pergunta recebem bônus (o caso concreto pesa mais que o tema). Um limiar no
reranker evita apresentar como "precedente" uma decisão sem relação com a pergunta (0,002: maior valor que mantém
Recall@3 >= 0,90 na validação e rejeita a pergunta sem precedente; calibrado só na validação, ver FASE_08)."""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.application.portas import EmbeddingPort, RerankerPort
from app.application.recuperacao.regras import consulta_fts, termos_da_pergunta
from app.domain.decisoes import Decisao, Precedente

MODOS = ("bm25", "denso", "hibrido", "hibrido_rerank")


@dataclass
class Candidato:
    id: int
    pontuacao: float


class RepositorioDecisoesPort(Protocol):
    def registrar(self, decisao: Decisao, documento_ids: Sequence[int] = (), trecho_ids: Sequence[int] = ()) -> int: ...
    def obter(self, ids: Sequence[int]) -> list[Decisao]: ...
    def buscar_lexical(self, expressao: str, k: int) -> list[Candidato]: ...
    def buscar_densa(self, vetor: Sequence[float], k: int) -> list[Candidato]: ...
    def salvar_vetor(self, decisao_id: int, vetor: Sequence[float], modelo: str) -> None: ...
    def atualizar_resultado(self, decisao_id: int, resultado: str, avaliacao: str) -> bool: ...
    def processos_dos_documentos(self, documento_ids: Sequence[int]) -> set: ...


def fundir(listas, k=60):
    pontos = {}
    for lista in listas:
        for pos, c in enumerate(lista, start=1):
            pontos[c.id] = pontos.get(c.id, 0.0) + 1.0 / (k + pos)
    return [Candidato(i, p) for i, p in sorted(pontos.items(), key=lambda x: -x[1])]


class MemoriaDecisoes:
    def __init__(self, repo: RepositorioDecisoesPort, embedder: EmbeddingPort | None = None,
                 reranker: RerankerPort | None = None, *, candidatos: int = 20, limiar_rerank: float = 0.002,
                 bonus_processo: float = 0.02):
        self.repo, self.embedder, self.reranker = repo, embedder, reranker
        self.candidatos, self.limiar, self.bonus = candidatos, limiar_rerank, bonus_processo

    def registrar(self, decisao: Decisao, documento_ids=(), trecho_ids=()) -> int:
        decisao_id = self.repo.registrar(decisao, documento_ids, trecho_ids)
        if self.embedder:
            self.repo.salvar_vetor(decisao_id, self.embedder.embed([decisao.texto_indexavel()])[0],
                                   getattr(self.embedder, "nome_modelo", "embedder"))
        return decisao_id

    def precedentes(self, pergunta: str, k: int = 3, *, modo: str = "hibrido_rerank",
                    documento_ids: Sequence[int] = (), filtrar: bool = True) -> list[Precedente]:
        if modo not in MODOS:
            raise ValueError(f"Modo desconhecido: {modo}")
        listas = []
        if modo != "denso":
            expr = consulta_fts(termos_da_pergunta(pergunta))
            listas.append(self.repo.buscar_lexical(expr, self.candidatos) if expr else [])
        if modo != "bm25":
            if not self.embedder:
                raise ValueError(f"Modo {modo} exige embedder.")
            listas.append(self.repo.buscar_densa(self.embedder.embed([pergunta])[0], self.candidatos))
        ordem = fundir(listas) if len(listas) > 1 else (listas[0] if listas else [])
        if not ordem:
            return []
        decisoes = {d.id: d for d in self.repo.obter([c.id for c in ordem])}
        processos = self.repo.processos_dos_documentos(documento_ids) if documento_ids else set()
        pontos = {c.id: c.pontuacao + (self.bonus if decisoes[c.id].processo_id in processos else 0.0)
                  for c in ordem if c.id in decisoes}
        ids = sorted(pontos, key=lambda i: -pontos[i])
        if modo == "hibrido_rerank" and self.reranker:
            topo = ids[: max(k * 4, 10)]
            notas = self.reranker.pontuar(pergunta, [decisoes[i].texto_indexavel() for i in topo])
            pontos = {i: float(n) + (self.bonus * 10 if decisoes[i].processo_id in processos else 0.0)
                      for i, n in zip(topo, notas, strict=True)}
            ids = sorted(pontos, key=lambda i: -pontos[i])
            if filtrar:
                ids = [i for i in ids if pontos[i] >= self.limiar]
        return [Precedente(decisoes[i], pontos[i], f"P{i}") for i in ids[:k]]

    def atualizar_resultado(self, decisao_id: int, resultado: str, avaliacao: str) -> bool:
        return self.repo.atualizar_resultado(decisao_id, resultado, avaliacao)
