# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico.

## [Não lançado] — Reestruturação SAD-GD

### Adicionado
- `CLAUDE.md` com prompt mestre do SAD-GD e decisões vigentes.
- Documentação de planejamento (Fase 1): termo de abertura, partes interessadas, requisitos, EAP, cronograma, riscos e backlog (`docs/projeto/`).
- ADR-001 (execução local, ferramentas gratuitas, tudo em subpastas) e ADR-002 (corpus acadêmico).
- `docs/STATUS.md`, `CONTINUIDADE.md`, `MODELOS_IA.md`, `METODOLOGIAS.md`, `HABILIDADES.md`, `AVALIACAO.md`.
- `scripts/github/criar_backlog.ps1` para publicar o backlog no GitHub Projects.
- Relatório de auditoria `docs/fases/FASE_00.md`.

### Alterado
- `app/services/llm.py`: mensagens de erro detalhadas do servidor de IA e filtro de modelos de embedding.
- Especificação v1 (`AGENTS.md`), `ARQUITETURA.md` e `CONFORMIDADE.md` movidos para `docs/legado/`.

### Removido
- Cópia duplicada da especificação (`READ ME — Agente de Inteligência Documental — Contratos e Checklists.md`).
- Fora do Git: 169.698 registros `REMOVIDO` do banco (compactado de 6,6 GB para 1,7 GB; original em `BACKUP\pre-reestruturacao\`), logs rotacionados antigos, `data/app.pid` e `.pytest_cache/`.

## [1.0.0] — 2026-10-14

- Aplicação local de inteligência documental para contratos e checklists (ver `docs/legado/`).
