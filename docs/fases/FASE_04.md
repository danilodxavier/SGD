# FASE 04 — Ingestão e base de conhecimento (Sprint S4)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aguardando aprovação** |

## 1. Planejamento

Itens: SAD-040 a SAD-045. Objetivo: corpus acadêmico reprodutível com gabarito, extração com OCR, chunking estrutural jurídico, metadados, embeddings locais e indexação híbrida incremental (FTS5 + sqlite-vec) no `sadgd.db`.

## 2. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| SAD-040 | **Corpus público: 69 atos oficiais** (CF/88, 34 leis/LC/DL, 34 decretos) baixados do portal da legislação federal, cada um validado pelo identificador e pelo `<title>`, com SHA-256 e licença em `corpus/MANIFESTO.csv` | `scripts/sadgd/coletar_corpus_publico.py`, `scripts/sadgd/corpus_publico_fontes.csv`, `corpus/publico/` |
| SAD-041 | **Corpus sintético: 117 documentos, 27 processos** do ente fictício "Estado de Vale Verde" (DOCX 43, PDF 27, PDF digitalizado 6, TXT 41), **99 relações** com evidência literal (aditivo 16, alteração 17, continuação 14, ruptura 12, contradição 10, substituição 8, revogação 7, retomada 7 + fundamenta 6, regulamenta 2), 11 contradições plantadas, gabarito com dispositivos, fatos e texto de referência para OCR. Gerador determinístico com semente fixa e autoverificação | `scripts/sadgd/gerar_corpus_sintetico.py`, `corpus/sintetico/`, `corpus/sintetico/GABARITO.json` |
| SAD-042 | **OCR**: Tesseract (portátil) × Windows OCR medidos por CER; Tesseract virou o padrão de `auto` | `scripts/sadgd/avaliar_ocr.py`, `app/ingestion/ocr.py` |
| SAD-043 | **Chunking estrutural** (artigo, §, parágrafo único, inciso, alínea, cláusula, item; títulos/capítulos/seções no caminho; texto literal com offsets; divisão de artigos longos nos subdispositivos; dispositivos tachados → `revogado`) | `app/application/ingestao/chunking.py`, `tests/sadgd/test_chunking.py` |
| — | **Extrator de HTML legal**: texto tachado (`<strike>/<s>/<del>`) vira marcador `[REVOGADO]` após o rótulo do dispositivo | `app/infrastructure/extratores/html_legal.py`, `adaptador.py` |
| SAD-044 | **Metadados por regras**: 30 tipos documentais, número, data, órgão, processo, vigência, espécie/nível hierárquico e situação da norma (revogada **somente** com nota no próprio documento, entre o título e o art. 1º) | `app/application/ingestao/metadados.py`, `tests/sadgd/test_metadados.py` |
| SAD-045 | **Indexação híbrida incremental**: caso de uso com portas, repositório SQLite, sqlite-vec, embeddings bge-m3, varredura somente leitura; limite de tempo com parada limpa; reprocessamento automático de documentos sem vetores | `app/application/ingestao/indexador.py`, `app/infrastructure/{sqlite/repositorio_indexacao.py, sqlite/vetores.py, modelos/embeddings.py, fonte_arquivos.py}`, `scripts/sadgd/indexar.py`, migração `003_ingestao.sql` |
| — | Preparação reprodutível do modelo de embeddings (download + conversão para safetensors em `modelos/bge-m3`) | `scripts/sadgd/preparar_bge_m3.py` |

## 3. Resultados medidos (evidências em `avaliacao/execucoes/fase4_*.json`)

| Critério | Meta | Resultado |
|---|---|---|
| Corpus (EAP 4.0.1) | ≥ 150 docs; ≥ 60 públicos; ≥ 90 sintéticos; ≥ 10 processos | **186**; **69**; **117**; **27** ✅ |
| RF-01 — formatos | todos os suportados com status | 186/186 indexados, **0 erros** (HTML, DOCX, PDF, PDF digitalizado, TXT) ✅ |
| RF-02 — OCR (CER) | ≤ 10% | **Tesseract 0,09%**, Windows OCR 0,52% (6 PDFs digitalizados) ✅ |
| RF-03 — limites de dispositivos | ≥ 95% | Sintético: **100%** de 319 unidades e 339 subdispositivos (63 docs); Lei 14.133: **194/194** artigos; Lei 9.784: **70/70** ✅ |
| RF-04 — tipo e número | ≥ 0,90 | **1,00** e **1,00** (186 docs; 7 sem número no texto); data **0,984** ✅ |
| RF-05 — incremental | reindexar sem mudanças processa 0 | **0 processados**, 186 inalterados, 0,0 s ✅ |
| RF-05 — novo arquivo aparece na busca | 1 execução | verificado em `tests/sadgd/test_indexador.py` ✅ |
| Base resultante | — | 5.691 trechos = 5.691 vetores; 96 normas (8 revogadas por evidência); 811 dispositivos tachados |

**Ressalva metodológica:** o 100% de chunking no sintético é otimista por construção (documentos gerados por modelos regulares). Por isso a verificação adicional em leis reais (194/194 e 70/70) — que revelou e corrigiu um defeito (artigos iniciados por "Da/Dos" eram tratados como citação).

## 4. Buscas de amostra (insumo da Fase 5)

| Pergunta | Observação |
|---|---|
| "Prazo para o fiscal atestar as notas fiscais" | A busca densa traz as 3 portarias da cadeia 010/2023 → 025/2024 → 040/2025 nos 3 primeiros lugares; falta aplicar vigência para preferir a 040/2025 |
| "Hipóteses de dispensa de licitação" | A densa prioriza dispositivos **revogados** (Lei 13.979, Lei 8.666) em vez do art. 75 da Lei 14.133 → justifica filtro de vigência + reranker (ADR-005) |
| "Vigência do contrato de limpeza" | Acerta o contrato, mas a cláusula do objeto, não a de vigência → papel do reranker |

## 5. Incidentes e correções

| Ocorrência | Tratamento |
|---|---|
| Portal da legislação recusa conexões TLS do Python/curl e User-Agents desconhecidos | Coleta via cliente HTTP do Windows (PowerShell) com o agente padrão — sem falsificar navegador |
| Colisão de IDs e relação `fundamenta` invertida no gerador | Detectadas pela autoverificação do gerador; corrigidas |
| Pasta em uso impedia regerar o corpus | Gerador passou a limpar o conteúdo sem apagar a pasta |
| Artigos legítimos iniciados por "Da/Dos" tratados como citação | Regra de citação refinada + teste com casos reais |
| Falso positivo de revogação total da Lei 12.462 (só artigos revogados) | Nota buscada apenas entre o título e o art. 1º + teste |
| Indexação encerrada 2× pelo Claude Code por falta de memória do sistema (RAM livre 1,2–2 GB) | Não reiniciada sem autorização; indexador ganhou parada limpa por tempo (`--max-minutos`) e retomada |
| Documento gravado sem vetores ficaria sem embeddings para sempre | Reprocessamento quando falta o modelo atual; marcação do modelo após cada lote (testes) |
| Crash nativo (`access violation`) ao carregar o bge-m3 (CPU e GPU) | Causa: carga paralela de pesos do transformers 5; corrigido com `HF_DEACTIVATE_ASYNC_LOAD=1` (variável oficial) |
| Embeddings a 3,8 trechos/s | fp16 é 5× mais lento na GTX 1660 SUPER (sem tensor cores); fp32 → 19 trechos/s |

## 6. Pendências e riscos

- Kanban no GitHub Projects ainda depende do `gh`.
- R02 (memória) **materializado**: a máquina opera com 1–2 GB de RAM livre; indexações longas devem rodar com `--max-minutos` ou fora do Claude Code.
- R08 (corpus sintético "fácil"): mantido como risco; métricas da Fase 5 serão reportadas separadamente por origem.

## 7. Retrospectiva

- **Bem:** gabarito com autoverificação e validação contra leis reais pegaram defeitos que métricas sintéticas esconderiam.
- **A melhorar:** medir desempenho (fp16 × fp32) antes de assumir a configuração "óbvia".
- **Ação:** Fase 5 começa pela busca híbrida com filtro de vigência e reranker, e pelo golden set derivado do gabarito.

## 8. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
