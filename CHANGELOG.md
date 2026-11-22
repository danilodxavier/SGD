# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento semântico.

## [Não lançado] — Reestruturação SAD-GD

### Adicionado
- Busca restrita ao contrato citado quando a ficha não basta (F1 e decisão): documentos da pasta + 3 vagas do acervo inteiro, reranqueados juntos — validação: documento esperado 37/37, foco 18% → 27%, busca 1,8 → 1,0 s.
- Ficha responde "contrato nº X" quando o número existe no acervo só em outros documentos (mostra onde aparece) e confere ausência com ano pelo início dos documentos (título/abertura + data).
- Ficha responde mais na hora: panorama de vigência de todos os contratos (vencendo em 120 dias, encerrados, vigentes), relatório de apuração e notificação extrajudicial reconhecidos pelo título, perguntas de existência sem contrato citado e ausência com ano conferida no texto dos documentos.
- Fichas de contrato atualizadas automaticamente ao fim de cada indexação (tela Acervo e `indexar.py`; `SADGD_FICHAS_APOS_INDEXAR`).
- Fichas de contrato pré-processadas (ADR-015): agrupamento por pasta/número, extração conferida com o LLM local (`scripts/sadgd/gerar_fichas.py`), inventário por tipo e resposta sem LLM em milissegundos para objeto, partes, valor, vigência, fiscal, documentos de um tipo, contratos de um fornecedor e perguntas transversais; o resto segue o caminho completo.
- Fase 12 (implantação na rede): fila de consultas com posição/etapa (`/api/sadgd/consultas`), chat por texto e **voz** na tela Perguntar (transcrição local com faster-whisper, `/api/sadgd/transcrever`), instalação/validação do certificado da STI (`scripts/rede/instalar_certificado.py`) e publicação com firewall e início automático (`scripts/rede/publicar_rede.ps1`).
- A1 (acervo real): segundo nível de classificação com 15 novos tipos e uso do nome do arquivo; `reclassificar.py`; amostra de tipos para conferência humana (`avaliar_real.py amostra-tipos|medir-tipos`).
- A3 (latência): reranker na GPU por padrão (`SADGD_DISPOSITIVO_RERANKER=auto`) e compressão do contexto orientada pela pergunta (`SADGD_CONTEXTO_MAX_CHARS=1200`); F1 no acervo real 60,5 s → 17,3 s, exatidão na validação inalterada (0,923).
- Avaliação com documentos reais: `scripts/sadgd/avaliar_real.py` (modelo, executar, revisao, resumo — só métricas agregadas na tela; resultados em `avaliacao/real/`, fora do Git) e protocolo `docs/AVALIACAO_REAL.md`; 3 testes.
- Fase 11: provedor Gemini (plano gratuito) para a F2 do corpus acadêmico, com reserva local e nova tentativa no próprio provedor quando o JSON vem cortado; avaliação da F2 no Gemini (p95 100 s, meta ≤ 120 s atendida); relatório de atividades e ferramentas; vídeo de apresentação com narração local (`scripts/video/`).
- Fase 10: cache semântico calibrado (identificadores + versão do acervo + cosseno ≥ 0,93) com auditoria; faithfulness com LLM-juiz de outra família, calibração por corrupções controladas, κ de Cohen, Rogan–Gladen e adjudicação; experimentos de latência da F2; scripts `avaliar_fidelidade.py`, `calibrar_cache.py`, `medir_cache.py`; orquestrador com LLM separado para o relator.
- Fase 9 (MVP): telas Perguntar (F1/F2 com fontes, pareceres, precedentes e RF-20), Acervo (upload e indexação no servidor), Linha do tempo (fases e evidências), Decisões e Painel do SAD-GD; perfil Gestor; API do acervo (painel, documentos, arquivo com CSP sandbox, trecho, busca, upload, indexação); serviço de indexação em segundo plano; caso de uso `construir_grafo`; migração 005; testes E2E no Edge com Playwright; 11 novos testes.
- Fase 8 (apoio à decisão): memória de decisões (domínio, migração 004 com FTS5, repositório, busca híbrida com rerank e limiar calibrado), memória sintética de 30 decisões e 50 perguntas de precedente, recomendação F2 com os 6 elementos de RF-20 (precedentes e base legal determinísticos, hierarquia e vigência), relator v2 (prompt e schema), API `/api/sadgd/decisoes` e `/api/sadgd/precedentes`, scripts `gerar_memoria_decisoes.py`, `importar_decisoes.py`, `avaliar_precedentes.py`; 17 novos testes.
- Fase 7 (multiagentes): roteador por regras, verificador de fontes determinístico (integrado ao ResponderF1), especialistas com JSON validado e reparo de forma, relator F2, orquestrador LangGraph com fan-out paralelo, anonimização LGPD reversível e política de envio a provedores remotos, auditoria de consultas (hash da pergunta), resumo da linha do tempo para a F2, API `POST /api/sadgd/perguntar`, scripts `avaliar_roteador.py`, `avaliar_anonimizacao.py`, `avaliar_f2.py` e flag `--verificador` em `avaliar_respostas.py`; Qwen 2.5 3B avaliado.
- Fase 6 (linha do tempo): extração de referências, classificador de relações por regras (notas de compilação, revogação parcial, retomada), detecção de contradições, agrupamento, vigência pelo grafo, respostas de conflito determinísticas, API `/api/sadgd/processos` e `/api/sadgd/linha-do-tempo`, scripts de construção e avaliação do grafo; 21 novos testes.
- Fase 5 (RAG): recuperação híbrida com RRF, filtro de vigência e reranker; ResponderF1 com citações e salvaguardas; golden set de 177 perguntas validadas; suíte de avaliação em estágios (recuperação, respostas, relatório, CI); baseline v1 × v2; benchmark Qwen 2.5 7B × Llama 3.1 8B; 31 novos testes.
- Fase 4 (ingestão): corpus público (69 atos oficiais) e sintético (117 documentos, 27 processos, 99 relações, gabarito); chunking estrutural jurídico; extrator de HTML legal com detecção de texto tachado; metadados por regras; indexação híbrida incremental (FTS5 + sqlite-vec + bge-m3) com parada limpa e retomada; scripts de avaliação (chunking, metadados, OCR); migração 003; 53 novos testes.
- Fase 3 (infraestrutura): camadas `app/domain`, `app/application/portas.py`, `app/infrastructure` (SQLite + sqlite-vec com migrações, adaptador LLM OpenAI-compatível, tracer SQLite); banco único `sadgd.db`; Ollama e Tesseract portáteis (`scripts/sadgd/*.ps1`); dependências em camadas e `constraints.txt`; `pyproject.toml` (pytest, coverage, ruff); CI no GitHub Actions; diagnóstico SAD-GD; 46 novos testes.
- Fase 2 (arquitetura): `docs/arquitetura/C4.md`, `docs/arquitetura/MODELO_DE_DADOS.md`, ADR-003 a ADR-013, `docs/agentes/README.md`, `docs/projeto/RASTREABILIDADE.md`.
- Prompts versionados de 12 agentes + regras comuns (`app/application/agentes/prompts/`) e 5 schemas JSON (`app/application/agentes/schemas/`).
- `tests/test_agentes_specs.py` (consistência prompts × schemas × catálogo).
- Backlog: item SAD-055 (benchmark de LLMs na Fase 5).
- `CLAUDE.md` com prompt mestre do SAD-GD e decisões vigentes.
- Documentação de planejamento (Fase 1): termo de abertura, partes interessadas, requisitos, EAP, cronograma, riscos e backlog (`docs/projeto/`).
- ADR-001 (execução local, ferramentas gratuitas, tudo em subpastas) e ADR-002 (corpus acadêmico).
- `docs/STATUS.md`, `CONTINUIDADE.md`, `MODELOS_IA.md`, `METODOLOGIAS.md`, `HABILIDADES.md`, `AVALIACAO.md`.
- `scripts/github/criar_backlog.ps1` para publicar o backlog no GitHub Projects.
- Relatório de auditoria `docs/fases/FASE_00.md`.

### Alterado
- Decisão (F2): contexto compartilhado entre especialistas e relator (cache de prefixo do Ollama; relator 58 → 25 s) e ficha do contrato com trechos citáveis no contexto; volta ao modelo padrão (a variante 100% GPU é mais lenta com o reranker na placa); LLM mantido carregado por 12 h.
- Desempenho (Fase 12): variante `sadgd-qwen2.5-7b-gpu` (`num_gpu 29`, modelo inteiro na GPU: geração 21 → 38 tok/s), compressão do contexto 800 caracteres, relator v3 só com instruções da F1, detalhe reprovado pelo verificador removido sem nova chamada ao LLM — validação: LLM p50 23 → 17 s, p95 49 → 31 s, sem perda de exatidão.
- Documentação final da Fase 11: `docs/RELATORIO_TECNICO.md`, manuais do usuário e técnico reescritos para o SAD-GD (os da v1 em `docs/legado/*_v1.md`), README final, `docs/DEMONSTRACAO.md` e `docs/projeto/LICOES_APRENDIDAS.md`.
- Relator F2: `consensos` explicitamente como lista de frases e reparo de forma de `{tema, posicoes}` para frase (schema do relator no Gemini 0,333 → 1,00).
- Produto renomeado para SAD-GD 2.0.0.dev0 na interface; painel, "Atualizar índice" e OCR passam a usar o indexador do SAD-GD; telas v1 (Perguntas, Documentos, Checklist, Relatórios) saem do menu; indexador com modo parcial; `.gitignore` restringe `corpus/` ao público/sintético.
- Grafo: documento não normativo que cita ato normativo passa a `fundamenta` (pureza do agrupamento 0,932 → 0,966); instruções dos especialistas exigem `pros`/`contras` como listas.
- Gabarito sintético revisado (99 → 103 relações) via `gerar_corpus_sintetico.py --somente-gabarito`; métrica de alucinação numérica normaliza datas por extenso e citações de atos.
- `LLMPort.chat` aceita `json_livre`; CI executa a avaliação reduzida (`avaliar.py ci`).
- OCR `auto` passa a priorizar o Tesseract (CER 0,09% contra 0,52%). Embeddings em float32 e carga sequencial de pesos (`HF_DEACTIVATE_ASYNC_LOAD`).
- `instalar.bat`, `start.bat`, `stop.bat` e diagnóstico adaptados ao SAD-GD; IA da v1 passa a usar o Ollama do projeto; caches de IA forçados para dentro do projeto e telemetria de terceiros desativada.
- `app/services/llm.py`: mensagens de erro detalhadas do servidor de IA e filtro de modelos de embedding.
- Especificação v1 (`AGENTS.md`), `ARQUITETURA.md` e `CONFORMIDADE.md` movidos para `docs/legado/`.

### Corrigido
- Respostas rápidas das fichas: vigência antes de "aditivo"; valor só do contrato e atualizado pelo aditivo mais recente; conteúdo de documento, dados pessoais/representantes e contradições do grafo (RF-09) vão ao caminho completo; ausência só é afirmada se o texto da pasta não cita o assunto. 2ª passada de extração (extratos, portarias, vigência e valor atuais pelo aditivo): campos reais 104 → 170.
- Respostas F1 secas ("recortes"): resposta direta + detalhes citados (relator v3, campo `detalhes`, sem detalhe sem citação ou repetido); verificador confere o número de cada frase contra o trecho que ela cita; perguntas de histórico recebem a linha do tempo do grafo; perguntas de lista buscam mais documentos distintos e respondem em itens; até 12 trechos na F1.
- Recusas indevidas no acervo real ("Qual o contrato do <fornecedor de software>?" (R05) com 8 trechos do contrato certo): cada trecho leva a ficha do documento (tipo, nº, processo, pasta), aceita também pelo verificador (regras comuns v2, regra 11); cópias idênticas saem antes do rerank; abertura (início + objeto) dos 3 documentos mais relevantes sem número (`SADGD_ABERTURAS`); 2ª leitura com evidências só quando a 1ª recusa, com correção dirigida se o modelo listar evidências e recusar.
- F2 no acervo real: prompts dos especialistas estouravam o contexto de 8.192 tokens (instruções cortadas, todas as afirmações removidas pelo verificador, recomendação sem fontes); a compressão do contexto (`SADGD_CONTEXTO_MAX_CHARS`) agora vale também para especialistas e relator.
- Grafo: documento que cita dois contratos não funde mais os processos (só substituição direta entre contratos).
- `scripts/github/criar_backlog.ps1`: argumentos com barra invertida final quebravam a chamada ao `gh` no PowerShell 5.1; reexecução falhava com `-like` e colchetes. Kanban publicado (GitHub Project #2, 52 issues).
- `POST /api/sadgd/perguntar`: a montagem real do orquestrador passava `ResultadoRecuperacao` ao grafo em vez da lista de trechos (falhava desde a Fase 7; métricas não afetadas); teste de regressão da montagem real.

### Removido
- Código v1 sem uso (aprovado na Fase 10; tag `backup/pre-limpeza-v1`): pacotes `checklist`, `contracts`, `retrieval`, `indexing`; serviços e rotas de perguntas, documentos, checklist, relatórios, busca e IA v1; telas v1; `scripts/indexar.py`, `scripts/aceitacao.py`, `aceitacao.bat`; 165 testes exclusivos da v1. Tabelas v1 do banco preservadas (decisão pendente).
- Cópia duplicada da especificação (`READ ME — Agente de Inteligência Documental — Contratos e Checklists.md`).
- Fora do Git: 169.698 registros `REMOVIDO` do banco (compactado de 6,6 GB para 1,7 GB; original em `BACKUP\pre-reestruturacao\`), logs rotacionados antigos, `data/app.pid` e `.pytest_cache/`.
- Fora do Git (a pedido do responsável): todos os documentos, trechos, contratos e itens do banco v1 (1,72 GB → 0,11 MB); raiz documental passa a ser `corpus\`.

## [1.0.0] — 2026-10-14

- Aplicação local de inteligência documental para contratos e checklists (ver `docs/legado/`).
