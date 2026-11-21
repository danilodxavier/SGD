# ADR-014 — Perguntas por voz com transcrição local (faster-whisper)

| Campo | Valor |
|---|---|
| Status | **Proposto** (Fase 12, 2026-11-21) — aguarda aprovação do responsável |
| Data | 2026-11-21 |
| Requisitos | Pedido de 2026-11-21 (chat por texto ou voz), ADR-001 (local), ADR-002 (dados reais só locais) |

## Contexto

A alta gestão quer perguntar por voz no navegador. As perguntas citam contratos, fornecedores e números reais.

## Opções

| Opção | Privacidade | Custo | Qualidade pt-BR | Observação |
|---|---|---|---|---|
| Web Speech API do navegador (Chrome/Edge) | **Áudio vai a servidores externos** | Gratuito | Boa | Contraria ADR-002 |
| Serviço de nuvem (Google/Azure/AWS) | Áudio vai a terceiros | Pago ou cota | Boa | Contraria ADR-002 e a regra de gratuidade |
| **faster-whisper local (CTranslate2, CPU, int8)** | Áudio fica na máquina; não é gravado | Gratuito, MIT | Boa (small); melhor (medium) | GPU fica para o LLM |
| whisper.cpp (binário) | Local | Gratuito | Equivalente | Exige binário externo e conversão de áudio |

## Decisão

faster-whisper **local**, modelo `small` em int8 na CPU (`SADGD_WHISPER_MODELO`), carregado na primeira transcrição.
O navegador grava e converte para **WAV 16 kHz mono** (Web Audio API), evitando ffmpeg/PyAV no servidor (o `av` 19
é incompatível com o faster-whisper 1.2.1 e o `onnxruntime` do filtro de silêncio não tem pacote para Python 3.15 —
o filtro fica desligado). A transcrição volta para a caixa de texto: **o gestor confere antes de enviar**.

## Consequências

- Medição (voz sintética pt-BR "Microsoft Maria", 3 perguntas com números): transcrição exata, 1,2–1,4 s por
  pergunta após a carga (1,4 s); ≈ 0,5 GB de RAM.
- O microfone só funciona em contexto seguro: exige o HTTPS com certificado válido (Fase 12) ou acesso local.
- Voz real, com ruído e sotaque, deve ser medida com os gestores; `medium` é a alternativa se o `small` errar nomes.
