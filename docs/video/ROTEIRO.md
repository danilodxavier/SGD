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
