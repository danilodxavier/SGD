"""RerankerPort com BAAI/bge-reranker-v2-m3 (cross-encoder, ADR-005), float32, pesos em modelos\\hf."""
import logging
from pathlib import Path

from app.core.config import settings  # HF_HOME e carga sequencial antes de importar torch

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
            import torch

            self._dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        return self._dispositivo

    def _carregar(self):
        if self._modelo is None:
            from sentence_transformers import CrossEncoder

            self._modelo = CrossEncoder(pasta_snapshot(self.nome_modelo), device=self.dispositivo,
                                        max_length=self._max)
        return self._modelo

    def pontuar(self, consulta, textos):
        if not textos:
            return []
        modelo = self._carregar()
        notas = modelo.predict([(consulta, t) for t in textos], batch_size=self._lote, show_progress_bar=False)
        return [float(n) for n in notas]

    def liberar(self):
        if self._modelo is not None and self.dispositivo == "cuda":
            import torch

            self._modelo = None
            torch.cuda.empty_cache()
