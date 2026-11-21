# Manual Técnico — SAD-GD

| | |
|---|---|
| **Sistema** | SAD-GD — Sistema de Apoio à Tomada de Decisão e Gestão Documental |
| **Versão documentada** | 2.0.0.dev0 |
| **Data** | 17/11/2026 |
| **Público** | Equipe de TI e desenvolvedores, inclusive sem contato prévio com o código |
| **Computador de referência** | Windows 11 Pro 64 bits · Python 3.15 · NVIDIA GTX 1660 SUPER (6 GB) · 16 GB RAM |

> Uso das telas: [Manual do Usuário](MANUAL_DO_USUARIO.md). Arquitetura e decisões: [`arquitetura/C4.md`](arquitetura/C4.md),
> [`adr/`](adr/), [`RELATORIO_TECNICO.md`](RELATORIO_TECNICO.md). Manual da v1: `legado/MANUAL_TECNICO_v1.md`.

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Requisitos](#2-requisitos)
3. [Estrutura de pastas](#3-estrutura-de-pastas)
4. [Instalação do zero](#4-instalação-do-zero)
5. [Preparar a base de conhecimento](#5-preparar-a-base-de-conhecimento)
6. [Configuração (`.env`)](#6-configuração-env)
7. [Operação do dia a dia](#7-operação-do-dia-a-dia)
8. [Provedor em nuvem para a F2 (opcional)](#8-provedor-em-nuvem-para-a-f2-opcional)
9. [Backup, restauração e migração](#9-backup-restauração-e-migração)
10. [Testes, qualidade e CI](#10-testes-qualidade-e-ci)
11. [Avaliação (métricas)](#11-avaliação-métricas)
12. [Manutenção e extensão](#12-manutenção-e-extensão)
13. [Solução de problemas](#13-solução-de-problemas)
14. [Segurança e LGPD — checklist de operação](#14-segurança-e-lgpd--checklist-de-operação)

---

## 1. Visão geral

```text
Navegador ──► FastAPI (127.0.0.1:8000) ──► Orquestrador LangGraph ──► Ollama local (Qwen 2.5 7B)
                    │                            │                └─► Gemini (opcional, só corpus acadêmico)
                    │                            └─► bge-m3 + bge-reranker-v2-m3 (em processo, GPU)
                    └─► SQLite data\database\sadgd.db (FTS5 + sqlite-vec + grafo + decisões + auditoria)
```

| Componente | Tecnologia | Onde |
|---|---|---|
| API e interface | FastAPI/Uvicorn; HTML/CSS/JS | `app/api/`, `app/interfaces/api/`, `frontend/` |
| Casos de uso | Python (Clean Architecture) | `app/application/` |
| Domínio | Python puro | `app/domain/` |
| Adaptadores | SQLite, sqlite-vec, Ollama/OpenAI-compatível, Tesseract, modelos HF | `app/infrastructure/` |
| LLM local | Ollama portátil + `sadgd-qwen2.5-7b` | `ferramentas\ollama\`, `modelos\ollama\` |
| Embeddings / reranker | `BAAI/bge-m3` (fp32) / `BAAI/bge-reranker-v2-m3` | `modelos\bge-m3\`, `modelos\hf\` |
| OCR | Tesseract 5 portátil (`por`) com Windows OCR como alternativa | `ferramentas\tesseract\` |
| Banco | SQLite único com migrações `001`–`006` | `app/infrastructure/sqlite/migracoes/` |

---

## 2. Requisitos

| Item | Mínimo | Observação |
|---|---|---|
| Sistema | Windows 10/11 64 bits | Scripts `.bat`/`.ps1` |
| Python | 3.13 ou superior (referência 3.15) | `python` no PATH para a instalação |
| GPU | NVIDIA com 6 GB (opcional) | Sem GPU funciona, com F1/F2 bem mais lentas |
| RAM | 16 GB | Com 1–2 GB livres, use os comandos com `--max-minutos` |
| Disco | ≈ 15 GB | Modelos (≈ 8 GB), dependências, banco e índices |
| Internet | Só na instalação | Download de dependências, Ollama, Tesseract e modelos |

Todas as ferramentas são gratuitas e ficam **dentro da pasta do projeto** (ADR-001): nada em `%TEMP%`,
`%USERPROFILE%` ou outras unidades.

---

## 3. Estrutura de pastas

```text
<projeto>\
├── app\            backend (domain, application, infrastructure, api, interfaces, core)
├── frontend\       interface web
├── tests\          testes (tests\sadgd\ = SAD-GD; E2E em test_e2e_navegador.py)
├── scripts\        backup, diagnóstico, usuários; scripts\sadgd\ = indexação, grafo, avaliação; scripts\video\
├── corpus\         publico\, sintetico\ (no Git), enviados\ (uploads reais, fora do Git), MANIFESTO.csv
├── avaliacao\      golden_set\ e execucoes\ (resultados)
├── modelos\        pesos (bge-m3, hf, ollama) — fora do Git
├── ferramentas\    Ollama e Tesseract portáteis — fora do Git
├── data\           banco, cache, logs, relatórios, observabilidade, vídeo — fora do Git
├── BACKUP\         backups — fora do Git
├── DOCUMENTOS\     documentos reais locais (opcional) — fora do Git, nunca vão à nuvem
└── docs\           documentação
```

> O caminho do projeto pode conter espaços (ex.: `GESTAO_ CONTRATO`): use **sempre aspas** nos comandos.

---

## 4. Instalação do zero

1. Copie a pasta do projeto (ou `git clone https://github.com/danilodxavier/SGD`).
2. Execute **`instalar.bat`** (duplo clique ou no terminal, com o caminho entre aspas). Ele faz 11 etapas:

| Etapa | O que faz |
|---|---|
| 1–2 | Verifica Windows e Python ≥ 3.13 |
| 3 | Cria `.venv` |
| 4 | Cria as pastas de trabalho (`data\…`, `modelos\…`, `corpus\…`, `avaliacao\…`) |
| 5 | Instala `requirements.txt` (cache do pip em `data\cache\pip`) |
| 6 | Instala PyTorch (CUDA 12.6 quando há GPU NVIDIA) |
| 7 | Instala `requirements-ia.txt`, `-avaliacao`, `-observabilidade`, `-dev` |
| 8 | Cria `.env` a partir de `.env.example` (mantém o existente) |
| 9 | Instala Ollama portátil, inicia e importa o modelo padrão; instala Tesseract portátil |
| 10 | Cria/migra o banco (`init_db`) e carrega a aplicação |
| 11 | Executa o diagnóstico |

3. Prepare o modelo de embeddings (uma vez):

```powershell
.\.venv\Scripts\python.exe scripts\sadgd\preparar_bge_m3.py
```

O reranker é baixado para `modelos\hf` no primeiro uso. **O servidor nunca baixa modelos ao iniciar**: sem o
bge-m3 em `modelos\`, a indexação automática gera só o índice textual (BM25).

4. Crie o primeiro administrador pela tela (primeiro acesso) ou por linha de comando:

```powershell
.\usuarios.bat criar --usuario maria.silva --nome "Maria Silva" --perfil admin
```

---

## 5. Preparar a base de conhecimento

Ordem obrigatória (cada etapa depende da anterior):

```powershell
# 1. Corpus acadêmico (já versionado; regenerar só se necessário)
.\.venv\Scripts\python.exe scripts\sadgd\coletar_corpus_publico.py      # atos oficiais -> corpus\publico
.\.venv\Scripts\python.exe scripts\sadgd\gerar_corpus_sintetico.py      # 117 documentos -> corpus\sintetico

# 2. Indexação incremental (retoma de onde parou)
.\.venv\Scripts\python.exe scripts\sadgd\indexar.py --max-minutos 7.5

# 3. Grafo documental, linha do tempo e vigência
.\.venv\Scripts\python.exe scripts\sadgd\construir_grafo.py

# 4. Memória de decisões (idempotente)
.\.venv\Scripts\python.exe scripts\sadgd\gerar_memoria_decisoes.py
.\.venv\Scripts\python.exe scripts\sadgd\importar_decisoes.py
```

- Repita `indexar.py --max-minutos 7.5` até indicar que terminou (com pouca RAM, processos longos em segundo plano
  são encerrados pelo sistema).
- Pela interface, o **upload** no Acervo indexa só o arquivo enviado e reconstrói o grafo automaticamente.
- Documentos **reais**: aponte `DOCUMENTS_ROOT` para a pasta e mantenha `CORPUS_ORIGEM=real` (padrão). Os
  originais nunca são alterados.

---

## 6. Configuração (`.env`)

O `.env` fica na raiz, **fora do Git**. Valores principais (lista completa e comentada em `.env.example`):

| Variável | Padrão | Uso |
|---|---|---|
| `APP_HOST` / `APP_PORT` | `127.0.0.1` / `8000` | Endereço do servidor. `0.0.0.0` aceita a rede (use com `ALLOWED_CLIENTS`, `ALLOWED_HOSTS` e HTTPS) |
| `SSL_CERTFILE` / `SSL_KEYFILE` | vazio | Certificado PEM para HTTPS no acesso pela rede |
| `SESSION_HOURS` | `8` | Duração da sessão |
| `DOCUMENTS_ROOT` | `.\corpus` | Raiz documental |
| `CORPUS_ORIGEM` | `real` | Origem padrão dos documentos da raiz (`real` nunca sai da máquina) |
| `DATABASE_PATH` | `.\data\database\sadgd.db` | Banco único |
| `AUTO_INDEX` | `true` | Indexação incremental ao iniciar |
| `OCR_ENABLED` / `OCR_ENGINE` | `true` / `auto` | `auto` = Tesseract, depois Windows OCR |
| `OLLAMA_URL` / `OLLAMA_EXE` / `OLLAMA_MODELS` | `127.0.0.1:11434` / `ferramentas\ollama` / `modelos\ollama` | LLM local do projeto |
| `LLM_MODELO_PADRAO` | `sadgd-qwen2.5-7b` | Modelo de redação, especialistas e relator |
| `SADGD_DISPOSITIVO_RERANKER` | `auto` | Reranker na GPU quando houver (`cpu`/`cuda` forçam). Na CPU, a consulta fica ≈ 3× mais lenta |
| `SADGD_CONTEXTO_MAX_CHARS` | `1200` | Compressão do contexto por trecho, orientada pela pergunta (`0` = trechos inteiros) |
| `OBSERVABILIDADE` | `sqlite` | `sqlite` (tabela de spans), `phoenix` ou `nenhuma` |
| `AI_ALLOW_REMOTE` | `false` | Libera provedores fora da máquina (ver §8) |
| `SADGD_LLM_F2` | `local` | `gemini` usa a nuvem na F2 do corpus acadêmico |
| `GEMINI_MODELO` | `gemini-3.5-flash-lite` | Modelo do Gemini |
| `GEMINI_API_KEY` | vazio | Chave do plano gratuito — **somente no `.env`** |

Variáveis fixadas pelo próprio sistema para manter caches no projeto: `HF_HOME=.\modelos\hf`,
`TORCH_HOME=.\modelos\torch`, `HF_DEACTIVATE_ASYNC_LOAD=1` (obrigatória: sem ela o carregamento do bge-m3 falha).

---

## 7. Operação do dia a dia

| Tarefa | Comando |
|---|---|
| Iniciar (abre o navegador) | `start.bat` |
| Iniciar sem navegador (Agendador de Tarefas) | `servidor.bat` (log em `data\logs\servidor_console.log`) |
| Parar | `stop.bat` |
| Diagnóstico | `diagnostico.bat` |
| Backup | `backup.bat` (grava em `BACKUP\`, mantém os 30 mais recentes) |
| Usuários | `usuarios.bat listar | criar | redefinir-senha | desbloquear | ativar` |
| Ollama | `powershell -ExecutionPolicy Bypass -File scripts\sadgd\ollama.ps1 -Acao iniciar|parar|status|instalar|modelo` |
| Tesseract | `powershell -ExecutionPolicy Bypass -File scripts\sadgd\tesseract.ps1 -Acao instalar` |
| GitHub (Kanban/issues) | `$env:GH_CONFIG_DIR = "$PWD\ferramentas\gh\config"` e depois `ferramentas\gh\bin\gh.exe ...` — ver `docs/projeto/BACKLOG.md` |
| Traces (opcional) | `.\.venv\Scripts\python.exe -m phoenix.server.main serve` → http://127.0.0.1:6006 |

**Início automático:** crie uma tarefa no Agendador de Tarefas do Windows "Ao fazer logon" executando
`servidor.bat`, e outra diária executando `backup.bat`.

**Logs:** `data\logs\`. **Auditoria das consultas:** tabela `consultas` do banco (pergunta guardada só como
hash SHA-256; rota, agentes, classificação, confiança, tokens, latência, fontes, pareceres e acerto de cache).

---

## 8. Provedor em nuvem para a F2 (opcional)

Reduz a latência da F2 (p95 387 s → 100 s) **apenas para o corpus acadêmico** (público/sintético).

1. O responsável cria uma chave gratuita no Google AI Studio e a grava **no `.env`** (nunca em código, chat ou `.md`).
2. Configure:

```ini
AI_ALLOW_REMOTE=true
SADGD_LLM_F2=gemini
GEMINI_MODELO=gemini-3.5-flash-lite
GEMINI_API_KEY=<no .env apenas>
```

3. Teste: `.\.venv\Scripts\python.exe scripts\sadgd\testar_gemini.py`.

Regras aplicadas automaticamente: a nuvem só é usada se **todos** os trechos do contexto forem de origem
`publico`/`sintetico`; nomes de pessoas e CPF são pseudonimizados antes do envio; qualquer trecho `real` mantém a
consulta no LLM local; erros 429/503/rede caem no Qwen local; JSON cortado é repetido no Gemini com orçamento maior.
O provedor usado e o motivo vêm na resposta da API (`provedor_f2`) e nos resultados da avaliação.

---

## 9. Backup, restauração e migração

**Backup** (`backup.bat` ou `scripts\backup.py --destino <pasta> --manter N`): banco (inclusive usuários),
índices, configurações e relatórios. **Documentos originais não entram** (ficam na raiz documental).

**Restauração:**

```powershell
.\stop.bat
.\.venv\Scripts\python.exe scripts\restaurar.py --arquivo "BACKUP\backup_AAAAMMDD_HHMMSS.zip" [--com-configuracao]
.\start.bat
```

`--com-configuracao` também restaura o `.env`.

**Migrar para outro computador:**
1. Faça um backup e copie a pasta do projeto **sem** `.venv`, `ferramentas\` e `modelos\` (ou com eles, se for o
   mesmo tipo de máquina).
2. Execute `instalar.bat` no destino e `preparar_bge_m3.py`.
3. Restaure o backup com `--com-configuracao` e ajuste `DOCUMENTS_ROOT` se a pasta dos documentos mudou.
4. Rode `diagnostico.bat` e confira o Painel.

**Pontos de restauração do código:** tags/branches `v1.0.0-pre-reestruturacao`, `backup/pre-reestruturacao`,
`backup/pre-limpeza-v1`.

---

## 10. Testes, qualidade e CI

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                   # suíte completa
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests\sadgd\test_e2e_navegador.py   # sem navegador
.\.venv\Scripts\python.exe -m pytest tests\sadgd\test_e2e_navegador.py    # E2E no Edge do sistema
.\.venv\Scripts\python.exe -m ruff check app tests scripts                # lint
```

- E2E usa o **Microsoft Edge instalado** via Playwright (`channel="msedge"`); não baixa navegadores.
  `SADGD_E2E_CAPTURAS=1` grava as telas em `docs\img\fase09\`.
- Testes que dependem de pasta documental usam uma raiz de amostra; a suíte passa sem `DOCUMENTS_ROOT` válido.
- **CI** (`.github/workflows/ci.yml`, a cada push): gitleaks (segredos), ruff, testes no Windows, portão de
  cobertura das camadas domínio/aplicação e regressão de recuperação BM25 no corpus sintético. Testes que falham
  viram anotações públicas do check run.

---

## 11. Avaliação (métricas)

| Avaliação | Comando | Saída |
|---|---|---|
| Recuperação (P@k, R@k, MRR, nDCG) | `scripts\sadgd\avaliar.py recuperacao` | `avaliacao\execucoes\` |
| Respostas F1 | `scripts\sadgd\avaliar_respostas.py --sistema v2 --modelo sadgd-qwen2.5-7b --conjunto teste --verificador --max-minutos 8.5` | idem |
| Relações / grafo | `scripts\sadgd\avaliar_relacoes.py` | `fase6\` |
| Roteador / anonimização | `avaliar_roteador.py`, `avaliar_anonimizacao.py` | `fase7\` |
| Precedentes | `avaliar_precedentes.py` | `fase8\` |
| F2 ponta a ponta | `avaliar_f2.py --rotulo <r> [--provedor-f2 gemini] --max-minutos 4`; `--resumo` | `fase<r>\f2_resumo.json` |
| Faithfulness (juiz calibrado) | `avaliar_fidelidade.py calibrar|medir|resumo` | `fase10\` |
| Cache semântico | `calibrar_cache.py`, `medir_cache.py` | `fase10\` |
| Documentos reais (julgamento humano) | `scripts\sadgd\avaliar_real.py modelo|executar|revisao|resumo` | `avaliacao\real\` (fora do Git) — ver `docs/AVALIACAO_REAL.md` |
| Relatório consolidado | `scripts\sadgd\avaliar.py relatorio` | `docs\AVALIACAO.md` (manual) |

Todos são **retomáveis**: rode novamente até "[OK]". Avaliações com LLM rodam em **primeiro plano** em ciclos de
`--max-minutos 4` (F2 local ≈ 4–6 min por item). O conjunto de **teste** nunca deve ser usado para ajustar
prompts, limiares ou regras.

---

## 12. Manutenção e extensão

| Tarefa | Onde mexer | Cuidados |
|---|---|---|
| Ajustar prompt de um agente | `app/application/agentes/prompts/<agente>.vN.md` (crie nova versão) | Teste de contrato prompt × schema; reavaliar na **validação** |
| Mudar a saída de um agente | `app/application/agentes/schemas/*.json` + reparo em `especialistas.py` | Atualizar testes de `tests/sadgd/test_orquestrador.py` |
| Novo agente especialista | prompt + schema + catálogo + matriz do roteador (`roteador.py`) | Documentar em `docs/agentes/README.md` |
| Trocar o LLM local | `LLM_MODELO_PADRAO` + `ollama.ps1 -Acao modelo` | Benchmark F1 na validação antes (`avaliar_respostas.py`) |
| Novo provedor em nuvem | Adaptador OpenAI-compatível em `app/infrastructure/llm/` + política em `politica_llm.py` | Manter a política por origem e a anonimização |
| Nova tabela/campo | Nova migração `00N_*.sql` em `app/infrastructure/sqlite/migracoes/` | Nunca editar migração aplicada; contar linhas antes de apagar dados |
| Nova tela | `frontend/index.html` + `frontend/js/sadgd.js` | Todo conteúdo do servidor passa por `esc()`; E2E |

Regras de arquitetura: domínio e aplicação **não importam** infraestrutura (teste de AST falha se isso ocorrer).
Commits no padrão Conventional Commits; registrar decisões relevantes em ADR (`docs/adr/`) e modelos em
`docs/MODELOS_IA.md`.

---

## 13. Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `start.bat`: "Ambiente não instalado" | `.venv` ausente | `instalar.bat` |
| Respostas "Não localizei…" para tudo | Índice vazio ou raiz errada | Painel → contagens; `indexar.py`; conferir `DOCUMENTS_ROOT` |
| Busca só textual (sem vetores) | bge-m3 ausente em `modelos\bge-m3` | `preparar_bge_m3.py` e reindexar |
| Falha nativa ao carregar o bge-m3 | `HF_DEACTIVATE_ASYNC_LOAD` não definido | Use os scripts do projeto (já definem) |
| Embeddings lentos | fp16 na GTX 1660 | Manter float32 (padrão; fp16 é 5× mais lento nessa GPU) |
| Perguntas lentas (≈ 1 min) | Reranker na CPU ou compressão desligada | `SADGD_DISPOSITIVO_RERANKER=auto` e `SADGD_CONTEXTO_MAX_CHARS=1200` no `.env` |
| Após mudar regras de metadados, tipos antigos no acervo | Metadados são calculados na indexação | `scripts/sadgd/reclassificar.py` (sem OCR, minutos) e depois `construir_grafo.py` |
| F1/F2 com erro de conexão ao LLM | Ollama parado | `ollama.ps1 -Acao iniciar`, depois `-Acao status` |
| Comando que inicia o Ollama não termina | Encadeado com `| Out-Null` | Não redirecionar a saída do `ollama.ps1 -Acao iniciar` |
| Respostas com recusa indevida / JSON fora de ordem | Schema estrito no Ollama | Manter `json_livre=True` com a ordem dos campos no prompt |
| F2 muito lenta (minutos) | Limite da GPU local | Esperado (≈ 5 min); cache para repetições; §8 para corpus acadêmico |
| Gemini com 429 / 503 | Cota por minuto / alta demanda | Automático: cai no LLM local; repetir mais tarde |
| Indexação/avaliação interrompida | Pouca RAM encerra processos em segundo plano | Rodar em primeiro plano com `--max-minutos` e repetir |
| OCR sem texto | Tesseract ausente | `tesseract.ps1 -Acao instalar`; Configurações → **Testar OCR** |
| Coletor do corpus público falha | Portal só aceita o cliente HTTP do Windows | Usar o coletor do projeto (já trata) |
| Conta bloqueada | 5 tentativas erradas | Aguardar 15 min ou `usuarios.bat desbloquear --usuario <u>` |
| `.ps1` com acentos quebrados | Codificação | Salvar `.ps1` em UTF-8 com BOM (PowerShell 5.1) |

---

## 14. Segurança e LGPD — checklist de operação

- [ ] `APP_HOST=127.0.0.1`, salvo autorização para uso em rede (então HTTPS + `ALLOWED_CLIENTS`).
- [ ] `AI_ALLOW_REMOTE=false` em instalações com documentos reais.
- [ ] `.env`, `DOCUMENTOS\`, `corpus\enviados\`, `data\`, `BACKUP\` **fora do Git** (já no `.gitignore`).
- [ ] Chaves de API apenas no `.env`; nunca em código, documentação ou chat.
- [ ] Senhas temporárias entregues pessoalmente; contas sem uso desativadas.
- [ ] Backup diário agendado e restauração testada periodicamente.
- [ ] Revisar a auditoria (`consultas`) e os logs conforme a política do órgão.
