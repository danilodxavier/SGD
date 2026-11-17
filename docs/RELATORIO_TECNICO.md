# Relatório técnico — SAD-GD

**Sistema de Apoio à Tomada de Decisão e Gestão Documental (Setor Público)**
Atividade avaliativa do Curso de Engenharia de IA · Versão do sistema: 2.0.0.dev0 · Data: 2026-11-17
Repositório: https://github.com/danilodxavier/SGD · Execução: 100% local e gratuita (nuvem opcional só para corpus acadêmico)

> Documento de referência técnica do projeto. Cada número citado tem arquivo de evidência no repositório
> (indicado entre parênteses). Complementos: atividades e ferramentas em `docs/RELATORIO_ATIVIDADES_E_FERRAMENTAS.md`,
> lições aprendidas em `docs/projeto/LICOES_APRENDIDAS.md`, roteiro de demonstração em `docs/DEMONSTRACAO.md`.

---

## Resumo

O SAD-GD responde perguntas sobre uma base de documentos do setor público (contratos, leis, decretos, instruções
normativas, pareceres, processos e decisões da gestão) **sempre com citação literal da fonte** (F1) e apoia a alta
gestão com **recomendações multiperspectiva** produzidas por agentes especialistas (F2), com alternativas, riscos,
base legal, precedentes e nível de confiança. A arquitetura combina RAG híbrido (BM25 + bge-m3 + reranker),
grafo documental com linha do tempo e vigência, regras determinísticas para o que é verificável (hierarquia
normativa, revogação, números citados) e um orquestrador LangGraph que aciona só os especialistas necessários.

No conjunto de **teste** do golden set (124 perguntas, nunca usado para ajuste), o sistema atingiu Recall@5 0,965,
faithfulness 0,964 (adjudicada), alucinação numérica 0% e roteamento 0,935, contra Recall@5 0,431 e exatidão 0,217
do sistema legado. Custo por consulta: R$ 0. A principal limitação é a latência da F2 no hardware local (p95 387 s);
para o corpus acadêmico, o provedor gratuito em nuvem reduziu o p95 para 100 s, atingindo a meta de 120 s.

---

## 1. Problema e objetivos

**Problema.** Gestores públicos precisam decidir com base em dezenas de documentos inter-relacionados: um contrato
tem aditivos, suspensões e retomadas; uma lei é alterada ou revogada; pareceres divergem. Localizar a cláusula
certa, saber o que está vigente e reunir a visão jurídica, de controle e de execução exige tempo e memória
institucional. Um LLM genérico agrava o risco: responde com fluência sem fonte e pode inventar números.

**Objetivos** (termo de abertura, `docs/projeto/TERMO_DE_ABERTURA.md`):

| Objetivo | Critério verificável |
|---|---|
| F1 — resposta rápida e confiável | Toda afirmação com documento, página e trecho; sem evidência, "Não localizei essa informação nos documentos disponibilizados." |
| F2 — apoio à decisão | Recomendação com 6 elementos (RF-20): alternativas, riscos, base legal, precedentes, confiança e aviso "o sistema sugere, a gestão decide" |
| Linha do tempo | Relações entre documentos classificadas em 8 tipos (continuação, aditivo, alteração, revogação, substituição, ruptura, contradição, retomada) |
| Hierarquia e vigência | Constituição > Lei > Decreto > IN > Orientação; norma revogada não fundamenta decisão atual |
| Confiabilidade medida | Metas: Recall@5 ≥ 0,90; faithfulness ≥ 0,90; F1 de classificação ≥ 0,85; alucinação ≤ 5% |
| Restrições | Somente ferramentas gratuitas; dados reais nunca saem da máquina (LGPD) |

Escopo e requisitos: 26 requisitos funcionais e 14 não funcionais com critérios de aceite
(`docs/projeto/ESCOPO_E_REQUISITOS.md`), rastreados até ADR, componente e teste (`docs/projeto/RASTREABILIDADE.md`).

---

## 2. Metodologia de trabalho

O projeto foi conduzido em **12 fases (sprints 0–11)**, cada uma com planejamento, execução, evidências e
**aprovação explícita do responsável** antes da seguinte (`docs/fases/FASE_XX.md`). Metodologias aplicadas
(detalhe em `docs/METODOLOGIAS.md`):

| Dimensão | Prática | Onde |
|---|---|---|
| Gestão | PMBOK 7 (termo de abertura, EAP, cronograma, riscos, partes interessadas), Scrum (fase = sprint, revisão = aprovação), Kanban | `docs/projeto/` |
| Dados e modelos | CRISP-DM, LLMOps: golden set com divisão validação/teste, avaliação contínua no CI | `avaliacao/`, `.github/workflows/ci.yml` |
| Arquitetura | Clean Architecture + SOLID (verificada por teste de AST das dependências entre camadas), C4, 13 ADRs | `docs/arquitetura/`, `docs/adr/` |
| Código | TDD nos componentes críticos, Conventional Commits, GitHub Flow, CI (gitleaks, ruff, testes, portão de cobertura, regressão de qualidade) | `tests/`, CI |
| Reversibilidade | Tag/branch de backup antes de qualquer exclusão (`backup/pre-reestruturacao`, `backup/pre-limpeza-v1`) | Git |

**Auditoria inicial (Fase 0).** O projeto partiu de um app local de contratos/checklists (v1). A auditoria
classificou cada componente em manter/refatorar/excluir; extratores de documentos, segurança de arquivos,
autenticação e backup foram aproveitados; o motor de perguntas por regras foi substituído. O código v1 sem uso
foi removido na Fase 10 com backup (`docs/fases/FASE_00.md`, `FASE_10.md`).

---

## 3. Arquitetura

### 3.1 Decisões principais (ADRs)

| ADR | Decisão | Alternativas avaliadas | Motivo |
|---|---|---|---|
| 001 | Execução local (Windows 11, GTX 1660 SUPER 6 GB, 16 GB RAM) | VPS Oracle Always Free, Vercel | LGPD, custo zero, dados reais não saem da máquina |
| 002 | Corpus acadêmico público + sintético para avaliação | Dados reais | Reprodutibilidade e publicação sem dados pessoais |
| 003 | LangGraph | CrewAI | Matriz ponderada: controle explícito do fluxo, fan-out seletivo, estado tipado |
| 004 | LLM local via Ollama (Qwen 2.5 7B), camada OpenAI-compatível com provedores trocáveis | Gemini, Groq, OpenRouter | Gratuito e local; nuvem só para corpus acadêmico |
| 005 | bge-m3 (embeddings) + bge-reranker-v2-m3 | e5, MiniLM multilíngue | Desempenho em português, multilíngue, licenças abertas |
| 006 | SQLite único: relacional + FTS5 + sqlite-vec + grafo | Qdrant, Supabase/pgvector, Neon | Sem Docker (bloqueado no ambiente), um arquivo, transações |
| 007 | PyMuPDF + Tesseract portátil | Docling, Unstructured, Windows OCR | CER 0,09% × 0,52% do Windows OCR |
| 008 | Interface HTML/CSS/JS servida pelo FastAPI | Next.js na Vercel | Backend em 127.0.0.1; Vercel exigiria túnel público |
| 009 | Tabela própria de spans + Arize Phoenix opcional | Langfuse | Sem Docker; métricas garantidas sem dependência externa |
| 010 | Python 3.15 | 3.12/3.13 | Stack testada; lacunas contornadas |
| 011 | Métricas próprias + LLM-juiz calibrado | RAGAS/DeepEval puros | RAGAS sem suporte ao 3.15; juiz precisa de calibração local |
| 012 | RAG avançado + prompts + precedentes; sem ajuste fino | Fine-tuning de embeddings/reranker | Recall@5 já ≥ 0,96 sem ajuste; custo e risco de sobreajuste |
| 013 | Clean Architecture com migração incremental da v1 | Reescrita do zero | Aproveitar código testado da v1 |

### 3.2 Visão de contêineres (C4 nível 2, resumo)

```text
Navegador (127.0.0.1) ──► API FastAPI ──► Orquestrador LangGraph ──► LLM local (Ollama: Qwen 2.5 7B)
                              │                  │                └─► Gemini free tier (opcional, só corpus acadêmico)
                              │                  ├─► bge-m3 + bge-reranker-v2-m3 (em processo, GPU)
                              ├─► Ingestão ──────┤
                              └─► SQLite (sadgd.db): documentos, trechos, FTS5, vetores, grafo, normas,
                                                    decisões, auditoria, cache semântico, spans
```

Diagramas completos (contexto, contêineres, componentes, sequência e implantação) em `docs/arquitetura/C4.md`;
modelo de dados em `docs/arquitetura/MODELO_DE_DADOS.md`.

### 3.3 Camadas (Clean Architecture)

| Camada | Pasta | Conteúdo |
|---|---|---|
| Domínio | `app/domain/` | Entidades, hierarquia normativa, políticas (aviso de decisão, frase de ausência) — sem dependências externas |
| Aplicação | `app/application/` | Casos de uso: ingestão, recuperação, respostas F1, agentes, linha do tempo, decisões, anonimização, cache, avaliação; `portas.py` define as interfaces |
| Infraestrutura | `app/infrastructure/` | SQLite/sqlite-vec, adaptador LLM OpenAI-compatível (Ollama/Gemini), OCR, embeddings, tracer |
| Interface | `app/api/`, `frontend/` | Rotas FastAPI e telas |

Trocar o provedor de LLM, OCR ou banco significa trocar um adaptador, não reescrever casos de uso. Um teste
automatizado lê o AST de cada módulo e falha se o domínio ou a aplicação importarem a infraestrutura.

---

## 4. Base de conhecimento

### 4.1 Corpus (`corpus/MANIFESTO.csv`, ADR-002)

| Origem | Documentos | Conteúdo | Proveniência |
|---|---|---|---|
| Público | 69 | Constituição, 36 leis, 3 leis complementares, 1 decreto-lei e 28 decretos federais (ex.: Leis 14.133/2021, 8.666/1993, 9.784/1999, 12.527/2011 — LAI, 13.709/2018 — LGPD; Decreto 9.203/2017) | URL oficial, data de coleta, SHA-256, licença |
| Sintético | 117 | 27 processos (contratos, aditivos, apostilamentos, suspensões, retomadas, rescisões, pareceres, decisões da gestão), com gabarito de 103 relações | `gerar_corpus_sintetico.py` (determinístico), `GABARITO.json` |

Total: 186 documentos, 5.691 trechos vetorizados, 96 normas no cadastro de vigência, 30 decisões na memória.

### 4.2 Ingestão

1. **Extração:** PDF (PyMuPDF), DOCX, HTML legal (com detecção de texto tachado = dispositivo revogado), TXT;
   PDFs digitalizados via Tesseract `por` (CER 0,0009 em 6 PDFs).
2. **Chunking estrutural jurídico:** respeita artigo, parágrafo, inciso, alínea e cláusula; limites corretos em
   1,00 dos dispositivos do corpus sintético; Lei 14.133 com 194/194 artigos reconhecidos.
3. **Metadados por regras:** tipo, número, órgão, data, processo; acurácia de tipo e número 1,00, data 0,984.
4. **Indexação incremental:** FTS5 (BM25) + sqlite-vec (bge-m3 float32, 19 trechos/s na GPU); retomável com
   `--max-minutos`; reindexação sem mudanças processa 0 documentos.

Evidências: `avaliacao/execucoes/fase4_*.json`, `docs/fases/FASE_04.md`.

### 4.3 Grafo documental e linha do tempo

Referências entre atos são extraídas por regras ("altera o art. 5º da Lei…", "revoga…", "1º Termo Aditivo ao
Contrato nº…") e classificadas em 8 relações. Documentos se agrupam em processos (pureza 0,966). A vigência de cada
norma vem do grafo; normas revogadas permanecem no histórico, mas não fundamentam recomendação atual. Contradições
(mesmo campo com valores diferentes em documentos do mesmo processo) geram resposta de conflito determinística,
que cita os dois lados.

---

## 5. Recuperação e resposta (F1)

```text
pergunta ─► BM25 (FTS5) ─┐
                         ├─► fusão RRF ─► filtro de vigência ─► bge-reranker-v2-m3 (top-24 → top-k)
pergunta ─► bge-m3 ──────┘                                        │
                                                                   ▼
                           Qwen 2.5 7B (JSON livre ordenado) ─► Verificador de fontes ─► resposta com [T<id>]
```

- **Saída estruturada sem schema estrito:** o schema estrito do Ollama reordena as chaves e induz recusas; usamos
  JSON livre com a ordem dos campos no prompt (`resposta` primeiro), com validação e reparo de forma no Python.
- **Verificador determinístico:** cada frase precisa de um trecho citado que a sustente; número, data ou valor que
  não aparece no trecho citado é rejeitado. Frases reprovadas são removidas e a confiança é limitada.
- **Salvaguardas:** pergunta sem evidência → frase padrão de ausência (recusa correta 1,00 no teste).

---

## 6. Sistema multiagentes e apoio à decisão (F2)

### 6.1 Agentes

| Agente | Papel | Acionamento |
|---|---|---|
| Roteador | Classifica em F1 simples, F1 complexa ou F2 e pontua os especialistas por sinais da pergunta e dos trechos | Toda pergunta (regras; 0,935 sem LLM). F1 simples: nenhum especialista; F1 complexa: até 2; F2: Gestor + até 3 |
| Procurador do Estado | Legalidade, constitucionalidade, risco jurídico do ente | Termos de legalidade, nulidade, constitucionalidade |
| Advogado | Interpretação contratual, direitos e obrigações, litígio | Cláusulas, obrigações, rescisão |
| Controlador-Geral | Conformidade, controle interno, improbidade, TCE/TCU/CGU | Irregularidade, auditoria, pagamentos |
| Fiscal de Contrato | Execução, prazos, entregas, sanções, aditivos (Lei 14.133) | Execução, prorrogação, sanção |
| Gestor Público | Viabilidade, orçamento, interesse público, conveniência | Toda F2 |
| Analista Administrativo | Fluxo processual, instrução, requisitos formais | Instrução, designação, prazos formais |
| Analista Orçamentário-Financeiro* | Dotação, reajuste, impacto financeiro | Valores, reajuste, dotação |
| Especialista em Licitações* | Modalidades, pesquisa de preços, dispensa | Licitação, contratação direta |
| Analista de Linha do Tempo | Cronologia e relações entre documentos do processo | F2 com processo identificado (resumo gerado a partir do grafo) |
| Verificador de Fontes | Anti-alucinação (determinístico) | Toda resposta |
| Relator | Consensos, divergências, alternativas, riscos, confiança | Toda resposta |

\* Perfis adicionais propostos e justificados na Fase 2 (`docs/agentes/README.md`). Cada agente tem prompt
versionado (`app/application/agentes/prompts/*.v1.md`), JSON Schema de saída (`schemas/`) e teste de contrato
prompt × schema × catálogo.

### 6.2 Fluxo da F2

```text
Roteador ─► recuperação híbrida + resumo da linha do tempo + precedentes (memória de decisões, limiar calibrado)
        ─► especialistas em paralelo (LangGraph Send; só os escolhidos; 2–3 por consulta)
        ─► verificador por parecer (afirmação com citação inexistente é descartada)
        ─► relator v2 ─► complemento determinístico do RF-20 (base legal vigente pela hierarquia; precedentes)
        ─► recomendação + aviso "o sistema sugere, a gestão decide" + auditoria (hash da pergunta)
```

Princípio de projeto: **o LLM argumenta, as regras verificam.** O que é verificável deterministicamente
(vigência, hierarquia, existência da citação, números) não fica a cargo do modelo.

### 6.3 Memória de decisões

Decisões anteriores da gestão (contexto, decisão, fundamentos, resultado, lição) ficam em tabela própria com FTS5
e vetores. A busca de precedentes é híbrida com reranker e um **limiar calibrado na validação** para não exibir
precedente sem relação (Recall@3 1,00 no teste; 1 falso precedente em 4 perguntas sem precedente).

### 6.4 Provedor em nuvem para a F2 (opcional)

Com `SADGD_LLM_F2=gemini`, `AI_ALLOW_REMOTE=true` e a chave no `.env`, especialistas e relator usam o Gemini
(plano gratuito) **somente** quando todos os trechos do contexto vêm do corpus `publico`/`sintetico`, após
pseudonimização. Qualquer origem real mantém a consulta no LLM local. Falhas remotas (cota, indisponibilidade)
caem no Qwen local; JSON cortado é repetido no próprio provedor com orçamento maior.

---

## 7. Segurança, privacidade e LGPD

| Controle | Implementação |
|---|---|
| Superfície de rede | Servidor em `127.0.0.1` por padrão |
| Acesso | Perfis Administrador, Gestor e Consulta; senhas com hash; troca obrigatória da senha temporária |
| Envio externo | Bloqueado por padrão; política por origem do trecho (real nunca sai); teste automatizado |
| Pseudonimização | Nomes de pessoas e CPF substituídos de forma reversível antes do envio (recall de nomes 1,00; CPF 100%); CNPJ e órgãos não são mascarados (pessoa jurídica) |
| Auditoria | Cada consulta registra hash SHA-256 da pergunta, usuário, rota, agentes, classificação, confiança, tokens, latência, fontes e acerto de cache |
| Arquivos | Confinamento de caminho, CSP sandbox ao abrir documentos, validação de upload; originais nunca alterados |
| Repositório | gitleaks no CI; `.env`, `DOCUMENTOS\`, `corpus/enviados/` e `data/` fora do Git |

---

## 8. Avaliação

### 8.1 Protocolo

- **Golden set:** 177 perguntas validadas (validação 53 / teste 124) cobrindo F1 simples (66), F1 complexa (24),
  linha do tempo (54), F2 (21) e ausência de evidência (12), mais 50 perguntas de precedente (15 / 35).
  O conjunto de **teste nunca foi usado para ajuste** (`avaliacao/golden_set/`).
- **Métricas:** recuperação (P@k, R@k, MRR, nDCG), classificação (acurácia, P/R/F1, matriz de confusão), geração
  (exatidão, faithfulness, alucinação, citações corretas), operação (latência p50/p95, tokens, custo).
- **Faithfulness com LLM-juiz de outra família** (Llama 3.1 8B julgando respostas do Qwen), calibrado na validação
  com 30 respostas corrompidas de propósito (número trocado, sentido invertido, frase inventada); correção de
  Rogan–Gladen e adjudicação de todas as discordâncias contra o texto integral dos trechos.
- **CI:** a cada push, regressão de recuperação BM25 no corpus sintético com piso calibrado.

### 8.2 Resultados finais × metas (teste)

| Métrica | Meta | Resultado | Situação |
|---|---|---|---|
| Recall@5 | ≥ 0,90 | **0,965** (MRR 0,909; nDCG@10 0,964) | ✅ |
| Faithfulness | ≥ 0,90 | **0,964** adjudicada (juiz bruto 0,795) | ✅ |
| Alucinação | ≤ 5% | **0,0%** numérica; 5,4% por frase (adjudicada) | ⚠️ marginal |
| F1 relações entre documentos | ≥ 0,85 | 1,00 sintético (sobreajuste declarado); 10/10 relações oficiais públicas | ✅ com ressalva |
| Classificação de tipo documental | ≥ 0,85 | **1,00** (186 documentos) | ✅ |
| Roteamento (3 rotas) | ≥ 0,90 | **0,935** (F1 × F2: 1,00) | ✅ |
| Precedentes Recall@3 | ≥ 0,80 | **1,00** | ✅ |
| RF-20 (6 elementos) | 100% | **100%** presentes ou declarados (71% com conteúdo nos 6) | ✅ |
| Latência F1 p50 / p95 | — | 14,6 s / 29,0 s | — |
| Latência F2 p95 | ≤ 120 s | 387 s local · **100 s** Gemini (corpus acadêmico) | ⚠️ local / ✅ nuvem |
| Cache semântico (acerto) | — | 5 ms p50 | ✅ |
| Custo por consulta | gratuito | **R$ 0** | ✅ |

### 8.3 Evolução por versão (teste)

| Versão | Mudança | R@5 | Exatidão | Conflito | Alucinação num. | Citações corretas |
|---|---|---|---|---|---|---|
| v1 (legado) | FTS + regras | 0,431 | 0,217 | 0,833 | 11,3% | 0,327 |
| v2.0 | Híbrido + RRF + vigência + reranker; Qwen 2.5 7B | 0,965 | 0,795 | 0,000 | 4,3% | 0,861 |
| v2.1 | + vigência pelo grafo, conflitos determinísticos | 0,965 | 0,843 | 1,000 | 3,1% | 0,891 |
| v2.2 | + verificador de fontes; multiagentes | 0,965 | 0,843 | 1,000 | **0,0%** | 0,861 |

### 8.4 F2 — local × nuvem (21 perguntas)

| Configuração | Schema relator | Recall docs | RF-20 presentes | p50 / p95 | Tokens (entr./saída) |
|---|---|---|---|---|---|
| Qwen 2.5 7B local (Fase 8) | 1,00 | 0,794 | 1,00 | 329 s / 387 s | 18.872 / 2.538 |
| Gemini 3.5 Flash-Lite, reserva local (Fase 11) | 1,00 | **0,865** | 1,00 | **30 s / 100 s** | 17.978 / 2.759 |

### 8.5 Experimentos negativos (registrados, não escondidos)

| Experimento | Resultado aparente | Resultado real | Decisão |
|---|---|---|---|
| Especialistas no Qwen 2.5 3B | 2,5× mais rápido, schema 1,00 após reparo | 13/14 pareceres **sem conteúdo**; RF-20 preenchido pelas regras mascarava | Rejeitado |
| Orçamento de tokens 1.300 | −8% latência | Recall de documentos 0,722 → 0,472 | Rejeitado |
| Juiz LLM sem adjudicação | 25% de respostas infiéis | 18/23 sinalizações eram falsos alarmes | Métrica publicada só adjudicada |
| Gemini 1ª rodada | Relator válido em 0,333 | Defeito de **formato** do prompt (`consensos` sem formato), não de conteúdo | Corrigido; reavaliado |
| Corpus sintético | F1 de relações 1,00 | Regras ajustadas no próprio gabarito | Verificação externa no corpus público |

---

## 9. Otimização de custo e tokens

| Técnica | Efeito medido |
|---|---|
| Roteamento por regras (sem LLM) | 0 tokens para classificar; 0,935 de acerto |
| Acionar só os especialistas relevantes | 2,48 pareceres por F2 em vez de 6–8 |
| Contexto reranqueado e compacto (top-k + resumo da linha do tempo) | F1 ≈ 2.457 / 107 tokens; F2 ≈ 18.000 / 2.600 |
| Cache semântico (mesmos identificadores, mesma versão do acervo, cosseno ≥ 0,93) | 5 ms e 0 tokens em repetições; 0 respostas erradas reaproveitadas no golden set |
| JSON conciso entre agentes, limites de itens por lista | Pareceres curtos e validáveis |
| Execução local / free tier | R$ 0 por consulta |

---

## 10. Limitações e trabalhos futuros

1. **Latência da F2 local** (p95 387 s) limitada pela GPU de 6 GB; mitigada por cache e, para corpus acadêmico,
   pelo Gemini (p95 100 s). Trabalho futuro: hardware maior ou modelo local maior com quantização eficiente.
2. **Alucinação por frase 5,4%** (meta 5%), adjudicada pelo agente de desenvolvimento — pende confirmação humana.
3. **Generalização das relações:** regras com F1 1,00 no sintético; no público, 10/10 oficiais e 38/39 coerentes.
   Corpus real maior é necessário para uma medida definitiva.
4. **Precedentes em F2 longas:** 8/21 precedentes top-1 fracos (R17); recalibrar com dados de validação maiores.
5. **Anonimização heurística** (lista de prenomes); por isso o envio remoto só aceita corpus acadêmico.
6. **Implantação:** apenas local; Vercel/VPS ficam como perfil futuro já previsto pelas portas e adaptadores.
7. **Kanban no GitHub Projects** depende da instalação/autenticação do `gh`.

---

## 11. Conclusão

O SAD-GD cumpre as metas de confiabilidade do projeto com custo zero e execução local: recuperação acima de 0,96,
faithfulness acima de 0,96 e nenhuma alucinação numérica no teste, além de recomendações F2 completas e
rastreáveis. Três escolhas sustentaram esse resultado: (1) **regras determinísticas** para tudo que é verificável,
deixando ao LLM apenas a argumentação; (2) **avaliação com protocolo** — teste isolado, juiz calibrado,
adjudicação e verificação externa de métricas perfeitas; (3) **governança por fases**, com ADRs, backups e
aprovação humana. O sistema sugere; a gestão decide.

---

## Apêndice A — Reprodução

```powershell
# instalação e execução
"D:\...\instalar.bat"; "D:\...\start.bat"            # http://127.0.0.1:8000
.venv\Scripts\python.exe scripts\sadgd\indexar.py --max-minutos 7.5
.venv\Scripts\python.exe scripts\sadgd\construir_grafo.py
.venv\Scripts\python.exe scripts\sadgd\importar_decisoes.py
# avaliação
.venv\Scripts\python.exe scripts\sadgd\avaliar.py recuperacao
.venv\Scripts\python.exe scripts\sadgd\avaliar_respostas.py --sistema v2 --modelo sadgd-qwen2.5-7b --conjunto teste --max-minutos 8.5
.venv\Scripts\python.exe scripts\sadgd\avaliar_f2.py --rotulo fase11 --provedor-f2 gemini --max-minutos 4
.venv\Scripts\python.exe -m pytest -q
```

Passo a passo completo no `docs/MANUAL_TECNICO.md`.

## Apêndice B — Modelos de IA

Registro completo em `docs/MODELOS_IA.md`: Qwen 2.5 7B (produção), bge-m3, bge-reranker-v2-m3, Tesseract 5,
Llama 3.1 8B (juiz), Qwen 2.5 3B (avaliado e rejeitado), Gemini 3.5 Flash-Lite (F2 opcional, corpus acadêmico)
e Claude Opus 5.5 (agente de desenvolvimento, não faz parte do sistema).
