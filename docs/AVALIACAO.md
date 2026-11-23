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

## Avaliação final (Fase 10) — métricas × metas, conjunto de TESTE

| Métrica | Meta | Resultado | Situação |
|---|---|---|---|
| Recall@5 | ≥ 0,90 | 0,965 | ✅ |
| Faithfulness | ≥ 0,90 | 0,964 (adjudicada; juiz bruto 0,795) | ✅ |
| Alucinação | ≤ 5% | 0,0% numérica; 5,4% por frase (adjudicada) | ⚠️ marginal |
| F1 relações | ≥ 0,85 | 1,00 sintético (sobreajuste); 10/10 públicas | ✅ ressalva |
| Classificação de tipo documental | ≥ 0,85 | 1,00 | ✅ |
| Roteamento | ≥ 0,90 | 0,935 | ✅ |
| Precedentes R@3 | ≥ 0,80 | 1,00 | ✅ |
| RF-20 (6 elementos) | 100% | 100% | ✅ |
| Latência F1 / F2 / cache (p50) | — | 14,6 s / 329 s / 5 ms | ⚠️ F2 (hardware) |
| Latência F2 p95 — Gemini, corpus acadêmico (Fase 11) | ≤ 120 s | **99,6 s** (p50 29,9 s) | ✅ (opcional, nuvem) |
| Tokens F1 / F2 (entrada/saída) | medir | 2.457/107 · 18.872/2.538 | ✅ |
| Custo | R$ 0 | R$ 0 | ✅ |

Juiz de faithfulness (Llama 3.1 8B) calibrado na validação: sensibilidade 0,82, especificidade 0,90, κ 0,71 (adjudicado). Detalhes em `docs/fases/FASE_10.md` §4 e `avaliacao/execucoes/fase10_fidelidade.json`.

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

### Fase 11 — F2 no Gemini, plano gratuito (`avaliacao/execucoes/fase11/f2_resumo.json`)

Mesmas 21 perguntas F2; especialistas e relator em `gemini-3.5-flash-lite` (contexto 100% acadêmico e anonimizado, `AI_ALLOW_REMOTE=true`), roteador, recuperação, verificador e RF-20 inalterados; falha remota cai no Qwen 2.5 7B local.

| Execução | Schema pareceres bruto / reparado | Schema relator | RF-20 presentes / com conteúdo | Recall docs | Precisão docs | Base legal (média) | p50 / p95 | Tokens (entr./saída) | Itens com falha remota |
|---|---|---|---|---|---|---|---|---|---|
| Fase 8 (Qwen local) | 0,789 / 1,00 | 1,00 | 1,00 / 0,714 | 0,794 | 0,444 | 1,81 | 329 s / 387 s | 18.872 / 2.538 | — |
| v0 (4 itens, reserva sem repetição) | 0,778 / 1,00 | 0,50 | 1,00 / 0,75 | 0,708 | 0,558 | 2,50 | 98 s / 273 s | 16.679 / 2.293 | 3/4 |
| v1 (21; `consensos` como objeto) | 0,692 / 1,00 | 0,333 | 1,00 / 0,714 | 0,841 | 0,573 | 1,71 | 91 s / 213 s | 18.083 / 2.693 | 15/21 (503) |
| **v2 (21; reparo de `consensos`)** | 0,731 / 1,00 | **1,00** | **1,00** / 0,714 | **0,865** | 0,554 | 1,43 | **30 s / 100 s** | 17.978 / 2.759 | 5/21 (503/429) |

Leitura: a F2 em nuvem **atinge a meta de p95 ≤ 120 s** (3,9× mais rápida no p95) com qualidade igual ou maior nos critérios estruturais e de recuperação. A queda do relator na v1 era de **forma**, não de conteúdo: o prompt citava `"consensos"` sem formato ao lado de `divergencias` em `{tema, posicoes}` e o Gemini repetia esse formato; correção = instrução explícita + reparo determinístico que preserva o conteúdo (teste de regressão em `test_orquestrador.py`). Ressalvas: a latência em nuvem varia com a demanda (503 "high demand") e a cota por minuto do plano gratuito (429); a menor média de base legal citada pelo modelo é coberta pelo complemento determinístico do RF-20. **Somente corpus acadêmico** — dados reais continuam no LLM local (ADR-002).

### Compressão do contexto na F2 — conjunto de TESTE (15 F2; `avaliacao/execucoes/fase11_f2ctx/`)

Qwen 2.5 7B local nas duas execuções; banco acadêmico separado; única diferença relevante: `SADGD_CONTEXTO_MAX_CHARS=1200`
nos especialistas e no relator (reranker na GPU desde a Fase 11).

| Execução (teste, 15) | Erros | Schema pareceres reparado | Relator válido | RF-20 presentes / com conteúdo | Afirmações removidas/consulta | Recall docs | Precisão docs | Base legal (média) | Confiança | p50 / p95 | Tokens (entr./saída) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fase 8 (sem compressão) | 0 | 1,00 | 1,00 | 1,00 / 0,667 | 0,27 | 0,822 | 0,466 | 1,73 | 0,62 | 334 s / 393 s | 18.894 / 2.648 |
| **Compressão 1.200** | 0 | 1,00 | 1,00 | 1,00 / 0,667 | 0,40 | **0,822** | 0,439 | 1,53 | 0,65 | **288 s** / 396 s | 17.492 / 2.734 |

Leitura: no teste, a compressão **não reduz o recall de documentos** (0,822 nas duas) e mantém schema, relator e RF-20
inalterados; a queda de recall vista na validação (0,722 → 0,639, 6 perguntas) não se confirmou e era ruído de amostra
pequena. Custos: precisão de documentos −0,027, base legal citada −0,2 por consulta (coberta pelo complemento
determinístico do RF-20) e +0,13 afirmação removida pelo verificador por consulta. Ganho: p50 −14% e −7% de tokens de
entrada. O benefício decisivo está no acervo real, onde os trechos longos estouravam o contexto (ver
`docs/AVALIACAO_REAL.md` §7.3). **A compressão 1.200 fica como padrão na F1 e na F2.**

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
| 2026-11-17 | fase10 (F2) | validação (6) | Especialistas 3B / orçamento 1.300 | 3B: 2,5× mais rápido, 7% pareceres com conteúdo (rejeitado); orçamento: −8% latência, recall pior (rejeitado) |
| 2026-11-17 | fase10_cache | golden set | Limiar do cache semântico | maior par diferente 0,883 → limiar 0,93 |
| 2026-11-17 | fase10_fidelidade | validação (calibração) + teste | LLM-juiz Llama 3.1 8B | κ 0,71; faithfulness 0,964 adjudicada; alucinação 5,4% |
| 2026-11-17 | fase11 (F2 Gemini v1) | validação + teste (21) | Especialistas e relator no Gemini 3.5 Flash-Lite | schema relator 0,333 (`consensos` em objeto); p95 213 s |
| 2026-11-23 | caminho real — versão de entrega (scratchpad) | validação (47 F1) | Torch na thread principal, laço Selector, correção do valor do aditivo | Exatidão 0,949 (47/47 adjudicada); classificação 0,979; recusa 1,00; 20/47 pela ficha. Ver `fases/FASE_12.md` §21 |
| 2026-11-23 | caminho real (scratchpad, sem arquivo no Git) | validação (47 F1) | Pipeline do servidor: fichas + escopo + busca ao vivo + verificador | Exatidão 0,949 (47/47 adjudicada); classificação 0,979; recusa 1,00; 20/47 pela ficha; p50 1,8 s, p95 62 s. Ver `fases/FASE_12.md` §19 |
| 2026-11-23 | fase12_f2_par2 | validação (6 F2) | `OLLAMA_NUM_PARALLEL=2` | p50 121 → 154 s; recall docs 0,639 → 0,583; **rejeitado**. Ver `fases/FASE_12.md` §18 |
| 2026-11-22 | fase12_ab2 | validação (47 F1, com verificador) | 2 aberturas em vez de 3 | Tokens 3.009 → 3.008 (sem efeito); exatidão 0,923; sem ganho |
| 2026-11-22 | fase12_kv_q8b | validação (47 F1, com verificador) | Repetição de `fase12_kv_q8` | Exatidão 0,923; recusa 1,00; citação 0,954; precisão das citações 0,700; p50 9,7 s (variação 9,7–20,7 s entre execuções idênticas) |
| 2026-11-22 | fase12_f2_kv_q8 | validação (6 F2) | Ollama com flash attention + cache de contexto q8_0 | p50 150 → 121 s (−19%); RF-20 1,00 =; recall docs 0,639 =; precisão 0,511 → 0,517; schema bruto 0,857 (reparado 1,00). Ver `fases/FASE_12.md` §18 |
| 2026-11-22 | fase12_kv_q8 | validação (47 F1, com verificador) | Ollama com flash attention + cache de contexto q8_0 (geração 23,8 → 26,7 tok/s) | Exatidão 0,923 → 0,949; recusa 1,00 =; conflito 1,00 =; citação 0,954 =; alucinação 0 =; precisão das citações 0,716 → 0,684; **adotado**. Ver `fases/FASE_12.md` §18 |
| 2026-11-22 | fase12_contexto_doc | validação (47 F1, com verificador) | Ficha do documento uma vez por documento (bloco DOCUMENTO) | Exatidão 0,923 =; tokens −3%; **recusa 1,00 → 0,75** (V036, confirmado isolado com o mesmo modelo); **rejeitado e revertido**. Ver `fases/FASE_12.md` §17 |
| 2026-11-22 | fase12_f2_orcamento | validação (6 F2) | Orçamento do contexto da decisão (num_ctx 8192), linha do tempo recente, parecer enxuto | Schema bruto 0,714 → 1,00; afirmações removidas 1,0 → 0; recall docs 0,639 =; precisão 0,442 → 0,511; RF-20 0,83 =; p50 236 → 150 s (−36%), p95 265 → 185 s. Ver `fases/FASE_12.md` §15 |
| 2026-11-22 | fase12_f2 | validação (6 F2) | Contexto compartilhado (cache de prefixo) entre especialistas e relator | Relator 1,00 =; RF-20 completo 0,83 =; recall docs 0,639 =; precisão 0,456 → 0,442; p50 319 → 236 s (−26%) |
| 2026-11-21 | fase12_rapido | validação (47 F1, com verificador) | Modelo 100% na GPU (`num_gpu 29`), compressão 800, relator v3 enxuto, detalhe reprovado sem nova chamada | Exatidão 0,923 =; classificação 0,915 → 0,979; citação 0,907 → 0,954; recusa 1,00; aluc. 0; LLM p50 23,1 → 16,9 s, p95 48,5 → 31,1 s. Ver `fases/FASE_12.md` §6 |
| 2026-11-21 | fase11_respostas_completas | validação (47 F1, **com verificador**) | Resposta direta + detalhes citados; verificador por frase; modos lista/histórico | Exatidão 0,923 =; recusa 1,00; aluc. num. 0; citação 0,907; resposta 129 → 273 caracteres; p50 23 s / p95 50 s. Ver `AVALIACAO_REAL.md` §9 |
| 2026-11-21 | fase11_detalhes / fase11_detalhes_verif | validação (47 F1) | Descartados: detalhes sem disciplina de citação | Aluc. num. 0,231 (sem verificador); recusa 0,75 |
| 2026-11-21 | fase11_abertura2 | validação (47 F1) | Ficha do documento + sem cópias + 2ª leitura nas recusas + abertura (docs sem nº) | Exatidão 0,923 =; classificação 0,936 → 0,957; recusa 1,00 =; citação correta 0,907 → 0,930; aluc. num. 0 → 0,023 (1 item, sem verificador); p50 9,5 → 16,5 s. Ver `AVALIACAO_REAL.md` §8 |
| 2026-11-21 | fase11_ficha / fase11_abertura | validação (47 F1) | Descartados: evidências em toda pergunta / abertura para todos | Classificação 0,830 e p50 17,9 s / p95 54 s sem ganho de exatidão |
| 2026-11-21 | fase11_f2ctx | teste (15 F2) | Compressão 1.200 na F2 × Fase 8 | Recall docs 0,822 = 0,822; RF-20 1,00; relator 1,00; p50 334 → 288 s; precisão docs 0,466 → 0,439 |
| 2026-11-21 | fase11_f2ctx | validação (6 F2) | Compressão 1.200 na F2 | RF-20 1,00 nas duas; recall docs 0,722 → 0,639; p50 333 → 303 s. Acervo real: 0 → 6–7 fontes citadas (contexto deixou de estourar) |
| 2026-11-20 | fase11_ctx0/1200/800 | validação (47 F1) | Compressão do contexto por trecho (A3) | exatidão 0,923 nas três; p50 14,9 / 9,5 / 11,6 s; 1.200 adotado |
| 2026-11-20 | acervo real (latência) | 4 perguntas | Reranker na GPU + compressão 1.200 | F1 60,5 s → 17,3 s; ranking idêntico com reranker na GPU |
| 2026-11-17 | fase11 (F2 Gemini v2) | validação + teste (21) | + reparo/instrução de `consensos` | schema relator 1,00; recall docs 0,865; p50/p95 30 s / 100 s |
