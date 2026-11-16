# ADR-004 — LLMs, abstração de provedor e roteamento por custo

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | RF-15, RNF-01, RNF-04, RNF-05, RNF-08, RNF-10 |

## Contexto

- Hardware: GTX 1660 SUPER **6 GB VRAM** (verificado com `nvidia-smi`), 16 GB RAM.
- Já disponível: LM Studio + `Qwen2.5-7B-Instruct Q4_K_M` (4,36 GB). Ollama não instalado.
- Regras: custo zero (ADR-001); dados reais nunca saem da máquina (ADR-002).
- Modelos 7–8B quantizados têm limitações em raciocínio jurídico longo (risco R01).

## Decisão

### 1. Porta única `LLMPort` com adaptadores

`chat(messages, schema=None, max_tokens, temperature) → {texto|json, tokens_in, tokens_out, latencia_ms, modelo}`

| Adaptador | Protocolo | Uso |
|---|---|---|
| `OllamaAdapter` | API OpenAI-compatível `:11434/v1` | **Padrão** local (open source, CLI, `OLLAMA_MODELS=<projeto>\modelos\ollama`) |
| `LMStudioAdapter` | OpenAI-compatível `:1234/v1` | Alternativa local (já em uso na v1) |
| `GeminiAdapter`, `GroqAdapter`, `OpenRouterAdapter` | HTTP + chave em `.env` | **Somente** corpus acadêmico; opcional |

### 2. Política de envio externo (regra de domínio, testada)

Adaptador remoto só é permitido se **todas** as condições forem verdadeiras: `AI_ALLOW_REMOTE=true`; todos os documentos dos trechos enviados têm `corpus_origem ∈ {publico, sintetico}`; o anonimizador foi aplicado. Caso contrário → `PoliticaEnvioExternoViolada` e fallback local. (RNF-08)

### 3. Roteamento por perfil de tarefa

| Tarefa | Perfil de modelo | Candidato local inicial | Observação |
|---|---|---|---|
| Roteador | determinístico (regras + intents da v1) → LLM pequeno apenas se ambíguo | Qwen2.5 3B Instruct Q4 | Custo ≈ 0 na maioria das perguntas |
| F1 redação com citação | 7–8B instruct | Qwen2.5 7B Instruct Q4_K_M | Bom português; já baixado |
| Especialistas, relator (F2) | 7–8B local; opção acadêmica: modelo grande free tier | idem | Gatilho R01 |
| Verificador | 7–8B com saída JSON estrita + checagem lexical determinística | idem | Afirmação só passa se houver sobreposição com o trecho citado |
| Juiz de avaliação (RAGAS) | modelo **diferente** do gerador | ver ADR-011 | Evita viés de autoavaliação |

### 4. Seleção empírica dos modelos (adiada com critério)

A comparação de ≥ 3 modelos locais (ex.: Qwen2.5 7B, Llama 3.1 8B, Gemma 2 9B — todos em Q4 ≤ 6 GB) **será feita na Fase 5 sobre o conjunto de validação do golden set**, com faithfulness, citações corretas, latência p95 e tokens. Comparar agora, sem golden set, produziria evidência fraca. O backlog SAD-012 foi ajustado para "decisão de arquitetura + protocolo de benchmark".

### 5. Otimização de tokens (prompt mestre §5)

Roteamento acima; especialistas acionados por matriz de gatilhos (≤ 4 em F2); contexto = apenas trechos reranqueados (top-k ≤ 8, truncados por dispositivo) + resumo hierárquico do processo; saídas JSON curtas entre agentes; cache semântico (ADR-006); `max_tokens` por papel; medição por span (ADR-009).

## Alternativas rejeitadas

- **Só nuvem free tier:** viola ADR-002 para dados reais e cria dependência de cota.
- **Modelos 13–14B locais:** não cabem nos 6 GB de VRAM com contexto útil; ficariam em CPU com latência > RNF-04.

## Consequências

- (+) Troca de provedor por configuração (RNF-10); demonstração possível 100% offline.
- (−) Qualidade F2 limitada localmente; mitigada por verificador, recuperação forte e opção acadêmica em nuvem.
- Pendência para a Fase 3: instalar Ollama com `OLLAMA_MODELS` apontando para `modelos\ollama`.

## Implementação (Fase 3, 2026-11-16)

- Ollama **portátil** v0.40.16 em `ferramentas\ollama` (zip oficial, sem instalador), servidor em `127.0.0.1:11434`, modelos em `modelos\ollama` (`OLLAMA_MODELS`). Gerenciado por `scripts\sadgd\ollama.ps1` (iniciado por `start.bat`, encerrado por `stop.bat`).
- Modelo `sadgd-qwen2.5-7b` criado a partir do GGUF já existente do LM Studio (sem novo download); 24/29 camadas na GPU (≈4 GB VRAM), contexto 8192; classificação curta em JSON em ~0,4 s após a carga.
- **Benchmark (Fase 5, validação):** Qwen 2.5 7B (exatidão 0,846; recusa 1,00; p50 13,9 s) × Llama 3.1 8B (0,718; 0,75; 16,1 s) → Qwen mantido como padrão F1; Llama reservado como verificador/juiz de outra família.
- **Saída JSON:** schema estrito no Ollama prejudica a qualidade (chaves em ordem alfabética); o `LLMPort` ganhou `json_livre=True` e a validação dos campos fica no código.
- Primeira carga teve falha transitória de inicialização CUDA (não reproduzida); o adaptador `OpenAICompativelAdapter` repete chamadas com recuo exponencial em erros 5xx/429/conexão e rejeita URLs que não sejam http/https.
