# FASE 03 — Infraestrutura local (Sprint S3)

| Campo | Valor |
|---|---|
| Período | 2026-11-16 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aguardando aprovação** |

## 1. Planejamento

Itens: SAD-030 a SAD-033 (+ SAD-002/003 bloqueados pelo GitHub). Diretriz do responsável na aprovação da Fase 2: *"Troque o que for necessário do projeto antigo, a fim de que o novo projeto seja entregue na íntegra"* — interpretada como autorização para substituir componentes v1 conforme a arquitetura exigir (sem nova aprovação por troca), mantendo a regra de parar ao fim de cada fase.

## 2. Entregas

### 2.1 Ambiente e ferramentas (tudo dentro do projeto — ADR-001)

| Item | Resultado | Evidência |
|---|---|---|
| Dependências em camadas | `requirements-ia.txt`, `-avaliacao`, `-observabilidade`, `-dev` + `constraints.txt` (224 pacotes) | `pip check`: sem conflitos |
| PyTorch com GPU | `torch 2.14.1+cu126`, `cuda.is_available() = True` (GTX 1660 SUPER) | diagnóstico |
| Ollama portátil | v0.40.16 em `ferramentas\ollama`; modelos em `modelos\ollama`; `scripts\sadgd\ollama.ps1` (instalar/iniciar/parar/status/modelo) | ciclo parar/iniciar testado |
| Modelo LLM local | `sadgd-qwen2.5-7b` importado do GGUF existente (4,36 GB); 24/29 camadas na GPU; JSON de roteamento em ~0,4 s | chamada real via `/v1/chat/completions` |
| Tesseract portátil | 5.4.0 em `ferramentas\tesseract` com `por` (tessdata_best); `scripts\sadgd\tesseract.ps1` | `--list-langs`: eng, osd, por |
| Arize Phoenix | 21.0.0, servidor em `127.0.0.1:6006`, dados em `data\observabilidade` | HTTP 200 |
| Telemetria de terceiros | desativada; nomes das variáveis conferidos no código das bibliotecas | diagnóstico "telemetria: desativada" |
| Caches no projeto | `HF_HOME`, `TORCH_HOME`, `PHOENIX_WORKING_DIR` definidos em `app/core/config.py`; pytest e ruff com cache em `data\cache` | diagnóstico "pastas no projeto: OK" |

### 2.2 Código (Clean Architecture — ADR-013)

| Camada | Arquivos | Testes |
|---|---|---|
| `app/domain` | `documentos.py`, `normas.py` (hierarquia + vigência), `relacoes.py` (8 + 2 relações, ciclos), `politicas.py` (envio externo, mensagens institucionais) | `tests/sadgd/test_dominio.py` (TDD) |
| `app/application` | `portas.py` (LLMPort, EmbeddingPort, RerankerPort, VectorStorePort, OCRPort, TracerPort) | contrato verificado nos testes de adaptadores |
| `app/infrastructure/sqlite` | `conexao.py` (sqlite-vec + migrador transacional), `migracoes/001_esquema_inicial.sql`, `002_vetores.sql` | `tests/sadgd/test_infra_sqlite.py` |
| `app/infrastructure/llm` | `openai_compativel.py` (Ollama/LM Studio/free tier; tokens, latência, JSON, retentativas, só http/https) | `tests/sadgd/test_llm_adapter.py` (servidor simulado) |
| `app/infrastructure/tracing` | `sqlite_tracer.py` (spans + p50/p95) | `tests/sadgd/test_infra_sqlite.py` |
| Regra de dependência | análise estática de imports | `tests/sadgd/test_arquitetura.py` |

### 2.3 Banco de dados único (ADR-006)

- `data\database\sadgd.db` criado a partir do banco v1 zerado (2 usuários e checklist preservados) + migrações 001/002. O arquivo `documents.db` foi retirado para `BACKUP\pre-reestruturacao\documents_v1_zerado.db`.
- `init_db()` da v1 agora também aplica as migrações SAD-GD (`preparar_esquema_sadgd`) — todos os testes v1 exercitam o novo esquema.
- Configuração v1 de IA redirecionada do LM Studio para o Ollama do projeto (`sadgd-qwen2.5-7b:latest`, status "Pronto").

### 2.4 Operação

- `instalar.bat` reescrito (11 etapas): caches no projeto, torch CUDA/CPU automático, dependências em camadas, Ollama + modelo, Tesseract, migração do banco, diagnóstico.
- `start.bat` inicia o Ollama do projeto; `stop.bat` o encerra.
- Diagnóstico ampliado (`checks_sadgd`): pastas no projeto, telemetria, sqlite-vec, migrações, bibliotecas de IA, GPU, Ollama + modelo, Tesseract + `por`, GitHub CLI.

### 2.5 Qualidade e CI

- `pyproject.toml`: pytest (`--basetemp` no projeto), coverage, ruff (E, F, W, I, B, UP, S, SIM) sobre o código SAD-GD.
- `.github/workflows/ci.yml`: varredura de segredos (gitleaks), lint, testes em Windows com Python 3.15, **portão de cobertura ≥ 80% em domain/application**, gancho da avaliação reduzida (Fase 5).

## 3. Evidências de verificação

| Verificação | Resultado |
|---|---|
| `pytest` (v1 + SAD-GD) | **300 passed** em 125 s |
| Cobertura `domain` + `application` | **97%** (portão 80%) |
| Cobertura SAD-GD total (incl. infraestrutura) | 95% |
| `ruff check .` | All checks passed |
| `scripts\diagnostico.py` | **0 erros**, 1 aviso (GitHub CLI ausente) |

## 4. Critérios de aceite

| Critério (backlog) | Situação |
|---|---|
| SAD-030 — Reestruturar em Clean Architecture mantendo testes v1 verdes | ✅ camadas criadas e regra de dependência testada; os módulos v1 serão absorvidos fase a fase (ingestão na Fase 4, respostas na 5, etc.), conforme ADR-013 |
| SAD-031 — Ambiente reprodutível com modelos e caches no projeto | ✅ |
| SAD-032 — CI: lint, testes, segredos | ⚠️ workflow pronto e validado localmente; **execução no GitHub depende do repositório remoto** |
| SAD-033 — Observabilidade com tokens e latência por consulta | ✅ base pronta (tabela `spans` + Phoenix); instrumentação do grafo na Fase 7 |
| SAD-002/003 — GitHub e Projects | ❌ bloqueado: `gh` não instalado |

## 5. Incidentes e correções (transparência)

| Ocorrência | Tratamento |
|---|---|
| Instalador do Tesseract ignorou `/D` e instalou em `C:\Program Files` | Cópia para `ferramentas\tesseract` e **desinstalação do sistema** (pasta e registro removidos, verificado). Procedimento automatizado em `tesseract.ps1` |
| `sed` removeu barras do `DATABASE_PATH` e o `init_db` criou um arquivo avulso na raiz | Linhas corrigidas e arquivo avulso removido; banco correto verificado |
| RAGAS 0.3.1 incompatível com `langchain-community` | Atualizado para 0.4.4 (ADR-011) |
| `openinference-instrumentation-langchain` sem versão para Python 3.15 | Removido; spans via `TracerPort` (ADR-009) |
| Falha CUDA transitória na primeira carga do Ollama | Não reproduziu; retentativas no adaptador |

## 6. Uso de disco no projeto

`ferramentas\` 2,35 GB (Ollama 2,1 GB + Tesseract 0,25 GB) · `modelos\` 4,36 GB · `.venv` com torch CUDA · `BACKUP\` 6,6 GB (banco v1 original). Espaço livre em `D:` após a fase: ~54 GB.

## 7. Pendências

1. **GitHub:** `winget install GitHub.cli` → `gh auth login` → `gh auth refresh -s project` → criar repositório privado e publicar backlog (`scripts\github\criar_backlog.ps1`). Sem isso, CI e Kanban não rodam.
2. Opcional: o responsável pode apagar `BACKUP\pre-reestruturacao\documents.db` (6,6 GB) quando não precisar mais dos dados antigos.

## 8. Retrospectiva

- **Bem:** todas as ferramentas pesadas ficaram em subpastas; problemas de compatibilidade foram detectados e resolvidos com evidência, não suposição.
- **A melhorar:** um comando `sed` com barras invertidas causou efeito colateral; passei a editar caminhos Windows só via PowerShell/Python.
- **Ação:** Fase 4 começa pelo corpus acadêmico (risco R03) e pelo chunking estrutural com TDD.

## 9. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
