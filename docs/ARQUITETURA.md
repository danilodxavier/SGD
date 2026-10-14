# Arquitetura — Agente de Inteligência Documental

Documento técnico para quem for manter ou evoluir a aplicação. O guia de uso está no [`README.md`](../README.md).

## Visão geral

```text
Navegador (HTML/CSS/JS puro)
        │  HTTP 127.0.0.1:8000 (somente local)
        ▼
FastAPI + Uvicorn  ── app/main.py, app/api/*
        │
        ├── Serviços ─────── perguntas, checklist, relatórios, documentos, diagnóstico, IA
        │
        ├── Indexação ────── varredura → extração (+OCR) → trechos → FTS5 → contratos e itens
        │
        └── SQLite (data\database\documents.db)

Diretório documental (D:\Documentos)  ── somente leitura
PowerShell (OCR do Windows) / Tesseract  ── opcional, local
Ollama / LM Studio (LLM)                 ── opcional, local (127.0.0.1)
```

Fluxo de uma pergunta (seção 36 da especificação):

```text
DOCUMENTOS → INDEXAÇÃO → ÍNDICE (FTS5) → PERGUNTA → RECUPERAÇÃO → EVIDÊNCIAS → RESPOSTA (+ validação da IA)
```

## Módulos

| Caminho | Responsabilidade |
|---|---|
| `app/__main__.py` | `python -m app` (usado pelo `start.bat`) e `python -m app parar` (`stop.bat`, via token em `data\app.pid`). |
| `app/main.py` | Cria a aplicação, registra rotas, tratadores de erro amigáveis e serve o `frontend/`. |
| `app/api/routes_*.py` | Rotas HTTP finas: validam entrada e delegam aos serviços. |
| `app/core/config.py` | Leitura do `.env`. Valores ajustáveis no painel ficam na tabela `settings` e prevalecem. |
| `app/core/database.py` | Esquema SQLite, migrações aditivas (`MIGRATIONS`) e configurações persistidas. |
| `app/core/security.py` | `NetworkGuard`: computadores autorizados (`ALLOWED_CLIENTS`), nomes de acesso (`ALLOWED_HOSTS`), cabeçalho `X-Requested-With` e identificação da sessão. |
| `app/core/auth.py` | Usuários (PBKDF2), política de senha, bloqueio por tentativas, sessões (hash do token no banco). |
| `app/api/deps.py`, `routes_auth.py` | Exigências `require_login`/`require_admin`/`require_local`; login, configuração inicial, troca de senha, usuários. |
| `app/core/text.py` | `fold()` — minúsculas sem acento **com o mesmo comprimento** do texto, base de todas as extrações. |
| `app/ingestion/scanner.py` | Varredura recursiva, hash SHA-256, verificação do diretório. |
| `app/ingestion/extractor.py` | Escolhe o leitor por extensão, classifica o status e aciona o OCR quando há páginas sem texto. |
| `app/ingestion/{pdf,docx,xlsx,text}.py` | Leitores (pypdf, python-docx, openpyxl/xlrd para XLSX e XLS, texto/CSV). |
| `app/ingestion/doc.py` | DOC (Word 97-2003): texto remontado pela tabela de peças [MS-DOC] via `olefile`; campos reduzidos ao texto exibido. |
| `app/ingestion/pptx.py` | PPTX (XML) e PPT (registros de texto do PowerPoint 97-2003), um segmento por slide. |
| `app/ingestion/odf.py`, `rtf.py`, `html.py` | ODT/ODS (content.xml), RTF (interpretador próprio) e HTML disfarçado de .doc/.xls. |
| `app/ingestion/images.py`, `ocr.py`, `ocr_windows.ps1` | Renderização de páginas (pypdfium2), mecanismos de OCR (Windows via PowerShell `-Command`; Tesseract). |
| `app/indexing/indexer.py` | Indexação incremental, reprocessamento para OCR, gravação de trechos, contratos e itens. |
| `app/indexing/chunks.py` | Trechos de até ~1.200 caracteres, com página e seção (cláusulas e títulos). |
| `app/indexing/metadata.py` | Tipo documental (contrato, aditivo, portaria, certidão…), ordem do aditivo, contrato principal. |
| `app/indexing/duplicates.py` | Arquivos idênticos (hash) e versões possivelmente relacionadas (nome). |
| `app/retrieval/search.py` | Busca FTS5 (bm25), termos com prefixo, cobertura mínima, documentos de um contrato. |
| `app/contracts/extractor.py` | Padrões de campos contratuais (nº, processo, contratada, CNPJ, objeto, valor, vigência, assinatura, validade). |
| `app/contracts/items.py` | Itens contratados lidos de planilhas e tabelas com as colunas preservadas. |
| `app/services/questions.py` | Intenções, coleta de evidências, resolução (fato, inferência, conflito, ausência) e `AnswerProvider`. |
| `app/services/ai_provider.py`, `llm.py` | Provedor com LLM local, montagem de trechos, validação e trava LOCAL ONLY. |
| `app/checklist/{parser,matcher,organizer,report}.py` | Interpretação do checklist, regras de status, organização virtual, CSV/TXT. |
| `app/services/reports.py`, `report_writers.py` | Seis relatórios em modelo neutro e gravação em PDF/DOCX/XLSX/CSV/JSON. |
| `app/services/diagnostics.py` | Verificações usadas pelo painel, `diagnostico.bat` e `aceitacao.bat`. |
| `frontend/` | Painel: `app.js` (núcleo, painel, configurações), `search.js`, `documents.js`, `checklist.js`, `reports.js`. |
| `scripts/` | `indexar.py`, `diagnostico.py`, `backup.py`, `gerar_exemplos.py`, `aceitacao.py`. |
| `tests/` | Testes automatizados; `sample_docs.py` gera os documentos fictícios. |

## Banco de dados

| Tabela | Conteúdo |
|---|---|
| `documents` | Um registro por arquivo: caminho, hash, datas, status, tipo, ordem do aditivo, contrato principal, OCR. |
| `document_chunks` + `chunks_fts` | Trechos com página/seção e o índice de texto completo (FTS5, sem acentos). |
| `contracts` | Resumo de cada termo de contrato (um registro por documento de contrato). |
| `contract_items` | Itens identificados em planilhas/tabelas, com contrato e localização (aba/tabela). |
| `checklist`, `checklist_items`, `checklist_matches` | Checklists, itens com status/justificativa e evidências por documento. |
| `settings` | Configurações feitas no painel (diretório, OCR, mecanismo de respostas). |
| `users`, `sessions` | Usuários (perfil, hash da senha, bloqueio) e sessões abertas (hash do token, validade, IP). |
| `index_runs` | Histórico das indexações. |

Migrações: `init_db()` cria o que falta e acrescenta colunas novas (`MIGRATIONS`) sem apagar dados; é executado a cada
inicialização. Não há migração destrutiva.

## API

Todas as rotas `/api/*` exigem login, exceto `/api/auth/*` e o encerramento local. Rotas de configuração, indexação,
usuários, logs e diagnóstico exigem perfil Administrador; "abrir no Windows", "selecionar pasta" e o encerramento só
funcionam no próprio computador.

| Método | Rota | Função |
|---|---|---|
| GET | `/health` | Saúde: banco, diretório documental, índice (pública, sem dados). |
| GET/POST | `/api/auth/status`, `/setup`, `/login`, `/logout`, `/password` | Situação da sessão, configuração inicial, login, saída e troca de senha. |
| GET/POST/PUT | `/api/users`, `/api/users/{id}`, `/password`, `/unlock` | Gestão de usuários (administradores). |
| GET | `/api/status` | Indicadores do painel. |
| GET/POST | `/api/config` | Diretório documental. `POST /api/config/browse` abre o seletor de pastas do Windows. |
| POST/GET | `/api/index`, `/api/index/status` | Inicia indexação (`force`, `retry_ocr`) e acompanha o progresso. |
| GET/POST | `/api/ocr`, `/api/ocr/test` | Configuração e teste do OCR. |
| GET/POST | `/api/ai`, `/api/ai/models`, `/api/ai/test` | Configuração e teste do LLM local. |
| GET | `/api/diagnostics`, `/api/logs` | Diagnóstico e últimas linhas do log. |
| POST | `/api/system/shutdown` | Encerramento controlado (exige token do `data\app.pid`). |
| GET | `/api/documents`, `/api/documents/{id}`, `/api/documents/duplicates` | Listagem, metadados e duplicidades. |
| GET/POST | `/api/documents/{id}/file`, `/open`, `/reindex` | Visualizar, abrir no Windows, reindexar. |
| GET | `/api/contracts`, `/api/search` | Contratos identificados e busca textual. |
| POST | `/api/ask` | Pergunta em linguagem natural. |
| GET/POST/PUT/DELETE | `/api/checklists[...]` | Cadastro, `parse-file`, `run`, `organization`, `export`. |
| GET | `/api/reports`, `/api/reports/{tipo}`, `/api/reports/files[/{nome}]` | Catálogo, geração e relatórios salvos. |

Documentação interativa (administradores): `http://127.0.0.1:8000/api/docs`.

## Decisões técnicas

| Decisão | Motivo |
|---|---|
| FastAPI + HTML/JS puro, sem Node | Seção 4 da especificação: simplicidade e instalação só com Python. |
| SQLite FTS5 com `remove_diacritics` | Busca rápida e sem acentos, embutida no Python; dispensa servidor de busca. |
| Extração por padrões sobre `fold()` | Valores recortados do texto original pelas mesmas posições: o que é exibido é exatamente o que consta do documento. |
| Respostas por regras antes de qualquer IA | Seção 49: funcionar e ser confiável antes de ser sofisticado. Conflitos nunca são resolvidos automaticamente. |
| OCR nativo do Windows via PowerShell `-Command` | Sem instalação adicional; pacotes `winrt` não existem para Python 3.15; `-Command` não depende da política de execução de scripts. |
| `pypdfium2` para renderizar PDFs | Roda em Python puro com binário incluso, sem Poppler. |
| Formatos legados em Python puro (`olefile`, `xlrd`, XML), sem automação do Office | Funciona em máquinas sem Office; automação COM do Office é frágil em servidor e trava com o Office sem ativação. XML de terceiros lido com `defusedxml` e limite de tamanho descompactado. |
| Fixtures reais salvas pelo Office | `tests/fixtures/legados` foi gerado pelo Word, Excel e PowerPoint (`gerar_fixtures_legados.ps1`), garantindo fidelidade sem exigir Office nos testes. |
| `fpdf2` para PDF | Sem dependências nativas além do Pillow; fonte Arial do Windows para acentuação completa. |
| IA somente local, com validação factual | Decisão do usuário (fase 13): privacidade e prevenção de alucinação. |
| Organização virtual em vez de cópias | Seção 19 e 45: originais nunca são movidos nem copiados. |

## Pontos de extensão

- **Novo formato de arquivo:** criar o leitor em `app/ingestion/` retornando `(segments, pages)` e registrá-lo em
  `extractor._readers()`; remover a extensão de `PLANNED_EXTENSIONS`.
- **Nova pergunta:** acrescentar a intenção em `INTENTS` e um método `h_<intenção>` em `Answerer`.
- **Novo campo contratual:** padrão em `app/contracts/extractor.py` + grupo em `FIELD_GROUPS`.
- **Nova regra de checklist:** acrescentar `Rule` em `app/checklist/matcher.py` (a ordem define a prioridade).
- **Novo relatório:** função `build_<tipo>` em `app/services/reports.py`, registrada em `REPORTS` e `BUILDERS`.
- **Outro mecanismo de OCR:** classe com `available()` e `recognize(paths)` em `app/ingestion/ocr.py`.
- **Outro provedor de IA:** subclasse de `AnswerProvider`; manter a validação de `ai_provider.validate`.
