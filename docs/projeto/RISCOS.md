# Matriz de Riscos — SAD-GD

Escala: Probabilidade (P) e Impacto (I) de 1 (muito baixo) a 5 (muito alto). Exposição = P × I. Revisar a cada sprint.

| ID | Risco | Categoria | P | I | Exp. | Resposta | Plano / gatilho | Dono |
|---|---|---|---|---|---|---|---|---|
| R01 | LLM local 7–8B (6 GB VRAM) com qualidade insuficiente para F2 multiagentes (Fase 5: F1 com exatidão 0,795, mas conflito 0% e erros de raciocínio sobre vigência) | Técnico | 4 | 5 | **20** | Mitigar | Avaliar em S2 modelos 7–14B quantizados (Qwen2.5/Qwen3, Llama 3.x, Gemma); para o **corpus acadêmico**, permitir free tier em nuvem (Gemini/Groq/OpenRouter) via abstração de provedor; gatilho: faithfulness F2 < 0,85 na validação | Arquiteto |
| R02 | 16 GB de RAM insuficientes para LLM + embeddings + reranker simultâneos (**materializado** na Fase 4: 1–2 GB livres) | Técnico | 5 | 3 | 15 | Mitigar | Carregar modelos sob demanda; LLM na GPU, embeddings em lote fora do horário de consulta; quantização | Arquiteto |
| R03 | Golden set (≥ 100 perguntas) atrasa por depender de curadoria manual | Cronograma | 4 | 4 | **16** | Mitigar | Gerar rascunhos semi-automáticos a partir do corpus sintético (gabarito conhecido) e revisar amostras; começar em S3 | Responsável + agente |
| R04 | Limites/alterações de cota em free tiers externos | Externo | 3 | 3 | 9 | Mitigar | Provedor local como padrão; cache semântico; repetição com backoff; avaliação com cache de respostas | Arquiteto |
| R05 | Vazamento de dados pessoais (LGPD) para serviço externo | Legal | 2 | 5 | 10 | Evitar | ADR-002: provedor externo bloqueado para base real (RNF-08, teste automatizado); anonimização (RF-25) | Arquiteto |
| R06 | Incompatibilidade de bibliotecas de IA com Python 3.15 | Técnico | 1 | 3 | 3 | Evitar | **Fase 3:** stack instalada e testada no 3.15; únicas lacunas (RAGAS 0.3.1, openinference) contornadas — ADR-010/011 | Arquiteto |
| R07 | Prazo acadêmico desconhecido / mais curto que o planejado | Cronograma | 3 | 5 | **15** | Mitigar | Confirmar data (pendência); priorização MoSCoW; F2 e UI podem ser reduzidos ao mínimo verificável | Responsável |
| R08 | Corpus sintético "fácil demais" inflando métricas (**materializado** na Fase 6: F1 1,00 por sobreajuste; mitigado com verificação no corpus público) | Qualidade | 4 | 4 | 16 | Mitigar | Misturar documentos públicos reais; casos adversariais (contradições sutis, revogações parciais); relatar métricas separadas por origem | Agente |
| R09 | Docker/WSL necessários para Qdrant/Langfuse conflitam com o ambiente (CrowdStrike, políticas) | Técnico | 1 | 3 | 3 | Evitado | **Fase 3:** sqlite-vec e Phoenix funcionando sem Docker | Arquiteto |
| R10 | Regressão do app v1 em uso pela equipe durante a reestruturação | Operacional | 2 | 4 | 8 | Mitigar | Branch/tag de backup; 238 testes v1 no CI; GitHub Flow com PRs | Agente |
| R11 | Alucinação em recomendação F2 levando a decisão errada | Negócio | 2 | 5 | 10 | Mitigar | Verificador de fontes, confiança explícita, aviso "sugere, não decide", trilha de auditoria | Arquiteto |
| R12 | Ausência de GitHub autenticado bloqueia Projects/CI (**parcialmente resolvido**: código e CI no GitHub desde 2026-11-16; Issues/Projects ainda dependem do `gh`) | Operacional | 3 | 2 | 6 | Mitigar | Backlog versionado em CSV + script `scripts\github\criar_backlog.ps1` executável após `gh auth login` | Responsável |
| R13 | Perda de dados locais (máquina única) — código e docs já no GitHub | Operacional | 1 | 4 | 4 | Mitigar | Remoto GitHub para código/docs; `BACKUP\` com rotina; corpus reprodutível pelo manifesto | Responsável |
| R14 | Escopo excessivo (11 fases, muitos agentes) | Escopo | 3 | 4 | 12 | Mitigar | Agentes acionados sob demanda; perfis extras só com justificativa; revisão de escopo a cada sprint | PO |

## Mapa de calor (exposição)

| P \ I | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 5 | | | | | |
| 4 | | | R06 | R03 | R01 |
| 3 | | R12 | R04, R09 | R02, R08, R14 | R07 |
| 2 | | | | R10, R13 | R05, R11 |
| 1 | | | | | |
