# ADR-006 — Armazenamento único em SQLite: relacional + FTS5 + sqlite-vec + grafo

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | RF-05, RF-11–14, RF-19, RF-24, RNF-02, RNF-03 |

## Contexto

Candidatos do prompt mestre: Qdrant (self-hosted/cloud), Supabase (Postgres+pgvector) e Neon. Com ADR-001 (local, sem dependência obrigatória de Docker, tudo no projeto), soluções em nuvem saem. Volume esperado: corpus acadêmico ~150–300 documentos (≈ 5–20 mil trechos); base real comparável à v1 (≈ 230 mil trechos).

Verificações em 2026-11-16: `sqlite-vec 0.1.9` tem wheel `win_amd64`; o Python 3.15 do projeto traz SQLite 3.53.4 com `enable_load_extension` funcional.

## Opções

| Critério | sqlite-vec | LanceDB | Qdrant local (Docker) | Chroma |
|---|---|---|---|---|
| Sem serviço/Docker | ✅ | ✅ | ❌ | ✅ |
| Mesmo arquivo/transação dos trechos e metadados | ✅ | ❌ | ❌ | ❌ |
| Filtros SQL com JOIN (vigência, tipo, processo) | ✅ nativo | parcial | payload filters | metadados simples |
| Escala | força bruta; 230 mil × 1024 float32 ≈ 0,9 GB — viável; int8/binário reduz 4–32× | ANN | ANN | ANN |
| Backup | 1 arquivo | diretório | volume | diretório |
| Maturidade | pré-1.0 | boa | alta | boa |

## Decisão

1. **SQLite como banco único** (`data\database\sadgd.db`): tabelas relacionais, FTS5 (BM25), tabela virtual `vec0` do **sqlite-vec** para embeddings, **grafo documental** em tabelas de nós/arestas, memória de decisões, auditoria, cache semântico e checkpoints do LangGraph.
2. O acesso vetorial fica atrás de `VectorStorePort`; **LanceDB é o plano B** (troca de adaptador) se a latência de busca densa exceder 500 ms p95 ou a extensão se mostrar instável.
3. Grafo: tabelas `processos`, `documento_processo`, `relacoes` (arestas tipadas com confiança e evidência); consultas recursivas com `WITH RECURSIVE`. Neo4j descartado (serviço extra, sem ganho no volume previsto).
4. O banco v1 (`documents.db`, zerado em 2026-11-16) fica para a aplicação v1 até a migração; o novo esquema é criado por migrações versionadas (Fase 3).

## Consequências

- (+) Consistência transacional entre texto, vetor e metadados; backup e reprodutibilidade triviais.
- (+) Zero serviços extras para instalar no Windows.
- (−) Busca vetorial exata (sem ANN); aceitável no volume previsto e medida na Fase 5.
- (−) sqlite-vec é pré-1.0: versão fixada e testes de contrato do adaptador.
