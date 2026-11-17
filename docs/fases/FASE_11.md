# FASE 11 — Entrega acadêmica (Sprint S11)

| Campo | Valor |
|---|---|
| Período | 2026-11-17 – |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | Em andamento |

## 1. Escopo

Relatório técnico, documentação final (README, manuais do usuário e técnico), roteiro de apresentação/demonstração, lições aprendidas e a avaliação da F2 no Gemini (decisão da Fase 10, `FASE_10.md` §6).

## 2. Entregas até aqui

| Item | Entregável | Arquivos | Situação |
|---|---|---|---|
| Provedor Gemini para a F2 | Especialistas e relator no Gemini (plano gratuito) só com contexto 100% acadêmico, anonimizado e envio autorizado; reserva no Qwen local; nova tentativa no próprio provedor com orçamento 1,6× quando o JSON vem cortado (429/503/rede vão direto à reserva) | `app/application/agentes/politica_llm.py`, `app/core/config.py`, `scripts/sadgd/testar_gemini.py` | ✅ |
| Avaliação da F2 no Gemini | 21 perguntas F2, comparação com a Fase 8 | `avaliacao/execucoes/fase11/`, `docs/AVALIACAO.md` (Fase 11) | ✅ |
| Correção do relator | `consensos` como lista de frases (instrução + reparo de `{tema, posicoes}`) | `app/application/agentes/especialistas.py`, `tests/sadgd/test_orquestrador.py` | ✅ |
| Relatório de atividades e ferramentas | Atividades por fase, ferramentas e conectores | `docs/RELATORIO_ATIVIDADES_E_FERRAMENTAS.md` | ✅ |
| Vídeo de apresentação | Roteiro e gerador (vídeo fora do Git, LGPD) | `docs/video/ROTEIRO.md`, `scripts/video/` | ✅ |
| Relatório técnico | Problema, metodologia, arquitetura, base de conhecimento, F1/F2, LGPD, avaliação, experimentos negativos, limitações | `docs/RELATORIO_TECNICO.md` | ✅ |
| Manuais do usuário e técnico | Reescritos para o SAD-GD; os da v1 movidos para `docs/legado/*_v1.md` | `docs/MANUAL_DO_USUARIO.md`, `docs/MANUAL_TECNICO.md` | ✅ |
| README final | Visão, resultados × metas, arquitetura, como rodar e avaliar, corpus, documentação (conteúdo v1 removido) | `README.md` | ✅ |
| Roteiro de demonstração ao vivo | — | `docs/DEMONSTRACAO.md` | Pendente |
| Lições aprendidas | — | `docs/projeto/LICOES_APRENDIDAS.md` | Pendente |

## 3. F2 no Gemini — resultados (2026-11-17)

| Execução | Schema relator | Recall docs | RF-20 presentes / com conteúdo | p50 / p95 | Itens com falha remota |
|---|---|---|---|---|---|
| Fase 8 (Qwen 2.5 7B local) | 1,00 | 0,794 | 1,00 / 0,714 | 329 s / 387 s | — |
| v1 (Gemini 3.5 Flash-Lite) | 0,333 | 0,841 | 1,00 / 0,714 | 91 s / 213 s | 15/21 |
| **v2 (+ reparo de `consensos`)** | **1,00** | **0,865** | **1,00** / 0,714 | **30 s / 100 s** | 5/21 |

- **Meta de latência F2 p95 ≤ 120 s atendida** com o provedor em nuvem (limitação R15 do hardware local contornada para o corpus acadêmico).
- **Diagnóstico da v1:** 14/21 relatores inválidos por um único motivo de forma — `consensos` vinha como `{tema, posicoes}` (formato de `divergencias`), porque o prompt não especificava o formato. Conteúdo preservado após o reparo. A v1 fica registrada (`f2_gemini__v1_consensos_objeto.jsonl`, `f2_resumo_v1_consensos_objeto.json`).
- **Variabilidade da nuvem:** na v1, 15/21 itens tiveram ao menos uma resposta 503 ("high demand"); na v2, 5/21 (503 e 429 de cota por minuto). A reserva local garantiu 0 erros em todas as execuções; os itens com reserva são mais lentos (90–112 s).
- Itens idênticos entre execuções (roteador e recuperação determinísticos): precisão/recall de agentes 0,942 / 0,790.

Evidências: `avaliacao/execucoes/fase11/f2_sadgd-qwen2.5-7b__f2_gemini.jsonl`, `f2_resumo.json`. Testes: 220 passando em `tests/sadgd`, ruff limpo.

## 4. Defeito encontrado e corrigido (transparência)

| Ocorrência | Causa | Tratamento |
|---|---|---|
| Ao validar ao vivo as perguntas do roteiro de demonstração, `POST /api/sadgd/perguntar` falhava com `TypeError: 'ResultadoRecuperacao' object is not subscriptable` | Desde a Fase 7, `construir_orquestrador` passava o objeto do recuperador híbrido ao grafo, que espera a lista de trechos. Os testes da API e o E2E substituem o orquestrador por um falso, e os scripts de avaliação montam a recuperação por conta própria — a montagem real nunca era exercitada | `rec.recuperar(p, k=k).trechos`; teste de regressão que monta o orquestrador real com recuperador que devolve `ResultadoRecuperacao` (falha sem a correção). Validação ao vivo no banco real: F1 fato, conflito, ausência e linha do tempo corretos; F2 com 2 especialistas, relator válido e 6 elementos de RF-20 |

**Impacto nas métricas:** nenhum — todas as avaliações (Fases 5–11) usam a mesma recuperação e o mesmo orquestrador, montados pelos scripts. **Impacto no produto:** a tela Perguntar falhava com o pipeline real desde a Fase 7; corrigido.

