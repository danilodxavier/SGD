# Modelos de IA utilizados — SAD-GD

Registro obrigatório (regra 6). Inclui desenvolvimento e produção. Custo em R$ por uso no projeto.

## Desenvolvimento

| Modelo | Provedor | Versão / ID | Finalidade | Fase(s) | Custo | Justificativa |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | Anthropic (via Claude Code) | `claude-opus-5-5` | Agente de engenharia: auditoria, planejamento, arquitetura, código, testes e documentação | 0– | Assinatura do responsável (não é custo do sistema) | Ferramenta de desenvolvimento escolhida pelo responsável |

## Produção / execução do sistema

| Modelo | Provedor | Versão / ID | Finalidade | Fase(s) | Custo | Justificativa | Status |
|---|---|---|---|---|---|---|---|
| Qwen2.5 7B Instruct Q4_K_M | LM Studio (local) | `qwen/qwen2.5-7b-instruct` GGUF | Redação de respostas na v1 (opcional) | v1 | R$ 0 | Herdado da v1; roda na GTX 1660 SUPER | Em uso (v1) |
| Windows OCR | Microsoft (nativo do Windows) | Windows.Media.Ocr | OCR de imagens/PDF escaneado na v1 | v1 | R$ 0 | Nativo, sem instalação | Em uso (v1) |

## Candidatos a avaliar (Fase 2 — ADRs)

| Modelo | Provedor | Finalidade | Observação |
|---|---|---|---|
| BAAI/bge-m3 | Local (Hugging Face) | Embeddings multilíngues (denso + esparso) | ~2,3 GB; bom desempenho em PT |
| BAAI/bge-reranker-v2-m3 | Local | Reranking | Cross-encoder multilíngue |
| Qwen2.5/Qwen3 7–14B, Llama 3.x 8B, Gemma 2/3 9B (quantizados) | Ollama / LM Studio (local) | Roteador, especialistas, relator | Limite de 6 GB de VRAM |
| Gemini (free tier) | Google | LLM para corpus acadêmico | Somente corpus público/sintético (ADR-002) |
| Llama/Qwen via Groq (free tier) | Groq | LLM rápido para corpus acadêmico | Idem |
| Modelos gratuitos OpenRouter | OpenRouter | Alternativa | Idem |
| Tesseract 5 (por) | Local | OCR portátil | RF-02 |
