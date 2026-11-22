# Vídeo de apresentação do SAD-GD — roteiro e produção

| Campo | Valor |
|---|---|
| Duração | 3 min 21 s (1920×1080, 25 fps, H.264 + AAC) |
| Formato | Professor virtual (avatar animado a partir da foto do apresentador) ao lado de uma lousa; tom de aula com técnicas de venda (gancho → dor → solução → prova → valor → chamada para ação) |
| Arquivos gerados (fora do Git, em `data/video/`) | `sadgd_apresentacao.mp4`, `narracao.wav`, `legendas.srt`, `capa.png` |
| Fonte do roteiro | `scripts/video/cenas.json` (falas, textos da lousa e pronúncia) |
| Gerador | `scripts/video/gerar_video.py` |

> A foto e o vídeo **não vão para o Git**: o repositório é público e a imagem de uma pessoa é dado pessoal (LGPD). Eles ficam em `data/video/`, que está no `.gitignore`.

## 1. Estrutura (técnica de venda aplicada à aula)

| # | Cena | Técnica | Mensagem-chave |
|---|---|---|---|
| 1 | Abertura | Gancho | "Imagine ter, em segundos, a resposta exata com a fonte na mão." |
| 2 | O problema | Dor | Documentos espalhados, normas revogadas, horas de busca, risco de decisão errada |
| 3 | F1 | Solução | Resposta com documento, página e trecho literal; verificador; "não localizei" |
| 4 | F2 multiagentes | Diferencial | 6 especialistas + relator; "o sistema sugere, a gestão decide" |
| 5 | Linha do tempo e memória | Diferencial | Aditivos, revogações, hierarquia, vigência, precedentes |
| 6 | Como construímos | Credibilidade | GitHub/CI, Markdown, Claude Code (skills, plugins, MCP), LangGraph e modelos locais |
| 7 | Resultados | Prova social/numérica | R@5 0,965 · fidelidade 0,964 · 0% alucinação numérica · 311 testes · R$ 0 |
| 8 | Valor para a SEMA-MT | Benefício | Rapidez, segurança jurídica, LGPD, memória institucional |
| 9 | Fechamento | Chamada para ação | "Pergunte. Confira a fonte. Decida." |

As falas completas estão em `scripts/video/cenas.json` e, com tempos, em `data/video/legendas.srt`.

## 2. Como o vídeo é produzido (100% local e gratuito)

| Etapa | Ferramenta | Detalhe |
|---|---|---|
| Narração | Voz neural pt-BR **Microsoft Daniel** (Windows, OneCore via SAPI) | Dicionário de pronúncia no `cenas.json` (ex.: "SAD-GD" → "Sad Gê Dê") |
| Avatar | Pillow + NumPy | Foto recortada (cabeça e ombros), pele suavizada e iluminação de volume; **movimento 3D** de cabeça (giro em perspectiva, inclinação e respiração); **piscadas** aleatórias; **boca sincronizada** com a energia do áudio (deformação da mandíbula + interior da boca) |
| Cenário | Pillow | Sala de aula com lousa; itens "escritos a giz" aparecem conforme a fala; legenda acessível; barra de progresso |
| Codificação | ffmpeg (pacote `imageio-ffmpeg`, instalado no `.venv`) | MP4 H.264 + AAC com `faststart` |

Regenerar:

```bash
.venv\Scripts\python.exe scripts\video\gerar_video.py
```

Opções: `--reusar-audio` (não sintetiza de novo), `--previa 5,30,90` (só quadros PNG nesses segundos), `--foto <caminho>`.
A renderização leva ≈ 8,5 min nesta máquina.

## 3. Limitação honesta e evolução para avatar 3D realista

O avatar local é uma **animação 2,5D** da foto (perspectiva, piscar e boca guiada pelo áudio), não um modelo 3D com fonemas. Um avatar 3D fotorrealista com sincronia labial por fonema exige:

- **Ferramentas locais open source** (SadTalker, LivePortrait, Wav2Lip): precisam de vários GB de pesos e mais VRAM/RAM livres do que esta máquina tem (GPU de 6 GB compartilhada com o Ollama; 1–3 GB de RAM livre); ou
- **Serviços online com plano gratuito** (ex.: D-ID, HeyGen, Vidnoz): o próprio apresentador envia a foto e a `narracao.wav` (ou grava a própria voz) e exporta o vídeo; depois basta trocar o quadro do avatar. Isso envia a **imagem do apresentador** a um terceiro — decisão e envio são do responsável, nunca automáticos (regra de dados do projeto).

Também é possível substituir a narração sintética pela **voz do próprio apresentador**: grave um `.wav` por cena em `data/video/audio/<id>.wav` (48 kHz, 16 bits) e rode com `--reusar-audio`.


---

## 4. Vídeo do Demo Day (23/11/2026) — apresentador 3D no estilo de animação

| Campo | Valor |
|---|---|
| Duração | 4 min 57 s (1920×1080, 25 fps, H.264 + AAC, ≈ 92 MB) + legendas `.srt` |
| Arquivos (fora do Git) | `data/video/demoday/SAD-GD_DemoDay_2026.mp4`, `SAD-GD_DemoDay_2026.srt`, `narracao.wav` |
| Roteiro | `scripts/video/cenas_demoday.json` (16 cenas: apresentação do autor, justificativa, solução e limitação de GPU, formas de acesso, painel/acervo, pergunta por texto, por voz, vigência e "não localizei", linha do tempo, decisão F2, memória, ferramentas, arquitetura, resultados, ganhos, encerramento) |
| Voz | Microsoft Daniel (a mesma do vídeo anterior), velocidade 3 |

Produção (100% local):

1. **Telas reais** — `scripts/video/capturar_telas.py --etapa basicas|f1|voz|f2`: instância isolada em `127.0.0.1:8011` com cópia do banco acadêmico (`data/video/trabalho/demo.db`), usuário de demonstração com senha gerada (`data/video/trabalho/demo_credenciais.txt`), Edge via Playwright em 1600×900 × 1,2 = PNG 1080p. A etapa `voz` injeta uma fala sintética como microfone (`--use-file-for-fake-audio-capture`) e passa pela transcrição real (Whisper).
2. **Apresentador 3D no estilo de animação** — gerado no Google Gemini (app gratuito, conta e autorização do responsável) a partir da foto: retrato base e quatro variações alinhadas ao pixel (boca "A", boca "O", olhos fechados, sorriso aberto com sobrancelhas erguidas) em `data/video/pixar/final/`. Os prompts estão em [`scripts/video/prompts_personagem.md`](../../scripts/video/prompts_personagem.md). A chave da API não serve: os modelos de imagem não têm cota no plano gratuito.
3. **Animação e montagem** — `scripts/video/gerar_video_demoday.py audio | previa 12,95 | parte K N | juntar`: recorte do fundo (preenchimento a partir das bordas para a cabeça; canal b* para a camisa), mistura por região a cada quadro — boca "A"/"O" guiada pela energia da voz, piscadas, sorriso nas pausas, sobrancelhas erguidas nas ênfases — com movimento de cabeça e respiração; cenas de apresentador, demonstração com zoom nas telas, cartões de ferramentas, diagrama da arquitetura e métricas; render em partes por causa da RAM.

Histórico: as versões 1 e 2 usavam um boneco de massinha gerado localmente a partir da foto; o responsável preferiu um personagem no estilo de animação 3D, mais carismático, e o gerador de massinha foi removido (está no histórico do Git, commit `8ec9f27`).

Durante a gravação foi encontrado e corrigido um defeito real: a fala "contrato doze barra dois mil e vinte e três" era transcrita como "contrato 12 barra 2023" e a busca não reconhecia o contrato (agora `normalizar_fala` em `app/infrastructure/voz/transcritor.py`).

## 5. PDF do pitch e guia completo

`scripts/entrega/gerar_guia_pdf.py [--video URL]` → `data/entrega/SAD-GD_DemoDay_Pitch_e_Guia.pdf` (30 páginas, A4): capa com os links (vídeo, GitHub, endereço na LAN, Kanban, documentação), os 5 itens do enunciado do Demo Day, percurso por fases, arquitetura e agentes, guia de uso com as telas, ferramentas (Claude Code, skills, plugins, subagentes, hooks, MCP, GitHub, CI, Kanban, bibliotecas e modelos), metodologias, resultados, LGPD, instalação, limitações e produção dos materiais.
