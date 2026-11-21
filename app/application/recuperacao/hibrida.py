"""Caso de uso RecuperadorHibrido (SAD-050, ADR-005): BM25 + denso → RRF → vigência → rerank → top-k.

Modos (para comparação na avaliação): "bm25", "denso", "hibrido", "hibrido_rerank" (padrão).
"""
import time
from dataclasses import dataclass, field
from typing import Protocol

from app.application.portas import EmbeddingPort, RerankerPort, ResultadoBusca, VectorStorePort
from app.application.recuperacao.aberturas import com_aberturas
from app.application.recuperacao.regras import (
    TrechoRecuperado,
    consulta_fts,
    filtrar_vigencia,
    fundir_rrf,
    termos_da_pergunta,
)

MODOS = ("bm25", "denso", "hibrido", "hibrido_rerank")


class BuscaLexicalPort(Protocol):
    def buscar(self, expressao: str, k: int) -> list[ResultadoBusca]: ...


class RepositorioTrechosPort(Protocol):
    def obter(self, ids: list[int]) -> list[TrechoRecuperado]: ...


@dataclass
class ResultadoRecuperacao:
    pergunta: str
    trechos: list
    historico: list = field(default_factory=list)
    termos: list = field(default_factory=list)
    tempos_ms: dict = field(default_factory=dict)


class RecuperadorHibrido:
    def __init__(self, lexical: BuscaLexicalPort, repositorio: RepositorioTrechosPort,
                 embedder: EmbeddingPort | None = None, vetores: VectorStorePort | None = None,
                 reranker: RerankerPort | None = None, *, candidatos: int = 50, para_rerank: int = 24,
                 aberturas: int = 0):
        self.lexical, self.repo = lexical, repositorio
        self.embedder, self.vetores, self.reranker = embedder, vetores, reranker
        self.candidatos, self.para_rerank = candidatos, para_rerank
        self.aberturas = aberturas  # nº de documentos que levam a abertura junto (0 = só os trechos)

    def recuperar(self, pergunta: str, k: int = 8, modo: str = "hibrido_rerank",
                  incluir_historico: bool = False) -> ResultadoRecuperacao:
        if modo not in MODOS:
            raise ValueError(f"Modo desconhecido: {modo}")
        tempos, listas = {}, []
        termos = termos_da_pergunta(pergunta)
        if modo != "denso":
            t0 = time.perf_counter()
            expr = consulta_fts(termos)
            listas.append(self.lexical.buscar(expr, self.candidatos) if expr else [])
            tempos["bm25"] = _ms(t0)
        if modo != "bm25":
            if not (self.embedder and self.vetores):
                raise ValueError(f"Modo {modo} exige embedder e índice vetorial.")
            t0 = time.perf_counter()
            vetor = self.embedder.embed([pergunta])[0]
            listas.append(self.vetores.buscar(vetor, self.candidatos))
            tempos["denso"] = _ms(t0)
        ordem = fundir_rrf(listas) if len(listas) > 1 else (listas[0] if listas else [])
        pontos = {r.trecho_id: r.pontuacao for r in ordem}
        t0 = time.perf_counter()
        trechos = self.repo.obter([r.trecho_id for r in ordem[: self.candidatos]])
        for t in trechos:
            t.pontuacao = pontos.get(t.id, 0.0)
        trechos.sort(key=lambda t: -t.pontuacao)
        trechos = sem_duplicatas(trechos)
        tempos["leitura"] = _ms(t0)
        atuais, historico = (trechos, []) if incluir_historico else filtrar_vigencia(trechos)
        if modo == "hibrido_rerank" and self.reranker and atuais:
            t0 = time.perf_counter()
            topo = atuais[: self.para_rerank]
            notas = self.reranker.pontuar(pergunta, [_texto_rerank(t) for t in topo])
            for t, nota in zip(topo, notas, strict=True):
                t.pontuacao = float(nota)
            atuais = sorted(topo, key=lambda t: -t.pontuacao) + atuais[self.para_rerank:]
            tempos["rerank"] = _ms(t0)
        selecionados = atuais[:k]
        if self.aberturas and selecionados and hasattr(self.repo, "iniciais"):
            selecionados = com_aberturas(selecionados, self.repo, self.aberturas)
        return ResultadoRecuperacao(pergunta, selecionados, historico[:k], termos, tempos)


def sem_duplicatas(trechos):
    """Mantém só a primeira ocorrência (a de maior pontuação) de cada texto: no acervo real o mesmo arquivo aparece
    em várias pastas e as cópias ocupavam metade das vagas do contexto."""
    vistos, saida = set(), []
    for t in trechos:
        chave = " ".join(t.texto.split()).lower()
        if chave not in vistos:
            vistos.add(chave)
            saida.append(t)
    return saida


def _texto_rerank(t: TrechoRecuperado) -> str:
    cabecalho = " | ".join(x for x in (t.titulo, t.caminho or t.dispositivo) if x)
    return f"{cabecalho}\n{t.texto}" if cabecalho else t.texto


def _ms(inicio):
    return int((time.perf_counter() - inicio) * 1000)
