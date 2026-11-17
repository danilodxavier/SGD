# FASE 08 — Apoio à decisão (F2) e memória de decisões (Sprint S8)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 a 2026-11-17 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aguardando aprovação** |

## 1. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| SAD-080 | **Memória de decisões**: entidade `Decisao` (contexto, decisão, fundamentos, resultado, avaliação positivo/negativo/neutro/pendente) e `Precedente` (lição derivada do resultado: negativo = alerta; pendente = precedente fraco); migração 004 (código, origem do corpus para a política LGPD, consulta de origem, FTS5 `decisoes_fts`); recuperação **híbrida** (BM25 + bge-m3 → RRF → bge-reranker), bônus para decisões do mesmo processo da pergunta e **limiar** contra falso precedente | `app/domain/decisoes.py`, `app/application/decisoes/memoria.py`, `app/infrastructure/sqlite/repositorio_decisoes.py`, `migracoes/004_memoria_decisoes.sql` |
| SAD-080 | **Memória sintética** de 30 decisões (Estado fictício) coerente com o corpus — 2 delas também são documentos (DG-004/2024, DG-011/2025) e ficam ligadas a eles — e **50 perguntas de precedente** (15 validação / 35 teste; 5 sem precedente; pares difíceis com desfechos opostos); importação idempotente com vetores | `scripts/sadgd/gerar_memoria_decisoes.py`, `importar_decisoes.py`, `corpus/sintetico/decisoes/`, `avaliacao/golden_set/precedentes_*.jsonl` |
| SAD-081 | **Recomendação F2 com os 6 elementos de RF-20** (alternativas, riscos, base legal, precedentes, confiança, aviso). Regras determinísticas que nunca inventam: precedentes vêm **só** da memória (o LLM não pode criar precedente); base legal vem das fundamentações verificadas dos pareceres (ou das normas recuperadas), **ordenada pela hierarquia**, e norma revogada vai para `normas_no_historico`; alternativas/riscos ausentes são completados com os dos pareceres; elemento impossível é **declarado** em lacunas; confiança limitada por evidência (sem base legal ≤ 0,5; sem parecer válido ≤ 0,4; frases removidas ≤ 0,6); precedente negativo gera **alerta** | `app/application/decisoes/recomendacao.py`, `especialistas.py` (`relatar_f2`) |
| SAD-081 | **Relator v2** (prompt e schema versionados; a F1 continua no v1): campo `recomendacao`, base legal e precedentes estruturados, aviso como constante | `prompts/relator.v2.md`, `schemas/relator.v2.json` |
| — | **Orquestrador**: o contexto da F2 inclui os precedentes (especialistas e relator os veem como `[P<id>]`) | `orquestrador.py` |
| SAD-082 | **API**: `GET/POST /api/sadgd/decisoes`, `PATCH /api/sadgd/decisoes/{id}/resultado` (registro e avaliação exigem Administrador — o perfil Gestor chega na Fase 9; tudo auditado), `GET /api/sadgd/precedentes`; `/perguntar` devolve `elementos_rf20` | `app/interfaces/api/decisoes.py`, `perguntar.py` |
| — | Ação da Fase 7 aplicada: instrução de `pros`/`contras` como **listas** | `especialistas.py` (`ORDEM_PARECER`) |
| — | **Correção no grafo** (achada nesta fase): contrato/aditivo/relatório que cita lei é `fundamenta`, nunca continuação/ruptura | `app/application/linha_do_tempo/grafo.py` + teste de regressão |
| — | Avaliações: `avaliar_precedentes.py` (ablação), `avaliar_f2.py` com precedentes e RF-20 | `scripts/sadgd/` |

Testes: **454 passando**, cobertura de domínio+aplicação **95%**, ruff limpo, `avaliar.py ci` acima do piso.

## 2. Correção no grafo documental (transparência)

Ao ligar decisões a processos, o contrato de TI 031/2023 aparecia dentro de um "processo" de 39 documentos (chave 129/2022, título do Decreto 93.872). Causa: a regra genérica "documento que se refere a outro anterior" tratava a **Lei 14.133 como antecessora** dos contratos que a citam, unindo contratos distintos a todas as normas federais. Regra nova: documento não normativo que cita ato normativo → `fundamenta` (que não une processos). Efeito: **pureza do agrupamento 0,932 → 0,966**, relações inalteradas (F1-macro 1,00 sintético; 10/10 públicas; 39 relações públicas fortes), mesmas 19 normas revogadas. Permanece um componente temático legítimo de 29 normas federais de licitações (cadeia real de revogações/alterações). O resumo de linha do tempo usado na F2 da Fase 7 estava contaminado nesses casos; a avaliação da Fase 8 já usa o grafo corrigido.

## 3. Resultados

### 3.1 Recuperação de precedentes (RF-19; `avaliacao/execucoes/fase8_precedentes.json`)

| Modo | Val R@1 | Val **R@3** | Val MRR | Teste R@1 | Teste **R@3** | Teste MRR | p50 |
|---|---|---|---|---|---|---|---|
| BM25 | 0,429 | 0,643 | 0,524 | 0,806 | 0,903 | 0,858 | 8 ms |
| Denso (bge-m3) | 0,857 | 1,000 | 0,917 | 1,000 | 1,000 | 1,000 | 25 ms |
| Híbrido (RRF) | 0,571 | 0,786 | 0,699 | 0,839 | 0,968 | 0,903 | 29 ms |
| Híbrido + rerank | 0,929 | 1,000 | 0,964 | 0,968 | 1,000 | 0,984 | 0,6 s |
| **Híbrido + rerank + limiar 0,002** (adotado) | 0,857 | **0,929** | 0,893 | 0,968 | **1,000** (meta ≥ 0,80) | 0,984 | 0,6 s |

- **Falso precedente** (perguntas sem precedente que recebem algum): sem limiar 100%; com limiar **0/1 na validação e 1/4 no teste**.
- **Calibração do limiar** só na validação, com regra fixada antes de olhar o teste: maior valor que mantém R@3 ≥ 0,90 e rejeita a pergunta sem precedente. Um limiar inicial de 0,05, posto sem calibrar, derrubava a validação para 0,43.
- **Ressalva:** perguntas e decisões têm o mesmo autor e a memória é pequena (30 decisões). O 1,00 do denso é otimista. A verificação externa está em 3.2.

### 3.2 F2 ponta a ponta com precedentes (21 perguntas de decisão; Qwen 2.5 7B local)

| Métrica | Fase 7 | **Fase 8** |
|---|---|---|
| Erros / rota F2 | 0 / 1,00 | 0 / 1,00 |
| **RF-20: 6 elementos presentes ou declarados** | — | **1,00** (meta 100%) |
| RF-20: 6 elementos com conteúdo | — | 0,714 |
| — alternativas / riscos / confiança / aviso | 1,00 / 1,00 / — / 1,00 | 1,00 / 1,00 / 1,00 / 1,00 |
| — base legal vigente | — | 0,762 (5 declaradas ausentes; média 1,8 norma) |
| — precedentes | — | 0,952 (1 sem precedente acima do limiar) |
| Schema dos pareceres bruto / reparado | 0,00 / 1,00 | **0,789** / 1,00 |
| Schema do relator | 1,00 (v1) | 1,00 (v2, mais exigente) |
| Recall de documentos citados | 0,746 | 0,794 |
| Confiança média declarada | 0,77 | 0,66 (tetos por evidência) |
| Latência p50 / p95 | 250 s / 348 s | 329 s / 387 s |
| Tokens (entrada / saída) | 17.353 / 2.514 | 18.872 / 2.538 |

**Pertinência dos precedentes nas 21 perguntas F2 (revisão manual; nenhuma pergunta F2 foi usada para calibrar):** o primeiro precedente é pertinente em **13/21** (inclui V031, sem precedente, corretamente vazio). Exemplos: aditivo da obra → DG-003/2025 e DG-019/2024; prorrogação da vigilância → DG-011/2025; empresa de limpeza → DG-004/2024 (negativo, com alerta). Em **8/21** o primeiro é fraco ou sem relação, sobretudo em "divergência de valor antes de autorizar pagamento", que deveria trazer a glosa DG-013/2024. São perguntas longas, com número de contrato, mais difíceis que as do conjunto de precedentes. O limiar não as barra porque o reranker dá nota acima de 0,002 a decisões do mesmo tema geral. Mitigação atual: cada precedente leva pontuação e lição, e o prompt manda tratá-lo como informação, não modelo. Ação na Fase 10: perguntas de precedente mais realistas e um limiar relativo, ou exigir o mesmo processo ou tema.

**Latência:** cada ciclo da avaliação recarrega na CPU os modelos da memória (≈ 25 s na etapa de contexto); na API eles ficam carregados. O resto do aumento vem dos tokens a mais dos precedentes no contexto (+9%). Segue como R15 para a Fase 10.

## 4. Critérios de aceite (backlog)

| Item | Critério | Resultado |
|---|---|---|
| SAD-080 | Recall@3 ≥ 0,80 em precedentes | ✅ 1,00 no teste (0,929 na validação), com limiar contra falso precedente |
| SAD-081 | 6 elementos em 100% das respostas F2 | ✅ 100% presentes ou declarados explicitamente; 71% com conteúdo nos 6 |
| RF-20 | Aviso "o sistema sugere" | ✅ 100% (constante no schema v2) |
| RF-14 | Norma revogada não fundamenta | ✅ separada em `normas_no_historico` (teste) |

## 5. Pendências

1. Latência da F2 (p50 329 s) e pertinência dos precedentes em perguntas F2 longas (13/21): Fase 10.
2. Perfil **Gestor** para registrar decisões: Fase 9 (RF-23); por ora só Administrador.
3. Faithfulness com LLM-juiz (Fase 10); revisão humana do golden set (desde a Fase 5); Kanban depende do `gh`.

## 6. Retrospectiva

- **Bem:** tirar do LLM o que pode ser determinístico (precedentes, base legal, hierarquia, vigência) garantiu os 6 elementos sem inventar nada; ligar decisões a processos revelou um defeito real do grafo.
- **A melhorar:** o limiar inicial sem calibração mostrou de novo que qualquer parâmetro precisa de regra de calibração escrita antes de olhar o teste.
- **Ação:** Fase 9 — MVP (chat com fontes, upload, linha do tempo visual, painel de pareceres e precedentes, perfis com Gestor).

## 7. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
