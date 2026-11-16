# FASE 02 — Arquitetura (Sprint S2)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aguardando aprovação** |

## 1. Planejamento da sprint

Itens do backlog: SAD-010 a SAD-021. Objetivo: definir a arquitetura-alvo verificável (C4), registrar as decisões de stack em ADRs com evidências levantadas na própria máquina, modelar dados e grafo documental e especificar os agentes (prompts versionados + schemas).

## 2. Evidências levantadas na máquina (2026-11-16)

| Verificação | Resultado | Impacto |
|---|---|---|
| `nvidia-smi` | GTX 1660 SUPER, **6.144 MiB**, driver 595.95 | LLM local limitado a 7–8B Q4 (ADR-004) |
| Modelos locais | LM Studio com `Qwen2.5-7B-Instruct-Q4_K_M` (4,36 GB; há uma cópia duplicada "- Copia.gguf" fora do projeto); Ollama ausente | Ollama a instalar na Fase 3 com modelos em `modelos\ollama` |
| Docker / WSL | Docker Desktop e WSL (Ubuntu) instalados | Disponíveis, mas **não obrigatórios** (ADR-006/009) |
| `py -3.13` | **Quebrado** (`C:\Python313\python.exe` inexistente) | Python 3.13 descartado como base (ADR-010) |
| `pip install --dry-run` no Python 3.15 | 205 pacotes resolvidos com **wheels cp315** (torch 2.15, sentence-transformers 6.3, langgraph 1.2.21, sqlite-vec 0.1.9, ragas 0.3.1, arize-phoenix 21.0) — exceto `pyyaml` e `zstandard` (sdist) | Risco R06 rebaixado; manter 3.15 (ADR-010) |
| SQLite do Python | 3.53.4 com `enable_load_extension` funcional | sqlite-vec viável (ADR-006) |
| Validação de schemas | `jsonschema` (instalação temporária em `data\cache`, removida) — Draft 2020-12 válido | `tests/test_agentes_specs.py`: 21 passed |

## 3. Entregáveis

| Item | Entregável |
|---|---|
| SAD-010 | `docs/arquitetura/C4.md` — contexto, contêineres, componentes, sequência de consulta e implantação local |
| SAD-011 | `docs/adr/ADR-003-framework-multiagentes.md` — **LangGraph** (155 × 98 pontos sobre CrewAI) |
| SAD-012 | `docs/adr/ADR-004-llms-e-roteamento.md` — `LLMPort`, Ollama padrão, free tier só no corpus acadêmico, roteamento por custo; benchmark empírico movido para SAD-055 (Fase 5, sobre o conjunto de validação) |
| SAD-013 | `docs/adr/ADR-005-embeddings-e-reranker.md` — bge-m3 + bge-reranker-v2-m3 + BM25, fusão RRF |
| SAD-014 | `docs/adr/ADR-006-armazenamento-vetorial-e-grafo.md` — SQLite único com FTS5 + **sqlite-vec** + grafo em tabelas; LanceDB como plano B |
| SAD-015 | `docs/adr/ADR-007-leitura-e-ocr.md` — extratores v1 + pypdfium2; **Tesseract** portátil; PyMuPDF evitado por AGPL |
| SAD-016 | `docs/adr/ADR-008-frontend.md` — HTML/CSS/JS servido pelo FastAPI (Next.js/Vercel adiados por ADR-001) |
| SAD-017 | `docs/adr/ADR-009-observabilidade.md` — tabela própria de métricas + **Arize Phoenix** local (Langfuse exige Docker multi-serviço ou nuvem) |
| SAD-018 | `docs/adr/ADR-010-versao-python.md` — Python 3.15, dependências em camadas e `constraints.txt` |
| — | `docs/adr/ADR-011-avaliacao.md` — métricas determinísticas + RAGAS com juiz calibrado; formato do golden set |
| — | `docs/adr/ADR-012-abordagem-de-aprendizado.md` — RAG + prompts + few-shot; ajuste fino só do reranker com portão na Fase 5 |
| — | `docs/adr/ADR-013-clean-architecture-e-migracao.md` — camadas, portas, strangler fig, TDD |
| SAD-019 | `docs/arquitetura/MODELO_DE_DADOS.md` — ER, grafo, 8 relações + 2 auxiliares, regras de hierarquia/vigência, LGPD |
| SAD-020 | `docs/agentes/README.md` (catálogo, grafo, matriz de acionamento, contrato de saída, métricas); 13 prompts em `app/application/agentes/prompts/` (12 agentes + regras comuns); 5 schemas em `app/application/agentes/schemas/` |
| SAD-021 | `docs/projeto/RASTREABILIDADE.md` |
| Teste | `tests/test_agentes_specs.py` — consistência prompts × schemas × catálogo |

## 4. Critérios de aceite

| Critério (prompt mestre §8, Fase 2) | Situação |
|---|---|
| Diagramas C4 | ✅ 3 níveis + sequência + implantação (Mermaid) |
| Escolha de stack e frameworks em ADRs | ✅ ADR-003 a ADR-013 |
| Modelagem de dados e do grafo documental | ✅ |
| Especificação dos agentes (prompt versionado, escopo, saída JSON, critérios de acionamento) | ✅ 12 agentes (6 pedidos + 4 de orquestração + 2 propostos com justificativa) |
| LangGraph × CrewAI avaliado em ADR | ✅ |
| Decisão sobre ajuste fino registrada | ✅ ADR-012 |

## 5. Desvios conscientes da stack sugerida (todos justificados por ADR-001/002)

| Sugerido no prompt mestre | Decidido | ADR |
|---|---|---|
| VPS Oracle + Docker | Máquina local, sem Docker obrigatório | 001 |
| Next.js na Vercel | HTML/CSS/JS servido pelo FastAPI | 008 |
| Qdrant / Supabase / Neon | SQLite + sqlite-vec | 006 |
| Langfuse | Tabela própria + Arize Phoenix local | 009 |
| PyMuPDF | pypdfium2 (licença permissiva); PyMuPDF opcional | 007 |
| RAGAS e/ou DeepEval | RAGAS + métricas determinísticas próprias | 011 |

## 6. Pendências para o responsável

1. Aprovar os ADRs 003–013 (status "Proposto" → "Aceito").
2. GitHub (`gh`) ainda não instalado — necessário para a Fase 3 (CI, Projects).
3. Opcional: apagar a cópia duplicada do modelo `Qwen2.5-7B-Instruct-Q4_K_M - Copia.gguf` (4,36 GB) em `%USERPROFILE%\.lmstudio\models` — fora do projeto; não foi tocada.

## 7. Retrospectiva

- **Bem:** decisões baseadas em evidências coletadas na máquina (GPU, wheels, SQLite), não em suposições; o risco R06 foi rebaixado com dados.
- **A melhorar:** a comparação empírica de LLMs depende do golden set; foi replanejada para a Fase 5, em vez de um benchmark fraco agora.
- **Ação:** Fase 3 começa pela instalação do Ollama e pela validação de CUDA no torch (maiores incertezas restantes).

## 8. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
