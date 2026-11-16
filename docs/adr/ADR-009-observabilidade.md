# ADR-009 — Observabilidade local: tabela de consultas + Arize Phoenix

| Campo | Valor |
|---|---|
| Status | **Proposto** |
| Data | 2026-11-16 |
| Requisitos | RNF-04, RNF-05, RNF-11, RF-24 |

## Contexto

O prompt mestre sugere Langfuse (self-hosted ou free tier). Constatações:

- **Langfuse self-hosted (v3)** exige Postgres, ClickHouse, Redis e armazenamento S3 compatível — na prática Docker Compose com vários serviços; pesado para 16 GB de RAM que já hospedam LLM e embeddings.
- **Langfuse Cloud (free tier)** envia prompts e trechos para fora da máquina — incompatível com ADR-002 quando há dados reais.
- **Arize Phoenix** (open source, Elastic License 2.0 — uso gratuito, inclusive self-hosted) roda com `pip` (`arize-phoenix 21.0.0` resolve no Python 3.15), armazena em SQLite local e recebe traces OpenTelemetry/OpenInference, com instrumentação para LangGraph/LangChain.

## Decisão

1. **Fonte de verdade das métricas operacionais:** tabela `consultas` + `spans_agentes` no próprio `sadgd.db` (tokens de entrada/saída por chamada, latência por nó, modelo, rota, agentes acionados, acerto de cache). Os relatórios de `AVALIACAO.md` (p50/p95, tokens/consulta) saem daqui — sem depender de ferramenta externa.
2. **Visualização de traces:** **Arize Phoenix local**, com `PHOENIX_WORKING_DIR=<projeto>\data\observabilidade`, em `127.0.0.1`. Opcional e desligável (`OBSERVABILIDADE=phoenix|nenhuma`).
3. Instrumentação via OpenTelemetry atrás de `TracerPort`, de modo que Langfuse possa ser plugado no futuro (perfil nuvem) sem alterar o código de domínio.
4. Fase 3: verificar e **desativar qualquer telemetria de uso** da própria ferramenta e documentar a variável.

## Consequências

- (+) Sem Docker, sem envio externo, dados no projeto.
- (+) Métricas reproduzíveis por SQL simples.
- (−) Phoenix acrescenta dependências; por isso é opcional, e a tabela própria garante as métricas mesmo sem ele.
