# FASE 01 — Iniciação e planejamento (Sprint S1)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aprovada em 2026-11-16** (ver §7) |

## 1. Planejamento da sprint

Objetivo: produzir os artefatos de iniciação e planejamento (PMBOK 7 + Scrum) e a estrutura de continuidade exigida pela seção 6 do prompt mestre, incorporando as diretrizes da aprovação da Fase 0 (gratuito, local, tudo em subpastas do projeto).

## 2. Entregáveis

| Entregável | Arquivo |
|---|---|
| Regras do projeto + decisões vigentes + convenção de pastas | `CLAUDE.md` |
| Termo de abertura (objetivos SMART, escopo, premissas, restrições, marcos) | `docs/projeto/TERMO_DE_ABERTURA.md` |
| Partes interessadas e personas | `docs/projeto/PARTES_INTERESSADAS.md` |
| Escopo e requisitos (26 RF, 14 RNF, MoSCoW, critérios verificáveis) | `docs/projeto/ESCOPO_E_REQUISITOS.md` |
| EAP com dicionário | `docs/projeto/EAP.md` |
| Cronograma (11 sprints, Gantt, caminho crítico) | `docs/projeto/CRONOGRAMA.md` |
| Matriz de riscos (14 riscos P×I) | `docs/projeto/RISCOS.md` |
| Product backlog (51 itens, 227 pontos; 52/228 após ajuste da Fase 2), DoR/DoD | `docs/projeto/backlog.csv`, `docs/projeto/BACKLOG.md` |
| Script de publicação no GitHub Projects | `scripts/github/criar_backlog.ps1` |
| ADR-001 execução local / ADR-002 corpus acadêmico | `docs/adr/` |
| Continuidade, modelos de IA, metodologias, habilidades, avaliação, changelog | `docs/CONTINUIDADE.md`, `docs/MODELOS_IA.md`, `docs/METODOLOGIAS.md`, `docs/HABILIDADES.md`, `docs/AVALIACAO.md`, `CHANGELOG.md` |

## 3. Critérios de aceite

| Critério (prompt mestre §8, Fase 1) | Situação |
|---|---|
| Termo de abertura | ✅ |
| Escopo | ✅ |
| Requisitos verificáveis | ✅ |
| EAP | ✅ |
| Riscos | ✅ |
| Cronograma | ✅ (data-limite a confirmar) |
| Backlog no GitHub Projects | ⚠️ Backlog pronto e script testado (parse OK, 51 itens); **publicação depende de `gh auth login`** |
| Estrutura de continuidade (§6) | ✅ (`docs/agentes/` será criada na Fase 2) |

## 4. Evidências

- Hardware de referência levantado: i7-12700 (12C/20T), 15,7 GB RAM, GTX 1660 SUPER, ~75 GB livres; Python 3.13 e Node já instalados; Ollama e Tesseract ausentes.
- Testes v1 após a limpeza da Fase 0: 238 passed.

## 5. Pendências para o responsável

1. **Data-limite da entrega acadêmica** (cronograma assume 2027-02-12 → ajustar).
2. **GitHub:** `winget install GitHub.cli`, `gh auth login`, `gh auth refresh -s project`; informar nome do repositório (privado recomendado).
3. Revisar metas e prioridades em `ESCOPO_E_REQUISITOS.md`.

## 6. Retrospectiva

- **Bem:** reaproveitamento do v1 reduz o risco técnico; decisões registradas como ADR desde o início.
- **A melhorar:** bloqueio do GitHub atrasa o Kanban — resolver antes da Fase 3 (CI).
- **Ação:** iniciar curadoria do corpus público já na Fase 3 (risco R03).

## 7. Aprovação

- [x] Aprovado pelo responsável em 2026-11-16 ("Vamos continuar, conforme sugerido"): cronograma com data-limite assumida de 2027-02-12 e repositório GitHub privado recomendado.
- Ressalva do responsável: **excluir os documentos, trechos e contratos do banco**, pois a nova versão usará novos documentos.

### Execução da ressalva (2026-11-16)

| Ação | Resultado |
|---|---|
| Exclusão no banco v1 `data\database\documents.db` | 5.670 documentos, 229.002 trechos (+ índice FTS5), 387 contratos, 28 itens de contrato e 5 resultados de checklist removidos |
| Índice FTS5 | reconstruído (`rebuild`) e banco compactado (`VACUUM`): **1,72 GB → 0,11 MB**; `integrity_check = ok` |
| Mantidos | 2 usuários, 1 checklist (4 itens, sem resultados), configurações, histórico de indexações |
| Raiz documental | configuração e `.env` apontam para `<projeto>\corpus` (subpastas `publico\` e `sintetico\` criadas) — evita reindexar o compartilhamento de rede real ao iniciar |
| Recuperação | o banco original completo continua em `BACKUP\pre-reestruturacao\documents.db` |
| Verificação | testes v1 verdes; configuração carregada com `documents_root=...\corpus` |
