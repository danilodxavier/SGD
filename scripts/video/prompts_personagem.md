# Prompts do apresentador 3D (estilo animação) — Demo Day 2026

Gerados no **Google Gemini** (app gratuito, modo Pro, conta do responsável), em 2026-11-22, a partir de
`data/video/foto.jpg`, com autorização do responsável para enviar a foto ao serviço. A chave da API do projeto
não serve: os modelos de imagem não têm cota no plano gratuito da API.

As imagens ficam fora do Git, em `data/video/pixar/final/` (imagem de pessoa, LGPD):

| Arquivo | Uso na animação |
|---|---|
| `base.jpg` | Retrato base: sorriso com a boca fechada |
| `boca_a.jpg` | Fala: boca aberta ("A") |
| `boca_o.jpg` | Fala: boca arredondada ("O") |
| `olhos_fechados.jpg` | Piscadas |
| `sorriso.jpg` | Pausas (sorriso aberto) e ênfases (sobrancelhas erguidas) |

## 1. Retrato base (com a foto anexada)

> Generate an image: transform the man in this photo into a high-end 3D animated feature film character (modern
> Pixar-style 3D animation, like a still from an animated movie), keeping him clearly recognizable: same face shape,
> short dark brown hair styled up and swept to the side with volume on top and short sides, thin dark mustache
> connected to a short goatee, light stubble along the jaw, warm brown eyes, natural thick dark eyebrows, light warm
> skin, light gray-white polo shirt with open collar (no sunglasses, no objects). Expression: friendly, charismatic
> and confident, warm gentle closed-mouth smile, eyes looking straight at the camera. Framing: head and upper chest,
> facing the camera frontally, head centered, shoulders reaching the bottom of the image. Background: plain solid
> soft warm light beige studio background, nothing else. Soft cinematic studio lighting, subtle subsurface scattering
> on skin, large expressive eyes with catchlights, high detail. Square 1:1 image.

## 2. Variações (sempre editando a primeira imagem)

- **Boca "A":** Edit the image you just generated. Keep EXACTLY the same character, face, hair, pose, head position
  and size, framing, lighting, colors and background, pixel-aligned. Change ONLY the mouth: open naturally as if
  speaking the vowel "A" in a friendly conversation, upper teeth visible, slight smile. Do not change the eyes,
  eyebrows or anything else. Square 1:1.
- **Olhos fechados:** Now edit the FIRST image again (the one with the closed-mouth smile). Keep EXACTLY the same
  character, pose, head position and size, framing, lighting, colors, background and mouth, pixel-aligned. Change
  ONLY the eyes: both eyes gently closed as in a natural blink, relaxed eyelids, same eyebrows. Square 1:1.
- **Boca "O":** Now edit the FIRST image again (closed-mouth smile, eyes open). Keep EXACTLY the same character,
  pose, head position and size, framing, lighting, colors, background, eyes and eyebrows, pixel-aligned. Change ONLY
  the mouth: rounded, as if speaking the vowel "O" in a friendly conversation, lips slightly forward, a little of the
  upper teeth visible. Square 1:1.
- **Sorriso aberto:** Now edit the FIRST image again (closed-mouth smile, eyes open). Keep EXACTLY the same
  character, pose, head position and size, framing, lighting, colors and background, pixel-aligned. Change ONLY the
  expression: a big warm genuine smile showing the upper teeth, cheeks slightly raised, eyebrows gently raised in a
  friendly enthusiastic way, eyes still open and looking at the camera. Square 1:1.

As variações saíram alinhadas ao pixel com a base: só a região editada muda, e a animação mistura só essa região.
