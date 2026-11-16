"""Prepara o modelo de embeddings BAAI/bge-m3 em modelos/bge-m3 (safetensors), tudo dentro do projeto (ADR-001/005).

1. Baixa do Hugging Face os arquivos necessários (cache em modelos/hf).
2. Converte pytorch_model.bin -> model.safetensors numa cópia local, lendo na thread principal.

O repositório oficial publica os pesos em .bin; a cópia em safetensors carrega por mapeamento de memória,
sem pickle. Uso: python scripts/sadgd/preparar_bge_m3.py
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import app.core.config  # noqa: E402,F401  (HF_HOME no projeto e carga sequencial)

DESTINO = RAIZ / "modelos" / "bge-m3"
ARQUIVOS = ["config.json", "config_sentence_transformers.json", "modules.json", "sentence_bert_config.json",
            "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
            "1_Pooling/config.json", "pytorch_model.bin"]


def main():
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors.torch import save_file

    if (DESTINO / "model.safetensors").is_file():
        print(f"[OK] Modelo já preparado em {DESTINO.relative_to(RAIZ)}")
        return 0
    DESTINO.mkdir(parents=True, exist_ok=True)
    pesos = None
    for nome in ARQUIVOS:
        caminho = Path(hf_hub_download("BAAI/bge-m3", nome))
        if nome == "pytorch_model.bin":
            pesos = caminho
            continue
        alvo = DESTINO / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(caminho, alvo)
    estado = torch.load(pesos, map_location="cpu", weights_only=True, mmap=False)
    estado = {k: v.contiguous().clone() for k, v in estado.items()}
    save_file(estado, str(DESTINO / "model.safetensors"),
              metadata={"format": "pt", "origem": "BAAI/bge-m3 pytorch_model.bin"})
    print(f"[OK] {len(estado)} tensores convertidos para {DESTINO.relative_to(RAIZ)}\\model.safetensors")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
