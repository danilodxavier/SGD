# Avaliação — SAD-GD

Resultados por versão sobre o golden set (`avaliacao\golden_set\`, a partir da Fase 5). Conjunto de **teste** nunca é usado para ajustes.

## Metas

| Métrica | Meta |
|---|---|
| Recall@5 | ≥ 0,90 |
| Faithfulness | ≥ 0,90 |
| F1-macro classificação de relações | ≥ 0,85 |
| Taxa de alucinação | ≤ 5% |
| Citações corretas | ≥ 0,95 |
| Latência F1 p95 | ≤ 15 s |
| Latência F2 p95 | ≤ 120 s |

## Fase 4 — qualidade da ingestão (2026-11-16)

| Métrica | Meta | Resultado | Evidência |
|---|---|---|---|
| Limites de dispositivos (sintético, 63 docs) | ≥ 0,95 | 1,00 (unidades e subdispositivos) | `avaliacao/execucoes/fase4_chunking.json` |
| Artigos reconhecidos em leis reais | — | Lei 14.133: 194/194; Lei 9.784: 70/70 | idem |
| Tipo documental (186 docs) | ≥ 0,90 | 1,00 | `fase4_metadados.json` |
| Número do ato (179 extraíveis) | ≥ 0,90 | 1,00 | idem |
| Data do documento | — | 0,984 | idem |
| CER do OCR (6 PDFs digitalizados) | ≤ 0,10 | Tesseract 0,0009; Windows 0,0052 | `fase4_ocr.json` |
| Reindexação sem mudanças | 0 processados | 0 (186 inalterados, 0,0 s) | `fase4_indexacao.json` |
| Vazão de embeddings (bge-m3, GTX 1660 SUPER) | — | 19 trechos/s (fp32) | `FASE_04.md` §5 |

## Tabela comparativa por versão

| Versão | Data | Descrição | P@5 | R@5 | MRR | nDCG@10 | Faithfulness | Alucinação | Citações corretas | F1 relações | p50/p95 F1 | Tokens/consulta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 (baseline) | — | Regras + BM25 (app legado) | a medir na Fase 5 | | | | | | | — | | 0 |

## Histórico de execuções

_(vazio — primeira execução prevista na Fase 5)_
