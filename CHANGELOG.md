# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico.

## [Não lançado] — Reestruturação SAD-GD

### Adicionado
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
- `instalar.bat`, `start.bat`, `stop.bat` e diagnóstico adaptados ao SAD-GD; IA da v1 passa a usar o Ollama do projeto; caches de IA forçados para dentro do projeto e telemetria de terceiros desativada.
- `app/services/llm.py`: mensagens de erro detalhadas do servidor de IA e filtro de modelos de embedding.
- Especificação v1 (`AGENTS.md`), `ARQUITETURA.md` e `CONFORMIDADE.md` movidos para `docs/legado/`.

### Removido
- Cópia duplicada da especificação (`READ ME — Agente de Inteligência Documental — Contratos e Checklists.md`).
- Fora do Git: 169.698 registros `REMOVIDO` do banco (compactado de 6,6 GB para 1,7 GB; original em `BACKUP\pre-reestruturacao\`), logs rotacionados antigos, `data/app.pid` e `.pytest_cache/`.
- Fora do Git (a pedido do responsável): todos os documentos, trechos, contratos e itens do banco v1 (1,72 GB → 0,11 MB); raiz documental passa a ser `corpus\`.

## [1.0.0] — 2026-10-14

- Aplicação local de inteligência documental para contratos e checklists (ver `docs/legado/`).
