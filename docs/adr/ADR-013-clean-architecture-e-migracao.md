# ADR-013 — Clean Architecture e migração incremental (strangler fig)

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | RNF-09, RNF-10, RF-26 |

## Contexto

O código v1 está organizado por tipo técnico (`api`, `services`, `ingestion`…), com regras de negócio misturadas a SQL e HTTP (ex.: `services/questions.py`, 633 linhas). Os 238 testes v1 são a rede de segurança.

## Decisão

### Estrutura-alvo

```text
app\
├── domain\            # Python puro, sem I/O: entidades, enums, regras
│   ├── documentos.py  # Documento, Trecho, Dispositivo, CorpusOrigem
│   ├── normas.py      # EspecieNormativa, hierarquia, vigência
│   ├── relacoes.py    # TipoRelacao (8 classes + auxiliares), Relacao
│   ├── decisoes.py    # Decisao, Precedente
│   ├── pareceres.py   # Parecer, Citacao, Risco, Recomendacao
│   └── politicas.py   # política de envio externo, classificação fato/inferência/conflito/ausência
├── application\       # casos de uso + portas (interfaces)
│   ├── portas.py      # LLMPort, EmbeddingPort, RerankerPort, VectorStorePort, Repositorios, OCRPort, TracerPort
│   ├── casos_de_uso\  # perguntar_f1, apoiar_decisao_f2, linha_do_tempo, indexar, registrar_decisao
│   ├── recuperacao\   # híbrido, RRF, rerank, filtros
│   └── agentes\       # grafo LangGraph, nós, prompts\ (versionados), schemas\
├── infrastructure\    # adaptadores: sqlite, sqlite_vec, fts5, llm\ (ollama, lmstudio, gemini, groq, openrouter), modelos\ (bge), ocr\, extratores\ (v1), tracing\
├── interfaces\api\    # FastAPI (rotas finas → casos de uso)
└── (pacotes v1)       # mantidos até serem absorvidos; removidos só com aprovação
```

Regra de dependência verificada por teste (`import-linter` ou teste próprio): `domain` não importa nada do projeto; `application` só importa `domain`; `infrastructure` e `interfaces` importam para dentro.

### Migração

1. **Strangler fig:** os módulos novos nascem ao lado da v1; as rotas v1 seguem funcionando.
2. Extratores v1 passam para `infrastructure\extratores\` com reexportação nos caminhos antigos até a remoção.
3. `services/questions.py` (regras) vira o adaptador `RespondedorRegrasV1` — **baseline** de avaliação.
4. Remoção de código v1 apenas com aprovação do responsável (regra 2).

### Práticas

- **SOLID:** portas pequenas (ISP), injeção de dependência por fábrica de configuração (DIP).
- **TDD** nos componentes críticos: regras de domínio (hierarquia, vigência, política de envio), métricas de avaliação, chunking estrutural, RRF, verificador de fontes, validação de schemas.
- **GitHub Flow + Conventional Commits**; PR com CI verde.
- Cobertura ≥ 80% em `domain\` e `application\` (RNF-09).

## Consequências

- (+) Troca de provedores e de armazenamento sem tocar no domínio; testes rápidos sem I/O.
- (−) Período de convivência v1/v2 com alguma duplicação; limitado por cronograma de absorção por fase.
