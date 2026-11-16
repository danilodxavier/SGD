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
| `sadgd-qwen2.5-7b` (Qwen2.5 7B Instruct Q4_K_M, importado do GGUF) | Ollama 0.40.16 portátil (local) | sha256 `fc258d6a…` | LLM local padrão (roteador, redação, especialistas) | 3– | R$ 0 | ADR-004; 24/29 camadas na GPU de 6 GB; **escolhido no benchmark da Fase 5** (exatidão 0,846 validação / 0,795 teste) | **Em uso** desde a Fase 3 (também pela v1) |
| Tesseract 5.4.0 + `por` (tessdata_best) | Local (`ferramentas\tesseract`) | 5.4.0.20240606 | OCR padrão (`auto`) | 4– | R$ 0 | ADR-007; CER 0,09% (Windows OCR: 0,52%) | **Em uso** desde a Fase 4 |
| BAAI/bge-reranker-v2-m3 (Apache-2.0) | Local (`modelos\hf`) | snapshot oficial (safetensors) | Reranking (cross-encoder), top-24, fp32 | 5– | R$ 0 | ADR-005; R@5 0,748 → 0,965 | **Em uso** |
| Llama 3.1 8B Instruct Q4_K_M | Ollama (registro oficial, `modelos\ollama`) | `llama3.1:8b-instruct-q4_K_M` | Concorrente no benchmark F1; candidato a verificador/juiz (outra família) | 5– | R$ 0 | Exatidão 0,718 × 0,846 do Qwen; melhor em conflitos | Avaliado; não escolhido para F1 |
| BAAI/bge-m3 (MIT) | Local (`modelos\bge-m3`, safetensors convertido do repositório oficial) | snapshot 5617a9f6 | Embeddings densos 1024 dims, float32 na GPU | 4– | R$ 0 | ADR-005; 19 trechos/s na GTX 1660 SUPER | **Em uso**: 5.691 vetores |

## Planejados (ADRs aceitos na Fase 2)

| Modelo | Provedor | Finalidade | Fase de adoção | Custo | Justificativa |
|---|---|---|---|---|---|
| Qwen2.5 3B Instruct Q4 | Ollama (local) | Roteador (casos ambíguos) | 7 | R$ 0 | Modelo pequeno para classificação barata (ADR-004) |
| Qwen 2.5 3B Instruct Q4 | Ollama (local) | Terceiro modelo do benchmark / roteador | 5 | R$ 0 | Download interrompido por falta de memória; aguarda autorização |
| Modelo grande de free tier (Gemini / Groq / OpenRouter) | Nuvem | Opção acadêmica para F2 e **juiz** de avaliação | 5–8 | R$ 0 (cota gratuita) | Somente corpus público/sintético (ADR-002/004/011) |
| Tesseract 5 (`por`) | Local (`ferramentas\tesseract`) | OCR portátil | 4 | R$ 0 | ADR-007 |
