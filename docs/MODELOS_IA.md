# Modelos de IA utilizados — SAD-GD

Registro obrigatório (regra 6). Inclui desenvolvimento e produção. Custo em R$ por uso no projeto.

## Desenvolvimento

| Modelo | Provedor | Versão / ID | Finalidade | Fase(s) | Custo | Justificativa |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | Anthropic (via Claude Code) | `claude-opus-5-5` | Agente de engenharia: auditoria, planejamento, arquitetura, código, testes e documentação | 0– | Assinatura do responsável (não é custo do sistema) | Ferramenta de desenvolvimento escolhida pelo responsável |
| Microsoft Daniel (voz neural pt-BR) | Microsoft (nativo do Windows, OneCore/SAPI) | `MSTTS_V110_ptBR_DanielM` | Narração do vídeo de apresentação (Fase 11) | 11 | R$ 0 | Local, sem envio de dados; `scripts/video/gerar_video.py` |

## Produção / execução do sistema

| Modelo | Provedor | Versão / ID | Finalidade | Fase(s) | Custo | Justificativa | Status |
|---|---|---|---|---|---|---|---|
| Qwen2.5 7B Instruct Q4_K_M | LM Studio (local) | `qwen/qwen2.5-7b-instruct` GGUF | Redação de respostas na v1 (opcional) | v1 | R$ 0 | Herdado da v1; roda na GTX 1660 SUPER | Em uso (v1) |
| Windows OCR | Microsoft (nativo do Windows) | Windows.Media.Ocr | OCR de imagens/PDF escaneado na v1 | v1 | R$ 0 | Nativo, sem instalação | Em uso (v1) |
| `sadgd-qwen2.5-7b` (Qwen2.5 7B Instruct Q4_K_M, importado do GGUF) | Ollama 0.40.16 portátil (local) | sha256 `fc258d6a…` | LLM local padrão (roteador, redação, especialistas) | 3– | R$ 0 | ADR-004; 24/29 camadas na GPU de 6 GB; **escolhido no benchmark da Fase 5** (exatidão 0,846 validação / 0,795 teste) | **Em uso** desde a Fase 3 (também pela v1) |
| Tesseract 5.4.0 + `por` (tessdata_best) | Local (`ferramentas\tesseract`) | 5.4.0.20240606 | OCR padrão (`auto`) | 4– | R$ 0 | ADR-007; CER 0,09% (Windows OCR: 0,52%) | **Em uso** desde a Fase 4 |
| BAAI/bge-reranker-v2-m3 (Apache-2.0) | Local (`modelos\hf`) | snapshot oficial (safetensors) | Reranking (cross-encoder), top-24, fp32 | 5– | R$ 0 | ADR-005; R@5 0,748 → 0,965 | **Em uso** |
| Whisper small (Systran/faster-whisper-small, MIT) | Local (`modelos\hf\whisper`), faster-whisper 1.2.1 + CTranslate2 4.9.0, CPU int8 | `small` (`SADGD_WHISPER_MODELO`) | Transcrição das perguntas por voz (pt-BR) | 12– | R$ 0 | ADR-014; áudio não sai da máquina; voz sintética: 3/3 exatas, 1,3 s | **Em uso** |
| Llama 3.1 8B Instruct Q4_K_M | Ollama (registro oficial, `modelos\ollama`) | `llama3.1:8b-instruct-q4_K_M` | Concorrente no benchmark F1; **juiz de faithfulness** (outra família) | 5, 10 | R$ 0 | Exatidão 0,718 × 0,846 do Qwen; como juiz: κ 0,71, sensibilidade 0,82, especificidade 0,90 (validação), mas 18 falsos alarmes em 23 reprovações no teste | **Em uso como juiz de avaliação** (não na resposta ao usuário) |
| BAAI/bge-m3 (MIT) | Local (`modelos\bge-m3`, safetensors convertido do repositório oficial) | snapshot 5617a9f6 | Embeddings densos 1024 dims, float32 na GPU | 4– | R$ 0 | ADR-005; 19 trechos/s na GTX 1660 SUPER | **Em uso**: 5.691 vetores |
| Qwen 2.5 3B Instruct Q4_K_M | Ollama (registro oficial, `modelos\ollama`) | `qwen2.5:3b-instruct-q4_K_M` | Terceiro modelo do benchmark F1; candidato a roteador e a especialista rápido | 7 | R$ 0 | Download autorizado em 2026-11-16. Validação F1: exatidão **0,462** (× 0,846 do 7B), p50 6,8 s (× 14 s). Roteador por regras atingiu 0,92–0,94 sem LLM → 3B dispensado no roteamento | Avaliado; **rejeitado também como especialista** na Fase 10 (2,5× mais rápido, mas 13/14 pareceres sem conteúdo) |

| Gemini 3.5 Flash-Lite | Google AI Studio (plano gratuito, API compatível com OpenAI) | `gemini-3.5-flash-lite` | Especialistas e relator da **F2 somente com corpus acadêmico anonimizado** (opcional: `SADGD_LLM_F2=gemini`, `AI_ALLOW_REMOTE=true`, chave no `.env`); reserva automática no Qwen local | 11 | R$ 0 (cota gratuita) | ADR-002/004/011; F2 p50/p95 30 s / 100 s × 329 s / 387 s local, schema relator 1,00, recall docs 0,865 (`docs/AVALIACAO.md`, Fase 11) | **Em uso opcional** (desligado por padrão) |

## Planejados (ADRs aceitos na Fase 2)

| Modelo | Provedor | Finalidade | Fase de adoção | Custo | Justificativa |
|---|---|---|---|---|---|
| Modelo grande de free tier (Gemini / Groq / OpenRouter) | Nuvem | Opção acadêmica para F2 e **juiz** de avaliação | 5–8 | R$ 0 (cota gratuita) | Somente corpus público/sintético (ADR-002/004/011) |
| Tesseract 5 (`por`) | Local (`ferramentas\tesseract`) | OCR portátil | 4 | R$ 0 | ADR-007 |
