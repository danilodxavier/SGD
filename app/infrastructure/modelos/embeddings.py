"""EmbeddingPort com BAAI/bge-m3 via sentence-transformers (ADR-005). Pesos em modelos\\hf (HF_HOME).

GPU de 6 GB é compartilhada com o Ollama: antes de um lote grande, os modelos do Ollama são descarregados
(keep_alive=0). Sem memória na GPU, o lote é refeito na CPU.
"""
import json
import logging
import urllib.request

from app.core.config import settings  # garante HF_HOME/TORCH_HOME no projeto antes de importar torch
from app.infrastructure.modelos.thread_principal import na_thread_principal

log = logging.getLogger("sadgd.embeddings")
MODELO_PADRAO = "BAAI/bge-m3"
# cópia local em safetensors preparada por scripts/sadgd/preparar_bge_m3.py (sem rede em tempo de execução)
PASTA_LOCAL = settings.data_dir.parent / "modelos" / "bge-m3"


def origem_modelo(nome=MODELO_PADRAO):
    return str(PASTA_LOCAL) if nome == MODELO_PADRAO and (PASTA_LOCAL / "model.safetensors").is_file() else nome


def modelo_local_disponivel(nome=MODELO_PADRAO):
    """True se os pesos estão em modelos/bge-m3 (nunca dispara download)."""
    return origem_modelo(nome) != nome


def liberar_gpu_ollama(url=None, timeout=10):
    """Descarrega modelos carregados no Ollama local para liberar VRAM. Silencioso se o Ollama estiver parado."""
    url = (url or settings.ollama_url).rstrip("/")
    try:
        with urllib.request.urlopen(f"{url}/api/ps", timeout=timeout) as r:  # noqa: S310 - URL local de config
            carregados = [m["name"] for m in json.load(r).get("models", [])]
        for nome in carregados:
            corpo = json.dumps({"model": nome, "keep_alive": 0}).encode()
            req = urllib.request.Request(f"{url}/api/generate", data=corpo,  # noqa: S310
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=timeout).read()  # noqa: S310
        return carregados
    except Exception:  # Ollama parado ou indisponível: nada a liberar
        return []


@na_thread_principal
def _cuda_ou_cpu():
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


class BgeM3Embedder:
    dimensao = 1024

    def __init__(self, modelo=MODELO_PADRAO, dispositivo=None, lote=16, max_tokens=1024, liberar_gpu=True):
        self.nome_modelo = modelo
        self._dispositivo = dispositivo
        self._lote, self._max_tokens, self._liberar = lote, max_tokens, liberar_gpu
        self._modelo = None

    @property
    def dispositivo(self):
        if self._dispositivo is None:
            self._dispositivo = _cuda_ou_cpu()
        return self._dispositivo

    def _carregar(self):
        if self._modelo is None:
            from sentence_transformers import SentenceTransformer

            if self.dispositivo == "cuda" and self._liberar:
                liberados = liberar_gpu_ollama()
                if liberados:
                    log.info("VRAM liberada (modelos Ollama descarregados): %s", liberados)
            # float32 também na GPU: na GTX 1660 SUPER (Turing sem tensor cores) o fp16 foi 5x MAIS LENTO
            # (3,8 vs 19,0 trechos/s, medido em 2026-11-16). Cabe na VRAM (≈2,3 GB) com o Ollama descarregado.
            self._modelo = SentenceTransformer(origem_modelo(self.nome_modelo), device=self.dispositivo)
            self._modelo.max_seq_length = self._max_tokens
        return self._modelo

    @na_thread_principal  # torch só na thread principal (ver thread_principal.py)
    def embed(self, textos):
        modelo = self._carregar()
        try:
            vetores = modelo.encode(list(textos), batch_size=self._lote, normalize_embeddings=True,
                                    show_progress_bar=False, convert_to_numpy=True)
        except RuntimeError as exc:  # falta de memória na GPU: refaz na CPU
            if "out of memory" not in str(exc).lower() or self.dispositivo != "cuda":
                raise
            log.warning("GPU sem memória para embeddings; usando CPU.")
            import torch

            torch.cuda.empty_cache()
            self._modelo, self._dispositivo = None, "cpu"
            return self.embed(textos)
        return vetores.astype("float32").tolist()

    @na_thread_principal
    def liberar(self):
        """Libera a VRAM após a indexação (o LLM volta a ter a GPU inteira)."""
        if self._modelo is not None and self.dispositivo == "cuda":
            import torch

            self._modelo = None
            torch.cuda.empty_cache()
