# FASE 00 — Auditoria do projeto existente

| Campo | Valor |
|---|---|
| Projeto | SAD-GD — Sistema de Apoio à Tomada de Decisão e Gestão Documental |
| Fase | 0 — Auditoria |
| Data | 2026-11-16 |
| Executor | Claude Code (modelo `claude-opus-5-5`) |
| Situação | **Aguardando aprovação** — nenhuma exclusão foi executada |

---

## 1. Método

Inspeção somente leitura do repositório `D:\AGENTES\INTELIGENCIA_DOCUMENTAL_GESTAO_ CONTRATO`:

1. `git status`, `git log`, branches, tags e remotos;
2. inventário dos 134 arquivos versionados e contagem de linhas por módulo;
3. leitura de `requirements.txt`, `.env` (chaves mascaradas), `docs/` e módulos centrais (`retrieval/search.py`, `services/questions.py`, `services/llm.py`, `core/database.py`);
4. execução da suíte de testes (`pytest`);
5. consulta **somente leitura** (`mode=ro`) ao banco SQLite para medir volume e estado do índice;
6. comparação de hash entre arquivos suspeitos de duplicidade.

---

## 2. O que existe hoje

### 2.1 Visão geral

Aplicação **local para Windows** ("Agente de Inteligência Documental — Contratos e Checklists"), versão 1.0.0, construída sob a especificação do `AGENTS.md` (14 fases concluídas) e em adequação ao padrão visual do Governo de MT (commits "Fase 2" e "Fase 3" de UI).

| Item | Constatação |
|---|---|
| Stack | Python 3.15 (venv), FastAPI + Uvicorn, SQLite + FTS5, HTML/CSS/JS puro servido pelo FastAPI |
| Tamanho | ~6.000 linhas Python em `app/`, ~1.900 em frontend, ~2.000 em testes |
| Testes | **238 aprovados, 0 falhas** (78 s); 1 aviso de depreciação (`httpx` no TestClient) |
| Git | branch `main`, 4 commits, **sem remoto**, sem tags; `gh` CLI **não instalado** |
| Pendência local | `app/services/llm.py` modificado e não commitado (melhorias de mensagens de erro e filtro de modelos de embedding — útil, recomendo commitar) |
| IA configurada | `llm_local` via LM Studio (`qwen2.5-7b-instruct q4_k_m`, `127.0.0.1:1234`) |
| Base indexada | raiz em **compartilhamento de rede real** (`\\piau\...\STI\01 - CONTRATOS ATIVOS`) |

### 2.2 Estado do banco (`data/database/documents.db`)

| Métrica | Valor |
|---|---|
| Tamanho do arquivo | **6,6 GB** |
| Registros em `documents` | 175.368, dos quais **169.703 com status `REMOVIDO`** |
| Documentos ativos | ~5.665 (4.632 com texto, 1.009 via OCR, 8 sem texto, 3 corrompidos, 13 não suportados) |
| Hashes distintos ativos | 4.419 (≈1.200 duplicatas exatas) |
| Trechos (`document_chunks`/FTS) | 229.002 |
| Contratos extraídos | 387 (28 itens) |
| Usuários / checklists | 2 / 1 |

Diagnóstico: em algum momento a raiz apontou para uma árvore ampla (há `.class`, `.jar`, `.java`, `.js`, `.svg` no histórico), e os registros removidos nunca foram expurgados — daí os 6,6 GB. **O banco contém dados reais de órgão público** (contratos, CNPJ, possivelmente CPF) → implicação direta de LGPD.

### 2.3 Avaliação por módulo

| Módulo | Função | Qualidade | Aderência ao SAD-GD |
|---|---|---|---|
| `app/ingestion/*` | Extração PDF, DOCX, DOC, XLSX/XLS, ODS/ODT, RTF, PPT/PPTX, HTML, imagens; OCR via Windows OCR (PowerShell) | Alta, testado com fixtures legadas | **Alta** — base da Fase 4; OCR precisa de alternativa portátil (Tesseract) para rodar fora do Windows |
| `app/indexing/*` | Varredura recursiva, hash, incremental, chunking, metadados, duplicidades | Boa | **Média** — chunking é por tamanho, não estrutural (artigo/inciso/cláusula) |
| `app/retrieval/*` | Busca FTS5 (BM25) + cobertura de termos + citações com trecho | Boa | **Média** — é só a perna lexical; faltam vetorial, fusão híbrida e reranking |
| `app/services/questions.py` | Respondedor **por regras** (intenções: vigência, valor, objeto, aditivos, CNPJ, itens…) com detecção de conflito e ausência | Boa, muito rastreável | **Alta como baseline** de avaliação; não escala para "qualquer pergunta" |
| `app/services/ai_provider.py`, `llm.py` | Abstração `AnswerProvider`, LLM local/OpenAI-compatível, mascaramento ao sair da máquina | Boa | **Alta** — embrião da camada de abstração de provedores |
| `app/contracts/*` | Extração de campos e itens de contrato com confiança | Boa | **Alta** — vira metadado e insumo do grafo documental |
| `app/checklist/*` | Checklist, matching, organização virtual, relatório | Boa | **Média** — fora do escopo central do SAD-GD, mas é funcionalidade de apoio à gestão útil |
| `app/core/auth.py`, `security.py` | Login, perfis, PBKDF2, bloqueio, sessões, allowlist de hosts | Boa | **Alta** — atende parte da regra 7 (LGPD/controle de acesso) |
| `app/services/reports.py`, `report_writers.py` | Exportação PDF/DOCX/XLSX/CSV/JSON | Boa | Média |
| `frontend/*` | SPA em JS puro, padrão visual Gov-MT, página de acessibilidade | Boa, acessível | **Depende da decisão D1** (Next.js exigido pelo prompt mestre) |
| `scripts/*`, `*.bat` | Instalação, diagnóstico, backup/restauração, aceitação, usuários | Boa | Média — específico de Windows |
| `tests/*` | 238 testes, documentos fictícios | Boa | **Alta** — rede de segurança para a refatoração |
| `docs/*` | Arquitetura, conformidade, manuais do usuário e técnico | Boa | Parcial — falta toda a estrutura de continuidade/ADR/avaliação |

### 2.4 Lacunas frente ao SAD-GD

| Exigência do prompt mestre | Situação atual |
|---|---|
| Busca semântica (embeddings bge-m3), híbrida, reranking | Ausente (apenas BM25) |
| Chunking estrutural (artigo, parágrafo, inciso, cláusula) | Ausente |
| Linha do tempo e classificação de relações (continuação, aditivo, revogação…) | Parcial — só aditivos de contrato por regras |
| Hierarquia normativa e vigência | Ausente |
| Multiagentes (roteador, especialistas, verificador, relator) | Ausente |
| Memória de decisões / F2 | Ausente |
| Golden set ≥ 100 perguntas, métricas (Recall@k, MRR, nDCG, faithfulness…) | Ausente |
| Observabilidade (Langfuse), tokens/latência por consulta | Ausente (há log de consultas) |
| CI/CD, GitHub remoto, Projects, ADRs, docs de continuidade | Ausente |
| Log de auditoria LGPD e anonimização | Parcial (login/sessão; mascaramento só no envio a LLM externo) |

---

## 3. Conflitos que exigem decisão antes da Fase 1

**C1 — Arquitetura local × nuvem.** O `AGENTS.md` vigente proíbe Node.js, Docker, nuvem e exige `127.0.0.1`. O prompt mestre exige Next.js/Vercel, Docker em VPS Oracle e LLMs em free tier na nuvem. Um dos dois precisa prevalecer (ou um híbrido explícito). Proposta: o prompt mestre substitui o `AGENTS.md`, que é arquivado em `docs/legado/`.

**C2 — Dados reais × free tier na nuvem (LGPD).** A base atual é real (`\\piau\...`). Free tiers como Gemini e alguns modelos do OpenRouter podem usar as entradas para melhoria de produto. Proposta: **corpus acadêmico público/sintético** (leis, decretos, INs e contratos já publicados em portais de transparência + documentos fictícios) para a versão em nuvem, golden set e demonstração; dados reais só em implantação local com LLM local (Ollama/LM Studio).

**C3 — "Somente gratuito" × Oracle Always Free.** O cadastro exige cartão de crédito para verificação (sem cobrança no Always Free) e a capacidade ARM costuma estar esgotada em várias regiões. Alternativas a avaliar na Fase 2: Hugging Face Spaces (CPU grátis), backend rodando localmente com túnel, ou Supabase/Qdrant Cloud free + inferência local.

**C4 — Python 3.15 no venv.** Versão muito recente; `torch`/`sentence-transformers` (bge-m3) e Docling podem não ter wheels. Proposta: padronizar Python 3.12 para o novo backend (registrar em ADR).

---

## 4. Proposta: manter / refatorar / excluir

### 4.1 Manter (reaproveitar como está, movendo de lugar quando necessário)

- `app/ingestion/*` (todos os extratores) e `tests/fixtures/legados/*`
- `app/core/auth.py`, `app/core/security.py`, `app/core/text.py`, `app/core/logging.py`
- `app/contracts/*`, `app/checklist/*`, `app/indexing/duplicates.py`, `app/indexing/metadata.py`
- `app/services/report_writers.py`, `app/services/reports.py`
- `tests/*` (todos), `scripts/gerar_exemplos.py`, `tests/sample_docs.py`
- `docs/MANUAL_DO_USUARIO.md`, `docs/MANUAL_TECNICO.md` (atualizados nas fases finais)
- `app/services/llm.py` **incluindo a alteração pendente** (commitar antes do backup)

### 4.2 Refatorar

| Item | Refatoração proposta |
|---|---|
| Estrutura `app/` | Reorganizar em Clean Architecture: `domain/` (entidades, relações, hierarquia normativa), `application/` (casos de uso F1/F2), `infrastructure/` (SQLite/Postgres, vetorial, LLMs, OCR), `interfaces/` (API) |
| `indexing/chunks.py` | Chunking estrutural jurídico (artigo/§/inciso/alínea; cláusula/subcláusula) preservando página e offsets |
| `retrieval/*` | Busca híbrida BM25 + vetorial (bge-m3) com RRF + reranker (bge-reranker-v2-m3); manter FTS5 como perna lexical |
| `services/questions.py` | Preservar como **`RuleBasedAnswerer` = baseline v1** para comparação na `AVALIACAO.md`; integrar como ferramenta de extração factual do Fiscal de Contrato |
| `services/ai_provider.py` + `llm.py` | Evoluir para camada de provedores (Gemini, Groq, OpenRouter, Ollama) com roteamento por custo |
| `ingestion/ocr.py` | Adicionar Tesseract como implementação portátil; manter Windows OCR como alternativa |
| `core/database.py` | Repositórios por porta/adaptador; migrações versionadas; tabelas de relações, normas, decisões e auditoria |
| `frontend/*` | Conforme D1: reescrever em Next.js (reaproveitando `tokens.css` e o padrão Gov-MT/acessibilidade) **ou** manter JS puro |
| `.bat` / `scripts/*` | Manter para o modo local Windows; acrescentar equivalentes multiplataforma se houver deploy em VPS |
| `docs/ARQUITETURA.md`, `docs/CONFORMIDADE.md` | Substituir por C4 + ADRs (conteúdo histórico migrado para `docs/legado/`) |

### 4.3 Excluir (somente após aprovação e após `backup/pre-reestruturacao`)

| # | Item | Motivo | Risco |
|---|---|---|---|
| E1 | `READ ME — Agente de Inteligência Documental — Contratos e Checklists.md` | Cópia byte-a-byte do `AGENTS.md` (hash idêntico) | Nenhum |
| E2 | `AGENTS.md` → **mover** para `docs/legado/AGENTS_v1.md` (não apagar) | Substituído pelo `CLAUDE.md` do SAD-GD; conflita com o novo escopo (C1) | Nenhum (histórico preservado) |
| E3 | Registros `REMOVIDO` do banco (169.703) + `VACUUM` | Liberar ~GB; não afetam consultas | Baixo — fazer cópia do `.db` antes |
| E4 | `data/logs/app.log.1` … `.5` (~25 MB) | Rotação antiga | Nenhum |
| E5 | `data/app.pid` | PID obsoleto | Nenhum |
| E6 | `.pytest_cache/` | Cache regenerável | Nenhum |

Nota: E3–E6 não são versionados no git; o backup git **não** os cobre. Para E3 farei cópia `documents.db.bak` (6,6 GB) ou, alternativa, você decide recriar a base do zero com o novo pipeline.

---

## 5. Recomendação

**Aproveitar parcialmente (evolução incremental, não recomeço).**

Justificativa:

1. Ingestão multiformato + OCR + indexação incremental + autenticação + 238 testes verdes representam o trecho mais trabalhoso e menos "visível" de um RAG; refazer custaria semanas sem ganho de nota.
2. O respondedor por regras é um **baseline mensurável** — permite mostrar no relatório acadêmico a evolução v1 (regras+BM25) → v2 (RAG híbrido) → v3 (multiagentes), com as mesmas métricas no mesmo golden set. Isso é rigor metodológico (CRISP-DM/LLMOps) que um recomeço perderia.
3. O que falta (vetorial, reranking, grafo, agentes, avaliação, CI) é **aditivo**: encaixa-se na arquitetura via novas portas/adaptadores sem descartar o núcleo.
4. O frontend é o único componente cuja reescrita depende de decisão (D1).

---

## 6. Decisões solicitadas

| ID | Decisão | Opção recomendada |
|---|---|---|
| D1 | Arquitetura-alvo (C1) | Prompt mestre prevalece; `AGENTS.md` arquivado; modo local Windows mantido como perfil de implantação "on-premise" |
| D2 | Corpus (C2) | Corpus público/sintético para nuvem, golden set e banca; dados reais apenas on-premise com LLM local |
| D3 | Lista de exclusão (4.3) | Aprovar E1–E6 |
| D4 | Commit da alteração pendente em `llm.py` | Commitar antes da tag de backup |
| D5 | GitHub | Instalar `gh` (`winget install GitHub.cli`), executar `gh auth login` e informar nome/visibilidade do repositório (privado recomendado) |

---

## 7. Critérios de aceite da Fase 0

| Critério | Situação |
|---|---|
| Repositório inspecionado e inventariado | ✅ |
| Testes executados e resultado registrado | ✅ 238/238 |
| Relatório manter / refatorar / excluir | ✅ seção 4 |
| Recomendação aproveitar × recomeçar | ✅ seção 5 |
| Nenhuma exclusão sem aprovação | ✅ nada foi excluído ou alterado no código |
| `docs/STATUS.md` atualizado | ✅ |

## 8. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
