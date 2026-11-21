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
| 2026-11-18/20 | **6.011 documentos**, 51.510 trechos e vetores (8,6 h); 1.101 com OCR; 2 corrompidos, 8 sem texto, 1 digitalizado sem OCR útil | — | Grafo: 4.131 grupos, só 21 com 2+ documentos; 13 processos de contrato; 3.330 relações; 0 contradições | 2 defeitos corrigidos (`022a053`): data ausente e chave de grupo duplicada |
| 2026-11-20 | A1 + A3 aplicados (§7.1, §7.2): `outro` 88% → 22%; 168 processos de contrato; F1 60,5 s → 17,3 s | — | — | Precisão dos tipos depende da amostra conferida pela equipe |
| 2026-11-20 | Fumaça (4 perguntas sem conteúdo real na saída) | 4 | Ausência → recusa correta; F1 com 4 fontes; F2 local, válida, 6 elementos — **mas 0 trechos citados** | F1 aquecida ≈ 30 s (rerank 18–27 s) |

## 7. Achados estruturais (somente contagens)

| # | Achado | Evidência agregada | Impacto | Proposta |
|---|---|---|---|---|
| A1 | **Classificação de tipo inadequada ao acervo real** | 5.307 de 6.011 (88%) como `outro`; entre eles, pistas no nome/início do texto: pagamento/liquidação 769/999, fiscalização 559/988, empenho 482/893, relatório 346/381, certidão 265/370, nota fiscal 182/519, apostilamento 116/111; "contrato" no início do texto de 1.994 | Linha do tempo, vigência e agrupamento quase não funcionam; a busca de trechos (F1) não depende disso | Novos tipos (nota de empenho, nota fiscal, certidão, processo de pagamento, atesto/relatório de fiscalização, portaria de fiscal) e uso do nome do arquivo; medir em amostra rotulada pela equipe |
| A2 | **Processos não reconstruídos** | 13 processos de contrato para 402 contratos e 181 aditivos; 21 grupos com 2+ documentos | Tela Linha do tempo pouco útil no acervo real | Usar a hierarquia de pastas (24 pastas de 1º nível, mediana 72 documentos; 165 de 2º nível) como sinal de processo — **depende de a equipe confirmar o que cada nível representa** |
| A3 | **Latência da F1 ≈ 30 s** (acadêmico 14,6 s) | Rerank 18–27 s: trechos reais com mediana de 2.374 caracteres (no limite de 2.400) porque PDFs reais não têm estrutura de artigos | Experiência de uso | Reranquear 12 em vez de 24 e/ou trechos menores para texto sem estrutura — decidir com o baseline real |
| A4 | **F2 sem trecho citado** na fumaça | 1 de 1 recomendação com `fontes=0` | Recomendação sem lastro documental | Conferir no julgamento humano; se recorrente, exigir citação mínima no relator |

### 7.1 A1 — classificação de tipos (feito em 2026-11-20, `c3866e9`)

| Indicador (acervo real) | Antes | Depois |
|---|---|---|
| Documentos `outro` | 5.307 (88%) | **1.326 (22%)** |
| Tipos distintos | 10 | 26 (novos: termo de recebimento/atesto 990, nota fiscal 541, certidão 539, nota de empenho 496, relatório 344, pagamento 307, extrato 148, apostilamento 118…) |
| Processos de contrato | 13 | **168** (maiores grupos: 97–100% numa única pasta de 1º nível) |
| Fidelidade da reclassificação (texto reconstruído dos trechos) | — | 1,00 nos 704 já classificados |
| Corpus acadêmico (regressão) | tipo/número 1,00 | tipo/número **1,00**; F1 relações 1,00; pureza 0,966 / inversa 0,983 |

Ao reclassificar apareceu uma **fusão indevida de processos**: documentos que citam dois contratos encadeavam 15
contratos num único grupo de 1.279 documentos. Corrigido: contratos diferentes só se unem por substituição direta.
**Precisão ainda não medida** — a equipe confere a amostra `avaliacao/real/amostra_tipos.csv` (168 documentos,
26 tipos) e roda `avaliar_real.py medir-tipos`.

### 7.2 A3 — latência (feito em 2026-11-20)

| Configuração (mesmas 4 perguntas, LLM descarregado no início) | F1 mediana | Reranking | Geração |
|---|---|---|---|
| A — anterior: reranker na CPU, trechos inteiros | 60,5 s | 16,6 s | 44,9 s |
| E0 — reranker na GPU | 53,0 s | 4,0 s | 49,9 s |
| **E1 — GPU + compressão do contexto a 1.200 caracteres (adotada)** | **19,9 s** (padrão novo, reconfirmado: **17,3 s**) | 3,8 s | 14,5 s |
| E2 — GPU + compressão a 800 caracteres | 15,8 s | 3,7 s | 12,0 s |
| Rejeitadas: reranquear 12 trechos ou cortar a 256 tokens | — | −1 s | ranking diferente (1–4 de 5 trechos em comum) |

Diagnóstico: (1) o cross-encoder rodava na CPU por padrão e disputava núcleos com as camadas do LLM; na GPU o
ranking é **idêntico** (5/5 trechos, mesma ordem); (2) o gargalo real é a **leitura do prompt** pelo LLM local
(≈ 130 tokens/s com 21% das camadas na CPU): trechos reais têm ≈ 600 tokens cada. *Flash attention* e cache KV
`q8_0` não ajudaram. A compressão mantém, na ordem original, as frases do trecho que compartilham termos com a
pergunta (texto literal; cortes marcados com "[…]").

Qualidade na **validação acadêmica** (47 perguntas F1, verificador ligado):

| Compressão | Exatidão | Classificação | Cita a fonte esperada | Precisão das citações | Alucinação numérica | p50 / p95 |
|---|---|---|---|---|---|---|
| desligada | 0,923 | 0,957 | 0,907 | 0,861 | 0% | 14,9 s / 24,8 s |
| **1.200** | **0,923** | 0,936 | 0,907 | 0,850 | 0% | 9,5 s / 17,5 s |
| 800 | 0,923 | 0,957 | 0,907 | 0,851 | 0% | 11,6 s / 15,1 s |

Escolha de 1.200 × 800: qualidade igual no acadêmico; no acervo real o corte de 800 atinge 87% dos trechos (1.200:
81%) — com qualidade idêntica, preferiu-se o corte menos agressivo (4 s de diferença). Configuração no `.env`:
`SADGD_DISPOSITIVO_RERANKER=auto`, `SADGD_CONTEXTO_MAX_CHARS=1200`.

**Cuidado de medição:** o Ollama reaproveita o cache de prompts idênticos; uma primeira leitura de "9,6 s" de
geração era esse artefato. Todas as medições acima partem do LLM descarregado.

### 7.3 A3 na F2 e resolução do A4 (2026-11-21)

A compressão passou a valer também para os especialistas e o relator. O diagnóstico no acervo real (mesma pergunta
de decisão, somente contagens) mostrou que **sem compressão a F2 estava quebrada**:

| F2 real | Sem compressão | **Compressão 1.200** |
|---|---|---|
| Prompt de cada especialista | ≈ 25.400 caracteres (≈ 7.000 tokens + até 1.200 de saída > contexto de 8.192 → o Ollama corta o início do prompt) | ≈ 8.400 caracteres |
| Chamadas com 2ª tentativa | 3 de 3 | 1 de 3 |
| Afirmações dos especialistas removidas pelo verificador | **6 de 6** | **0 de 4** |
| Fontes citadas na recomendação | **0** (achado A4) | **6–7** |
| Tempo (2 perguntas) | 102 s / 69 s | 203 s / 246 s |

A F2 "rápida" sem compressão era rápida porque o contexto estourava e quase nada útil era gerado. Com compressão,
os pareceres saem completos e citados; o tempo (≈ 3,5–4 min) fica perto do limite do hardware (saída a ≈ 24
tokens/s, especialistas atendidos um de cada vez pelo mesmo LLM). **A4 resolvido.**

Validação acadêmica (6 perguntas F2, LLM local): erros 0, relator válido 1,00 e RF-20 1,00 nas duas; recall de
documentos 0,722 → 0,639 e precisão 0,434 → 0,456 (≈ 1 documento em 6 perguntas — nível de ruído); p50 333 s → 303 s
(trechos acadêmicos são curtos). Resultados em `avaliacao/execucoes/fase11_f2ctx/`.

Conjunto de teste acadêmico (15 F2, comparado com a Fase 8): recall de documentos 0,822 nas duas, RF-20 e relator
1,00 nas duas, precisão 0,466 → 0,439, p50 334 s → 288 s — a queda de recall da validação era ruído de amostra
pequena (ver `docs/AVALIACAO.md`).

Observação de medição: `tokens_entrada` do relator subestima o prompt quando há 2ª tentativa (o Ollama só conta o que
não veio do cache).

Ordem recomendada: **medir o baseline real primeiro** (perguntas da equipe, §3–§5) e só então aplicar A1–A4, medindo o ganho contra esse baseline.

