"""RerankerPort com BAAI/bge-reranker-v2-m3 (cross-encoder, ADR-005), float32, pesos em modelos\\hf."""
import logging
import os
from pathlib import Path

from app.core.config import settings  # HF_HOME e carga sequencial antes de importar torch
from app.infrastructure.modelos.embeddings import _cuda_ou_cpu
from app.infrastructure.modelos.thread_principal import na_thread_principal

log = logging.getLogger("sadgd.reranker")
MODELO_PADRAO = "BAAI/bge-reranker-v2-m3"


def pasta_snapshot(repositorio: str):
    """Pasta local do snapshot no cache do projeto (sem acesso à rede)."""
    base = Path(settings.data_dir.parent, "modelos", "hf", "hub", "models--" + repositorio.replace("/", "--"),
                "snapshots")
    pastas = sorted(base.iterdir()) if base.is_dir() else []
    return str(pastas[-1]) if pastas else repositorio


class BgeReranker:
    def __init__(self, modelo=MODELO_PADRAO, dispositivo=None, max_tokens=512, lote=8):
        self.nome_modelo, self._dispositivo = modelo, dispositivo
        self._max, self._lote = max_tokens, lote
        self._modelo = None

    @property
    def dispositivo(self):
        if self._dispositivo is None:
            self._dispositivo = _cuda_ou_cpu()
        return self._dispositivo

    def _carregar(self):
        if self._modelo is None:
            from sentence_transformers import CrossEncoder

            extra = {}
            if self.dispositivo == "cuda" and os.environ.get("SADGD_RERANK_FP16") == "1":
                import torch

                extra = {"model_kwargs": {"torch_dtype": torch.float16}}
            self._modelo = CrossEncoder(pasta_snapshot(self.nome_modelo), device=self.dispositivo,
                                        max_length=self._max, **extra)
        return self._modelo

    @na_thread_principal  # torch só na thread principal (ver thread_principal.py)
    def pontuar(self, consulta, textos):
        if not textos:
            return []
        try:
            modelo = self._carregar()
            notas = modelo.predict([(consulta, t) for t in textos], batch_size=self._lote, show_progress_bar=False)
        except RuntimeError as exc:
            # sem memória na GPU (ex.: llama-server do Ollama com >12 GB comprometidos após horas de uso): a busca
            # segue na CPU (≈ 4× mais lenta) em vez de falhar a pergunta inteira; vale até o processo reiniciar
            if "out of memory" not in str(exc).lower() or self.dispositivo != "cuda":
                raise
            log.warning("GPU sem memória para o reranker; usando CPU até reiniciar o servidor.")
            self.liberar()
            self._modelo, self._dispositivo = None, "cpu"
            return self.pontuar(consulta, textos)
        return [float(n) for n in notas]

    @na_thread_principal
    def liberar(self):
        if self._modelo is not None and self.dispositivo == "cuda":
            import torch

            self._modelo = None
            torch.cuda.empty_cache()
