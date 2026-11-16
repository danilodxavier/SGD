# FASE 05 — RAG, golden set e avaliação baseline F1 (Sprint S5)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aprovada em 2026-11-16** |

## 1. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| SAD-050 | **Recuperação híbrida**: termos/expressão FTS5, BM25, denso (bge-m3), **RRF**, **filtro de vigência** (dispositivo tachado/norma revogada → histórico), **reranker bge-reranker-v2-m3**; 4 modos comparáveis | `app/application/recuperacao/{regras,hibrida}.py`, `app/infrastructure/sqlite/busca.py`, `app/infrastructure/modelos/reranker.py` |
| SAD-051 | **ResponderF1**: contexto rotulado `[T<id>]`, prompt versionado (regras comuns + relator), JSON livre ordenado, salvaguardas determinísticas (citação fora do contexto descartada; resposta factual sem citação → ausência; sem trechos → ausência sem LLM) | `app/application/respostas/f1.py` |
| SAD-052 | **Golden set: 177 perguntas** (66 F1 simples, 24 F1 complexas — 10 de conflito —, 54 linha do tempo, 21 F2, 12 ausência; 155 sintéticas, 22 públicas) — **toda fonte validada contra o índice** (0 rejeitadas na versão final); split estratificado **53 validação / 124 teste** | `scripts/sadgd/gerar_golden_set.py`, `avaliacao/golden_set/` |
| SAD-053 | **Suíte de avaliação** em estágios com cache e retomada (cabe na RAM da máquina); métricas determinísticas com TDD: P@k, R@k, MRR, nDCG graduado, exatidão por resposta-chave, classificação, citação correta, precisão de citação, **alucinação numérica**; modo `ci` com piso de regressão | `app/application/avaliacao/{metricas,metricas_resposta}.py`, `scripts/sadgd/{avaliar,avaliar_respostas}.py` |
| SAD-054 | **Baseline v1 × v2** (v1 = app legado: FTS + regras, sem modificações; reindexado nas tabelas v1) | `avaliacao/execucoes/fase5/` |
| SAD-055 | **Benchmark de LLMs** (validação): Qwen 2.5 7B × Llama 3.1 8B → Qwen escolhido; Qwen 2.5 3B pendente (download interrompido por falta de memória) | idem |

## 2. Resultados — conjunto de TESTE (nunca usado para ajustes)

### 2.1 Recuperação (perguntas com fonte, exceto F2)

| Sistema | R@1 | R@5 | R@10 | MRR | nDCG@10 | p50 | p95 |
|---|---|---|---|---|---|---|---|
| v1 (FTS legado) | 0,351 | 0,431 | 0,460 | 0,401 | 0,451 | 4 ms | 4 ms |
| BM25 | 0,490 | 0,594 | 0,634 | 0,589 | 0,669 | 9 ms | 11 ms |
| Denso (bge-m3) | 0,713 | 0,906 | 0,946 | 0,844 | 0,904 | 45 ms | 65 ms |
| Híbrido (RRF) | 0,535 | 0,748 | 0,896 | 0,709 | 0,845 | 56 ms | 86 ms |
| **Híbrido + rerank** | **0,782** | **0,965** | **0,965** | **0,897** | **0,951** | 1,6 s | 2,6 s |

Nenhum dispositivo revogado no top-5 de nenhum modo v2 (filtro de vigência).

### 2.2 Respostas (F1 simples/complexa, linha do tempo e ausência; 109 perguntas)

| Sistema | Exatidão | Classificação | Recusa correta | Conflito | Cita fonte esperada | Precisão citações | Alucinação numérica | p50 | p95 |
|---|---|---|---|---|---|---|---|---|---|
| v1 (regras) | 0,217 | 0,615 | 0,375 | 0,833 | 0,327 | 0,366 | 0,113 | 3 ms | 5 ms |
| **v2 (RAG + Qwen 2.5 7B)** | **0,795** | **0,908** | **1,000** | 0,000 | **0,861** | **0,809** | **0,043** | 14,6 s | 28,7 s |

### 2.3 Metas

| Meta (ADR-011) | Resultado | Situação |
|---|---|---|
| Recall@5 ≥ 0,90 | 0,965 | ✅ |
| Alucinação ≤ 5% | 4,3% (indicador numérico determinístico) | ✅ (proxy) |
| Citações corretas ≥ 0,95 | 0,861 | ❌ — a atacar na Fase 7 (verificador) |
| Faithfulness ≥ 0,90 | não medido: exige LLM-juiz de outra família + calibração humana | ⏳ Fase 10 |
| Latência F1 p95 ≤ 15 s | 28,7 s | ❌ — Fase 10 (contexto menor, roteador 3B, cache semântico) |
| Detecção de conflito | 0% no v2 (v1: 83% por regras) | ❌ — Fase 6 (detecção determinística de contradições, RF-09) |

## 3. Benchmark de LLMs (validação, 47 perguntas)

| Modelo | Exatidão | Classif. | Recusa | Conflito | Cita OK | Precisão cit. | Aluc. num. | p50 |
|---|---|---|---|---|---|---|---|---|
| **Qwen 2.5 7B (Q4_K_M)** | **0,846** | 0,872 | **1,00** | 0,0 | **0,86** | **0,83** | **2,5%** | **13,9 s** |
| Llama 3.1 8B (Q4_K_M) | 0,718 | 0,872 | 0,75 | **0,5** | 0,84 | 0,75 | 4,9% | 16,1 s |

Escolha: **Qwen 2.5 7B** — melhor exatidão, latência e, sobretudo, **recusa** (o Llama afirmou algo inexistente nos documentos). O Llama detecta melhor conflitos e é de outra família: candidato a **verificador/juiz** (Fases 7 e 10).

## 4. Experimentos e achados (insumo do relatório acadêmico)

| # | Achado | Evidência |
|---|---|---|
| 1 | **Ordem dos campos na saída estruturada muda o comportamento do modelo.** Com JSON Schema estrito, o Ollama emite as chaves em ordem alfabética: o modelo "decide" `classificacao` antes de redigir `resposta` e recusa indevidamente (17 de 27 factuais viraram ausência). Com JSON livre e a ordem resposta → fontes → classificação no prompt: exatidão 0,26 → **0,85** na validação | `experimento_schema_estrito_v2_*.jsonl` |
| 2 | **Fusão RRF sem reranker piora o denso** (R@5 0,906 → 0,748): o BM25 traz candidatos ruins para o topo; o cross-encoder recupera e supera ambos (0,965) | `relatorio.json` |
| 3 | **Formato de citação varia entre modelos** (Llama devolve `[8306]` em vez de `"T8306"`); validar só o formato derrubava 25 respostas corretas. Normalização do formato mantendo a exigência de que o id esteja no contexto | `experimento_fontes_numericas_v2_llama*.jsonl`, teste dedicado |
| 4 | A métrica de alucinação numérica precisava considerar os **metadados mostrados ao modelo** (título/data do documento, extraídos do próprio documento); sem isso, 17,5% de "alucinações" eram falsos positivos (corrigido → 2,5%) | `avaliar_respostas.py --recalcular` |
| 5 | Erros reais de raciocínio que as métricas automáticas não pegam: "ainda está vigente, pois foi revogado" (V038) e "continua vigente" para norma com nota de revogação (V049) — alvo do verificador da Fase 7 | `respostas_v2_sadgd-qwen2.5-7b.jsonl` |
| 6 | O v1 só lê 119 dos 186 documentos (não suporta HTML): os 69 atos oficiais ficam invisíveis — limitação estrutural que explica parte da diferença | `data/logs/indexar_v1.out.log` |

## 5. Ressalvas metodológicas

- **Golden set gerado** a partir do gabarito sintético e de uma lista curada do corpus público; todas as fontes foram validadas automaticamente contra o índice, mas o ADR-011 exige **revisão humana** (`revisado_por: pendente`). Recomendo ao responsável revisar ao menos as 53 perguntas de validação.
- **Alucinação numérica** é um indicador determinístico conservador (números/datas/valores não suportados pelos trechos citados); não substitui o faithfulness com juiz calibrado (Fase 10).
- O sintético é regular por construção (risco R08): as métricas por origem estão em `relatorio.json` (`por_tipo`), e o corpus público entra no golden set (22 perguntas).
- O CI roda a avaliação reduzida BM25 no corpus sintético com **piso de regressão** (R@10 ≥ 0,65; MRR ≥ 0,50), não as metas — metas exigem GPU e modelos locais.

## 6. Incidentes

| Ocorrência | Tratamento |
|---|---|
| Download do Llama 3.1 8B + Qwen 2.5 3B encerrado por falta de memória | Llama concluiu antes; Qwen 3B **não** foi baixado de novo sem autorização |
| `# noqa` inserido por engano dentro da string de palavras vazias | Detectado na revisão (antes do commit, após a avaliação — resultados não afetados); lista restaurada e verificada (88 termos) |
| Piso do CI acima do valor medido | Piso recalibrado = valor medido − margem, documentado no código |

## 7. Pendências

1. Autorizar o download do **Qwen 2.5 3B** (1,9 GB) para completar o benchmark com 3 modelos (SAD-055) — candidato a roteador.
2. **Revisão humana do golden set** (ao menos o conjunto de validação).
3. Kanban (GitHub Projects) depende do `gh`.

## 8. Retrospectiva

- **Bem:** avaliação em estágios com cache tornou viável medir tudo com 1–2 GB de RAM livre; os experimentos negativos (schema estrito, RRF puro, formato de citação) viraram achados documentados.
- **A melhorar:** inspecionar respostas brutas logo na primeira execução — dois "maus resultados" eram defeitos de integração, não do modelo.
- **Ação:** Fase 6 ataca conflitos (contradições) e relações; Fase 7, citações e raciocínio de vigência via verificador.

## 9. Aprovação

- [x] Aprovado pelo responsável em 2026-11-16 ("aprovado"). Sem resposta sobre o download do Qwen 2.5 3B — não realizado.
