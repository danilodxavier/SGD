# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-16 |
| Fase atual | **Fase 1 — Iniciação e planejamento** |
| Situação da fase | Entregáveis concluídos — **aguardando aprovação do responsável** |
| Última tarefa concluída | Artefatos da Fase 1 (`docs/fases/FASE_01.md`) e commit |
| Próxima tarefa exata | Após "Aprovado, siga para a Fase 2": criar `docs/arquitetura/C4.md` (SAD-010) e iniciar os ADRs 003+ (SAD-011 a SAD-018), começando pelo benchmark rápido de LLMs locais (SAD-012) |
| Bloqueios | `gh` não instalado/autenticado (SAD-002/003); data-limite acadêmica não confirmada |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_00.md` |
| 1 — Iniciação e planejamento | Aguardando aprovação | `docs/fases/FASE_01.md` |

## Fatos-chave para retomada

- Diretrizes do responsável: **gratuito, máquina local, VPS em segundo plano, tudo em subpastas do projeto** (ADR-001).
- Avaliação e demonstração usam corpus público/sintético; dados reais só locais (ADR-002).
- Código v1 (FastAPI + SQLite FTS5 + JS puro) mantido; 238 testes verdes.
- Banco v1 compactado (1,72 GB); original em `BACKUP\pre-reestruturacao\`.
- Restauração: branch `backup/pre-reestruturacao`, tag `v1.0.0-pre-reestruturacao`.
