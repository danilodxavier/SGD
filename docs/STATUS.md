# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-16 |
| Fase atual | **Fase 6 — Linha do tempo e relações entre documentos** |
| Situação da fase | Entregáveis concluídos — **aguardando aprovação do responsável** |
| Última tarefa concluída | Grafo documental (referências, relações por regras, contradições, vigência), API da linha do tempo, respostas de conflito; v2.1 avaliada no teste (`docs/fases/FASE_06.md`) |
| Próxima tarefa exata | Após "Aprovado, siga para a Fase 7": (1) SAD-070 roteador (regras + intents; LLM pequeno só se ambíguo) em `app/application/agentes/`; (2) SAD-072 verificador de fontes (checagem lexical/numérica determinística + LLM de outra família — Llama 3.1 8B) atacando as alucinações de data (T100, T109, T124); (3) SAD-071 especialistas com saída JSON validada; (4) SAD-073 relator; (5) SAD-074 anonimizador; (6) SAD-075 auditoria; grafo LangGraph com checkpointer SQLite |
| Bloqueios | Kanban (SAD-003) depende do `gh`. RAM livre da máquina baixa (1–2 GB): rodar indexações com `--max-minutos 7.5` |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_00.md` |
| 1 — Iniciação e planejamento | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_01.md` |
| 2 — Arquitetura | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_02.md` |
| 3 — Infraestrutura local | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_03.md` |
| 4 — Ingestão e base de conhecimento | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_04.md` |
| 5 — RAG, golden set e baseline | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_05.md` |
| 6 — Linha do tempo e relações | Aguardando aprovação | `docs/fases/FASE_06.md` |

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
