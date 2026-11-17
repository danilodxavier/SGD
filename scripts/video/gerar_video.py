"""Gera o vídeo de apresentação do SAD-GD com avatar animado a partir de uma foto.

Tudo local e gratuito:
- narração: voz pt-BR do Windows (SAPI/OneCore "Daniel");
- avatar: foto estilizada com volume (iluminação), movimento de cabeça em
  perspectiva, piscadas e boca sincronizada com a energia do áudio;
- composição: Pillow + NumPy; codificação: ffmpeg do pacote imageio-ffmpeg.

Uso (na raiz do projeto):
    .venv\\Scripts\\python.exe scripts\\video\\gerar_video.py [--previa 3,40,75] [--foto data\\video\\foto.jpg]

Saídas em data\\video\\ (fora do Git): sadgd_apresentacao.mp4, narracao.wav,
legendas.srt e capa.png. Com --previa, grava só os quadros (segundos) pedidos.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "data" / "video"
W, H, FPS = 1920, 1080, 25
TAXA = 48000
PAUSA_ENTRE_CENAS = 0.7
FONTES = Path("C:/Windows/Fonts")

# Pontos do rosto na foto original (618 x 619), medidos com grade.
OLHOS = [(268, 250), (365, 250)]
OLHO_RAIO = (22, 9)
BOCA_X, BOCA_Y, BOCA_LARG = 315, 357, 56
QUEIXO_Y = 430
RECORTE = (95, 40, 545, 619)  # cabeça e ombros

# Paleta
PAREDE_TOPO, PAREDE_BASE = (231, 222, 204), (200, 186, 160)
LOUSA, MOLDURA = (32, 74, 56), (122, 82, 48)
GIZ, GIZ_AMARELO, GIZ_VERDE = (240, 240, 232), (250, 214, 92), (150, 230, 170)
VERDE_MT, AZUL_MT = (0, 122, 61), (0, 63, 125)


def fonte(nome: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / nome), tam)


# ---------------------------------------------------------------- narração
def sintetizar(cenas: list[dict], cfg: dict, pasta: Path) -> list[Path]:
    import win32com.client as w

    voz = w.Dispatch("SAPI.SpVoice")
    cat = w.Dispatch("SAPI.SpObjectTokenCategory")
    cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", False)
    toks = cat.EnumerateTokens()
    escolhidos = [toks.Item(i) for i in range(toks.Count) if cfg["voz"] in toks.Item(i).GetDescription()]
    if not escolhidos:
        raise SystemExit(f"Voz {cfg['voz']!r} não encontrada")
    voz.Voice = escolhidos[0]
    voz.Rate = cfg.get("velocidade", 0)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for c in cenas:
        texto = c["fala"]
        for k, v in sorted(cfg["pronuncia"].items(), key=lambda kv: -len(kv[0])):
            texto = texto.replace(k, v)
        arq = pasta / f"{c['id']}.wav"
        fs = w.Dispatch("SAPI.SpFileStream")
        fmt = w.Dispatch("SAPI.SpAudioFormat")
        fmt.Type = 39  # 48 kHz 16 bits estéreo
        fs.Format = fmt
        fs.Open(str(arq), 3)
        voz.AudioOutputStream = fs
        voz.Speak(texto)
        fs.Close()
        arquivos.append(arq)
    return arquivos


def ler_wav(arq: Path) -> np.ndarray:
    with wave.open(str(arq)) as f:
        assert f.getframerate() == TAXA and f.getsampwidth() == 2
        dados = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
        return dados.reshape(-1, f.getnchannels()).mean(axis=1).astype(np.float32) / 32768


def montar_audio(wavs: list[Path], destino: Path) -> tuple[np.ndarray, list[tuple[float, float]]]:
    partes, tempos, t = [np.zeros(int(TAXA * 0.8), np.float32)], [], 0.8
    for arq in wavs:
        a = ler_wav(arq)
        tempos.append((t, t + len(a) / TAXA))
        partes += [a, np.zeros(int(TAXA * PAUSA_ENTRE_CENAS), np.float32)]
        t += len(a) / TAXA + PAUSA_ENTRE_CENAS
    partes.append(np.zeros(int(TAXA * 1.5), np.float32))
    audio = np.concatenate(partes)
    pcm = (np.clip(audio * 0.95, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(destino), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(TAXA)
        f.writeframes(pcm.tobytes())
    return audio, tempos


def envelope(audio: np.ndarray, n_quadros: int) -> np.ndarray:
    passo = TAXA // FPS
    env = np.array([np.sqrt(np.mean(audio[i * passo:(i + 1) * passo] ** 2) + 1e-12) for i in range(n_quadros)])
    ref = np.percentile(env[env > 1e-3], 90) if np.any(env > 1e-3) else 1
    env = np.clip(env / ref, 0, 1.2)
    env[env < 0.08] = 0
    suave = np.copy(env)
    for i in range(1, len(env)):  # ataque rápido, soltura suave
        suave[i] = env[i] if env[i] > suave[i - 1] else suave[i - 1] * 0.55 + env[i] * 0.45
    return suave


# ---------------------------------------------------------------- avatar
class Avatar:
    def __init__(self, foto: Path, altura: int):
        bruto = Image.open(foto).convert("RGB")
        x0, y0, x1, y1 = RECORTE
        self.esc = altura / (y1 - y0)
        tam = (round((x1 - x0) * self.esc), altura)
        img = bruto.crop(RECORTE).resize(tam, Image.LANCZOS)
        # Estilização "3D": pele suavizada, cor viva, luz principal e sombra de volume.
        img = img.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.SMOOTH_MORE)
        img = ImageEnhance.Color(img).enhance(1.15)
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = img.filter(ImageFilter.UnsharpMask(2, 60, 2))
        a = np.asarray(img).astype(np.float32)
        yy, xx = np.mgrid[0:tam[1], 0:tam[0]].astype(np.float32)
        cx, cy = self.p(BOCA_X, 260)
        luz = 1.12 - 0.35 * (((xx - cx * 0.92) / (tam[0] * 0.75)) ** 2 + ((yy - cy * 0.85) / (tam[1] * 0.8)) ** 2)
        a = np.clip(a * np.clip(luz, 0.72, 1.15)[..., None], 0, 255)
        self.base = a
        self.tam = tam
        self.yy, self.xx = yy, xx
        bx, by = self.p(BOCA_X, BOCA_Y)
        qy = self.p(0, QUEIXO_Y)[1]
        d0 = 12 * self.esc
        gy = np.clip((yy - by) / d0, 0, 1) * np.clip(1 - (yy - qy) / (80 * self.esc), 0, 1)
        gx = np.exp(-(((xx - bx) / (60 * self.esc)) ** 2))
        self.peso_mandibula = gx * gy
        self.boca = (bx, by)
        self.pele = []
        for ox, oy in OLHOS:
            sx, sy = self.p(ox, oy - 18)
            self.pele.append(tuple(int(v) for v in a[int(sy) - 2:int(sy) + 2, int(sx) - 6:int(sx) + 6].reshape(-1, 3).mean(0)))

    def p(self, x: float, y: float) -> tuple[float, float]:
        return (x - RECORTE[0]) * self.esc, (y - RECORTE[1]) * self.esc

    def quadro(self, abertura: float, piscar: float, giro: float, inclina: float, respira: float) -> Image.Image:
        d = abertura * 13 * self.esc
        if d > 0.4:
            src_y = np.clip(self.yy - d * self.peso_mandibula, 0, self.tam[1] - 1)
            y0 = np.floor(src_y).astype(np.int32)
            f = (src_y - y0)[..., None]
            y1 = np.minimum(y0 + 1, self.tam[1] - 1)
            xi = self.xx.astype(np.int32)
            arr = self.base[y0, xi] * (1 - f) + self.base[y1, xi] * f
        else:
            arr = self.base
        img = Image.fromarray(arr.astype(np.uint8))
        dr = ImageDraw.Draw(img, "RGBA")
        if d > 1.2:  # interior da boca e dentes
            bx, by = self.boca
            mw = BOCA_LARG * self.esc * (0.75 + 0.25 * min(1, abertura))
            camada = Image.new("L", img.size, 0)
            ImageDraw.Draw(camada).ellipse([bx - mw / 2, by - 1, bx + mw / 2, by + d + 1], fill=255)
            camada = camada.filter(ImageFilter.GaussianBlur(3.0))
            interior = Image.new("RGB", img.size, (78, 34, 36))
            if d > 4:
                ImageDraw.Draw(interior).rectangle([bx - mw / 2, by - 1, bx + mw / 2, by + min(3.5, d * 0.22)], fill=(196, 182, 172))
                interior = interior.filter(ImageFilter.GaussianBlur(1.2))
            img = Image.composite(interior, img, camada)
            dr = ImageDraw.Draw(img, "RGBA")
        if piscar > 0.05:  # pálpebras
            rx, ry = OLHO_RAIO[0] * self.esc, OLHO_RAIO[1] * self.esc * 1.35
            for (ox, oy), pele in zip(OLHOS, self.pele):
                cx, cy = self.p(ox, oy)
                topo = cy - ry
                limite = topo + piscar * 2 * ry
                mascara = Image.new("L", img.size, 0)
                md = ImageDraw.Draw(mascara)
                md.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
                md.rectangle([0, limite, img.size[0], img.size[1]], fill=0)
                mascara = mascara.filter(ImageFilter.GaussianBlur(1.2))
                img = Image.composite(Image.new("RGB", img.size, pele), img, mascara)
                dr = ImageDraw.Draw(img, "RGBA")
                dr.arc([cx - rx, limite - ry * 0.6, cx + rx, limite + ry * 0.25], 15, 165, fill=(60, 40, 35, 200), width=max(2, int(2 * self.esc)))
        # Movimento 3D: giro (perspectiva), inclinação e respiração.
        w_, h_ = img.size
        k = giro * 0.035
        pts_dst = [(0, 0), (w_, 0), (w_, h_), (0, h_)]
        pts_src = [(0, -k * h_), (w_, k * h_), (w_, h_ - k * h_), (0, h_ + k * h_)]
        img = img.transform(img.size, Image.PERSPECTIVE, _coef_perspectiva(pts_dst, pts_src), Image.BICUBIC)
        esc = 1.10 + 0.006 * respira
        img = img.rotate(inclina, Image.BICUBIC, center=(w_ / 2, h_ * 0.8))
        nova = (round(w_ * esc), round(h_ * esc))
        img = img.resize(nova, Image.BICUBIC)
        ox = (nova[0] - w_) / 2 + giro * 6
        oy = (nova[1] - h_) / 2 - respira * 2
        return img.crop((ox, oy, ox + w_, oy + h_))


def _coef_perspectiva(dst, src):
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(m, float), np.array(src, float).reshape(8)).tolist()


# ---------------------------------------------------------------- cenário
CARTAO = (70, 150, 650, 880)  # moldura do avatar
LOUSA_BOX = (720, 120, 1860, 840)


def fundo_base() -> Image.Image:
    img = Image.new("RGB", (W, H))
    g = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(PAREDE_TOPO) * (1 - g) + np.array(PAREDE_BASE) * g
    img = Image.fromarray(np.broadcast_to(arr, (H, W, 3)).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 64], fill=AZUL_MT)
    d.rectangle([0, 64, W, 70], fill=VERDE_MT)
    d.text((40, 14), "SAD-GD", font=fonte("segoeuib.ttf", 30), fill="white")
    d.text((170, 20), "Apoio à decisão e gestão documental · SEMA-MT", font=fonte("segoeui.ttf", 22), fill=(220, 230, 245))
    x0, y0, x1, y1 = LOUSA_BOX
    d.rounded_rectangle([x0 - 22, y0 - 22, x1 + 22, y1 + 22], 10, fill=MOLDURA)
    d.rectangle([x0, y0, x1, y1], fill=LOUSA)
    rng = np.random.default_rng(7)
    lousa = np.asarray(img.crop(LOUSA_BOX)).astype(np.int16)
    lousa += rng.integers(-6, 7, lousa.shape[:2])[..., None]
    img.paste(Image.fromarray(np.clip(lousa, 0, 255).astype(np.uint8)), LOUSA_BOX[:2])
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 10, y1 + 22, x1 + 10, y1 + 38], fill=(98, 64, 38))
    for i, cor in enumerate([GIZ, GIZ_AMARELO, GIZ_VERDE]):
        d.rounded_rectangle([x1 - 260 + i * 70, y1 + 12, x1 - 210 + i * 70, y1 + 24], 4, fill=cor)
    sombra = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sombra).rounded_rectangle([c + 12 for c in CARTAO], 28, fill=110)
    img.paste((40, 30, 20), mask=sombra.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(CARTAO, 28, fill=VERDE_MT)
    d.rounded_rectangle([CARTAO[0], CARTAO[3] - 4, CARTAO[2], CARTAO[3] + 64], 18, fill=AZUL_MT)
    d.text(((CARTAO[0] + CARTAO[2]) / 2, CARTAO[3] + 30), "Professor virtual · SAD-GD", font=fonte("segoeuib.ttf", 26), fill="white", anchor="mm")
    return img


def quebrar(texto: str, f: ImageFont.FreeTypeFont, largura: int) -> list[str]:
    linhas, atual = [], ""
    for p in texto.split():
        t = f"{atual} {p}".strip()
        if f.getlength(t) <= largura:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    return linhas + [atual]


def desenhar_lousa(base: Image.Image, cena: dict, progresso: float, t_cena: float) -> None:
    """Escreve a cena na lousa; itens aparecem ao longo da fala (efeito de aula)."""
    x0, y0, x1, _ = LOUSA_BOX
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    alfa_t = int(255 * min(1, t_cena / 0.5))
    ft = fonte("segoeprb.ttf", 58 if "subtitulo" not in cena else 78)
    y = y0 + 50
    for linha in quebrar(cena["titulo"], ft, x1 - x0 - 120):
        d.text((x0 + 60, y), linha, font=ft, fill=GIZ_AMARELO + (alfa_t,))
        y += ft.size + 22
    d.line([x0 + 60, y + 4, x0 + 60 + min(1, t_cena / 0.8) * 520, y + 4], fill=GIZ + (alfa_t,), width=4)
    y += 40
    if "subtitulo" in cena:
        fs = fonte("segoepr.ttf", 38)
        for linha in quebrar(cena["subtitulo"], fs, x1 - x0 - 120):
            d.text((x0 + 60, y), linha, font=fs, fill=GIZ + (alfa_t,))
            y += 54
        y += 30
    if "metricas" in cena:
        n = len(cena["metricas"])
        fv, fr = fonte("segoeprb.ttf", 76), fonte("segoeui.ttf", 30)
        for i, (valor, rotulo) in enumerate(cena["metricas"]):
            ap = max(0.0, min(1.0, (progresso * (n + 0.6) - i) * 2.5))
            if ap <= 0:
                continue
            cx = x0 + 60 + (i % 3) * 360
            cy = y + (i // 3) * 230
            d.rounded_rectangle([cx, cy, cx + 330, cy + 200], 16, outline=GIZ + (int(150 * ap),), width=3)
            d.text((cx + 165, cy + 82), valor, font=fv, fill=GIZ_AMARELO + (int(255 * ap),), anchor="mm")
            d.text((cx + 165, cy + 160), rotulo, font=fr, fill=GIZ + (int(255 * ap),), anchor="mm")
    else:
        fi = fonte("segoeui.ttf", 38)
        itens = cena.get("itens", [])
        for i, item in enumerate(itens):
            ap = max(0.0, min(1.0, (progresso * (len(itens) + 0.5) - i) * 3))
            if ap <= 0:
                continue
            a = int(255 * ap)
            d.text((x0 + 64, y + 2), "✔", font=fonte("seguisym.ttf", 36), fill=GIZ_VERDE + (a,))
            for linha in quebrar(item, fi, x1 - x0 - 190):
                d.text((x0 + 120, y), linha, font=fi, fill=GIZ + (a,))
                y += 52
            y += 26
    base.alpha_composite(camada) if base.mode == "RGBA" else base.paste(camada, (0, 0), camada)


def legendas(cenas: list[dict], tempos: list[tuple[float, float]]) -> list[tuple[float, float, str]]:
    saida = []
    for cena, (ini, fim) in zip(cenas, tempos):
        partes = []
        for frase in re.split(r"(?<=[.!?:;])\s+", cena["fala"]):
            while len(frase) > 90:
                corte = frase.rfind(",", 0, 90)
                corte = corte if corte > 30 else frase.rfind(" ", 0, 90)
                partes.append(frase[:corte + 1].strip())
                frase = frase[corte + 1:].strip()
            partes.append(frase)
        total = sum(len(p) for p in partes)
        t = ini
        for p in partes:
            dur = (fim - ini) * len(p) / total
            saida.append((t, t + dur, p))
            t += dur
    return saida


def srt(itens: list[tuple[float, float, str]], destino: Path) -> None:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

    destino.write_text("\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(itens, 1)), encoding="utf-8")


# ---------------------------------------------------------------- render
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", default=str(SAIDA / "foto.jpg"))
    ap.add_argument("--previa", default="")
    ap.add_argument("--reusar-audio", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((Path(__file__).with_name("cenas.json")).read_text(encoding="utf-8"))
    cenas = cfg["cenas"]
    pasta_audio = SAIDA / "audio"
    wavs = [pasta_audio / f"{c['id']}.wav" for c in cenas]
    if not (args.reusar_audio and all(a.exists() for a in wavs)):
        wavs = sintetizar(cenas, cfg, pasta_audio)
    audio, tempos = montar_audio(wavs, SAIDA / "narracao.wav")
    duracao = len(audio) / TAXA
    n = int(duracao * FPS)
    env = envelope(audio, n)
    subs = legendas(cenas, tempos)
    srt(subs, SAIDA / "legendas.srt")

    av_h = CARTAO[3] - CARTAO[1] - 24
    avatar = Avatar(Path(args.foto), av_h)
    av_w = CARTAO[2] - CARTAO[0] - 24
    mascara_av = Image.new("L", (av_w, av_h), 0)
    ImageDraw.Draw(mascara_av).rounded_rectangle([0, 0, av_w, av_h], 20, fill=255)
    fundo = fundo_base()
    fsub = fonte("segoeuib.ttf", 34)

    rnd = random.Random(42)
    piscadas, t = [], 1.5
    while t < duracao:
        piscadas.append(t)
        t += rnd.uniform(2.8, 5.2)

    def render(i: int) -> Image.Image:
        t = i / FPS
        idx = max([k for k, (ini, _) in enumerate(tempos) if t >= ini - PAUSA_ENTRE_CENAS / 2] or [0])
        ini, fim = tempos[idx]
        progresso = min(1.0, max(0.0, (t - ini) / max(0.1, fim - ini)))
        quadro = fundo.copy()
        desenhar_lousa(quadro, cenas[idx], progresso, t - ini + PAUSA_ENTRE_CENAS / 2)
        pisc = 0.0
        for tp in piscadas:
            dt = t - tp
            if 0 <= dt < 0.24:
                pisc = [0.6, 1, 1, 0.7, 0.35, 0.1][min(5, int(dt * FPS))]
        fala = env[min(i, n - 1)]
        giro = 0.9 * math.sin(t * 2 * math.pi / 6.1) + 0.4 * math.sin(t * 2 * math.pi / 2.3) * min(1, fala * 2)
        inclina = 1.1 * math.sin(t * 2 * math.pi / 7.3) + 0.6 * fala * math.sin(t * 9)
        rosto = avatar.quadro(fala, pisc, giro, inclina, math.sin(t * 2 * math.pi / 4.2))
        rosto = rosto.crop(((rosto.width - av_w) // 2, 0, (rosto.width - av_w) // 2 + av_w, av_h))
        quadro.paste(rosto, (CARTAO[0] + 12, CARTAO[1] + 12), mascara_av)
        d = ImageDraw.Draw(quadro, "RGBA")
        # indicador de voz
        for b in range(9):
            alt = 6 + 40 * fala * (0.5 + 0.5 * math.sin(t * 13 + b * 1.7)) if fala > 0 else 6
            x = 460 + b * 18
            d.rounded_rectangle([x, CARTAO[3] - 30 - alt / 2, x + 9, CARTAO[3] - 30 + alt / 2], 4, fill=(255, 255, 255, 210))
        # legenda
        atual = next((txt for a, b, txt in subs if a <= t < b), "")
        if atual:
            linhas = quebrar(atual, fsub, 1500)
            y = H - 40 - 48 * len(linhas)
            d.rounded_rectangle([170, y - 14, W - 170, H - 26], 16, fill=(10, 20, 30, 190))
            for linha in linhas:
                d.text((W / 2, y + 20), linha, font=fsub, fill="white", anchor="mm")
                y += 48
        d.rectangle([0, H - 8, W * i / n, H], fill=VERDE_MT)
        return quadro

    if args.previa:
        for s in args.previa.split(","):
            render(int(float(s) * FPS)).save(SAIDA / f"previa_{s}s.png")
        print(f"duração {duracao:.1f}s; prévias gravadas")
        return

    import imageio_ffmpeg

    destino = SAIDA / "sadgd_apresentacao.mp4"
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(SAIDA / "narracao.wav"),
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        q = render(i)
        if i == int(tempos[0][0] * FPS + 60):
            q.save(SAIDA / "capa.png")
        proc.stdin.write(q.tobytes())
        if i % (FPS * 10) == 0:
            print(f"{i / FPS:5.0f}s / {duracao:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"OK: {destino} ({duracao:.1f}s)")


if __name__ == "__main__":
    main()
