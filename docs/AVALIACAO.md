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
| v2.2 | 2026-11-16 | v2.1 + verificador de fontes no F1; orquestrador multiagentes (F2) | 0,240 | **0,965** | 0,909 | 0,964 | pendente (juiz) | **0,0%** (num.) | 0,861 | 1,00 (sint.) / 10/10 públicas | 14,6 s / 29,0 s (F2: 250 s / 348 s) | ≈ 2.460 / 107 (F2: 17.350 / 2.510) |
| v2.1 | 2026-11-16 | v2.0 + vigência pelo grafo + respostas de conflito determinísticas | 0,240 | **0,965** | 0,909 | 0,964 | pendente (juiz) | **3,1%** (num.) | 0,891 | 1,00 (sint.) / 10/10 públicas | 14,4 s / 29,2 s | ≈ 2.500 / 110 |
| v2.0 | 2026-11-16 | Híbrido BM25+bge-m3 → RRF → vigência → bge-reranker-v2-m3; ResponderF1 com Qwen 2.5 7B | 0,240 | **0,965** | 0,897 | 0,951 | pendente (juiz) | **4,3%** (num.) | 0,861 | — | 14,6 s / 28,7 s | ≈ 2.500 / 110 |

Notas: conjunto de **teste** (124 perguntas; 109 nas métricas de resposta, sem F2). "Alucinação (num.)" = indicador determinístico de números/datas/valores não suportados pelos trechos citados. Faithfulness com LLM-juiz calibrado fica para a Fase 10. Detalhes por tipo em `avaliacao/execucoes/fase5/relatorio.json`.

### Respostas — teste

| Sistema | Exatidão | Classificação | Recusa correta | Conflito | Cita fonte esperada | Precisão citações |
|---|---|---|---|---|---|---|
| v1 | 0,217 | 0,615 | 0,375 | 0,833 | 0,327 | 0,366 |
| v2.0 (Qwen 2.5 7B) | 0,795 | 0,908 | 1,000 | 0,000 | 0,861 | 0,809 |
| v2.1 (grafo + conflitos) | 0,843 | **0,954** | 1,000 | **1,000** | **0,891** | 0,794 |
| **v2.2** (+ verificador) | **0,843** | 0,927 | 1,000 | **1,000** | 0,861 | 0,791 |

Alucinação numérica recalculada com normalização de datas e citações de atos (mesmo critério para todas as versões): v1 11,3%; v2.0 3,2%; v2.1 3,1%; **v2.2 0,0%** (as 3 datas erradas viraram recusas).

### F2 — apoio à decisão (21 perguntas; `avaliacao/execucoes/fase7/f2_resumo.json`)

| Rota F2 | Agentes P / R | Schema pareceres bruto / reparado | Schema relator | Alternativas / riscos / aviso | Recall docs | p50 / p95 | Tokens |
|---|---|---|---|---|---|---|---|
| 1,00 | 0,942 / 0,790 | 0,00 / 1,00 | 1,00 | 1,00 / 1,00 / 1,00 | 0,746 | 250 s / 348 s | 17.353 / 2.514 |

### Fase 8 — precedentes e F2 com RF-20 (`avaliacao/execucoes/fase8*`)

| Avaliação | Validação | Teste |
|---|---|---|
| Precedentes R@3 — denso / híbrido+rerank / **+limiar (adotado)** | 1,00 / 1,00 / 0,929 | 1,00 / 1,00 / **1,00** |
| Falso precedente (sem precedente que recebe algum), com limiar | 0/1 | 1/4 |

| F2 (21) | RF-20 presentes ou declarados | RF-20 com conteúdo | Schema pareceres bruto / reparado | Recall docs | Precedente pertinente (top-1, manual) | p50 / p95 |
|---|---|---|---|---|---|---|
| Fase 8 | **1,00** | 0,714 | 0,789 / 1,00 | 0,794 | 13/21 | 329 s / 387 s |

### Fase 9 — MVP (testes de aceitação)

| Critério | Evidência | Resultado |
|---|---|---|
| RF-21 pergunta → resposta → fonte abre o documento | E2E no Edge (`test_e2e_navegador.py`) | ✅ |
| RF-22 documento enviado aparece na busca | API + E2E | ✅ |
| RF-13 fases e relações clicáveis | E2E (evidência da ruptura) | ✅ |
| RF-23 401/403 por perfil | `test_api_acervo.py`, `test_api_decisoes.py` | ✅ |

### Roteador e anonimização (Fase 7)

| Avaliação | Validação | Teste |
|---|---|---|
| Roteador F1 × F2 / 3 rotas | 1,00 / 0,925 | 1,00 / 0,935 |
| Roteador agentes P / R | 0,857 / 0,667 | 0,974 / 0,841 |
| Anonimização: recall nomes PF / CPF (sintético) | 1,00 / 1,00 | — |

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
| 2026-11-16 | fase5 | validação | Qwen 2.5 3B no benchmark F1 | exatidão 0,462; p50 6,8 s |
| 2026-11-16 | fase7_roteador | validação + teste | Roteador por regras | 3 rotas 0,925 / 0,935 |
| 2026-11-16 | fase7 | **teste** | v2.2: verificador de fontes no F1 | alucinação num. 0,0%; exatidão 0,843 |
| 2026-11-16 | fase7 (F2) | validação + teste (21) | Orquestrador multiagentes ponta a ponta | 0 erros; schema 1,00 após reparo; p50 250 s |
| 2026-11-17 | fase8_relacoes | sintético + público | Contrato que cita lei = fundamenta | pureza 0,932 → 0,966; relações inalteradas |
| 2026-11-17 | fase8_precedentes | precedentes (15/35) | Memória de decisões híbrida + limiar calibrado na validação | R@3 0,929 / 1,00 |
| 2026-11-17 | fase8 (F2) | validação + teste (21) | Precedentes no contexto, relator v2, RF-20 | 6 elementos 100%; schema bruto 0 → 0,789; p50 329 s |
| 2026-11-17 | fase9 (E2E) | navegador | MVP completo | 4/4 E2E; 465 testes |
