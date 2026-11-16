# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-16 |
| Fase atual | **Fase 2 — Arquitetura** |
| Situação da fase | Entregáveis concluídos — **aguardando aprovação do responsável** |
| Última tarefa concluída | ADRs 003–013, C4, modelo de dados, especificação dos 12 agentes, rastreabilidade (`docs/fases/FASE_02.md`) |
| Próxima tarefa exata | Após "Aprovado, siga para a Fase 3": (1) marcar ADRs 003–013 como "Aceito"; (2) instalar Ollama com `OLLAMA_MODELS=<projeto>\modelos\ollama`; (3) criar `requirements-ia.txt`/`requirements-dev.txt`/`constraints.txt` e validar `torch.cuda.is_available()`; (4) criar `app/domain`, `app/application/portas.py`, migrações do `sadgd.db` (SAD-030/031); (5) CI no GitHub Actions (SAD-032) — depende do `gh` |
| Bloqueios | `gh` não instalado/autenticado (SAD-002/003/032) |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_00.md` |
| 1 — Iniciação e planejamento | ✅ Aprovada em 2026-11-16 (com exclusão dos documentos do banco v1) | `docs/fases/FASE_01.md` |
| 2 — Arquitetura | Aguardando aprovação | `docs/fases/FASE_02.md` |

## Fatos-chave para retomada

- Diretrizes: **gratuito, máquina local, VPS em segundo plano, tudo em subpastas do projeto** (ADR-001).
- Stack proposta: Python 3.15 · FastAPI · LangGraph · SQLite (FTS5 + sqlite-vec + grafo) · bge-m3 + bge-reranker-v2-m3 · Ollama (Qwen2.5 7B inicial) · Tesseract · Arize Phoenix · RAGAS · frontend HTML/JS.
- Banco v1 `documents.db` **zerado** (0,11 MB; só usuários, checklist e configurações). Raiz documental = `<projeto>\corpus`. Banco original em `BACKUP\pre-reestruturacao\`.
- Prompts versionados: `app/application/agentes/prompts/`; schemas: `app/application/agentes/schemas/`.
- Restauração do código v1: branch `backup/pre-reestruturacao`, tag `v1.0.0-pre-reestruturacao`.
