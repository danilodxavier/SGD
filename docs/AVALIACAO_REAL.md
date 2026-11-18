# Avaliação com documentos reais — protocolo

| Campo | Valor |
|---|---|
| Início | 2026-11-18 |
| Acervo | Compartilhamento de rede da STI (contratos ativos) — 6.025 arquivos, 4,9 GB; 6.010 em formatos suportados |
| Origem | `real`: nunca sai da máquina (LLM local; `AI_ALLOW_REMOTE=false`, `SADGD_LLM_F2=local`) |
| Corpus de teste | Índice dos 186 documentos acadêmicos e das 30 decisões fictícias **excluído** do banco em 2026-11-18 (backup `BACKUP\backup_20261118_095229.zip`); os arquivos continuam em `corpus\` e podem ser reindexados |
| Privacidade | Perguntas, respostas, fontes e julgamentos ficam em `avaliacao\real\` (fora do Git). O agente de desenvolvimento (nuvem) **não lê** conteúdo real: vê apenas contagens e métricas agregadas |

## 1. Por que este protocolo

As métricas acadêmicas (Recall@5 0,965, faithfulness 0,964) foram medidas em corpus público e sintético. O
comportamento em documentos reais — PDFs digitalizados, planilhas, nomes de arquivo irregulares, contratos com
muitos aditivos — só pode ser confirmado com perguntas reais e **julgamento de quem conhece os processos**.

## 2. Etapas

| # | Etapa | Quem | Como |
|---|---|---|---|
| 1 | Indexar o acervo | Sistema | `scripts\sadgd\indexar.py` (processo independente; retoma de onde parou). Depois: `scripts\sadgd\construir_grafo.py` |
| 2 | Escrever as perguntas | Equipe | `avaliacao\real\perguntas.csv` (abre no Excel; separador `;`) |
| 3 | Executar | Sistema | `python scripts\sadgd\avaliar_real.py executar --max-minutos 30` (repetir até `[OK]`) |
| 4 | Julgar as respostas | Equipe | `python scripts\sadgd\avaliar_real.py revisao` → preencher `avaliacao\real\revisao.csv` |
| 5 | Medir | Sistema | `python scripts\sadgd\avaliar_real.py resumo` → `avaliacao\real\resumo.json` (só números) |

## 3. Como escrever as perguntas (`perguntas.csv`)

| Coluna | Conteúdo |
|---|---|
| `id` | Identificador único (R001, R002…) |
| `pergunta` | Como um servidor perguntaria, citando o número do contrato/processo |
| `tipo` | `fato` (está escrito), `linha_do_tempo` (prazos, aditivos, suspensões), `conflito` (documentos divergem), `ausencia` (a informação **não** está no acervo), `decisao` (apoio à decisão: "Devo…?") |
| `termos_esperados` | Trechos que a resposta correta precisa conter, separados por `|` (ex.: `R$ 1.200.000,00|28/02/2025`). Vazio em `ausencia` e `decisao` |
| `documento_esperado` | Parte do nome do arquivo que contém a resposta (ex.: `2º Termo Aditivo`). Vazio quando não se aplica |

**Composição recomendada (mínimo 50, ideal 100):** 40% `fato`, 25% `linha_do_tempo`, 10% `conflito`, 15%
`ausencia`, 10% `decisao`; cobrir várias pastas do acervo, contratos com e sem aditivos, documentos digitalizados.
Escreva as perguntas **antes** de ver as respostas do sistema e não as ajuste depois.

## 4. Como julgar (`revisao.csv`)

| Coluna | Valores |
|---|---|
| `julgamento` | `C` correta e completa · `P` parcialmente correta · `I` incorreta ou recusa indevida · `A` alucinação (afirma algo que não está nos documentos citados) |
| `fontes_corretas` | `S` se as fontes citadas sustentam a resposta; `N` caso contrário |
| `observacao` | Livre (ex.: "pegou o valor do contrato original, não o do aditivo") |

Para perguntas `ausencia`, a resposta correta é a recusa ("Não localizei essa informação…"). Para `decisao`,
julgue se a recomendação é coerente com os documentos e se alternativas, riscos e base legal fazem sentido.

## 5. Métricas produzidas (`resumo.json`)

| Métrica | Significado | Referência acadêmica |
|---|---|---|
| `recall@5_documento_esperado` | O documento certo está entre os 5 trechos recuperados | 0,965 |
| `documento_esperado_entre_fontes_citadas` | A resposta cita o documento certo | — |
| `termos_esperados_na_resposta` | Indicador automático de exatidão | exatidão 0,843 |
| `recusa_correta` / `recusa_indevida` | Recusa quando deve / recusa quando não deveria | 1,00 / — |
| `exatidao_humana` | (C + 0,5·P) / julgadas — **métrica definitiva** | — |
| `julgamento_humano.alucinacao` | Proporção julgada `A` | ≤ 5% (meta) |
| `fontes_corretas_humano` | Fontes sustentam a resposta | citações corretas 0,861 |
| `latencia_s` p50/p95 | Tempo por pergunta (F1 e F2) | F1 14,6 s / 29 s |

## 6. Registro de execuções

| Data | Documentos indexados | Perguntas | Resultado | Observações |
|---|---|---|---|---|
| 2026-11-18 | 1º ciclo: 112 arquivos, 571 trechos, 0 falhas (24% com OCR) | — | — | Indexação completa estimada em ≈ 7 h |
