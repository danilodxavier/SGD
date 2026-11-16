# ADR-001 — Execução na máquina local, somente ferramentas gratuitas

| Campo | Valor |
|---|---|
| Status | **Aceito** |
| Data | 2026-11-16 |
| Decisores | Responsável pelo projeto (aprovação da Fase 0) |
| Substitui | Trecho "Backend em VPS Oracle Cloud Always Free" da seção 3 do prompt mestre |

## Contexto

O prompt mestre propunha backend, OCR e embeddings em uma VPS Oracle Always Free (ARM), com Docker, e frontend Next.js na Vercel. A auditoria (FASE_00, conflito C3) mostrou que:

- a Oracle exige cartão de crédito para verificação e frequentemente não tem capacidade ARM disponível;
- a base documental existente é real e sensível (LGPD), e o código v1 já roda bem no Windows;
- a máquina disponível tem i7-12700 (12 núcleos/20 threads), 16 GB de RAM e GPU NVIDIA GTX 1660 SUPER (6 GB), suficiente para embeddings (bge-m3), reranker e LLM 7–8B quantizado.

Em 2026-11-16 o responsável decidiu: **ferramentas gratuitas, VPS em segundo plano, usar a máquina local, salvar tudo em subpastas do projeto.**

## Decisão

1. Todo o processamento (API, ingestão, OCR, embeddings, banco vetorial, LLM local, observabilidade, avaliação) roda **na máquina local Windows 11**.
2. Somente ferramentas gratuitas; preferência por open source executável localmente.
3. Todos os artefatos gerados (modelos, caches, corpus, índices, backups, resultados de avaliação) ficam em **subpastas do projeto** (convenção em `CLAUDE.md`).
4. A VPS Oracle e o deploy na Vercel ficam como **perfil de implantação opcional/futuro**; a arquitetura (Fase 2) deve mantê-los possíveis via portas/adaptadores e configuração, sem depender deles.
5. Serviços em nuvem gratuitos (ex.: GitHub, LLM free tier) só são usados com o **corpus público/sintético** (ADR-002).

## Alternativas consideradas

| Alternativa | Motivo da rejeição (agora) |
|---|---|
| VPS Oracle Always Free | Cartão de crédito, capacidade incerta, esforço de infraestrutura sem ganho de nota proporcional |
| Hugging Face Spaces (CPU grátis) | CPU fraca para OCR/embeddings em lote; dorme quando ocioso |
| Tudo em serviços SaaS free tier | Risco LGPD e limites de cota |

## Consequências

- (+) Custo zero, controle total dos dados, sem dependência de cota externa.
- (+) Reaproveita integralmente o ambiente v1 (venv, LM Studio, Windows OCR).
- (−) Demonstração pública depende da máquina ligada; mitigação: vídeo de demonstração e, opcionalmente, deploy futuro.
- (−) LLM local de 7–8B tem qualidade limitada para F2; mitigação em avaliação na Fase 2 (ADR de LLM): roteamento local + free tier em nuvem apenas para o corpus público.
- (−) Docker não é necessário; se usado (ex.: Qdrant/Langfuse), requer Docker Desktop/WSL — a ser decidido em ADR próprio na Fase 2 com alternativas sem Docker.
