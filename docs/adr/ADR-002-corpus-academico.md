# ADR-002 — Corpus acadêmico público/sintético separado dos dados reais

| Campo | Valor |
|---|---|
| Status | **Aceito** |
| Data | 2026-11-16 |
| Decisores | Responsável pelo projeto (aprovação da Fase 0, decisão D2) |

## Contexto

O banco v1 indexa documentos reais de órgão público (`\\piau\...\STI\01 - CONTRATOS ATIVOS`), com CNPJ, nomes e possivelmente CPF. O projeto é avaliativo: golden set, métricas e demonstração precisam ser reprodutíveis e compartilháveis com a banca. Free tiers de LLM em nuvem podem reter ou usar entradas para melhoria de produto.

## Decisão

1. Criar o **corpus acadêmico** em `corpus\` com duas origens:
   - `corpus\publico\` — atos normativos e documentos já publicados oficialmente (ex.: Constituição Federal, Lei 14.133/2021, decretos e instruções normativas federais e do Estado de MT, orientações/pareceres publicados, extratos de contratos e aditivos publicados em diário oficial/portal da transparência);
   - `corpus\sintetico\` — processos e contratos fictícios coerentes (linha do tempo com aditivos, revogações, rupturas, contradições plantadas) gerados por script versionado, com dados pessoais inventados.
2. Um **manifesto** (`corpus\MANIFESTO.csv`, versionado) registra origem (URL), data de coleta, hash, tipo e licença de cada arquivo.
3. **Golden set, métricas, CI e demonstração** usam exclusivamente o corpus acadêmico.
4. **Dados reais** só são processados localmente, com LLM local, nunca enviados a serviço externo e nunca versionados.

## Consequências

- (+) Avaliação reprodutível e publicável; conformidade LGPD.
- (+) O corpus sintético permite plantar casos difíceis (contradições, revogações) com gabarito conhecido para medir F1 de classificação de relações.
- (−) Esforço de curadoria (Fase 4/5); risco de o sintético ser "fácil demais" — mitigação: misturar com documentos públicos reais e revisar amostras manualmente.
