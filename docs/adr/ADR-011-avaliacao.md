# ADR-011 — Estratégia de avaliação (métricas, juiz e golden set)

| Campo | Valor |
|---|---|
| Status | **Proposto** |
| Data | 2026-11-16 |
| Requisitos | RNF-06, RNF-12, RF-06–20; prompt mestre §4 |

## Decisão

### 1. Métricas determinísticas (código próprio, com testes unitários)

| Grupo | Métricas | Como |
|---|---|---|
| Recuperação | Precision@k, Recall@k, MRR, nDCG@k (k = 1, 3, 5, 10) | Relevância = trecho/documento listado em `fontes_esperadas` do golden set (graduada: 2 = dispositivo exato, 1 = mesmo documento) |
| Citação | Taxa de citações corretas | Citação correta ⇔ (documento, página/dispositivo) ∈ fontes esperadas **e** o trecho citado ocorre literalmente no texto do chunk (normalizado) |
| Ausência | Acurácia de recusa | Perguntas sem resposta na base devem retornar a mensagem de ausência |
| Classificação | Acurácia, precisão, recall, F1 (macro e por classe), matriz de confusão | `scikit-learn`, para tipo documental, relações (8 classes) e roteamento |
| Operacionais | Latência p50/p95, tokens de entrada/saída por consulta, custo (R$ 0 local; tokens para free tier) | Tabela `consultas` (ADR-009) |

### 2. Métricas de geração com LLM-juiz

- **RAGAS** (`ragas 0.3.x`): faithfulness, answer relevancy, context precision, context recall.
- **Taxa de alucinação** = proporção de afirmações sem suporte em algum trecho recuperado (afirmações extraídas e checadas pelo juiz; cruzada com o veredito do Verificador de fontes).
- **Juiz diferente do gerador:** sobre o **corpus acadêmico** (permitido por ADR-002), usar um modelo grande de free tier de outra família; sem free tier disponível, um modelo local de outra família, com a ressalva registrada.
- **Calibração do juiz:** 30 respostas anotadas manualmente pelo responsável; meta de concordância κ de Cohen ≥ 0,6. Sem calibração, métricas do juiz são reportadas como "não calibradas".
- Telemetria das bibliotecas de avaliação desativada (`RAGAS_DO_NOT_TRACK=true`). DeepEval não é adotado (sobreposição com RAGAS; telemetria/plataforma própria por padrão).

### 3. Golden set

- Local: `avaliacao\golden_set\{validacao,teste}.jsonl`; **teste nunca usado para ajustes**.
- Tamanho: ≥ 100 perguntas (≥ 60 F1, ≥ 20 linha do tempo/normas, ≥ 20 F2), incluindo ≥ 10 sem resposta e ≥ 10 com contradição.
- Divisão estratificada por tipo: 30% validação / 70% teste.
- Esquema por linha:

```json
{"id": "F1-001", "tipo": "F1_simples|F1_complexa|linha_do_tempo|F2|ausente",
 "pergunta": "...", "resposta_referencia": "...",
 "fontes_esperadas": [{"documento": "...", "pagina": 3, "dispositivo": "art. 107"}],
 "relacoes_esperadas": [{"origem": "...", "destino": "...", "tipo": "aditivo"}],
 "agentes_esperados": ["fiscal_contrato"], "origem": "publico|sintetico", "revisado_por": "responsavel"}
```

### 4. Execução

- `scripts\avaliar.py --versao vX --conjunto validacao|teste` grava resultados em `avaliacao\execucoes\<data>_<versao>\` e acrescenta linha em `docs/AVALIACAO.md`.
- **CI:** a cada PR, suíte **reduzida e determinística** (recuperação + citação + classificação de relações, sem LLM) sobre um subconjunto do corpus; suíte completa executada localmente ao fim de cada fase.
- **Baseline v1** (regras + BM25) medido primeiro (Fase 5), depois v2 (RAG híbrido) e v3 (multiagentes).

## Consequências

- (+) Métricas centrais (recuperação, citação) não dependem de LLM — reprodutíveis e baratas.
- (−) Métricas com juiz têm variância; mitigada por calibração humana e temperatura 0.
