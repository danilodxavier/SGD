# FASE 09 — MVP completo (Sprint S9)

| Campo | Valor |
|---|---|
| Período | 2026-11-17 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | ✅ **Aprovada** em 2026-11-17 |

## 1. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| SAD-090 (RF-21) | **Perguntar**: chat F1/F2 com classificação, confiança, rota e latência; citações `[T…]` clicáveis (abrem o trecho) e fontes com "Ver trecho" e "Abrir documento" (arquivo original); na F2, recomendação, selos dos **6 elementos de RF-20**, alertas, alternativas (prós/contras), riscos (probabilidade × impacto), base legal vigente, normas só históricas, **precedentes** com lição, consensos/divergências, lacunas e **pareceres por agente** (acordeão com validade, afirmações verificadas e fundamentação); relógio de espera para a F2 | `frontend/js/sadgd.js`, `frontend/index.html` |
| SAD-091 (RF-22) | **Acervo**: lista com filtros (texto, tipo, origem), situação da norma, abrir documento, atalho para a linha do tempo; **upload** (Gestor/Administrador) → indexação em segundo plano no servidor → grafo reconstruído → documento na busca; acompanhamento da indexação na tela | `app/interfaces/api/acervo.py`, `app/infrastructure/servico_indexacao.py` |
| SAD-092 (RF-13) | **Linha do tempo**: seletor de processos, fases coloridas, eventos em ordem cronológica, relações com rótulo e **evidência clicável** (trecho que fundamenta a relação), inconsistências | `sadgd.js`, CSS em `frontend/css/app.css` |
| — | **Decisões**: memória de decisões, busca de precedentes, registro de decisão e de resultado (Gestor/Administrador) | `sadgd.js`, `app/interfaces/api/decisoes.py` |
| — | **Painel** do SAD-GD (documentos por origem, trechos, vetores, processos, relações, contradições, normas revogadas, decisões, consultas por rota com latência, última indexação) e "Atualizar índice" com o indexador do SAD-GD | `app/interfaces/api/acervo.py` (`/painel`), `frontend/js/app.js` |
| SAD-093 (RF-23) | **Perfis** Administrador / **Gestor** / Consulta: Gestor registra decisões e envia documentos; reindexar o acervo inteiro só Administrador; Consulta só lê | `app/core/auth.py`, `app/api/deps.py` (`require_gestor`), `frontend/js/users.js` |
| — | API: `GET /api/sadgd/painel`, `GET /api/sadgd/documentos`, `GET /api/sadgd/documentos/{id}/arquivo`, `GET /api/sadgd/trechos/{id}`, `GET /api/sadgd/busca`, `POST /api/sadgd/documentos` (upload), `POST /api/sadgd/indexar`, `GET /api/sadgd/indexacao` | `app/interfaces/api/acervo.py` |
| — | Identidade do produto: SAD-GD 2.0.0.dev0 no título, cabeçalho e rodapé | `index.html`, `app/__init__.py` |

## 2. Segurança e LGPD no MVP

| Risco | Tratamento |
|---|---|
| HTML de terceiros (portal da legislação) executando scripts na origem do sistema | Todo arquivo servido com `Content-Security-Policy: sandbox`, `X-Content-Type-Options: nosniff`, `no-store` |
| Servir arquivos fora do acervo (path traversal) | Caminho resolvido precisa estar **dentro** da raiz documental; teste com registro forjado apontando para fora → 404 |
| Upload malicioso ou excessivo | Só extensões suportadas, ≤ 25 MB, não vazio, nome saneado, **nunca sobrescreve** (sufixo), Gestor/Administrador, auditado |
| Documento real enviado vazando para a nuvem | Upload grava em `corpus/enviados/` com origem **real** (provedor remoto bloqueado pela política da Fase 7); `.gitignore` passou a versionar dentro de `corpus/` **somente** o público, o sintético e os manifestos |

## 3. Defeitos encontrados e corrigidos (transparência)

| Ocorrência | Tratamento |
|---|---|
| Indexar só o arquivo enviado marcaria **todo o resto do acervo como removido** | Modo `parcial` no indexador (teste de regressão) |
| Reconstruir o grafo recria `processos` (ids novos; FK `ON DELETE SET NULL`) → decisões perderiam o vínculo com o processo a cada upload | Migração 005 (`processo_chave`); religação pela chave ao salvar o grafo; o script do grafo agora aplica migrações |
| Painel, indexação e OCR da v1 acionavam o indexador antigo (tabelas v1) | Trocados pelo indexador do SAD-GD |
| Raiz documental lida de lugares diferentes (banco × `.env`) | Serviço usa a mesma função da tela Configurações |
| Construção do grafo só existia como script | Caso de uso `construir_grafo` reutilizado pelo script e pelo serviço |
| CI falhou após o commit da fase: `python-multipart` (upload por formulário) estava instalado no venv local, mas não declarado em `requirements.txt` — um clone limpo com o **mesmo venv** não detecta isso | Dependência declarada; o CI passou a publicar cada teste que falha como **anotação pública** do check run (diagnóstico sem login) |

## 4. Testes

| Tipo | Cobertura | Resultado |
|---|---|---|
| API do acervo | upload → indexação → grafo → busca; origem real; não sobrescrever; arquivo com isolamento; trecho; fora da raiz; formato/vazio; perfis Consulta/Gestor/Admin; painel | 6 testes |
| **E2E no navegador** (Playwright + Microsoft Edge do sistema, headless, servidor uvicorn real) | RF-21 pergunta → resposta → citação abre o trecho → fonte abre o documento original; RF-22 upload → "Concluído" → documento no acervo e na busca; RF-13 fases + evidência da ruptura; F2 com recomendação, 6 elementos, alerta de precedente negativo e pareceres | 4 testes |
| Regressão | indexação parcial; nome do produto | +1 |
| Total | | **465 passando**, cobertura domínio+aplicação **95%**, ruff limpo |

Capturas geradas pelos próprios testes (`SADGD_E2E_CAPTURAS=1`) em `docs/img/fase09/`: `01_perguntar_f1`, `02_trecho_citado`, `03_acervo_upload`, `04_linha_do_tempo`, `05_perguntar_f2`.

Fumaça sobre o banco real (somente leitura): painel com 186 documentos / 5.691 vetores / 31 processos / 30 decisões (22 ligadas a processos); Lei 14.133 (HTML) servida com `sandbox`; linha do tempo do Contrato 012/2023 com 7 eventos; busca e decisões respondendo.

## 5. Critérios de aceite (backlog)

| Item | Critério | Resultado |
|---|---|---|
| SAD-090 | Teste E2E pergunta-resposta-fonte | ✅ no navegador real (Edge) |
| SAD-091 | Documento enviado aparece na busca | ✅ API + E2E |
| SAD-092 | Tela com fases e relações clicáveis | ✅ E2E (evidência da ruptura abre o trecho) |
| SAD-093 | 401/403 corretos por perfil | ✅ testes de API (Consulta 403 em upload/decisão/reindexação; Gestor 403 em reindexação) |

## 6. Para sua decisão

1. **Exclusão de código v1 sem uso** (regra 2: nada é deletado sem aprovação). Saíram do menu, mas o código continua no repositório: telas e scripts *Perguntas (v1)*, *Documentos (v1)*, *Checklist* e *Relatórios* (`frontend/js/search.js`, `documents.js`, `checklist.js`, `reports.js` e as seções correspondentes do `index.html`), as rotas `/api/ask`, `/api/documents`, `/api/checklists`, `/api/reports`, `/api/index` e os serviços da v1 (`app/services/questions.py`, `app/indexing/`…), cujas tabelas foram esvaziadas na Fase 1. Proposta: remover na Fase 10, com tag de backup, se você aprovar.
2. **Identidade visual institucional** herdada da v1 (marca do Governo de MT / SEMA-MT no cabeçalho e rodapé). O produto passou a se chamar SAD-GD, mas a marca institucional foi mantida. Para um trabalho acadêmico, você pode preferir uma identidade neutra ou do IFMT.

## 7. Pendências

1. Latência da F2 (Fase 10).
2. Faithfulness com LLM-juiz (Fase 10); revisão humana do golden set; Kanban depende do `gh`.
3. "Deploy" segue o ADR-001 (execução local via `start.bat`); Vercel/VPS não se aplicam.

## 8. Retrospectiva

- **Bem:** os testes no navegador real pegaram o que testes de API não pegam (aviso repetido, rótulos de status); escrever o serviço de upload revelou dois defeitos latentes graves (remoção do acervo e desvinculação das decisões) antes de chegarem ao usuário.
- **A melhorar:** o frontend v1 ainda carrega telas mortas; a remoção depende da sua aprovação.
- **Ação:** Fase 10 — otimização de latência e tokens, LLM-juiz e avaliação final contra as metas.

## 9. Aprovação

- [x] Aprovado pelo responsável em 2026-11-17 ("Aprovado siga para fase 10"); exclusão do código v1 aprovada com backup; identidade Governo de MT/SEMA mantida
