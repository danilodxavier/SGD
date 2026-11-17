# Continuidade — como retomar o SAD-GD em uma nova sessão

## Para o agente (Claude Code)

1. Ler `CLAUDE.md` (regras + decisões vigentes, que prevalecem sobre o prompt mestre).
2. Ler `docs/STATUS.md`: fase atual, última tarefa, **próxima tarefa exata** e bloqueios.
3. Ler o `docs/fases/FASE_XX.md` da fase atual e os ADRs citados.
4. Conferir o estado real: `git status`, `git log --oneline -10`, e rodar os testes (comando abaixo).
5. Se a fase atual estiver "aguardando aprovação", **não avançar**: reapresentar o resumo e esperar "Aprovado, siga para a Fase X".
6. Ao final de cada tarefa: atualizar `docs/STATUS.md`, `CHANGELOG.md` e, quando aplicável, `MODELOS_IA.md`, `METODOLOGIAS.md`, `HABILIDADES.md`, `AVALIACAO.md`.

## Para uma pessoa (do zero)

```powershell
cd "D:\AGENTES\INTELIGENCIA_DOCUMENTAL_GESTAO_ CONTRATO"
.\instalar.bat                     # cria .venv, instala dependências, cria .env e roda diagnóstico
.\.venv\Scripts\python.exe scripts\sadgd\preparar_bge_m3.py   # modelo de embeddings (uma vez)
.\.venv\Scripts\python.exe -m pytest -q   # testes (316 + 4 E2E)
.\start.bat                        # painel em http://127.0.0.1:8000
```

## Mapa da documentação

| Arquivo | Conteúdo |
|---|---|
| `CLAUDE.md` | Prompt mestre + decisões vigentes + convenção de pastas |
| `docs/STATUS.md` | Checkpoint |
| `docs/fases/FASE_XX.md` | Planejamento, execução, evidências e aprovação de cada fase |
| `docs/projeto/` | TAP, partes interessadas, requisitos, EAP, cronograma, riscos, backlog |
| `docs/adr/` | Decisões de arquitetura |
| `docs/agentes/` | Especificação e prompts dos agentes (a partir da Fase 2) |
| `docs/AVALIACAO.md` | Métricas por versão |
| `docs/MODELOS_IA.md`, `docs/METODOLOGIAS.md`, `docs/HABILIDADES.md` | Rastreabilidade de IA, métodos e aprendizado |
| `docs/legado/` | Especificação e documentos da v1 |
| `docs/MANUAL_DO_USUARIO.md`, `docs/MANUAL_TECNICO.md` | Manuais do SAD-GD (Fase 11); os da v1 estão em `docs/legado/` |
| `docs/RELATORIO_TECNICO.md` | Relatório técnico (Fase 11) |

## Pontos de restauração

| Ref | O que é |
|---|---|
| branch `backup/pre-reestruturacao`, tag `v1.0.0-pre-reestruturacao` | Código v1 antes da reestruturação |
| `BACKUP\pre-reestruturacao\documents.db` | Banco v1 original (6,6 GB, antes do expurgo) — não versionado |
| `BACKUP\pre-reestruturacao\documents_v1_zerado.db` | Banco v1 após a exclusão dos documentos, antes da unificação em `sadgd.db` |

## Serviços locais

| Serviço | Como controlar | Endereço |
|---|---|---|
| Painel/API | `start.bat` / `stop.bat` | http://127.0.0.1:8000 |
| Ollama (LLM local) | `scripts\sadgd\ollama.ps1 -Acao iniciar|parar|status|modelo` (o `start.bat` já inicia) | http://127.0.0.1:11434 |
| Phoenix (traces, opcional) | `.venv\Scripts\python.exe -m phoenix.server.main serve` | http://127.0.0.1:6006 |
| `BACKUP\pre-reestruturacao\env.backup` | `.env` da v1 — não versionado |
