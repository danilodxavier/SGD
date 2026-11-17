# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-17 |
| Fase atual | **Fase 8 — Apoio à decisão (F2) e memória de decisões** |
| Situação da fase | Entregáveis concluídos — **aguardando aprovação do responsável** |
| Última tarefa concluída | Memória de decisões (30 decisões + 50 perguntas de precedente; R@3 1,00 no teste), recomendação F2 com os 6 elementos de RF-20 (100% presentes ou declarados), relator v2, API de decisões, correção do agrupamento do grafo (pureza 0,966) (`docs/fases/FASE_08.md`) |
| Próxima tarefa exata | Após "Aprovado, siga para a Fase 9": MVP — (1) SAD-090 chat com fontes clicáveis, pareceres por agente, precedentes e elementos RF-20; (2) upload de documentos com indexação (RF-22); (3) linha do tempo visual (RF-13); (4) perfil Gestor (RF-23) para registrar decisões; (5) testes E2E. Reaproveitar o frontend da v1 em `frontend\` |
| Bloqueios | Kanban (SAD-003) depende do `gh`. RAM livre da máquina baixa (1–2 GB): indexações com `--max-minutos 7.5`; avaliações F2 só em primeiro plano com `--max-minutos 4` |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_00.md` |
| 1 — Iniciação e planejamento | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_01.md` |
| 2 — Arquitetura | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_02.md` |
| 3 — Infraestrutura local | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_03.md` |
| 4 — Ingestão e base de conhecimento | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_04.md` |
| 5 — RAG, golden set e baseline | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_05.md` |
| 6 — Linha do tempo e relações | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_06.md` |
| 7 — Sistema multiagentes | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_07.md` |
| 8 — Apoio à decisão (F2) | Aguardando aprovação | `docs/fases/FASE_08.md` |

## Fatos-chave para retomada

- Diretrizes: gratuito, máquina local, tudo em subpastas do projeto (ADR-001); autorização para substituir componentes v1.
- Repositório: https://github.com/danilodxavier/SGD (público). CI: segredos + lint + testes + cobertura.
- Banco: `data\database\sadgd.db` — 186 documentos, 5.691 trechos/vetores (bge-m3, 1024 dims), 96 normas.
- Indexar: `.venv\Scripts\python.exe scripts\sadgd\indexar.py [--max-minutos 7.5]`. Modelo: `scripts\sadgd\preparar_bge_m3.py` (cópia local em `modelos\bge-m3`).
- Corpus: `corpus\publico` (`coletar_corpus_publico.py`), `corpus\sintetico` (`gerar_corpus_sintetico.py`, gabarito em `GABARITO.json`), manifesto em `corpus\MANIFESTO.csv`.
- Avaliações da fase: `scripts\sadgd\avaliar_{chunking,metadados,ocr}.py` → `avaliacao\execucoes\fase4_*.json`.
- Avaliação: `scripts\sadgd\avaliar.py recuperacao|relatorio|ci` e `scripts\sadgd\avaliar_respostas.py --sistema v1|v2 --modelo <tag> --conjunto validacao|teste [--max-minutos 8.5]` (retomáveis). Resultados em `avaliacao\execucoes\fase5\`. LLM escolhido: `sadgd-qwen2.5-7b`; `llama3.1:8b-instruct-q4_K_M` também instalado.
- Grafo: `scripts\sadgd\construir_grafo.py` (rodar após indexar); avaliação: `scripts\sadgd\avaliar_relacoes.py`. API: `/api/sadgd/processos`, `/api/sadgd/linha-do-tempo`. Resultados v2.1 em `avaliacao\execucoes\fase6\`.
- Embeddings em **float32** (fp16 é 5× mais lento nesta GPU); `HF_DEACTIVATE_ASYNC_LOAD=1` é obrigatório (crash nativo sem ele).
- Multiagentes: `app/application/agentes/` (roteador, verificador, especialistas, orquestrador, politica_llm); API `POST /api/sadgd/perguntar`. Avaliações: `avaliar_roteador.py`, `avaliar_anonimizacao.py`, `avaliar_respostas.py --verificador --rotulo fase7`, `avaliar_f2.py [--resumo]` → `avaliacao\execucoes\fase7\`.
- Qwen 2.5 3B (`qwen2.5:3b-instruct-q4_K_M`) instalado: exatidão 0,462 na validação; candidato a especialista rápido na Fase 10.
- Memória de decisões: `scripts\sadgd\gerar_memoria_decisoes.py` → `importar_decisoes.py` (rodar após `construir_grafo.py`; idempotente). Avaliações: `avaliar_precedentes.py`, `avaliar_f2.py --rotulo fase8` (ciclos `--max-minutos 4` em primeiro plano). API: `/api/sadgd/decisoes`, `/api/sadgd/precedentes`.
