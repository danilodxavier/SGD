# EAP — Estrutura Analítica do Projeto SAD-GD

Decomposição orientada a entregas (PMBOK). Pacotes de trabalho no 3º nível viram issues do backlog (`docs/projeto/BACKLOG.md`).

```text
1 SAD-GD
├── 1.0 Gerenciamento do projeto
│   ├── 1.0.1 Auditoria do legado (FASE_00) ✅
│   ├── 1.0.2 Termo de abertura, partes interessadas
│   ├── 1.0.3 Escopo e requisitos
│   ├── 1.0.4 EAP, cronograma, riscos
│   ├── 1.0.5 Backlog e quadro Kanban (GitHub Projects)
│   ├── 1.0.6 Revisões de sprint/aprovações e retrospectivas
│   └── 1.0.7 Lições aprendidas
├── 2.0 Arquitetura
│   ├── 2.0.1 Diagramas C4 (contexto, contêiner, componente)
│   ├── 2.0.2 ADRs de stack (framework de agentes, LLM, embeddings, vetorial, OCR, frontend, observabilidade)
│   ├── 2.0.3 Modelo de dados e grafo documental
│   ├── 2.0.4 Especificação e prompts dos agentes (docs/agentes/)
│   └── 2.0.5 Matriz de rastreabilidade
├── 3.0 Infraestrutura local
│   ├── 3.0.1 Reestruturação do repositório (Clean Architecture)
│   ├── 3.0.2 Ambiente Python reprodutível + modelos em modelos\
│   ├── 3.0.3 Repositório GitHub, proteção de branch, Projects
│   ├── 3.0.4 CI (GitHub Actions): lint, testes, varredura de segredos, avaliação reduzida
│   └── 3.0.5 Observabilidade (traces, tokens, latência)
├── 4.0 Base de conhecimento
│   ├── 4.0.1 Corpus acadêmico (público + sintético) e manifesto
│   ├── 4.0.2 OCR portátil (Tesseract)
│   ├── 4.0.3 Chunking estrutural jurídico
│   ├── 4.0.4 Extração de metadados
│   ├── 4.0.5 Embeddings locais e índice vetorial
│   └── 4.0.6 Indexação híbrida incremental
├── 5.0 RAG F1 e avaliação
│   ├── 5.0.1 Busca híbrida + RRF + reranking
│   ├── 5.0.2 Geração com citação literal e recusa
│   ├── 5.0.3 Golden set ≥ 100 perguntas (validação/teste)
│   ├── 5.0.4 Suíte de métricas (recuperação, geração, operacionais)
│   └── 5.0.5 Baseline v1 (regras) × v2 (RAG) em AVALIACAO.md
├── 6.0 Linha do tempo e normas
│   ├── 6.0.1 Agrupamento por processo/contrato/tema
│   ├── 6.0.2 Classificador de relações (8 classes) + métricas
│   ├── 6.0.3 Hierarquia normativa e vigência
│   └── 6.0.4 Grafo documental persistido
├── 7.0 Multiagentes
│   ├── 7.0.1 Roteador
│   ├── 7.0.2 Especialistas (6 + propostos)
│   ├── 7.0.3 Verificador de fontes
│   ├── 7.0.4 Relator
│   ├── 7.0.5 Anonimização e auditoria
│   └── 7.0.6 Avaliação multiagentes
├── 8.0 Apoio à decisão (F2)
│   ├── 8.0.1 Memória de decisões e precedentes
│   ├── 8.0.2 Recomendação com alternativas/riscos/confiança
│   └── 8.0.3 Avaliação F2 (golden set F2)
├── 9.0 MVP
│   ├── 9.0.1 Chat + painel de fontes + pareceres
│   ├── 9.0.2 Upload e gestão de documentos
│   ├── 9.0.3 Visualização da linha do tempo
│   ├── 9.0.4 Autenticação e perfis
│   └── 9.0.5 Empacotamento local (instalar/start)
├── 10.0 Otimização
│   ├── 10.0.1 Cache semântico, compressão de contexto, roteamento de modelos
│   └── 10.0.2 Avaliação final × metas
└── 11.0 Entrega acadêmica
    ├── 11.0.1 Relatório técnico
    ├── 11.0.2 README, manuais e documentação final
    ├── 11.0.3 Roteiro e vídeo de demonstração
    └── 11.0.4 Lições aprendidas
```

## Dicionário resumido

| Pacote | Entregável | Critério de aceite |
|---|---|---|
| 4.0.1 | `corpus\` + `MANIFESTO.csv` | ≥ 150 documentos (≥ 60 públicos, ≥ 90 sintéticos) com origem e hash; ≥ 10 processos com linha do tempo |
| 5.0.3 | `avaliacao\golden_set\*.jsonl` | ≥ 100 perguntas (≥ 60 F1, ≥ 20 linha do tempo, ≥ 20 F2), split 30/70 validação/teste, revisadas pelo responsável |
| 5.0.4 | `scripts\avaliar.py` + relatório | Gera todas as métricas da seção 4 do prompt mestre em uma execução |
| 6.0.2 | Classificador + matriz de confusão | F1-macro ≥ 0,85 |
| 7.0.3 | Verificador | Alucinação ≤ 5% |
