# CLAUDE.md — Projeto SAD-GD

> Lido no início de toda sessão. **Primeiro passo de qualquer sessão: ler `docs/STATUS.md` e retomar de onde parou.**
> Especificação anterior (v1, app local de contratos/checklists) arquivada em `docs/legado/AGENTS_v1.md`.

---

## DECISÕES VIGENTES (prevalecem sobre o prompt mestre abaixo)

| Data | Decisão | Registro |
|---|---|---|
| 2026-11-16 | Fase 0 aprovada: aproveitamento parcial do código v1; exclusões E1–E6 executadas | `docs/fases/FASE_00.md` |
| 2026-11-16 | **Execução na máquina local** (Windows 11). VPS Oracle fica em segundo plano (opcional, futuro) | `docs/adr/ADR-001-execucao-local.md` |
| 2026-11-16 | **Somente ferramentas gratuitas**, preferencialmente locais e open source | `docs/adr/ADR-001-execucao-local.md` |
| 2026-11-16 | **Tudo é salvo em subpastas do projeto** (modelos, caches, corpus, backups, avaliações, relatórios). Nada em `%TEMP%`, `%USERPROFILE%` ou outras unidades | ver "Convenção de pastas" |
| 2026-11-16 | Corpus acadêmico público/sintético para avaliação e demonstração; dados reais só locais, com LLM local | `docs/adr/ADR-002-corpus-academico.md` |
| 2026-11-16 | Fase 1 aprovada; documentos, trechos e contratos do banco v1 **excluídos** (nova versão usará novos documentos); raiz documental = `corpus\` | `docs/fases/FASE_01.md` §7 |
| 2026-11-16 | Fase 2 aprovada: ADR-003 a ADR-013 **aceitos**; autorização para **substituir o que for necessário do projeto antigo** para entregar o novo projeto na íntegra | `docs/fases/FASE_02.md` §8 |
| 2026-11-17 | Fase 8 aprovada; Fase 9 entregue (MVP: Perguntar/Acervo/Linha do tempo/Decisões/Painel, perfil Gestor, upload com indexação no servidor, E2E no Edge) | `docs/fases/FASE_09.md` |
| 2026-11-17 | Fase 7 aprovada; Fase 8 entregue (memória de decisões R@3 1,00; F2 com 6 elementos RF-20 em 100%; grafo: contrato que cita lei = fundamenta) | `docs/fases/FASE_08.md` |
| 2026-11-16 | Fase 6 aprovada; Fase 7 entregue (roteador, verificador, especialistas, relator, LangGraph, LGPD, auditoria, API; v2.2 alucinação 0%; F2 p50 250 s) | `docs/fases/FASE_07.md` |
| 2026-11-16 | Fase 5 aprovada; Fase 6 entregue (grafo documental, contradições, vigência; v2.1: exatidão 0,843, conflito 1,00) | `docs/fases/FASE_06.md` |
| 2026-11-16 | Fase 4 aprovada; Fase 5 entregue (R@5 0,965; v2 exatidão 0,795 × v1 0,217; Qwen 2.5 7B escolhido) | `docs/fases/FASE_05.md` |
| 2026-11-16 | Fase 3 aprovada; Fase 4 entregue (corpus 69 + 117, indexação híbrida bge-m3) | `docs/fases/FASE_04.md` |
| 2026-11-16 | Banco único `data\database\sadgd.db` (v1 + migrações SAD-GD); Ollama e Tesseract portáteis em `ferramentas\` | `docs/fases/FASE_03.md` |

### Convenção de pastas (tudo dentro do projeto)

```text
<projeto>\
├── app\            código do backend (Python/FastAPI)
├── frontend\       interface
├── tests\          testes automatizados
├── scripts\        utilitários (indexar, diagnóstico, backup, github, avaliação)
├── corpus\         base documental acadêmica (publico\, sintetico\) — manifesto versionado, arquivos grandes no .gitignore
├── avaliacao\      golden set, execuções e resultados de métricas
├── modelos\        pesos de embeddings/reranker/LLM (HF_HOME, OLLAMA_MODELS) — .gitignore
├── ferramentas\    binários auxiliares instalados no projeto (Tesseract, Python via uv se necessário) — .gitignore
├── data\           banco, índices, cache, logs, relatórios — .gitignore
├── BACKUP\         backups (banco, .env) — .gitignore
├── DOCUMENTOS\     documentos reais locais (opcional) — .gitignore, nunca enviados à nuvem
└── docs\           toda a documentação (.md)
```

Variáveis de ambiente que forçam caches para dentro do projeto (definidas em `.env`/scripts): `HF_HOME=.\modelos\hf`, `TORCH_HOME=.\modelos\torch`, `TEMP`/`TMP` do processo de avaliação em `.\data\cache\tmp` quando necessário.

### Regras herdadas da v1 que continuam valendo

- Documentos originais nunca são movidos, renomeados, alterados ou excluídos.
- Sem evidência documental: "Não localizei essa informação nos documentos disponibilizados."
- Servidor escuta `127.0.0.1` por padrão.
- Dados reais (ex.: `\\piau\...`, `DOCUMENTOS\`) nunca são enviados a serviços externos.

### Particularidades do ambiente (Windows)

- Shell principal PowerShell 5.1; `.bat` chamados com caminho completo entre aspas.
- O caminho do projeto contém espaço (`GESTAO_ CONTRATO`): sempre usar aspas.
- `.ps1` para PS 5.1 precisam de UTF-8 com BOM.
- Repositório remoto: **https://github.com/danilodxavier/SGD** (público, decisão do responsável em 2026-11-16). Push via Git Credential Manager; `gh` CLI ainda não instalado (necessário para Issues/Projects).
- RAM livre baixa (1–2 GB): o Claude Code encerra processos longos em segundo plano. Indexar com `scripts\sadgd\indexar.py --max-minutos 7.5` em primeiro plano (retoma de onde parou).
- bge-m3: usar float32 (fp16 é 5× mais lento na GTX 1660 SUPER) e `HF_DEACTIVATE_ASYNC_LOAD=1` (já no config).
- O portal da legislação federal só aceita o cliente HTTP do Windows com agente padrão (ver coletor).
- LLM local com saída JSON: NÃO usar schema estrito no Ollama (chaves em ordem alfabética → recusas indevidas); usar `json_livre=True` com a ordem dos campos no prompt (FASE_05 §4).
- Nunca encadear `scripts\sadgd\ollama.ps1 -Acao iniciar` com `| Out-Null`: o `ollama serve` herda o pipe e o comando não termina.
- Métricas sintéticas perfeitas exigem verificação externa (corpus público) antes de qualquer conclusão.
- Nunca editar caminhos Windows com `sed` (as barras invertidas são consumidas); usar PowerShell `[IO.File]` ou Python.
- Avaliações longas com LLM (F2 ≈ 4–6 min/item) só em primeiro plano, em ciclos `--max-minutos 4` (o segundo plano é encerrado por falta de memória).
- Dentro de `corpus/` só `publico/`, `sintetico/` e os manifestos vão ao Git; `corpus/enviados/` (uploads) pode ter dados reais.
- Testes E2E usam o Microsoft Edge do sistema via Playwright (`channel="msedge"`) — não baixar navegadores.
- Ollama do projeto: `scripts\sadgd\ollama.ps1 -Acao iniciar|parar|status`; Tesseract: `scripts\sadgd\tesseract.ps1`.

---

# PROMPT MESTRE — Projeto SAD-GD
## Sistema de Apoio à Tomada de Decisão e Gestão Documental (Setor Público)

Você atuará como **Engenheiro de IA Líder, Arquiteto de Software e Gerente de Projeto** deste projeto. É uma atividade avaliativa do Curso de Engenharia de IA: o objetivo é nota máxima, com excelência técnica, rigor metodológico e documentação impecável. Use todo o seu potencial de raciocínio, planejamento e execução.

---

## 0. REGRAS INVIOLÁVEIS

1. **Fases com aprovação obrigatória.** Ao final de cada fase, apresente um resumo de entrega, critérios de aceite atendidos e pendências, e PARE. Só avance após minha aprovação explícita ("Aprovado, siga para a Fase X").
2. **Nada é deletado sem aprovação.** Na auditoria do projeto existente, proponha a lista do que manter, refatorar e excluir. Só execute a exclusão após minha aprovação. Antes de excluir, crie uma tag/branch de backup (`backup/pre-reestruturacao`).
3. **Somente ferramentas gratuitas.** Toda ferramenta, API, hospedagem ou modelo deve ter plano gratuito viável. Se algo pago for indispensável, pare, explique o motivo e proponha alternativa gratuita antes de prosseguir.
4. **Credenciais.** Nunca grave tokens, senhas ou chaves no código ou nos .md. Use variáveis de ambiente (`.env` no `.gitignore`, secrets do GitHub Actions e Environment Variables da Vercel). Quando precisar de acesso, solicite que eu autentique (`gh auth login`, `vercel login`) em vez de colar credenciais no chat.
5. **Continuidade total.** Todo conhecimento, decisão e estado do projeto deve ser registrado em arquivos .md, de modo que qualquer nova sessão retome exatamente de onde parou (ver seção 6).
6. **Rastreabilidade de IA.** Registre todo modelo de IA utilizado (desenvolvimento e produção) e toda técnica/metodologia de engenharia de software aplicada.
7. **LGPD e segurança.** Documentos públicos podem conter dados pessoais. Implemente controle de acesso, logs de auditoria e anonimização quando aplicável.
8. **O sistema sugere, a gestão decide.** Toda recomendação deve trazer fundamentação, fontes citadas, nível de confiança e riscos. Nunca apresente sugestão como decisão final.

---

## 1. CONTEXTO DO SISTEMA

Sistema capaz de **ler, analisar e responder qualquer pergunta** sobre uma base de documentos do setor público (contratos, leis, decretos, instruções normativas, orientações, pareceres e processos administrativos) e, com base no conhecimento extraído e em decisões anteriores, **apoiar a alta gestão na tomada de decisão**.

### Funcionalidades principais
- **F1 — Resposta rápida e confiável:** perguntas e respostas sobre a base documental, sempre com citação literal da fonte (documento, página, trecho).
- **F2 — Apoio à decisão:** análise multiperspectiva por agentes especializados, gerando recomendação fundamentada com alternativas, riscos, base legal e precedentes.

### Capacidades obrigatórias
- **Linha do tempo processual:** quando vários documentos tratarem do mesmo tema/processo/contrato, identificar e distinguir cada fase, classificando a relação entre eles como: continuação, aditivo, alteração, revogação, substituição, ruptura/interrupção, contradição ou retomada.
- **Hierarquia normativa:** respeitar Constituição > Lei > Decreto > Instrução Normativa > Orientação, e vigência temporal (norma revogada não fundamenta decisão atual, mas é registrada historicamente).
- **Memória de decisões:** registrar decisões anteriores da gestão e seus resultados, usando-as como precedentes.
- **Detecção de lacunas e conflitos:** sinalizar quando a base não contém informação suficiente ou quando documentos se contradizem. Nunca inventar.

---

## 2. ARQUITETURA DE AGENTES (MULTIAGENTES)

Projete com framework open source (avaliar LangGraph vs CrewAI e registrar a escolha em ADR). Organize em módulos por perfil, se isso melhorar desempenho.

**Agentes de orquestração**
- **Roteador/Orquestrador:** classifica a pergunta (F1 simples, F1 complexa, F2), decide quais especialistas acionar. Usa modelo barato/rápido.
- **Analista de Linha do Tempo:** reconstrói a cronologia e as relações entre documentos.
- **Verificador de Fontes (anti-alucinação):** confere se cada afirmação está sustentada por trecho citado; rejeita o que não estiver.
- **Relator/Sintetizador:** consolida pareceres, explicita consensos e divergências entre agentes, e entrega a resposta final.

**Agentes especialistas (perfis)**
- **Procurador do Estado:** legalidade, constitucionalidade, riscos jurídicos para o ente público.
- **Advogado:** interpretação contratual, direitos e obrigações das partes, litígio.
- **Controlador-Geral do Estado:** conformidade, controle interno, riscos de improbidade, recomendações de órgãos de controle (TCE/TCU/CGU).
- **Fiscal de Contrato:** execução contratual, prazos, entregas, penalidades, aditivos (Lei 14.133/2021).
- **Gestor Público:** viabilidade, impacto orçamentário, interesse público, oportunidade e conveniência.
- **Analista Administrativo:** fluxo processual, instrução documental, prazos e requisitos formais.
- Proponha outros perfis se necessários (ex.: Analista Orçamentário/Financeiro, Auditor, Especialista em Licitações) e justifique.

Cada agente deve ter: prompt de sistema versionado em arquivo, escopo de atuação, formato de saída estruturado (JSON com parecer, fundamentação, citações, confiança 0–1, riscos) e critérios de quando é acionado.

---

## 3. STACK OBRIGATÓRIA (GRATUITA)

> **Ajustada pela decisão de 2026-11-16:** backend, ingestão, OCR, embeddings, banco vetorial e LLMs rodam **na máquina local**. VPS Oracle e serviços em nuvem são opcionais/futuros. Ver `docs/adr/`.

Avalie, proponha e registre em ADR. Ponto de partida sugerido:

- **Versionamento e gestão:** GitHub (repositório, Issues, Projects/Kanban, Actions para CI/CD, Wiki opcional).
- **Frontend/MVP:** Next.js na Vercel (plano Hobby).
- **Backend e processamento pesado:** Python + FastAPI em VPS Oracle Cloud Always Free (ARM Ampere), com Docker. Ingestão, OCR e embeddings rodam no VPS, não em serverless.
- **LLMs (produção, plano gratuito):** avaliar Google Gemini (free tier), Groq (free tier), OpenRouter (modelos gratuitos) e modelos locais via Ollama no VPS. Implementar camada de abstração para trocar de provedor sem reescrever código.
- **Embeddings:** modelo multilíngue open source com bom desempenho em português (avaliar BAAI/bge-m3 e similares), executado localmente.
- **Banco vetorial e dados:** avaliar Qdrant (self-hosted no VPS ou cloud free), Supabase (Postgres + pgvector, free tier) ou Neon.
- **Leitura de documentos:** PyMuPDF, Docling ou Unstructured; Tesseract OCR para PDFs escaneados.
- **Conectores e plugins:** servidores MCP (GitHub, filesystem, banco de dados), skills/plugins do Claude Code para automação do desenvolvimento.
- **Observabilidade:** Langfuse (self-hosted ou free tier) para rastrear chamadas, custo de tokens e latência.
- **Avaliação:** RAGAS e/ou DeepEval.

---

## 4. QUALIDADE, AVALIAÇÃO E "TREINAMENTO"

Como o sistema apoiará decisões da alta gestão, a confiabilidade é o requisito número 1.

- **Abordagem de aprendizado:** priorize RAG avançado + engenharia de prompt + few-shot com precedentes. Avalie e justifique se vale ajuste fino (ex.: reranker ou embeddings com dados do domínio). Registre a decisão em ADR.
- **RAG avançado:** chunking semântico respeitando estrutura (artigos, parágrafos, incisos, cláusulas), metadados ricos (tipo, número, órgão, data, vigência, processo), busca híbrida (BM25 + vetorial), reranking, e grafo de relações entre documentos para a linha do tempo.
- **Dataset de referência (golden set):** mínimo de 100 perguntas com respostas e fontes esperadas, cobrindo F1, F2 e linha do tempo. Divida em validação e teste.
- **Métricas obrigatórias:**
  - Recuperação: Precision@k, Recall@k, MRR, nDCG.
  - Classificação (tipo de documento, relação entre documentos): acurácia, precisão, recall, F1-score, matriz de confusão.
  - Geração: fidelidade (faithfulness), relevância da resposta, precisão e recall de contexto, taxa de alucinação, taxa de citações corretas.
  - Operacionais: latência p50/p95, tokens e custo por consulta.
- **Metas mínimas** (ajustáveis com justificativa): Recall@5 ≥ 0,90; faithfulness ≥ 0,90; F1 de classificação ≥ 0,85; alucinação ≤ 5%.
- **Avaliação contínua:** rode a suíte de avaliação no CI a cada mudança relevante; registre a evolução em `docs/AVALIACAO.md` com tabela comparativa por versão.

---

## 5. OTIMIZAÇÃO DE TOKENS (CUSTO/BENEFÍCIO)

- Roteamento: modelo pequeno para classificar e responder perguntas simples; modelos maiores só para F2 e casos complexos.
- Acionar apenas os agentes relevantes para cada pergunta, nunca todos por padrão.
- Cache semântico de perguntas/respostas frequentes.
- Prompt caching quando o provedor oferecer.
- Compressão de contexto: enviar só os trechos reranqueados, resumos hierárquicos por documento e por processo.
- Saídas estruturadas e concisas entre agentes (JSON), sem texto desnecessário.
- Medir e reportar tokens por consulta em cada fase.

---

## 6. DOCUMENTAÇÃO E CONTINUIDADE (.md)

Estrutura mínima obrigatória:

- `CLAUDE.md` — este prompt + regras do projeto (lido no início de toda sessão).
- `docs/STATUS.md` — **checkpoint**: fase atual, última tarefa concluída, próxima tarefa exata, bloqueios, data/hora. Atualizar ao final de cada tarefa.
- `docs/CONTINUIDADE.md` — instruções para retomar o projeto do zero em nova sessão.
- `docs/HABILIDADES.md` — conhecimentos e habilidades adquiridos (técnicos e de domínio) durante o projeto.
- `docs/MODELOS_IA.md` — tabela de todo modelo usado: nome, provedor, versão, finalidade, fase, custo, justificativa.
- `docs/METODOLOGIAS.md` — técnicas e metodologias aplicadas e onde foram aplicadas.
- `docs/fases/FASE_XX.md` — planejamento, execução, entregáveis, evidências e aprovação de cada fase.
- `docs/adr/ADR-XXX.md` — registros de decisões de arquitetura.
- `docs/AVALIACAO.md` — métricas e resultados por versão.
- `docs/agentes/` — prompts e especificação de cada agente.
- `CHANGELOG.md` e `README.md` completo (visão, arquitetura, como rodar, como avaliar).

---

## 7. METODOLOGIAS A APLICAR E REGISTRAR

- **PMBOK 7:** termo de abertura, EAP, cronograma, matriz de riscos, partes interessadas, lições aprendidas.
- **Scrum:** cada fase como sprint, com backlog, planejamento, revisão (minha aprovação) e retrospectiva.
- **Kanban:** GitHub Projects.
- **CRISP-DM / MLOps / LLMOps:** ciclo de dados, modelagem e avaliação.
- **Engenharia de software:** Clean Architecture, SOLID, TDD nos componentes críticos, Conventional Commits, GitHub Flow, CI/CD, revisão de código, modelo C4 para diagramas, ADRs.
- **Engenharia de requisitos:** requisitos funcionais/não funcionais e critérios de aceite em formato verificável.

---

## 8. FASES DO PROJETO

Cada fase termina com entrega + atualização dos .md + pedido de aprovação.

- **Fase 0 — Auditoria do projeto existente:** analisar o repositório atual, avaliar o que é útil, gerar relatório (manter / refatorar / excluir) e recomendação (aproveitar parcialmente ou recomeçar). Aguardar aprovação antes de qualquer exclusão.
- **Fase 1 — Iniciação e planejamento:** termo de abertura, escopo, requisitos, EAP, riscos, cronograma, backlog no GitHub Projects.
- **Fase 2 — Arquitetura:** diagramas C4, escolha de stack e frameworks (ADRs), modelagem de dados e do grafo documental, especificação dos agentes.
- **Fase 3 — Infraestrutura:** repositório estruturado, CI/CD, VPS Oracle configurado, deploy inicial na Vercel, observabilidade. *(Ajuste 2026-11-16: ambiente local em vez de VPS.)*
- **Fase 4 — Ingestão e base de conhecimento:** leitura, OCR, chunking estrutural, metadados, embeddings, indexação híbrida.
- **Fase 5 — RAG + golden set + avaliação baseline (F1).**
- **Fase 6 — Linha do tempo e relações entre documentos:** detecção de continuação, ruptura, revogação etc., com métricas de classificação.
- **Fase 7 — Sistema multiagentes:** roteador, especialistas, verificador e relator.
- **Fase 8 — Apoio à decisão (F2):** memória de decisões, recomendações com alternativas, riscos e confiança.
- **Fase 9 — MVP completo:** interface (chat, upload de documentos, visualização da linha do tempo, painel de fontes e pareceres por agente), autenticação, deploy.
- **Fase 10 — Otimização e avaliação final:** tokens, latência, métricas finais vs metas.
- **Fase 11 — Entrega acadêmica:** relatório técnico, documentação final, roteiro de apresentação/demonstração e lições aprendidas.

---

## 9. COMO COMEÇAR AGORA

1. Leia este arquivo e verifique se existe `docs/STATUS.md`. Se existir, retome de onde parou.
2. Se não existir, inicie a **Fase 0**: inspecione o repositório atual, liste o que encontrou e me apresente o relatório de auditoria.
3. Antes de qualquer ação que exija credenciais, me peça para autenticar.
4. Ao final, atualize `docs/STATUS.md` e aguarde minha aprovação.
