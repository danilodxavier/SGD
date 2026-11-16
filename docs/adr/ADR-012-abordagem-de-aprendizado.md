# ADR-012 — Abordagem de "treinamento": RAG avançado + prompts + few-shot, sem ajuste fino de LLM

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | Prompt mestre §4; RF-06, RF-12, RF-19 |

## Contexto

O conhecimento do sistema muda continuamente (novos contratos, aditivos, revogações). Precisamos de citação literal e rastreável. Hardware: 6 GB de VRAM. Custo zero.

## Decisão

| Técnica | Uso | Justificativa |
|---|---|---|
| **RAG avançado** (chunking estrutural, metadados, híbrido, rerank, filtro de vigência, grafo) | Toda resposta factual | Conhecimento atualizável sem retreino; citação nativa |
| **Engenharia de prompt** versionada (`app\agentes\prompts\*.vN.md`) | Todos os agentes | Mudanças rastreáveis e avaliáveis por versão |
| **Saída estruturada** (JSON Schema) | Comunicação entre agentes | Validação automática; menos tokens |
| **Few-shot dinâmico com precedentes** | F2 e classificação de relações | Exemplos recuperados da memória de decisões / gabarito de validação |
| **Classificação híbrida** de relações: regras (marcadores textuais explícitos) + LLM para casos ambíguos | Linha do tempo | Regras dão precisão e explicação; LLM cobre redações variadas |
| **Ajuste fino do reranker** | Somente se Recall@5 < 0,90 após otimizações (portão na Fase 5) | Barato, cabe na GPU, ganho localizado |
| **Ajuste fino de embeddings** | Somente se o ajuste do reranker não bastar | Requer reindexação completa |
| **Ajuste fino de LLM generativo** | **Não** | Custo/hardware; risco de "decorar" fatos desatualizados; não melhora citação |

## Consequências

- (+) Atualização imediata do conhecimento; avaliação comparável entre versões de prompt.
- (−) Qualidade limitada pelo LLM local em raciocínio complexo (R01), mitigada pelo verificador e pela opção de free tier no corpus acadêmico.
