# ADR-005 — Embeddings e reranker locais

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | RF-05, RF-06, RNF-01, RNF-03, RNF-04 |

## Contexto

Busca semântica em português jurídico-administrativo, com números (contratos, CNPJ, artigos) que embeddings densos tratam mal. Execução local; pesos devem ficar em `modelos\` (ADR-001). `sentence-transformers 6.3` e `torch 2.15` têm wheels para Python 3.15 (verificado por resolução `pip --dry-run`).

## Decisão

| Componente | Modelo | Motivo |
|---|---|---|
| Embeddings densos | **BAAI/bge-m3** (1024 dims, 8192 tokens, multilíngue, MIT) | Forte em PT entre modelos abertos; contexto longo comporta artigos/cláusulas inteiros |
| Reranker | **BAAI/bge-reranker-v2-m3** (cross-encoder, Apache-2.0) | Mesma família/tokenizador; multilíngue |
| Lexical | **FTS5/BM25** (já existente na v1) | Exatidão em números, siglas e nomes |
| Fusão | **Reciprocal Rank Fusion** (k = 60) | Sem calibração de escalas; robusto |

Pipeline de recuperação: `BM25 top-50 ∪ denso top-50 → RRF → filtros (vigência, tipo, processo) → rerank top-20 → top-k (5–8)`.

Execução: indexação em lote na GPU (fp16, LLM descarregado); consulta na CPU (1 vetor). Pesos em `modelos\hf` via `HF_HOME`.

## Plano B (gatilho: reranker CPU > 4 s p95 na Fase 5)

Rerank em top-10; ou `bge-reranker-base`; ou rerank na GPU quando o LLM rodar em outro processo com VRAM folgada.

## Ajuste fino (prompt mestre §4)

Não fazer ajuste fino de início. **Portão de decisão na Fase 5:** se Recall@5 < 0,90 após híbrido + rerank + ajuste de chunking, ajustar o reranker com pares (pergunta, trecho positivo, negativos difíceis) gerados do corpus sintético, separado do conjunto de teste. Registrar em ADR próprio.

## Alternativas

| Alternativa | Por que não agora |
|---|---|
| multilingual-e5-large | 512 tokens, cortaria dispositivos longos |
| Embeddings via API (Gemini/OpenAI) | Envio externo de todo o corpus; viola ADR-002 para dados reais |
| Esparso do bge-m3 no lugar de BM25 | FTS5 já existe, é exato para números e explicável; reavaliar se houver ganho |

## Implementação (Fase 4, 2026-11-16)

- Pesos oficiais vêm como `pytorch_model.bin`; `scripts/sadgd/preparar_bge_m3.py` baixa e converte para `modelos/bge-m3/model.safetensors` (cópia local, sem rede em execução).
- **Carga sequencial obrigatória** (`HF_DEACTIVATE_ASYNC_LOAD=1`): a carga paralela do transformers 5 causou `access violation` (CPU e GPU) neste ambiente.
- **float32 na GPU**: na GTX 1660 SUPER, fp16 rendeu 3,8 trechos/s e fp32 19,0 trechos/s (sem NaN). VRAM ≈ 2,3 GB, com o Ollama descarregado automaticamente antes do lote.
- Texto do embedding = título + caminho hierárquico + caput + trecho literal (o texto citado no banco permanece literal).
- Corpus indexado: 5.691 trechos/vetores. Reranker será implementado na Fase 5.