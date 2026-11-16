# STATUS — Checkpoint do projeto SAD-GD

> Leia este arquivo no início de toda sessão. Atualize-o ao final de cada tarefa.

| Campo | Valor |
|---|---|
| Atualizado em | 2026-11-16 |
| Fase atual | **Fase 4 — Ingestão e base de conhecimento** |
| Situação da fase | Entregáveis concluídos — **aguardando aprovação do responsável** |
| Última tarefa concluída | Corpus (69 públicos + 117 sintéticos com gabarito), chunking estrutural, metadados, OCR Tesseract, indexação híbrida com bge-m3 (`docs/fases/FASE_04.md`) |
| Próxima tarefa exata | Após "Aprovado, siga para a Fase 5": (1) SAD-050 busca híbrida BM25 + densa com RRF, filtro de vigência e reranker bge-reranker-v2-m3 em `app/application/recuperacao/`; (2) SAD-052 golden set ≥ 100 perguntas derivado do `GABARITO.json` + perguntas sobre o corpus público, split 30/70; (3) SAD-053 `scripts/sadgd/avaliar.py` (P@k, R@k, MRR, nDCG, citações, recusa); (4) SAD-054 baseline v1 × v2; (5) SAD-051 geração com citação; (6) SAD-055 benchmark de LLMs |
| Bloqueios | Kanban (SAD-003) depende do `gh`. RAM livre da máquina baixa (1–2 GB): rodar indexações com `--max-minutos 7.5` |

## Histórico de fases

| Fase | Situação | Documento |
|---|---|---|
| 0 — Auditoria | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_00.md` |
| 1 — Iniciação e planejamento | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_01.md` |
| 2 — Arquitetura | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_02.md` |
| 3 — Infraestrutura local | ✅ Aprovada em 2026-11-16 | `docs/fases/FASE_03.md` |
| 4 — Ingestão e base de conhecimento | Aguardando aprovação | `docs/fases/FASE_04.md` |

## Fatos-chave para retomada

- Diretrizes: gratuito, máquina local, tudo em subpastas do projeto (ADR-001); autorização para substituir componentes v1.
- Repositório: https://github.com/danilodxavier/SGD (público). CI: segredos + lint + testes + cobertura.
- Banco: `data\database\sadgd.db` — 186 documentos, 5.691 trechos/vetores (bge-m3, 1024 dims), 96 normas.
- Indexar: `.venv\Scripts\python.exe scripts\sadgd\indexar.py [--max-minutos 7.5]`. Modelo: `scripts\sadgd\preparar_bge_m3.py` (cópia local em `modelos\bge-m3`).
- Corpus: `corpus\publico` (`coletar_corpus_publico.py`), `corpus\sintetico` (`gerar_corpus_sintetico.py`, gabarito em `GABARITO.json`), manifesto em `corpus\MANIFESTO.csv`.
- Avaliações da fase: `scripts\sadgd\avaliar_{chunking,metadados,ocr}.py` → `avaliacao\execucoes\fase4_*.json`.
- Embeddings em **float32** (fp16 é 5× mais lento nesta GPU); `HF_DEACTIVATE_ASYNC_LOAD=1` é obrigatório (crash nativo sem ele).
