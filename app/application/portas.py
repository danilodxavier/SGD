"""Portas (interfaces) que a camada de aplicação exige da infraestrutura (DIP — ADR-013).

Implementações ficam em app/infrastructure; os casos de uso dependem apenas destes contratos.
"""
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RespostaLLM:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    json: Any = None


@runtime_checkable
class LLMPort(Protocol):
    nome: str
    remoto: bool  # True quando o conteúdo sai da máquina (ADR-004)

    def chat(self, mensagens: Sequence[dict], *, schema: dict | None = None, max_tokens: int = 700,
             temperatura: float = 0.0, json_livre: bool = False) -> RespostaLLM: ...
    # json_livre=True: pede JSON sem impor schema (a ordem dos campos fica a cargo do prompt) — ver FASE_05 §4


@runtime_checkable
class EmbeddingPort(Protocol):
    dimensao: int

    def embed(self, textos: Sequence[str]) -> list[list[float]]: ...


@runtime_checkable
class RerankerPort(Protocol):
    def pontuar(self, consulta: str, textos: Sequence[str]) -> list[float]: ...


@dataclass(frozen=True)
class ResultadoBusca:
    trecho_id: int
    pontuacao: float
    fonte: str  # bm25 | denso | rrf | rerank


@runtime_checkable
class VectorStorePort(Protocol):
    def inserir(self, itens: Sequence[tuple[int, Sequence[float]]]) -> None: ...

    def remover(self, trecho_ids: Sequence[int]) -> None: ...

    def buscar(self, vetor: Sequence[float], k: int,
               filtro_trechos: Sequence[int] | None = None) -> list[ResultadoBusca]: ...


@runtime_checkable
class OCRPort(Protocol):
    def reconhecer(self, imagem_png: bytes, idioma: str = "por") -> str: ...


@dataclass
class Span:
    no: str
    consulta_id: int | None = None
    modelo: str | None = None
    tokens_entrada: int = 0
    tokens_saida: int = 0
    atributos: dict = field(default_factory=dict)


@runtime_checkable
class TracerPort(Protocol):
    def span(self, no: str, *, consulta_id: int | None = None,
             modelo: str | None = None) -> AbstractContextManager[Span]: ...
