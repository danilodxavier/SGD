# FASE 07 — Sistema multiagentes (Sprint S7)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | ✅ **Aprovada** em 2026-11-16 |

## 1. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| SAD-070 | **Roteador** por regras: intenções (decisão, história, análise) → rota `F1_simples`, `F1_complexa` ou `F2`; matriz de pontuação escolhe os especialistas (F2: `gestor_publico` + até 3; F1 complexa: até 2), filtros por contrato. Nunca aciona todos os agentes | `app/application/agentes/roteador.py` |
| SAD-071 | **Especialistas** com prompt versionado e saída JSON validada por schema; reparo apenas de forma (tipos, listas, enums, citações fora do contexto); afirmação sem citação válida ou com número/data sem suporte é descartada; saída cortada → nova tentativa concisa com +50% de tokens; falha persistente → parecer inválido, ignorado pelo relator (o grafo não cai) | `especialistas.py` |
| SAD-072 | **Verificador de fontes** determinístico (número/data/valor sem suporte, vigência contrária à fonte, afirmação contraditória), integrado ao ResponderF1: nova tentativa com o feedback → remoção das frases sem suporte → ausência | `verificador.py`, `app/application/respostas/f1.py` |
| SAD-073 | **Relator** F2: consensos, divergências, alternativas, riscos, base legal, precedentes, lacunas; aviso "O sistema sugere; a decisão cabe à gestão." sempre forçado; frases sem suporte removidas (confiança ≤ 0,6) | `especialistas.py` (`relatar_f2`) |
| — | **Orquestrador LangGraph**: `rotear → recuperar → (responder_f1 | contexto_f2 → especialista×N via Send → relator)`, span por nó, checkpointer opcional; contexto da F2 com o **resumo da linha do tempo** do grafo documental | `orquestrador.py`, `repositorio_grafo.py` (`resumo`) |
| SAD-074 | **Anonimização LGPD** reversível (CPF, e-mail, telefone, matrícula, nomes de pessoas físicas) e **política de envio**: provedor remoto bloqueado com corpus real; com corpus acadêmico, texto pseudonimizado e resposta restaurada | `app/application/anonimizacao.py`, `politica_llm.py` |
| SAD-075 | **Auditoria** por consulta: hash SHA-256 da pergunta (nunca o texto), rota, agentes, classificação, confiança, tokens, latência, fontes aprovadas, pareceres com validade; spans ligados à consulta | `app/infrastructure/sqlite/auditoria.py` |
| SAD-076 | **API** `POST /api/sadgd/perguntar` (login; 1 consulta por vez; recuperação na CPU por padrão para deixar a GPU ao LLM; falha → 503 auditado) | `app/interfaces/api/perguntar.py` |
| — | Avaliações: `avaliar_roteador.py`, `avaliar_anonimizacao.py`, `avaliar_f2.py`, `avaliar_respostas.py --verificador` | `scripts/sadgd/` |
| — | Qwen 2.5 3B baixado (autorizado) e avaliado | `docs/MODELOS_IA.md` |

Testes: 437 passando, cobertura de domínio+aplicação **95%**, ruff limpo, `avaliar.py ci` acima do piso.

## 2. Resultados

### 2.1 Roteador (golden set, 177 perguntas)

| Conjunto | F1 × F2 | 3 rotas | Agentes — precisão | Agentes — recall |
|---|---|---|---|---|
| Validação (53) | **1,00** | 0,925 | 0,857 | 0,667 |
| Teste (124) | **1,00** | **0,935** (meta ≥ 0,90) | 0,974 | 0,841 |

Erros só entre F1 simples e complexa (efeito: 0–2 especialistas a mais/menos, nunca F2 indevida). Com regras atingindo a meta, o LLM pequeno ficou dispensado do roteamento (custo zero de tokens).

### 2.2 F1 v2.2 (verificador) — conjunto de TESTE, mesmas métricas da v2.1

| Métrica | v2.1 | **v2.2** |
|---|---|---|
| Exatidão | 0,843 | **0,843** |
| **Alucinação numérica** | 3,1% | **0,0%** (meta ≤ 5%) |
| Detecção de conflito / recusa correta | 1,00 / 1,00 | 1,00 / 1,00 |
| Classificação correta | 0,954 | 0,927 |
| Falsa recusa | 3,0% | 5,9% |
| Cita fonte esperada / precisão das citações | 0,891 / 0,794 | 0,861 / 0,791 |
| Latência p50 / p95 | 14,4 s / 29,2 s | 14,6 s / 29,0 s |

As únicas respostas alteradas foram **T100, T109 e T124** — exatamente as 3 datas erradas da v2.1: o verificador detectou a data sem suporte, pediu nova tentativa e, sem resposta sustentada, devolveu "Não localizei essa informação nos documentos disponibilizados.". Troca deliberada: em apoio à alta gestão, uma recusa é preferível a uma data errada (as 3 já contavam como não exatas).

### 2.3 F2 ponta a ponta (21 perguntas de decisão; validação + teste; Qwen 2.5 7B local)

| Métrica | Resultado |
|---|---|
| Rota F2 / erros | **1,00** / 0 |
| Seleção de agentes — precisão / recall | 0,942 / 0,790 |
| Pareceres por consulta | 2,48 |
| Schema dos pareceres — bruto / após reparo de forma | 0,00 / **1,00** |
| Schema do relator | **1,00** |
| Com alternativas / com riscos / com aviso | **1,00 / 1,00 / 1,00** |
| Recall de documentos citados (vs. fontes esperadas) / precisão | 0,746 / 0,445 |
| Afirmações descartadas pelo verificador por consulta | 0,24 |
| Confiança média declarada | 0,77 |
| Latência p50 / p95 | **250 s / 348 s** |
| Tokens por consulta (entrada / saída) | 17.353 / 2.514 |

Análise:
- **Schema bruto 0,00:** os erros são de forma — o modelo devolve `pros`/`contras` como texto em vez de lista (a instrução de ordem dos campos não deixa isso explícito). O reparo de forma corrige 100% sem alterar conteúdo. Ação na Fase 10: explicitar `"pros": ["…"]` no prompt e medir de novo.
- **Saída cortada:** 25 das 52 chamadas a especialistas (48%) precisaram da nova tentativa (JSON cortado pelo limite de tokens) — principal causa da latência. Antes da correção, a F2 falhava em 4/4 consultas.
- **Precisão de documentos 0,445:** os especialistas também citam documentos relevantes que não estão na lista de fontes esperadas (ex.: a lei de licitações numa pergunta sobre aditivo); é um indicador conservador, sem juiz humano.
- **Latência:** inviável para uso interativo no hardware local (≈ 4 min). As gerações dos especialistas são serializadas pelo Ollama (6 GB de GPU), então o fan-out paralelo não reduz o tempo. Registrado como risco R15; alvo da Fase 10.

### 2.4 Anonimização (RF-25)

| Métrica | Resultado |
|---|---|
| Recall de nomes de pessoas físicas (corpus sintético, 160 ocorrências) | **1,00** (meta ≥ 0,90) |
| Recall de CPF | **1,00** (3/3) |
| Corpus público — mascarados como pessoa (revisão manual, top 40) | signatários reais (Paulo Guedes, Wagner de Campos Rosário, Luís Inácio Lucena Adams…) — corretos; 1 truncamento ("Carlos Sant", de Sant'Anna) |
| Pessoas jurídicas, órgãos, CNPJ e leis | preservados (teste) |

## 3. Incidentes e correções (transparência)

| Ocorrência | Tratamento |
|---|---|
| Primeira execução da F2: 4/4 consultas falharam com "O modelo não retornou JSON válido" | Diagnóstico com a saída bruta: `finish_reason=length` (JSON cortado em 800 tokens). Limites de concisão nos prompts, nova tentativa com +50% de tokens, degradação graciosa; 2 testes de regressão |
| Relator inválido por enum acentuado ("médio") | Normalização de forma (minúsculas, sem acento) em riscos |
| Nomes atravessando quebra de linha ("Paulo Guedes\nEste Decreto") e conector maiúsculo ("Carlos De Souza") | Sobrenomes só na mesma linha; conectores só contam se seguidos de sobrenome; testes |
| Avaliação da F2 em segundo plano interrompida pelo Claude Code por falta de memória (2/21 feitos) | Retomada em primeiro plano, em ciclos de 4 min (retomável, sem perda) |
| Tarefa antiga da Fase 6 travada (Ollama iniciado com `| Out-Null`) | Encerrada; regra já registrada no `CLAUDE.md` |

## 4. Critérios de aceite (backlog)

| Item | Critério | Resultado |
|---|---|---|
| SAD-070 | Acurácia de roteamento ≥ 0,90 | ✅ 0,935 (3 rotas, teste); 1,00 F1×F2 |
| SAD-071 | 100% das saídas válidas no schema | ✅ após reparo de forma (bruto 0% — ação na Fase 10) |
| SAD-072 | Alucinação ≤ 5% | ✅ 0,0% (numérica, teste) |
| SAD-073 | Consensos/divergências explícitos | ✅ schema do relator 1,00; alternativas, riscos e aviso em 100% |
| SAD-074 | 100% CPF/e-mail mascarados; recall nomes PF ≥ 0,90 | ✅ CPF 1,00; nomes 1,00 (sem e-mails no corpus sintético; coberto por teste) |
| SAD-075 | Registro por consulta sem texto integral | ✅ só hash SHA-256 (teste verifica) |

## 5. Pendências

1. Latência da F2 (p50 250 s) — Fase 10: especialistas no Qwen 2.5 3B, contexto menor, prompt com listas explícitas, cache semântico.
2. Faithfulness com LLM-juiz calibrado (Fase 10).
3. Revisão humana do golden set (desde a Fase 5).
4. Kanban no GitHub Projects depende do `gh`.

## 6. Retrospectiva

- **Bem:** o verificador determinístico zerou a alucinação numérica sem custo de LLM; o diagnóstico pela saída bruta achou a causa real da falha da F2 (corte por tokens), em vez de culpar o modelo.
- **A melhorar:** a avaliação da F2 levou ≈ 1h40 — com RAM de 1–2 GB livres, só ciclos em primeiro plano são confiáveis.
- **Ação:** Fase 8 — memória de decisões (precedentes) e recomendações F2 com alternativas, riscos e confiança.

## 7. Aprovação

- [x] Aprovado pelo responsável em 2026-11-16 ("aprovada siga para a fase 8")
