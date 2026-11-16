# Habilidades e conhecimentos adquiridos — SAD-GD

## Técnicos

| Data | Habilidade / conhecimento | Contexto |
|---|---|---|
| 2026-11-16 | Diagnóstico de inchaço em SQLite: registros lógicos removidos + freelist (1,16 M páginas livres) explicam 6,6 GB; `VACUUM INTO` gera cópia compacta verificável sem tocar no original | Fase 0 — banco reduzido de 6,6 GB para 1,7 GB |
| 2026-11-16 | Tabelas FTS5 sem *external content* não são limpas por `ON DELETE CASCADE`; a remoção precisa ser explícita | Fase 0 — análise do indexador v1 |
| 2026-11-16 | Limites de hardware local para IA: 6 GB de VRAM comportam LLM 7–8B Q4; 16 GB de RAM exigem carregar modelos sob demanda | Fase 1 — riscos R01/R02 |
| 2026-11-16 | Após `DELETE` em massa numa tabela FTS5 comum, os segmentos do índice continuam no arquivo; é preciso `INSERT INTO t(t) VALUES('rebuild')` (ou `optimize`) antes do `VACUUM` (1,48 GB → 0,11 MB) | Fase 1 — exclusão dos documentos |
| 2026-11-16 | `pip install --dry-run --report` resolve dependências usando metadados PEP 658 sem baixar wheels — forma barata de verificar compatibilidade de uma stack com uma versão nova do Python | Fase 2 — ADR-010 |
| 2026-11-16 | Entradas do `py` launcher podem apontar para instalações removidas; verificar o executável antes de planejar em cima delas | Fase 2 — Python 3.13 quebrado |
| 2026-11-16 | Licenças importam na escolha de stack: PyMuPDF é AGPL-3.0; Phoenix é Elastic License 2.0; LangGraph e bge-m3 são permissivos | Fase 2 — ADR-007/009 |
| 2026-11-16 | Langfuse v3 self-hosted depende de Postgres + ClickHouse + Redis + S3; para máquina única com 16 GB, uma ferramenta pip-only (Phoenix) é mais adequada | Fase 2 — ADR-009 |
| 2026-11-16 | Ferramentas de IA com telemetria ativa por padrão (CrewAI, RAGAS, DeepEval) exigem opt-out explícito em contexto LGPD | Fase 2 — ADR-003/011 |
| 2026-11-16 | Instaladores NSIS podem ignorar `/D` e instalar em Program Files; ferramentas relocáveis (Tesseract) podem ser copiadas para o projeto e desinstaladas do sistema | Fase 3 — ADR-007 |
| 2026-11-16 | Ollama tem distribuição portátil (zip) e importa GGUF existente com `ollama create -f Modelfile` — evita baixar o mesmo modelo duas vezes | Fase 3 — ADR-004 |
| 2026-11-16 | Índices do PyTorch publicam CUDA por versão de Python com atraso: para cp315 havia 2.14.1 (cu126/cu130), não 2.15; listar o índice com ordenação por `[version]`, não alfabética | Fase 3 — ADR-010 |
| 2026-11-16 | Resolução `pip --dry-run` não garante funcionamento: RAGAS 0.3.1 resolvia, mas quebrava na importação por API removida do langchain-community — sempre testar `import` | Fase 3 — ADR-011 |
| 2026-11-16 | Nomes de variáveis de opt-out de telemetria devem ser conferidos no código-fonte da biblioteca, não presumidos | Fase 3 — ADR-009 |
| 2026-11-16 | Em Python, `sqlite3` com `isolation_level=None` permite `BEGIN/COMMIT` explícitos para migrações DDL atômicas | Fase 3 — migrador |
| 2026-11-16 | `sed` em Git Bash consome barras invertidas de caminhos Windows na substituição; editar caminhos via PowerShell/Python | Fase 3 — incidente |
| 2026-11-16 | Um venv de desenvolvimento "sujo" esconde dependências não declaradas (`defusedxml` da v1); só o CI em ambiente limpo revelou — reproduzir o CI num venv novo antes de concluir | Fase 3 — primeiro CI no GitHub |
| 2026-11-16 | gitleaks-action usa código 1 para falha da ferramenta (2 = segredos); a CLI em contêiner sobre o histórico completo tem semântica mais simples e independe da faixa do push | Fase 3 — CI |
| 2026-11-16 | transformers 5 carrega pesos em paralelo (pool de threads); com Python 3.15 + torch 2.14 no Windows isso causa `access violation` — `HF_DEACTIVATE_ASYNC_LOAD=1` força carga sequencial | Fase 4 — embeddings |
| 2026-11-16 | Em GPUs Turing sem tensor cores (GTX 16xx), float16 pode ser muito mais lento que float32 no PyTorch (3,8 × 19 trechos/s) | Fase 4 — embeddings |
| 2026-11-16 | Portais governamentais podem recusar a assinatura TLS de clientes Python/curl e User-Agents desconhecidos; o cliente HTTP do Windows passa | Fase 4 — coleta |
| 2026-11-16 | Processos em lote devem gravar progresso e marcar conclusão por lote: um encerramento abrupto entre "gravar documento" e "gravar vetores" deixaria dados órfãos permanentes | Fase 4 — indexador |
| 2026-11-16 | Um processo pode bloquear a remoção de pasta no Windows só por ter o diretório como pasta corrente | Fase 4 — gerador |

## Domínio (setor público)

| Data | Conhecimento | Contexto |
|---|---|---|
| 2026-11-16 | Hierarquia normativa (CF > Lei > Decreto > IN > Orientação) e vigência temporal como requisito de recuperação, não só de geração | Requisito RF-14 |
| 2026-11-16 | Lei 14.133/2021 como referência para aditivos, prorrogações e fiscalização contratual | Agente Fiscal de Contrato |
| 2026-11-16 | LGPD: documentos públicos podem conter dados pessoais; separar corpus de avaliação de dados reais | ADR-002 |
| 2026-11-16 | No texto compilado oficial, dispositivos revogados ou com redação substituída aparecem tachados, e a nota de revogação do ato inteiro fica logo abaixo do título — evidências documentais de vigência | Fase 4 — extrator HTML |
| 2026-11-16 | Revogação parcial (ex.: Lei 12.462 teve artigos revogados pela 14.133) não pode ser confundida com revogação total | Fase 4 — metadados |
| 2026-11-16 | Atos oficiais não têm proteção autoral (Lei 9.610/1998, art. 8º, IV) — podem compor corpus público versionado | Fase 4 — corpus |
