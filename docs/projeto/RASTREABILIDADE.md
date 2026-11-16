# Matriz de rastreabilidade — requisito → decisão → componente → verificação

Atualizada a cada fase. Componentes seguem a estrutura de ADR-013. "Teste/métrica" indica onde o critério de aceite será comprovado.

| Req. | Decisão | Componente | Teste / métrica | Fase |
|---|---|---|---|---|
| RF-01 | ADR-007 | `infrastructure/extratores` (v1) | `tests/test_extraction.py`, `test_legacy.py` | 4 |
| RF-02 | ADR-007 | `infrastructure/ocr` (Tesseract, Windows OCR) | `tests/test_ocr.py` + CER ≤ 10% | 4 |
| RF-03 | ADR-012 | `application/ingestao/chunking_estrutural` | teste com 20 documentos anotados (≥ 95%) | 4 |
| RF-04 | MODELO_DE_DADOS | `application/ingestao/metadados` | acurácia tipo/número ≥ 0,90 | 4 |
| RF-05 | ADR-005, ADR-006 | `infrastructure/sqlite_vec`, `fts5`, indexador incremental | teste de reindexação sem mudanças | 4 |
| RF-06 | ADR-005 | `application/recuperacao` (BM25+denso+RRF+rerank) | Recall@5, MRR, nDCG (ADR-011) | 5 |
| RF-07 | ADR-011 | relator + verificador | taxa de citações corretas | 5 |
| RF-08 | `_regras_comuns.v1.md` | relator | acurácia de recusa | 5 |
| RF-09 | MODELO_DE_DADOS (`contradicao`) | linha do tempo + relator | casos plantados ≥ 90% | 5–6 |
| RF-10 | `relator.v1.json` | relator | schema obrigatório | 5 |
| RF-11 | MODELO_DE_DADOS (`PROCESSO`) | `application/linha_do_tempo/agrupamento` | pureza ≥ 0,90 | 6 |
| RF-12 | MODELO_DE_DADOS (8 relações), ADR-012 | classificador híbrido + `analista_linha_do_tempo.v1` | F1-macro ≥ 0,85, matriz de confusão | 6 |
| RF-13 | ADR-008 | API linha do tempo + SVG | teste E2E | 6/9 |
| RF-14 | MODELO_DE_DADOS §2 | `domain/normas.py`, filtro de vigência | testes de domínio (TDD) | 6 |
| RF-15 | ADR-003, ADR-004 | roteador (regras + `roteador.v1`) | acurácia de rota ≥ 0,90 | 7 |
| RF-16 | `parecer_especialista.v1.json` | 8 especialistas | validade JSON 100% (`tests/test_agentes_specs.py` + contrato) | 7 |
| RF-17 | ADR-003 | `verificador_fontes.v1` + checagem lexical | alucinação ≤ 5% | 7 |
| RF-18 | `relator.v1.json` | relator | presença de consensos/divergências | 7 |
| RF-19 | MODELO_DE_DADOS (`DECISAO`) | memória de decisões | Recall@3 de precedentes ≥ 0,80 | 8 |
| RF-20 | `relator.v1.md` | relator F2 | 6 elementos + aviso em 100% | 8 |
| RF-21–23 | ADR-008, v1 auth | interface + API | E2E, 401/403 | 9 |
| RF-24 | ADR-009, MODELO_DE_DADOS (`CONSULTA`, `AUDITORIA`) | API | teste de auditoria | 7–9 |
| RF-25 | ADR-004 §2 | `application/anonimizador` | 100% CPF/e-mail; recall nomes ≥ 0,90 | 7 |
| RF-26 | ADR-013 | pacotes v1 | 238 testes v1 verdes | todas |
| RNF-01 | ADR-001 | — | MODELOS_IA.md (custo R$ 0) | todas |
| RNF-02/03 | ADR-001, ADR-010 | `instalar.bat`, variáveis de cache | diagnóstico de pastas | 3 |
| RNF-04/05 | ADR-004, ADR-009 | tabela `consultas`/`spans` | p50/p95, tokens/consulta | 5–10 |
| RNF-06 | ADR-011 | verificador + avaliação | faithfulness, alucinação | 5–10 |
| RNF-07 | ADR-001 | CI | varredura de segredos | 3 |
| RNF-08 | ADR-002, ADR-004 | `domain/politicas.py` | teste: provedor remoto bloqueado com `corpus_origem=real` | 3–7 |
| RNF-09 | ADR-013 | todo o código | cobertura ≥ 80% em domain/application; teste de dependências | 3– |
| RNF-10 | ADR-004 | `LLMPort` + adaptadores | teste com 2 provedores | 7 |
| RNF-11 | ADR-009 | `TracerPort`, Phoenix | 100% das consultas com trace | 3–7 |
| RNF-12 | ADR-011 | GitHub Actions | suíte reduzida por PR | 3–5 |
| RNF-13 | ADR-008 | frontend | `scripts/verificar_contraste.py`, teclado | 9 |
| RNF-14 | CLAUDE.md | docs | retomada por STATUS.md | todas |
