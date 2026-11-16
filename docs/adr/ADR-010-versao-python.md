# ADR-010 — Versão do Python e gestão de dependências

| Campo | Valor |
|---|---|
| Status | **Proposto** |
| Data | 2026-11-16 |
| Requisitos | RNF-02, RNF-03, RNF-09 |
| Revisa | Risco R06 e conflito C4 da FASE_00 |

## Contexto (evidências de 2026-11-16)

- `.venv` do projeto usa **Python 3.15.0** (SQLite 3.53.4, `enable_load_extension` funcional).
- O Python 3.13 listado no `py -0` está **quebrado** (`C:\Python313\python.exe` inexistente) — não utilizável.
- Resolução `pip install --dry-run` no 3.15 para `langgraph sqlite-vec sentence-transformers pymupdf pytesseract ragas arize-phoenix`: **205 pacotes, todos com wheel para cp315/win_amd64**, inclusive `torch 2.15.0`, `numpy 2.5.5`, `scipy 1.18.1`, `scikit-learn 1.9.1`, `pyarrow 26.0.1`, `grpcio 1.85.1` — **exceto `pyyaml` e `zstandard`**, que viriam como código-fonte (sdist).

O risco R06 ("bibliotecas de IA incompatíveis com 3.15") **não se confirmou** para o conjunto escolhido.

## Decisão

1. **Manter Python 3.15** e o `.venv` atual do projeto.
2. Dependências em camadas: `requirements.txt` (núcleo v1), `requirements-ia.txt` (IA: langgraph, sentence-transformers, torch, sqlite-vec, ragas, phoenix…), `requirements-dev.txt` (pytest, cobertura, lint). Versões **fixadas** em `constraints.txt` gerado pelo ambiente validado (reprodutibilidade/LLMOps).
3. `torch` com CUDA: instalar pelo índice oficial do PyTorch compatível com a GTX 1660 SUPER (Turing, sm_75), validando `torch.cuda.is_available()` na Fase 3; fallback CPU.
4. **Plano B** (se `pyyaml`/`zstandard` não compilarem ou surgir incompatibilidade): Python 3.13 instalado **dentro do projeto** via `uv` (`UV_PYTHON_INSTALL_DIR=<projeto>\ferramentas\python`), sem tocar no sistema.
5. Caches dentro do projeto: `PIP_CACHE_DIR=data\cache\pip`, `HF_HOME=modelos\hf`, `TORCH_HOME=modelos\torch`.

## Consequências

- (+) Nenhuma migração de ambiente; a v1 continua funcionando.
- (−) Versão nova do Python reduz a margem para bibliotecas menos mantidas; mitigado pelo plano B e pelo `constraints.txt`.
