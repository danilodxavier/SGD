# ADR-003 — Framework multiagentes: LangGraph

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | RF-15 a RF-20, RNF-05, RNF-08, RNF-11 |

## Contexto

O prompt mestre pede avaliar LangGraph × CrewAI. O sistema precisa de: roteamento condicional (acionar **só** os agentes relevantes), execução paralela de especialistas, um verificador obrigatório antes da resposta, saídas JSON validadas, rastreabilidade por consulta, possibilidade de pausa para intervenção humana e nenhum envio de dados não autorizado.

## Critérios e pontuação (0–5, peso)

| Critério | Peso | LangGraph 1.2 | CrewAI |
|---|---|---|---|
| Controle explícito do fluxo (grafo, arestas condicionais, ordem garantida do verificador) | 5 | 5 | 3 (processos sequencial/hierárquico; o fluxo fica implícito no "manager") |
| Acionamento seletivo e paralelismo (fan-out/fan-in) | 4 | 5 (`Send`, reducers) | 3 |
| Estado tipado e saída estruturada validável | 4 | 5 (estado TypedDict/Pydantic) | 4 (output_pydantic) |
| Persistência / checkpoint / human-in-the-loop | 3 | 5 (checkpointer SQLite, `interrupt`) | 3 |
| Independência de provedor de LLM (usar nossas portas) | 4 | 5 (nós são funções Python comuns) | 3 (acoplado ao LiteLLM) |
| Privacidade (telemetria) | 5 | 5 (sem telemetria própria; LangSmith só se configurado) | 2 (telemetria anônima ativa por padrão; exige `CREWAI_DISABLE_TELEMETRY`) |
| Peso de dependências | 2 | 4 (langgraph + langchain-core) | 2 (puxa LiteLLM, ChromaDB, etc.) |
| Curva de aprendizado / produtividade | 2 | 3 | 5 |
| Compatibilidade verificada com Python 3.15 | 3 | 5 (wheel puro `langgraph-1.2.21`) | não verificado |
| **Total ponderado** (máx. 160) | | **155** | **98** |

## Decisão

Usar **LangGraph** como orquestrador. Os nós chamam as **portas da camada `application`** (LLMPort, RecuperadorPort etc.), não classes de modelo do LangChain — o framework fica restrito à orquestração e pode ser substituído.

Grafo-alvo (detalhado em `docs/agentes/README.md`):

```text
START → cache → roteador ─┬─(F1 simples)──────────────────────────────→ redator_f1 → verificador → relator → END
                          ├─(F1 complexa)→ recuperação → [1–2 especialistas] → verificador → relator → END
                          └─(F2)→ recuperação + linha_do_tempo + precedentes → [2–4 especialistas em paralelo] → verificador → relator → END
```

O checkpointer persiste em SQLite dentro de `data\`.

## Consequências

- (+) Fluxo auditável e testável nó a nó (TDD); verificador impossível de "pular".
- (+) Nenhuma telemetria de terceiros por padrão.
- (−) Mais código de orquestração que o CrewAI; mitigado por nós pequenos e padronizados.
- Risco: mudanças de API do LangGraph → versão fixada em `requirements` e testes de contrato do grafo.
