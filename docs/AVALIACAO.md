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

## Tabela comparativa por versão

| Versão | Data | Descrição | P@5 | R@5 | MRR | nDCG@10 | Faithfulness | Alucinação | Citações corretas | F1 relações | p50/p95 F1 | Tokens/consulta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 (baseline) | — | Regras + BM25 (app legado) | a medir na Fase 5 | | | | | | | — | | 0 |

## Histórico de execuções

_(vazio — primeira execução prevista na Fase 5)_
