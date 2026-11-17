# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico.

## [Não lançado] — Reestruturação SAD-GD

### Adicionado
- Fase 7 (multiagentes): roteador por regras, verificador de fontes determinístico (integrado ao ResponderF1), especialistas com JSON validado e reparo de forma, relator F2, orquestrador LangGraph com fan-out paralelo, anonimização LGPD reversível e política de envio a provedores remotos, auditoria de consultas (hash da pergunta), resumo da linha do tempo para a F2, API `POST /api/sadgd/perguntar`, scripts `avaliar_roteador.py`, `avaliar_anonimizacao.py`, `avaliar_f2.py` e flag `--verificador` em `avaliar_respostas.py`; Qwen 2.5 3B avaliado.
- Fase 6 (linha do tempo): extração de referências, classificador de relações por regras (notas de compilação, revogação parcial, retomada), detecção de contradições, agrupamento, vigência pelo grafo, respostas de conflito determinísticas, API `/api/sadgd/processos` e `/api/sadgd/linha-do-tempo`, scripts de construção e avaliação do grafo; 21 novos testes.
- Fase 5 (RAG): recuperação híbrida com RRF, filtro de vigência e reranker; ResponderF1 com citações e salvaguardas; golden set de 177 perguntas validadas; suíte de avaliação em estágios (recuperação, respostas, relatório, CI); baseline v1 × v2; benchmark Qwen 2.5 7B × Llama 3.1 8B; 31 novos testes.
- Fase 4 (ingestão): corpus público (69 atos oficiais) e sintético (117 documentos, 27 processos, 99 relações, gabarito); chunking estrutural jurídico; extrator de HTML legal com detecção de texto tachado; metadados por regras; indexação híbrida incremental (FTS5 + sqlite-vec + bge-m3) com parada limpa e retomada; scripts de avaliação (chunking, metadados, OCR); migração 003; 53 novos testes.
- Fase 3 (infraestrutura): camadas `app/domain`, `app/application/portas.py`, `app/infrastructure` (SQLite + sqlite-vec com migrações, adaptador LLM OpenAI-compatível, tracer SQLite); banco único `sadgd.db`; Ollama e Tesseract portáteis (`scripts/sadgd/*.ps1`); dependências em camadas e `constraints.txt`; `pyproject.toml` (pytest, coverage, ruff); CI no GitHub Actions; diagnóstico SAD-GD; 46 novos testes.
- Fase 2 (arquitetura): `docs/arquitetura/C4.md`, `docs/arquitetura/MODELO_DE_DADOS.md`, ADR-003 a ADR-013, `docs/agentes/README.md`, `docs/projeto/RASTREABILIDADE.md`.
- Prompts versionados de 12 agentes + regras comuns (`app/application/agentes/prompts/`) e 5 schemas JSON (`app/application/agentes/schemas/`).
- `tests/test_agentes_specs.py` (consistência prompts × schemas × catálogo).
- Backlog: item SAD-055 (benchmark de LLMs na Fase 5).
- `CLAUDE.md` com prompt mestre do SAD-GD e decisões vigentes.
- Documentação de planejamento (Fase 1): termo de abertura, partes interessadas, requisitos, EAP, cronograma, riscos e backlog (`docs/projeto/`).
- ADR-001 (execução local, ferramentas gratuitas, tudo em subpastas) e ADR-002 (corpus acadêmico).
- `docs/STATUS.md`, `CONTINUIDADE.md`, `MODELOS_IA.md`, `METODOLOGIAS.md`, `HABILIDADES.md`, `AVALIACAO.md`.
- `scripts/github/criar_backlog.ps1` para publicar o backlog no GitHub Projects.
- Relatório de auditoria `docs/fases/FASE_00.md`.

### Alterado
- Gabarito sintético revisado (99 → 103 relações) via `gerar_corpus_sintetico.py --somente-gabarito`; métrica de alucinação numérica normaliza datas por extenso e citações de atos.
- `LLMPort.chat` aceita `json_livre`; CI executa a avaliação reduzida (`avaliar.py ci`).
- OCR `auto` passa a priorizar o Tesseract (CER 0,09% contra 0,52%). Embeddings em float32 e carga sequencial de pesos (`HF_DEACTIVATE_ASYNC_LOAD`).
- `instalar.bat`, `start.bat`, `stop.bat` e diagnóstico adaptados ao SAD-GD; IA da v1 passa a usar o Ollama do projeto; caches de IA forçados para dentro do projeto e telemetria de terceiros desativada.
- `app/services/llm.py`: mensagens de erro detalhadas do servidor de IA e filtro de modelos de embedding.
- Especificação v1 (`AGENTS.md`), `ARQUITETURA.md` e `CONFORMIDADE.md` movidos para `docs/legado/`.

### Removido
- Cópia duplicada da especificação (`READ ME — Agente de Inteligência Documental — Contratos e Checklists.md`).
- Fora do Git: 169.698 registros `REMOVIDO` do banco (compactado de 6,6 GB para 1,7 GB; original em `BACKUP\pre-reestruturacao\`), logs rotacionados antigos, `data/app.pid` e `.pytest_cache/`.
- Fora do Git (a pedido do responsável): todos os documentos, trechos, contratos e itens do banco v1 (1,72 GB → 0,11 MB); raiz documental passa a ser `corpus\`.

## [1.0.0] — 2026-10-14

- Aplicação local de inteligência documental para contratos e checklists (ver `docs/legado/`).
