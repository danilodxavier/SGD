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

## Fase 6 — relações e agrupamento (2026-11-16)

| Métrica | Meta | Resultado |
|---|---|---|
| F1-macro, 8 classes (sintético, 103 relações) | ≥ 0,85 | 1,00 — otimista: regras ajustadas nesse gabarito |
| Relações oficiais conhecidas (público, 10) | — | 10/10 |
| Relações fortes públicas conferidas manualmente | — | 38/39 |
| Pureza do agrupamento | ≥ 0,90 | 0,932 (inversa 0,983) |

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
| v1 (baseline) | 2026-11-16 | App legado: FTS + regras (sem HTML) | 0,099 | 0,431 | 0,401 | 0,451 | — | 11,3% (num.) | 0,327 | — | 3 ms / 5 ms | 0 |
| v2.1 | 2026-11-16 | v2.0 + vigência pelo grafo + respostas de conflito determinísticas | 0,240 | **0,965** | 0,909 | 0,964 | pendente (juiz) | **3,1%** (num.) | 0,891 | 1,00 (sint.) / 10/10 públicas | 14,4 s / 29,2 s | ≈ 2.500 / 110 |
| v2.0 | 2026-11-16 | Híbrido BM25+bge-m3 → RRF → vigência → bge-reranker-v2-m3; ResponderF1 com Qwen 2.5 7B | 0,240 | **0,965** | 0,897 | 0,951 | pendente (juiz) | **4,3%** (num.) | 0,861 | — | 14,6 s / 28,7 s | ≈ 2.500 / 110 |

Notas: conjunto de **teste** (124 perguntas; 109 nas métricas de resposta, sem F2). "Alucinação (num.)" = indicador determinístico de números/datas/valores não suportados pelos trechos citados. Faithfulness com LLM-juiz calibrado fica para a Fase 10. Detalhes por tipo em `avaliacao/execucoes/fase5/relatorio.json`.

### Respostas — teste

| Sistema | Exatidão | Classificação | Recusa correta | Conflito | Cita fonte esperada | Precisão citações |
|---|---|---|---|---|---|---|
| v1 | 0,217 | 0,615 | 0,375 | 0,833 | 0,327 | 0,366 |
| v2.0 (Qwen 2.5 7B) | 0,795 | 0,908 | 1,000 | 0,000 | 0,861 | 0,809 |
| **v2.1** (grafo + conflitos) | **0,843** | **0,954** | 1,000 | **1,000** | **0,891** | 0,794 |

Alucinação numérica recalculada com normalização de datas e citações de atos (mesmo critério para todas as versões): v1 11,3%; v2.0 3,2%; v2.1 3,1%.

### Benchmark de LLMs — validação (47)

| Modelo | Exatidão | Recusa | Conflito | Cita OK | Aluc. num. | p50 |
|---|---|---|---|---|---|---|
| Qwen 2.5 7B | 0,846 | 1,00 | 0,0 | 0,86 | 2,5% | 13,9 s |
| Llama 3.1 8B | 0,718 | 0,75 | 0,5 | 0,84 | 4,9% | 16,1 s |

## Histórico de execuções

| Data | Rótulo | Conjunto | O que mudou | Evidência |
|---|---|---|---|---|
| 2026-11-16 | fase5 / experimento_schema_estrito | validação | ResponderF1 com JSON Schema estrito | exatidão 0,26 |
| 2026-11-16 | fase5 | validação | JSON livre ordenado (resposta primeiro) | exatidão 0,846 |
| 2026-11-16 | fase5 / experimento_fontes_numericas | validação | Llama sem normalização de ids | exatidão 0,205 |
| 2026-11-16 | fase5 | validação | Llama com normalização de ids | exatidão 0,718 |
| 2026-11-16 | fase5 | **teste** | v2.0 final (Qwen 2.5 7B) | exatidão 0,795; R@5 0,965 |
| 2026-11-16 | fase6_relacoes | sintético + público | Classificador de relações por regras | F1-macro 1,00 (sint., sobreajuste); 10/10 relações oficiais; 38/39 relações públicas coerentes |
| 2026-11-16 | fase6 | **teste** | v2.1: vigência do grafo + conflitos determinísticos | exatidão 0,843; conflito 1,00; MRR 0,909 |
