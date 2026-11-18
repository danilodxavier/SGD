# Relatório de atividades e ferramentas — SAD-GD

**Sistema de Apoio à Tomada de Decisão e Gestão Documental (Setor Público) — SEMA-MT**
Atividade avaliativa do Curso de Engenharia de IA · Data: 2026-11-17 · Repositório: https://github.com/danilodxavier/SGD

> Este relatório descreve **cada atividade e ferramenta** usada no projeto, **o que foi feito**, **onde está a evidência** e **qual a relevância** para o curso e para o sistema. Tudo o que está aqui pode ser conferido no repositório (commits, `docs/`, `avaliacao/`). Onde uma ferramenta prevista **não** foi usada, o motivo está registrado (não há omissão).

---

## 1. Resumo executivo

O SAD-GD lê e responde perguntas sobre contratos, leis, decretos, instruções normativas, pareceres e processos, **sempre citando o trecho literal da fonte**, e apoia a alta gestão com **pareceres de agentes especialistas** (Procurador, Advogado, Controlador, Fiscal de Contrato, Gestor, Analista). Foi construído em 12 fases (0 a 11), cada uma com entrega, evidências e aprovação do responsável.

| Indicador final (conjunto de teste) | Meta | Resultado |
|---|---|---|
| Recall@5 da busca | ≥ 0,90 | **0,965** |
| Faithfulness (fidelidade às fontes) | ≥ 0,90 | **0,964** (adjudicada) |
| Alucinação numérica / por frase | ≤ 5% | **0%** / 5,4% |
| Classificação de tipo documental | ≥ 0,85 | **1,00** |
| Roteamento de perguntas | ≥ 0,90 | **0,935** |
| Precedentes (Recall@3) | ≥ 0,80 | **1,00** |
| Custo por consulta | gratuito | **R$ 0** (tudo local) |

Números de base: 186 documentos, 5.691 trechos vetorizados, 96 normas, 316 testes automatizados + 4 E2E no navegador, cobertura de 96% nas camadas de domínio e aplicação (Fase 10), mais de 35 commits, 13 ADRs.

---

## 2. Visão geral das atividades por fase

| Fase | Atividade | Entregável principal | Relevância |
|---|---|---|---|
| 0 | Auditoria do app v1 (manter/refatorar/excluir) com backup antes de excluir | `docs/fases/FASE_00.md`, tag `v1.0.0-pre-reestruturacao` | Engenharia de software responsável: nada se perde, tudo é reversível |
| 1 | Iniciação e planejamento (PMBOK 7, Scrum) | Termo de abertura, EAP, riscos, cronograma, requisitos, backlog | Gestão de projetos aplicada a IA |
| 2 | Arquitetura (C4, 11 ADRs, modelo de dados, especificação dos agentes) | `docs/arquitetura/`, `docs/adr/` | Decisões justificadas por critério e evidência |
| 3 | Infraestrutura local, Clean Architecture, CI no GitHub Actions | `.github/workflows/ci.yml`, `app/` | Reprodutibilidade e qualidade contínua |
| 4 | Ingestão: corpus acadêmico, OCR, chunking por artigo/cláusula, indexação híbrida | `corpus/`, `app/application/ingestao/` | CRISP-DM: dados de qualidade com proveniência |
| 5 | RAG (BM25 + vetorial + reranker), golden set de 100+ perguntas, baseline | `avaliacao/`, `docs/AVALIACAO.md` | Medição científica: v2 0,795 × v1 0,217 de exatidão |
| 6 | Linha do tempo e grafo documental (aditivo, revogação, contradição…) | `app/application/linha_do_tempo/` | Capacidade exigida: distinguir fases de um processo |
| 7 | Sistema multiagentes (LangGraph), verificador anti-alucinação, LGPD, auditoria | `app/application/agentes/` | Núcleo de IA agêntica do curso |
| 8 | Apoio à decisão (F2): memória de decisões, precedentes, recomendação com 6 elementos | `app/application/decisoes/` | "O sistema sugere, a gestão decide" |
| 9 | MVP: telas Perguntar, Acervo, Linha do tempo, Decisões; perfis; upload; E2E | `frontend/`, `tests/sadgd/test_e2e_navegador.py` | Produto utilizável pelo servidor público |
| 10 | Otimização: cache semântico, LLM-juiz calibrado, experimentos de latência | `docs/fases/FASE_10.md` | LLMOps: métricas finais × metas |
| 11 | Entrega acadêmica: relatórios, manuais, vídeo, provedor Gemini opcional | este documento, `docs/video/` | Comunicação dos resultados |

---

## 3. Ferramentas e atividades — descrição e relevância

### 3.1 GitHub (repositório, versionamento, CI/CD)

**O que foi feito**
- Repositório público `danilodxavier/SGD` com **GitHub Flow** e **Conventional Commits** (`feat`, `fix`, `docs`, `perf`, `refactor!`, `ci`).
- **Tags e branch de backup** antes de toda mudança destrutiva: `v1.0.0-pre-reestruturacao`, `backup/pre-reestruturacao`, `backup/pre-limpeza-v1`.
- **GitHub Actions** (`.github/workflows/ci.yml`) a cada push:
  1. varredura de segredos com **gitleaks** no histórico completo;
  2. **lint** com ruff (pycodestyle, pyflakes, isort, bugbear, bandit…);
  3. **testes** automatizados no Windows;
  4. **portão de cobertura** mínima das camadas domínio/aplicação (RNF-09);
  5. **avaliação de regressão de qualidade** (BM25 no corpus sintético com piso calibrado).
- Testes que falham viram **anotações públicas** do check run, permitindo diagnóstico sem login.
- **GitHub Projects (Kanban)** publicado em https://github.com/users/danilodxavier/projects/2: 52 issues do backlog com labels por fase/épico/prioridade, milestones por fase e comentário de evidência em cada item, geradas por `scripts/github/criar_backlog.ps1` com o `gh` portátil (`ferramentas/gh`), autorizado pelo responsável no navegador.

**Relevância** — Para o curso: prática real de MLOps/LLMOps (qualidade de IA verificada automaticamente, não só código). Para o sistema: nenhuma mudança entra sem testes e sem varredura de credenciais; tudo é auditável e reversível.

### 3.2 Vercel (frontend em nuvem) — avaliada, adiada por decisão registrada

**O que foi feito** — Avaliação formal em `docs/adr/ADR-008-frontend.md` e `ADR-001-execucao-local.md`. Com o backend em `127.0.0.1` e dados públicos podendo conter dados pessoais (LGPD), um frontend na Vercel exigiria túnel público até a máquina local. Decisão: interface em HTML/CSS/JS servida pelo próprio FastAPI, com o padrão visual do Governo de MT e acessibilidade; Vercel e VPS Oracle ficaram como **perfil de implantação futuro**, já previsto na arquitetura (portas e adaptadores).

**Relevância** — Mostra uma competência central de engenharia: **dizer não com justificativa** quando a ferramenta sugerida conflita com requisitos de segurança e custo. A decisão é rastreável (ADR) e reversível.

### 3.3 Markdown — documentação como código e memória do projeto

**O que foi feito** — Toda a documentação está em `.md`, versionada junto com o código:
- `CLAUDE.md` (regras lidas no início de toda sessão), `docs/STATUS.md` (checkpoint), `docs/CONTINUIDADE.md` (retomar do zero);
- `docs/fases/FASE_00..10.md` (planejamento, execução, evidências e aprovação de cada sprint);
- 13 ADRs (`docs/adr/`), C4 e modelo de dados (`docs/arquitetura/`), documentos PMBOK (`docs/projeto/`);
- `MODELOS_IA.md`, `METODOLOGIAS.md`, `HABILIDADES.md`, `AVALIACAO.md`, manuais do usuário e técnico, `CHANGELOG.md`, `README.md`;
- prompts dos agentes versionados em Markdown (`app/application/agentes/prompts/*.md`).

**Relevância** — Garante **continuidade total**: qualquer sessão nova (humana ou de IA) retoma exatamente de onde parou. Os próprios prompts de IA são artefatos versionados e testados (teste de contrato prompt × schema).

### 3.4 Claude Code — agente de engenharia de IA

**O que foi feito** — O desenvolvimento foi conduzido com o **Claude Code** (modelo `claude-opus-5-5`, registrado em `docs/MODELOS_IA.md`) atuando como engenheiro de IA, arquiteto e gerente de projeto sob regras explícitas: fases com aprovação obrigatória, nada excluído sem aprovação, somente ferramentas gratuitas, credenciais nunca no chat ou no código.

Recursos do Claude Code usados no projeto:

| Recurso | Uso no projeto |
|---|---|
| `CLAUDE.md` do projeto | "Prompt mestre" + decisões vigentes + particularidades do ambiente Windows; carregado em toda sessão |
| **Memória persistente** (auto-memória) | Fatos entre sessões (ex.: responder em português; como testar com banco isolado) |
| **Skills** (habilidades empacotadas) | Catálogo disponível na sessão: ADR/arquitetura (`engineering:architecture`), revisão de código, estratégia de testes, documentação, geração de documentos (docx/pdf/pptx). Usadas como roteiros de trabalho padronizados |
| **Plugins** | Plugin `engineering` instalado (agrupa skills e conectores de engenharia) |
| **Subagentes** | Exploração e verificação em paralelo sem poluir o contexto principal |
| **Hooks/permissões** | Execução sob modo de permissão escolhido pelo responsável; ações destrutivas sempre confirmadas |

**Relevância** — Para o curso: demonstra **engenharia assistida por IA com governança** — a IA trabalha com regras, rastreabilidade e aprovação humana a cada fase. Para o sistema: velocidade de desenvolvimento sem abrir mão de testes, ADRs e documentação.

### 3.5 MCP (Model Context Protocol) e conectores

**O que foi feito**
- Servidores MCP disponíveis no ambiente de desenvolvimento: **navegador embutido** (validação visual da interface e leitura de páginas), **Claude in Chrome**, **terminal**, **registro de conectores MCP**, **tarefas agendadas** e **Claude Docs**.
- Conectores do plugin `engineering` (GitHub, Slack, Notion, Linear, Asana, Atlassian…) estão disponíveis, mas **exigem autorização OAuth do responsável** — por regra do projeto, credenciais nunca são passadas no chat. Por isso o GitHub foi operado via `git` + Git Credential Manager e a API pública (consulta do CI com intervalo ≥ 40 s por causa do limite de 60 req/h).
- No sistema SAD-GD, o equivalente a "conectores" são as **portas e adaptadores** da Clean Architecture: provedor de LLM (Ollama local ↔ Gemini), OCR (Tesseract ↔ Windows OCR), fonte de arquivos, banco (SQLite). Trocar de provedor não exige reescrever o código.

**Relevância** — MCP é o padrão aberto que liga agentes de IA a ferramentas e dados. O projeto aplica o mesmo princípio internamente (abstração de provedores) e respeita a fronteira de segurança: nenhum dado real sai da máquina.

### 3.6 Sistema multiagentes de IA (LangGraph)

**O que foi feito** — Escolha do **LangGraph** contra CrewAI por matriz de decisão ponderada (`ADR-003`). Grafo de estados em `app/application/agentes/orquestrador.py`:

```text
Pergunta → Roteador (F1 simples | F1 complexa | F2)
   F1: Recuperação híbrida → Redação → Verificador de Fontes → Resposta com citações
   F2: Recuperação + Linha do tempo + Precedentes
        → Especialistas em paralelo (fan-out com Send): Procurador, Advogado,
          Controlador-Geral, Fiscal de Contrato, Gestor Público, Analista Administrativo
        → Relator (consensos, divergências, alternativas, riscos, confiança)
```

- Cada agente tem **prompt versionado**, **JSON Schema** de saída (parecer, fundamentação, citações, confiança 0–1, riscos) e critério de acionamento — só os agentes relevantes são chamados (economia de tokens).
- **Verificador anti-alucinação determinístico**: frase sem trecho que a sustente é removida; número que não está na fonte é rejeitado (alucinação numérica 0%).
- **Regras determinísticas** para o que é verificável: hierarquia normativa (Constituição > Lei > Decreto > IN > Orientação), vigência (norma revogada não fundamenta), precedentes.

**Relevância** — É o coração do curso de Engenharia de IA: orquestração, saídas estruturadas, anti-alucinação, avaliação. Para a gestão: análise multiperspectiva que antes exigia reunir vários setores.

### 3.7 Modelos de IA (todos gratuitos)

| Modelo | Função | Onde roda |
|---|---|---|
| Qwen 2.5 7B Instruct (Q4) via **Ollama** | Redação, especialistas, relator | Local (GPU 6 GB) |
| **BAAI/bge-m3** | Embeddings multilíngues (1024 dims) | Local |
| **BAAI/bge-reranker-v2-m3** | Reranking (R@5 0,748 → 0,965) | Local |
| Llama 3.1 8B | Juiz de faithfulness (outra família, calibrado κ 0,71) | Local |
| Qwen 2.5 3B | Avaliado e rejeitado (sem conteúdo em 13/14 pareceres) | Local |
| **Tesseract 5** (`por`) | OCR de PDFs escaneados (CER 0,09%) | Local |
| Google Gemini (plano gratuito) | Opcional para F2 **só com corpus acadêmico anonimizado** | Nuvem, com chave no `.env` |

**Relevância** — Benchmark comparativo sob o mesmo protocolo, escolha por evidência e **custo zero por consulta**.

### 3.8 RAG avançado e base de conhecimento

Chunking estrutural (artigo, parágrafo, inciso, cláusula), metadados ricos (tipo, número, órgão, data, vigência, processo), busca **híbrida BM25 + vetorial** com fusão RRF e **reranker**, grafo de relações entre documentos (continuação, aditivo, alteração, revogação, substituição, ruptura, contradição, retomada). Corpus com proveniência (`corpus/MANIFESTO.csv`, SHA-256, licença).

**Relevância** — Confiabilidade é o requisito nº 1 para apoiar a alta gestão: toda resposta traz documento, página e trecho.

### 3.9 Avaliação científica (LLMOps)

Golden set com 100+ perguntas (validação 30% / teste 70%, teste nunca usado para ajuste), métricas de recuperação (P@k, R@k, MRR, nDCG), classificação (P/R/F1, matriz de confusão), geração (faithfulness, alucinação, citações) e operacionais (latência p50/p95, tokens). LLM-juiz **calibrado** com respostas corrompidas de propósito, correção de Rogan–Gladen e **adjudicação humana** das discordâncias.

**Relevância** — Diferencia um protótipo de um sistema confiável: cada afirmação de qualidade tem número, protocolo e arquivo de evidência.

### 3.10 Segurança e LGPD

Controle de acesso por papéis (Administrador, Gestor, Consulta), servidor em `127.0.0.1`, **pseudonimização** (nomes 1,00; CPF 100%) antes de qualquer envio remoto, política por origem do corpus (dados reais nunca saem da máquina), **auditoria** com hash da pergunta, defesa em profundidade nos arquivos (confinamento, CSP, validação de upload), gitleaks no CI.

**Relevância** — Requisito legal para o setor público e boa prática de IA responsável.

### 3.11 Interface (MVP) e testes ponta a ponta

Telas **Perguntar** (F1/F2 com trecho citado), **Acervo** (upload com indexação no servidor), **Linha do tempo**, **Decisões** e **Painel**; padrão visual do Governo de MT; testes E2E com **Playwright** no Microsoft Edge do sistema (capturas em `docs/img/fase09/`).

### 3.12 Metodologias de gestão e engenharia

PMBOK 7 (termo de abertura, EAP, riscos, partes interessadas, lições aprendidas), **Scrum** (fase = sprint, revisão = aprovação), **Kanban**, **CRISP-DM**, **Clean Architecture/SOLID** verificada por teste de AST, **TDD** nas regras críticas, **C4**, **ADRs**, matriz de rastreabilidade requisito → ADR → componente → teste. Lista completa em `docs/METODOLOGIAS.md`.

---

## 4. Relevância para a SEMA-MT

| Necessidade da gestão | O que o SAD-GD entrega |
|---|---|
| Encontrar rapidamente a cláusula, o artigo ou o aditivo certo | Resposta em segundos com citação literal (documento, página, trecho) |
| Saber em que fase está um contrato/processo | Linha do tempo com aditivos, suspensões, retomadas, revogações e contradições |
| Decidir com segurança jurídica | Pareceres de 6 perfis especialistas + alternativas, riscos, base legal, precedentes e nível de confiança |
| Não depender de memória individual | Memória de decisões anteriores usada como precedente |
| Proteger dados e cumprir a LGPD | Execução local, perfis de acesso, anonimização e trilha de auditoria |
| Orçamento restrito | Somente ferramentas gratuitas e open source: R$ 0 por consulta |

**Princípio inegociável:** o sistema **sugere**, a gestão **decide**. Sem evidência, a resposta é "Não localizei essa informação nos documentos disponibilizados."

---

## 5. Limitações declaradas

- Latência da F2 local (p50 ≈ 5 min) limitada pela GPU de 6 GB; mitigação: cache semântico (5 ms em repetições) e opção Gemini para o corpus acadêmico, que levou a F2 a p50 30 s / p95 100 s (meta ≤ 120 s) sem perda de qualidade estrutural (`docs/AVALIACAO.md`, Fase 11).
- Alucinação por frase 5,4% (meta 5%) — margem pequena, adjudicação pendente de confirmação humana.
- F1 = 1,00 nas relações do corpus sintético indica sobreajuste declarado; no corpus público, 10/10 relações oficiais.
- Conectores OAuth do plugin `engineering` (Slack, Notion etc.) não foram autorizados — não eram necessários ao projeto.
- Vercel/VPS não implantados (decisão ADR-001/008).

---

## 6. Referências internas

`docs/STATUS.md` · `docs/fases/` · `docs/adr/` · `docs/AVALIACAO.md` · `docs/MODELOS_IA.md` · `docs/METODOLOGIAS.md` · `docs/HABILIDADES.md` · `docs/MANUAL_DO_USUARIO.md` · `docs/MANUAL_TECNICO.md` · `docs/video/` (roteiro e vídeo de apresentação)
