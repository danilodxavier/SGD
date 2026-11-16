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

| Modelo C4 (contexto, contêiner, componente) + diagrama de sequência e implantação | Arquitetura | `docs/arquitetura/C4.md` | 2 |
| Matriz de decisão ponderada (critérios × pesos) | Escolha LangGraph × CrewAI | `docs/adr/ADR-003-framework-multiagentes.md` | 2 |
| Decisões baseadas em evidência (spikes: `nvidia-smi`, `pip --dry-run`, teste de extensão SQLite) | ADRs 004, 006, 010 | `docs/fases/FASE_02.md` §2 | 2 |
| Clean Architecture, SOLID (ISP/DIP com portas), strangler fig | Estrutura-alvo do código | `docs/adr/ADR-013-clean-architecture-e-migracao.md` | 2 |
| Modelagem ER + grafo de propriedades em tabelas | Dados e linha do tempo | `docs/arquitetura/MODELO_DE_DADOS.md` | 2 |
| Engenharia de prompt versionada + saída estruturada (JSON Schema 2020-12) | Agentes | `app/application/agentes/prompts/`, `schemas/` | 2 |
| Testes de contrato de especificação | Prompts × schemas × catálogo | `tests/test_agentes_specs.py` | 2 |
| Matriz de rastreabilidade bidirecional | Requisitos → ADR → componente → teste | `docs/projeto/RASTREABILIDADE.md` | 2 |
| Planejamento de avaliação (CRISP-DM/LLMOps): golden set, split validação/teste, juiz calibrado (κ de Cohen) | Avaliação | `docs/adr/ADR-011-avaliacao.md` | 2 |
| TDD (testes escritos antes da implementação) | Regras de domínio: hierarquia, vigência, relações, política de envio externo | `tests/sadgd/test_dominio.py` | 3 |
| Clean Architecture verificada por análise estática (AST) | Regra de dependência entre camadas | `tests/sadgd/test_arquitetura.py` | 3 |
| Migrações de banco versionadas e transacionais | Esquema SAD-GD | `app/infrastructure/sqlite/migracoes/` | 3 |
| Testes com dublês (servidor HTTP simulado) | Adaptador de LLM | `tests/sadgd/test_llm_adapter.py` | 3 |
| CI/CD (GitHub Actions): lint, testes, portão de cobertura, varredura de segredos | Pipeline | `.github/workflows/ci.yml` | 3 |
| Análise estática (ruff: pycodestyle, pyflakes, isort, bugbear, pyupgrade, bandit, simplify) | Código SAD-GD | `pyproject.toml` | 3 |
| Gestão de dependências reprodutível (camadas + constraints) — LLMOps | Ambiente | `requirements-*.txt`, `constraints.txt` | 3 |
| Infraestrutura como código (scripts idempotentes) | Ollama, Tesseract, instalação | `scripts/sadgd/*.ps1`, `instalar.bat` | 3 |

| CRISP-DM — entendimento e preparação de dados: corpus com proveniência (manifesto, SHA-256, licença) | Corpus público | `corpus/MANIFESTO.csv` | 4 |
| Geração de dados sintéticos com gabarito e autoverificação (semente fixa, reprodutível) | Corpus sintético | `scripts/sadgd/gerar_corpus_sintetico.py` | 4 |
| Validação cruzada sintético × real (leis com estrutura conhecida) para evitar métrica otimista | Chunking | `scripts/sadgd/avaliar_chunking.py` | 4 |
| Avaliação de OCR por CER (distância de Levenshtein) | OCR | `scripts/sadgd/avaliar_ocr.py` | 4 |
| TDD com casos reais de regressão (art. 56 da Lei 9.784; Lei 12.462) | Chunking e metadados | `tests/sadgd/test_chunking.py`, `test_metadados.py` | 4 |
| Benchmark de configuração (fp16 × fp32 × atenção) antes de decidir | Embeddings | `docs/fases/FASE_04.md` §5 | 4 |
| Processamento incremental idempotente com retomada (checkpoint por lote) | Indexação | `app/application/ingestao/indexador.py` | 4 |

Planejadas: GitHub Flow, RAGAS, métricas de IR (Precision/Recall@k, MRR, nDCG).
