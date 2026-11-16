# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-16 |
| Fase atual | **Fase 3 — Infraestrutura local** |
| Situação da fase | Entregáveis concluídos — **aguardando aprovação do responsável** |
| Última tarefa concluída | Ambiente IA local (torch CUDA, Ollama, Tesseract, Phoenix), camadas domain/application/infrastructure, banco único `sadgd.db`, CI, diagnóstico (`docs/fases/FASE_03.md`) |
| Próxima tarefa exata | Após "Aprovado, siga para a Fase 4": (1) SAD-040 coletar corpus público com `corpus\MANIFESTO.csv`; (2) SAD-041 gerador do corpus sintético com gabarito; (3) SAD-043 chunking estrutural jurídico com TDD em `app/application/ingestao/`; (4) SAD-042 OCR Tesseract (CER); (5) SAD-044 metadados; (6) SAD-045 embeddings bge-m3 + `trechos_vec` incremental |
| Bloqueios | `gh` não instalado/autenticado (SAD-002/003; CI no GitHub) |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_00.md` |
| 1 — Iniciação e planejamento | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_01.md` |
| 2 — Arquitetura | ✅ Aprovada em 2026-11-16 (ADRs 003–013 aceitos) | `docs/fases/FASE_02.md` |
| 3 — Infraestrutura local | Aguardando aprovação | `docs/fases/FASE_03.md` |

## Fatos-chave para retomada

- Diretrizes: **gratuito, máquina local, tudo em subpastas do projeto** (ADR-001); autorização para **substituir componentes v1** conforme a arquitetura (aprovação da Fase 2).
- Banco único: `data\database\sadgd.db` (tabelas v1 + migrações SAD-GD 001/002). `init_db()` aplica as migrações.
- Ferramentas: Ollama portátil (`ferramentas\ollama`, `scripts\sadgd\ollama.ps1`), modelo `sadgd-qwen2.5-7b`; Tesseract (`ferramentas\tesseract`, com `por`); Phoenix opcional (`127.0.0.1:6006`).
- Testes: `.\.venv\Scripts\python.exe -m pytest -q` (300 passam); lint: `python -m ruff check .`; diagnóstico: `diagnostico.bat`.
- Restauração do código v1: branch `backup/pre-reestruturacao`, tag `v1.0.0-pre-reestruturacao`; banco original em `BACKUP\pre-reestruturacao\`.
