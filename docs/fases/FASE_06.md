# FASE 06 — Linha do tempo e relações entre documentos (Sprint S6)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aguardando aprovação** |

## 1. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| SAD-060 | **Agrupamento** por processo/contrato/tema: componentes conexos das relações (a base legal — `fundamenta` — não une processos) | `app/application/linha_do_tempo/grafo.py` (`agrupar`) |
| SAD-061 | **Classificador de relações por regras explicáveis**: extração de referências normalizadas ("Contrato nº 012/2023", "Lei nº 14.133, de …", "Decreto-Lei nº 4.657"…); marcador mais próximo **na mesma frase**; regras de tipo documental (aditivo, apostilamento); **notas de compilação** oficiais em voz passiva ("(Revogado pela Lei nº X)", "(Redação dada pela…)") com direção invertida; detecção de **revogação parcial** ("arts.", "§§", "incisos", "dispositivos e seção da…"); retomada ligada à interrupção correspondente; sequência do mesmo processo administrativo (inferência, confiança 0,6) | `referencias.py`, `grafo.py` |
| RF-09 | **Detecção determinística de contradições**: valor vigente = cadeia contrato → aditivos; documento que declara valor diferente → `contradicao` com as duas evidências | `contradicoes.py` |
| RF-09 | **Respostas de conflito** no ResponderF1: se o grafo registra contradição entre documentos do contexto sobre o campo perguntado (valor/vigência), a resposta é determinística (mensagem institucional + os dois valores + citações dos trechos que os contêm), sem LLM | `app/application/respostas/f1.py` |
| SAD-062 | **Vigência pelo grafo**: revogação total ou substituição integral marcam a norma como revogada com evidência ("Grafo: revogada por … (trecho T…)"); revogação parcial não; a recuperação deixa normas revogadas no histórico | `vigencia.py`, `app/infrastructure/sqlite/repositorio_grafo.py` |
| SAD-063 | **API da linha do tempo** (com login): `GET /api/sadgd/processos` e `GET /api/sadgd/linha-do-tempo?processo_id=|documento_id=` — eventos em ordem cronológica, relações com trecho de evidência, fases (Execução, Interrupção, Execução retomada, Extinção) e inconsistências | `app/interfaces/api/linha_do_tempo.py` |
| — | Scripts: construção do grafo e avaliação das relações | `scripts/sadgd/construir_grafo.py`, `scripts/sadgd/avaliar_relacoes.py` |

## 2. Revisão do gabarito (antes de avaliar)

Ao ler os textos gerados, 4 lacunas do gabarito foram corrigidas no gerador (`--somente-gabarito`, sem regravar documentos nem reindexar): o apostilamento S062 também reajusta (alteração); a medição S074 cita o contrato, não a ordem de reinício; as decisões S101/S102 dão continuidade aos contratos que analisam; a portaria S111 não cita o ofício S110 (ambos continuam o Contrato 072/2024). Gabarito: 99 → **103 relações**. O golden set da Fase 5 foi mantido congelado.

## 3. Resultados

### 3.1 Classificação de relações (RF-12)

| Classe | P | R | F1 | Suporte |
|---|---|---|---|---|
| continuação | 1,00 | 1,00 | 1,00 | 17 |
| aditivo | 1,00 | 1,00 | 1,00 | 16 |
| alteração | 1,00 | 1,00 | 1,00 | 18 |
| revogação | 1,00 | 1,00 | 1,00 | 7 |
| substituição | 1,00 | 1,00 | 1,00 | 8 |
| ruptura | 1,00 | 1,00 | 1,00 | 12 |
| contradição | 1,00 | 1,00 | 1,00 | 10 |
| retomada | 1,00 | 1,00 | 1,00 | 7 |
| **F1-macro (8 classes)** | | | **1,00** (meta ≥ 0,85) | 95 |
| regulamenta / fundamenta (auxiliares) | 1,00 | 1,00 | 1,00 | 2 / 6 |

Matriz de confusão completa em `avaliacao/execucoes/fase6_relacoes.json`.

**Ressalva decisiva:** as regras foram desenvolvidas olhando os erros nesse mesmo gabarito sintético — o 1,00 é **otimista por construção** (sobreajuste). A evidência de generalização vem do corpus público, que **não** foi usado para ajustar as regras:

| Corpus público | Resultado |
|---|---|
| Relações oficiais conhecidas (lista curada de 10: revogações da 8.666, 10.520, 7.892, 8.420, 2.271, 11.317, 11.871, 6.170; alterações da 8.429 e da LINDB) | **10/10** |
| Relações fortes previstas entre atos públicos (revogação, alteração, regulamentação, substituição), conferidas manualmente | **38/39** coerentes com o texto; 1 falso positivo (14.133 → Decreto 10.426 "substituição", **parcial**, sem efeito na vigência) |
| Normas marcadas como revogadas | 19, **todas com evidência e corretas** (8 públicas pela nota do próprio ato; 11 sintéticas pelo grafo); Lei 8.429 e Lei 12.462 corretamente **vigentes** (revogações parciais) |

### 3.2 Agrupamento (RF-11)

Pureza **0,932** (meta ≥ 0,90); pureza inversa 0,983. A impureza vem de documentos que o gabarito separou em processos próprios mas que tratam de outro processo (ex.: decisões da gestão sobre a prorrogação de um contrato entram no grupo do contrato).

### 3.3 Efeito nas respostas — v2.1 × v2.0 (conjunto de TESTE, mesmas métricas)

| Métrica | v1 | v2.0 | **v2.1** |
|---|---|---|---|
| Recall@5 / MRR / nDCG@10 | 0,431 / 0,401 / 0,451 | 0,965 / 0,897 / 0,951 | **0,965 / 0,909 / 0,964** |
| Exatidão | 0,217 | 0,795 | **0,843** |
| Classificação correta | 0,615 | 0,908 | **0,954** |
| **Detecção de conflito** | 0,833 | 0,000 | **1,000** (8/8) |
| Recusa correta | 0,375 | 1,000 | **1,000** |
| Cita fonte esperada | 0,327 | 0,861 | **0,891** |
| Precisão das citações | 0,366 | 0,809 | 0,794 |
| Alucinação numérica | 11,3% | 3,2% | **3,1%** |
| Latência p50 / p95 | 3 ms / 5 ms | 14,6 s / 28,7 s | 14,4 s / 29,2 s |

As 3 alucinações numéricas restantes da v2.1 (T100, T109, T124) são **datas de término erradas** produzidas pelo LLM (ex.: "28/08/2026" quando o aditivo diz "31/08/2026") — alvo do verificador de fontes da Fase 7.

## 4. Incidentes e correções (transparência)

| Ocorrência | Tratamento |
|---|---|
| Primeira versão gerou 85 revogações e 48 normas "revogadas" (ex.: "Lei 14.133 revogada pelo Decreto 11.317") | Causas: notas de compilação na voz passiva lidas na direção errada; a tag `[REVOGADO]` do nosso extrator lida como verbo; marcador buscado além da frase. Corrigidas com testes de regressão baseados nos casos reais |
| Lei 8.429 marcada como revogada pela 14.230 (era revogação parcial de dispositivos) | Detecção de parcialidade ampliada; revogação parcial + alteração = alteração |
| Padrão "vigência" de remissão casou com frase comum ("prorrogada a vigência do Contrato") | Anotações exigem parêntese, como no texto oficial |
| Métrica de alucinação: "Lei nº 8.666/1993" e datas por extenso tratadas como números não suportados | Normalização de datas e de citação de ato (teste garante que data inventada continua detectada); métricas da v2.0 recalculadas com o mesmo critério para comparação justa (4,3% → 3,2%) |
| Resposta de conflito citava trecho que não continha o valor | A porta de conflitos fornece o trecho que contém cada valor |
| Comando de partida do Ollama com `| Out-Null` travou a sessão (o processo filho herda o pipe) | Ollama iniciado sem redirecionamento; anotado no `CLAUDE.md` |

## 5. Pendências

1. Revisão humana do golden set (desde a Fase 5).
2. Download do Qwen 2.5 3B (benchmark e roteador) — aguarda autorização.
3. Kanban no GitHub Projects depende do `gh`.

## 6. Retrospectiva

- **Bem:** a revisão manual do corpus público pegou erros que o gabarito sintético jamais mostraria (direção de notas de compilação, revogação parcial).
- **A melhorar:** métricas sintéticas de 1,00 devem vir sempre acompanhadas de verificação externa — está feito, e registrado como ressalva.
- **Ação:** Fase 7 — verificador de fontes para as alucinações de data restantes, roteador e especialistas; o Llama 3.1 8B é candidato a verificador (outra família).

## 7. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
