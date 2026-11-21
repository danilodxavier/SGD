"""Caso de uso IndexarCorpus (SAD-045, RF-05): indexação híbrida incremental.

Para cada arquivo novo ou alterado (tamanho/mtime): extrai → divide em trechos estruturais → extrai metadados →
grava documento, trechos (FTS5 via gatilhos) e norma → gera embeddings em lote → grava vetores. Arquivos
inalterados não são reprocessados; arquivos que sumiram são removidos (com trechos, FTS e vetores em cascata).
Depende apenas de portas (ADR-013).
"""
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.application.ingestao.chunking import Trecho, dividir
from app.application.ingestao.metadados import Metadados, extrair_metadados
from app.application.portas import EmbeddingPort, VectorStorePort
from app.domain.documentos import CorpusOrigem

log = logging.getLogger("sadgd.indexador")
STATUS_PESQUISAVEIS = ("COM_TEXTO", "COM_OCR")


@dataclass(frozen=True)
class ArquivoFonte:
    caminho: Path
    relativo: str
    tamanho: int
    mtime: float


@dataclass
class DocumentoIndexado:
    arquivo: ArquivoFonte
    hash: str
    status: str
    corpus_origem: CorpusOrigem
    metadados: Metadados
    paginas: int | None
    erro: str | None = None
    motor_ocr: str | None = None


class RepositorioIndexacao(Protocol):
    def estado(self) -> dict[str, tuple]: ...  # caminho -> (id, tamanho, mtime, modelo_embedding)
    def salvar(self, doc: DocumentoIndexado, trechos: list[Trecho]) -> list[int]: ...  # ids dos trechos
    def remover(self, ids_documentos: Iterable[int]) -> None: ...
    def registrar_execucao(self, resumo: dict) -> None: ...
    def marcar_modelo(self, ids_documentos: Iterable[int], modelo: str) -> None: ...


@dataclass
class Resumo:
    encontrados: int = 0
    novos: int = 0
    alterados: int = 0
    inalterados: int = 0
    removidos: int = 0
    erros: int = 0
    trechos: int = 0
    vetores: int = 0
    segundos: float = 0.0
    interrompido: bool = False  # limite de tempo atingido: arquivos restantes ficam para a próxima execução
    falhas: list = field(default_factory=list)


def origem_por_caminho(relativo: str, padrao: CorpusOrigem) -> CorpusOrigem:
    """corpus/publico/... e corpus/sintetico/... têm origem conhecida; o resto usa o padrão (mais restritivo: real)."""
    primeira = Path(relativo).parts[0].lower() if Path(relativo).parts else ""
    return {"publico": CorpusOrigem.PUBLICO, "sintetico": CorpusOrigem.SINTETICO}.get(primeira, padrao)


def texto_para_embedding(t: Trecho, md: Metadados) -> str:
    """Contexto hierárquico + caput enriquecem o vetor; o texto citado permanece literal no banco."""
    cabecalho = " | ".join(x for x in (md.titulo, t.caminho or t.dispositivo) if x)
    contexto = t.contexto if t.contexto and not t.texto.lstrip().startswith(t.contexto[:40]) else ""
    return "\n".join(x for x in (cabecalho, contexto, t.texto.strip()) if x)


class IndexarCorpus:
    def __init__(self, repositorio: RepositorioIndexacao, extrair: Callable, calcular_hash: Callable,
                 embedder: EmbeddingPort | None, vetores: VectorStorePort | None, *,
                 origem_padrao: CorpusOrigem = CorpusOrigem.REAL, lote_embeddings: int = 32, modelo: str = ""):
        self.repo, self.extrair, self.calcular_hash = repositorio, extrair, calcular_hash
        self.embedder, self.vetores = embedder, vetores
        self.origem_padrao, self.lote, self.modelo = origem_padrao, lote_embeddings, modelo

    def executar(self, raiz: str, arquivos: Iterable[ArquivoFonte], forcar: bool = False,
                 limite_segundos: float | None = None, parcial: bool = False) -> Resumo:
        """parcial=True: `arquivos` é só um subconjunto (ex.: upload) — nada fora dele é considerado removido."""
        inicio_iso, t0 = datetime.now().isoformat(timespec="seconds"), time.perf_counter()
        resumo, conhecidos = Resumo(), self.repo.estado()
        pendentes_vetor, docs_com_vetor = [], set()
        vistos = set()
        for arquivo in arquivos:
            if limite_segundos is not None and time.perf_counter() - t0 >= limite_segundos:
                resumo.interrompido = True
                break
            resumo.encontrados += 1
            chave = str(arquivo.caminho)
            vistos.add(chave)
            anterior = conhecidos.get(chave)
            # sem vetores do modelo atual (ex.: execução interrompida antes dos embeddings) → reprocessa
            vetores_em_dia = anterior is not None and (
                self.embedder is None or (len(anterior) > 3 and anterior[3] == self.modelo))
            if (anterior and not forcar and vetores_em_dia
                    and anterior[1] == arquivo.tamanho and anterior[2] == arquivo.mtime):
                resumo.inalterados += 1
                continue
            try:
                doc, trechos = self._processar(arquivo)
                ids = self.repo.salvar(doc, trechos)
            except Exception as exc:  # um arquivo problemático não interrompe a indexação
                log.exception("Falha ao indexar %s", arquivo.relativo)
                resumo.erros += 1
                resumo.falhas.append((arquivo.relativo, type(exc).__name__))
                continue
            if anterior:
                resumo.alterados += 1
            else:
                resumo.novos += 1
            if doc.status not in STATUS_PESQUISAVEIS:
                resumo.erros += doc.status in ("CORROMPIDO",)
            resumo.trechos += len(ids)
            if self.embedder and self.vetores:
                pendentes_vetor.extend((tid, texto_para_embedding(t, doc.metadados)) for tid, t in zip(ids, trechos,
                                                                                                        strict=True))
                docs_com_vetor.add(chave)  # inclui documentos sem trechos: nada a vetorizar, já estão em dia
                if len(pendentes_vetor) >= self.lote * 8:
                    resumo.vetores += self._descarregar(pendentes_vetor, docs_com_vetor)
                    pendentes_vetor, docs_com_vetor = [], set()
        if docs_com_vetor:
            resumo.vetores += self._descarregar(pendentes_vetor, docs_com_vetor)
        # numa execução interrompida, arquivos não vistos NÃO são considerados removidos
        removidos = [] if resumo.interrompido or parcial else [v[0] for k, v in conhecidos.items()
                                                                if k not in vistos]
        if removidos:
            self.repo.remover(removidos)
            resumo.removidos = len(removidos)
        resumo.segundos = round(time.perf_counter() - t0, 1)
        self.repo.registrar_execucao({"inicio": inicio_iso, "fim": datetime.now().isoformat(timespec="seconds"),
                                      "raiz": raiz, "modelo_embedding": self.modelo,
                                      **{k: v for k, v in resumo.__dict__.items()
                                         if k not in ("falhas", "interrompido")}})
        return resumo

    def _processar(self, arquivo: ArquivoFonte):
        r = self.extrair(arquivo.caminho)
        texto = "".join(p.texto for p in r.paginas)
        # o nome do arquivo é a última pista do tipo (2º nível) quando o texto não traz título reconhecível
        md = (extrair_metadados(texto, arquivo.relativo, arquivo.caminho.suffix) if texto.strip()
              else extrair_metadados("", arquivo.relativo, arquivo.caminho.suffix))
        trechos = dividir(r.paginas) if r.status in STATUS_PESQUISAVEIS else []
        doc = DocumentoIndexado(arquivo, self.calcular_hash(arquivo.caminho), r.status,
                                origem_por_caminho(arquivo.relativo, self.origem_padrao), md, r.num_paginas,
                                r.erro, r.motor_ocr)
        return doc, trechos

    def _descarregar(self, pendentes, chaves_documentos):
        """Grava os vetores do lote e, em seguida, marca os documentos como vetorizados com o modelo atual.
        Se o processo morrer antes da marcação, os documentos serão reprocessados (nunca ficam sem vetores)."""
        total = self._gravar_vetores(pendentes) if pendentes else 0
        if self.modelo:
            estado = self.repo.estado()
            self.repo.marcar_modelo([estado[c][0] for c in chaves_documentos if c in estado], self.modelo)
        return total

    def _gravar_vetores(self, pendentes):
        total = 0
        for i in range(0, len(pendentes), self.lote * 8):
            bloco = pendentes[i:i + self.lote * 8]
            vetores = self.embedder.embed([texto for _, texto in bloco])
            self.vetores.inserir([(tid, v) for (tid, _), v in zip(bloco, vetores, strict=True)])
            total += len(bloco)
        return total
