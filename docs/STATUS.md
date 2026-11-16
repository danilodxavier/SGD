# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-16 |
| Fase atual | **Fase 0 — Auditoria do projeto existente** |
| Situação da fase | Relatório entregue — **aguardando aprovação do usuário** |
| Última tarefa concluída | Auditoria completa registrada em `docs/fases/FASE_00.md` |
| Próxima tarefa exata | Após aprovação: (1) commitar `app/services/llm.py`; (2) criar branch+tag `backup/pre-reestruturacao`; (3) executar exclusões aprovadas (E1–E6); (4) iniciar Fase 1 (termo de abertura, requisitos, EAP, riscos, cronograma, backlog) |
| Bloqueios | Decisões D1–D5 de `docs/fases/FASE_00.md` §6; `gh` CLI não instalado e sem autenticação GitHub; repositório sem remoto |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | Aguardando aprovação | `docs/fases/FASE_00.md` |

## Fatos-chave para retomada

- Código existente: app local v1.0.0 (FastAPI + SQLite FTS5 + JS puro), 238 testes verdes.
- Banco local contém **dados reais** de órgão público (6,6 GB, 169.703 registros `REMOVIDO`). Não enviar a serviços externos.
- `AGENTS.md` (escopo antigo, local-only) conflita com o prompt mestre do SAD-GD — ver C1.
- Nenhuma exclusão foi executada.
