# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-17 |
| Fase atual | **Fase 11 — Entrega acadêmica** |
| Situação da fase | Em andamento |
| Última tarefa concluída | **Roteiro de demonstração** (`docs/DEMONSTRACAO.md`, perguntas validadas ao vivo) e **correção da API** `POST /api/sadgd/perguntar` (falhava com o pipeline real desde a Fase 7; `bead9a7`, `FASE_11.md` §4). Antes: README, manuais, relatório técnico, F2 no Gemini |
| Próxima tarefa exata | (1) lições aprendidas `docs/projeto/LICOES_APRENDIDAS.md`; (2) fechar `FASE_11.md` (critérios, retrospectiva) e pedir aprovação da Fase 11 |
| Bloqueios | Nenhum para a Fase 11. Kanban (SAD-003) depende do `gh` |

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
| 8 — Apoio à decisão (F2) | ✅ Aprovada em 2026-11-17 | `docs/fases/FASE_08.md` |
| 9 — MVP completo | ✅ Aprovada em 2026-11-17 | `docs/fases/FASE_09.md` |
| 10 — Otimização e avaliação final | ✅ Aprovada em 2026-11-17 | `docs/fases/FASE_10.md` |
| 11 — Entrega acadêmica | Em andamento | `docs/fases/FASE_11.md` |

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
- MVP: `start.bat` → http://127.0.0.1:8000 (telas Perguntar, Acervo, Linha do tempo, Decisões). Uploads vão para `corpus/enviados/` (fora do Git, origem real). E2E: `pytest tests/sadgd/test_e2e_navegador.py` (Edge do sistema; `SADGD_E2E_CAPTURAS=1` grava telas em `docs/img/fase09/`).
- Fase 10: `avaliar_fidelidade.py calibrar|medir|resumo` (juiz Llama 3.1 8B; adjudicações em `avaliacao/execucoes/fase10/fidelidade_adjudicacao*.json`), `calibrar_cache.py`, `medir_cache.py`, `avaliar_f2.py --modelo-especialistas`. Código v1 removido; reprodutível pela tag `backup/pre-limpeza-v1`.
