# Metodologias e técnicas aplicadas — SAD-GD

| Metodologia / técnica | Onde foi aplicada | Evidência | Fase |
|---|---|---|---|
| Auditoria de código legado (inventário, testes, análise de dados) | Avaliação do app v1 | `docs/fases/FASE_00.md` | 0 |
| Gestão de configuração: branch/tag de backup antes de mudança destrutiva | Reestruturação | branch `backup/pre-reestruturacao`, tag `v1.0.0-pre-reestruturacao` | 0 |
| Conventional Commits | Todos os commits a partir da Fase 0 | `git log` | 0– |
| ADR (Architecture Decision Records — Nygard) | Decisões estruturais | `docs/adr/` | 0– |
| PMBOK 7 — Termo de abertura | Iniciação | `docs/projeto/TERMO_DE_ABERTURA.md` | 1 |
| PMBOK 7 — Registro de partes interessadas e personas | Iniciação | `docs/projeto/PARTES_INTERESSADAS.md` | 1 |
| PMBOK 7 — EAP orientada a entregas + dicionário | Planejamento | `docs/projeto/EAP.md` | 1 |
| PMBOK 7 — Matriz de riscos P×I com respostas | Planejamento | `docs/projeto/RISCOS.md` | 1 |
| Cronograma com caminho crítico (Gantt) | Planejamento | `docs/projeto/CRONOGRAMA.md` | 1 |
| Engenharia de requisitos: RF/RNF, MoSCoW, critérios verificáveis | Escopo | `docs/projeto/ESCOPO_E_REQUISITOS.md` | 1 |
| Scrum: fase = sprint, DoR/DoD, revisão = aprovação do responsável | Todo o projeto | `docs/projeto/BACKLOG.md`, `docs/fases/` | 1– |
| Kanban (GitHub Projects) | Gestão do fluxo | `scripts/github/criar_backlog.ps1` (publicação pendente) | 1– |
| Objetivos SMART | TAP | `TERMO_DE_ABERTURA.md` §2 | 1 |

Planejadas: C4, Clean Architecture/SOLID, TDD, GitHub Flow, CI/CD, CRISP-DM/LLMOps, avaliação RAG (RAGAS/DeepEval), métricas de IR (Precision/Recall@k, MRR, nDCG).
