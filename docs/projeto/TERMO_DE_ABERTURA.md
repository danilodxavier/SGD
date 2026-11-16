# Termo de Abertura do Projeto (TAP) — SAD-GD

| Campo | Valor |
|---|---|
| Projeto | SAD-GD — Sistema de Apoio à Tomada de Decisão e Gestão Documental (Setor Público) |
| Natureza | Atividade avaliativa — Curso de Engenharia de IA |
| Versão do documento | 1.0 — 2026-11-16 |
| Patrocinador / responsável | Responsável pelo projeto (aluno) |
| Gerente técnico | Claude Code (`claude-opus-5-5`) sob supervisão do responsável |
| Referência metodológica | PMBOK 7 (domínios de desempenho), Scrum, Kanban |

## 1. Justificativa

Gestores públicos decidem sob grande volume de contratos, leis, decretos, instruções normativas, pareceres e processos, frequentemente desatualizados, contraditórios ou dispersos. Erros de interpretação geram risco jurídico, de controle (TCE/TCU/CGU) e de improbidade. Um sistema que responda com **fonte literal**, reconstrua a **linha do tempo** documental, respeite a **hierarquia normativa** e ofereça **pareceres multiperspectiva** reduz esse risco — desde que seja confiável e nunca invente.

O projeto parte do aplicativo v1 já existente (FASE_00), que lê, indexa e responde perguntas sobre contratos por regras e BM25.

## 2. Objetivos (SMART)

| ID | Objetivo | Indicador / meta |
|---|---|---|
| O1 | Responder perguntas sobre a base documental com citação literal (F1) | Recall@5 ≥ 0,90; taxa de citações corretas ≥ 0,95; alucinação ≤ 5% no conjunto de teste |
| O2 | Gerar recomendação multiperspectiva fundamentada (F2) | 100% das recomendações com fundamentação, fontes, confiança, riscos e alternativas; faithfulness ≥ 0,90 |
| O3 | Reconstruir linha do tempo e classificar relações entre documentos | F1-macro ≥ 0,85 nas 8 classes de relação |
| O4 | Operar com custo zero na máquina local | R$ 0,00 em ferramentas; latência p95 F1 ≤ 15 s e F2 ≤ 120 s em hardware local |
| O5 | Documentação e rastreabilidade de nível acadêmico | 100% das fases com FASE_XX.md aprovado; todos os modelos em MODELOS_IA.md; ADR para cada decisão estrutural |

## 3. Escopo resumido

**Inclui:** ingestão multiformato + OCR; chunking estrutural jurídico; busca híbrida (BM25 + vetorial) com reranking; grafo e linha do tempo documental; hierarquia e vigência normativa; sistema multiagentes (roteador, especialistas, verificador, relator); memória de decisões; golden set ≥ 100 perguntas e suíte de métricas; interface web (chat, upload, linha do tempo, fontes, pareceres); autenticação, auditoria e anonimização; documentação completa.

**Não inclui:** decisão automática (o sistema sugere, a gestão decide); integração com sistemas oficiais (SEI, SIGPLAN etc.); assinatura digital; infraestrutura paga; hospedagem pública permanente (VPS/Vercel ficam opcionais — ADR-001); ajuste fino de LLM generativo.

Detalhamento em `docs/projeto/ESCOPO_E_REQUISITOS.md`.

## 4. Premissas

- Máquina local disponível: i7-12700, 16 GB RAM, GTX 1660 SUPER (6 GB), Windows 11, ~75 GB livres em `D:`.
- Ferramentas gratuitas e open source suficientes para cumprir as metas.
- Corpus acadêmico público/sintético aceito pela banca como base de avaliação (ADR-002).
- Responsável disponível para aprovar cada fase.

## 5. Restrições

- Custo zero (regra 3); nenhuma credencial no repositório (regra 4).
- Tudo salvo em subpastas do projeto (ADR-001).
- Dados reais não saem da máquina (ADR-002, LGPD).
- Avanço de fase só com aprovação explícita (regra 1).

## 6. Riscos de alto nível

LLM local de 7–8B insuficiente para F2; limites de cota de free tiers; esforço de construção do golden set; 16 GB de RAM para rodar LLM + embeddings simultaneamente; prazo acadêmico. Matriz completa em `docs/projeto/RISCOS.md`.

## 7. Marcos

| Marco | Fase | Critério |
|---|---|---|
| M0 | 0 | Auditoria aprovada ✅ (2026-11-16) |
| M1 | 1 | Planejamento aprovado |
| M2 | 2 | Arquitetura e ADRs aprovados |
| M3 | 3 | Ambiente local reprodutível + CI verde |
| M4 | 5 | Baseline F1 medido (v1 regras × v2 RAG) |
| M5 | 7 | Multiagentes funcionando com verificador |
| M6 | 9 | MVP completo |
| M7 | 11 | Entrega acadêmica |

Datas em `docs/projeto/CRONOGRAMA.md`.

## 8. Partes interessadas

Ver `docs/projeto/PARTES_INTERESSADAS.md`.

## 9. Aprovação

- [ ] Aprovado por: ______________________ em ____/____/______
