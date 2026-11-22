"""Vídeo do Demo Day (23/11/2026): apresentador em massinha 3D + demonstração real do SAD-GD — 100% local.

Pré-requisitos (fora do Git, em data/video/):
  - telas reais do sistema com o corpus acadêmico: scripts/video/capturar_telas.py (+ páginas públicas do GitHub);
  - boneco de massinha: scripts/video/avatar_massinha.py;
  - roteiro: scripts/video/cenas_demoday.json (voz pt-BR Microsoft Daniel, a mesma do vídeo anterior).

Uso (na raiz do projeto; a renderização é feita em partes curtas por causa da RAM):
    python scripts/video/gerar_video_demoday.py audio            # sintetiza a fala e grava a linha do tempo
    python scripts/video/gerar_video_demoday.py previa 12,95     # quadros PNG nesses segundos
    python scripts/video/gerar_video_demoday.py parte 0 6        # renderiza a parte 0 de 6 (repita 0..5)
    python scripts/video/gerar_video_demoday.py juntar           # junta as partes + áudio → MP4 final

Saída: data/video/demoday/SAD-GD_DemoDay_2026.mp4 (1920×1080, 25 fps, H.264 + AAC) e legendas .srt.
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import gerar_video as base_video  # noqa: E402  (síntese de voz e legendas do vídeo anterior)

VIDEO = RAIZ / "data" / "video"
SAIDA = VIDEO / "demoday"
TELAS = VIDEO / "telas"
MASSA = VIDEO / "trabalho" / "massinha"
CENAS = Path(__file__).with_name("cenas_demoday.json")
W, H, FPS, TAXA = 1920, 1080, 25, 48000
INICIO, PAUSA, FIM = 0.9, 0.55, 2.2
FONTES = Path("C:/Windows/Fonts")
LOGO = RAIZ / "frontend" / "assets" / "marcas" / "_govmt_sema_horizontal.png"

AZUL, AZUL2, VERDE, AMARELO = (13, 44, 104), (7, 29, 74), (0, 122, 61), (246, 190, 0)
CREME, CREME2, TINTA = (240, 231, 216), (221, 205, 182), (24, 32, 48)
BRANCO = (255, 255, 255)


def fonte(nome: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / nome), tam)


F_TIT = lambda t: fonte("seguibl.ttf", t)  # noqa: E731
F_SB = lambda t: fonte("seguisb.ttf", t)  # noqa: E731
F_RG = lambda t: fonte("segoeui.ttf", t)  # noqa: E731
F_BD = lambda t: fonte("segoeuib.ttf", t)  # noqa: E731


# ------------------------------------------------------------------ utilidades de imagem (NumPy, RGB uint8)
def rgba(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGBA"))


def colar(dst: np.ndarray, src: np.ndarray, x: int, y: int, alfa: float = 1.0) -> None:
    """Composição alfa de src (RGBA) em dst (RGB) na posição (x, y), com recorte nas bordas."""
    if alfa <= 0.003:
        return
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x0 >= x1 or y0 >= y1:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4].astype(np.float32) * (alfa / 255.0)
    d = dst[y0:y1, x0:x1].astype(np.float32)
    dst[y0:y1, x0:x1] = (d + (s[..., :3].astype(np.float32) - d) * a).astype(np.uint8)


def texto_rgba(txt: str, f: ImageFont.FreeTypeFont, cor, largura: int | None = None, entre: int = 8,
               alinhar: str = "left") -> np.ndarray:
    linhas = []
    for par in txt.split("\n"):
        linhas += quebrar(par, f, largura) if largura else [par]
    asc, desc = f.getmetrics()
    alt = asc + desc
    larg = max(1, int(max(f.getlength(li) for li in linhas)) + 4)
    img = Image.new("RGBA", (larg, alt * len(linhas) + entre * (len(linhas) - 1) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, li in enumerate(linhas):
        x = {"left": 0, "center": (larg - f.getlength(li)) / 2, "right": larg - f.getlength(li)}[alinhar]
        d.text((x, i * (alt + entre)), li, font=f, fill=cor)
    return rgba(img)


def quebrar(texto: str, f: ImageFont.FreeTypeFont, largura: int) -> list[str]:
    linhas, atual = [], ""
    for p in texto.split():
        t = f"{atual} {p}".strip()
        if f.getlength(t) <= largura:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    return [li for li in linhas + [atual] if li]


def cartao(w: int, h: int, cor, raio: int = 28, sombra: int = 26, opac_sombra: int = 70, borda=None) -> np.ndarray:
    """Cartão arredondado com sombra suave (RGBA, com margem para a sombra)."""
    m = sombra
    img = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    sm = Image.new("L", img.size, 0)
    ImageDraw.Draw(sm).rounded_rectangle([m, m + 10, m + w, m + h + 10], raio, fill=opac_sombra)
    sm = sm.filter(ImageFilter.GaussianBlur(sombra / 2))
    img.paste((10, 15, 30, 255), mask=sm)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([m, m, m + w, m + h], raio, fill=cor, outline=borda, width=3 if borda else 0)
    return rgba(img)


def suave(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def gradiente(c1, c2, w=W, h=H, vertical=True) -> np.ndarray:
    g = np.linspace(0, 1, h if vertical else w, dtype=np.float32)
    g = g[:, None, None] if vertical else g[None, :, None]
    arr = np.array(c1, np.float32) * (1 - g) + np.array(c2, np.float32) * g
    return np.broadcast_to(arr, (h, w, 3)).astype(np.uint8).copy()


# ------------------------------------------------------------------ boneco de massinha
class Massinha:
    """Boneco de massinha com olhos de contas, pálpebras, boca e mandíbula animadas e movimento de cabeça."""

    def __init__(self, altura: int):
        meta = json.loads((MASSA / "meta.json").read_text(encoding="utf-8"))
        b = cv2.imread(str(MASSA / "base.png"), cv2.IMREAD_UNCHANGED)
        b = cv2.cvtColor(b, cv2.COLOR_BGRA2RGBA)
        self.k = altura / b.shape[0]
        self.base = cv2.resize(b, None, fx=self.k, fy=self.k, interpolation=cv2.INTER_AREA)
        self.h, self.w = self.base.shape[:2]
        rx = np.clip(np.minimum(np.arange(self.w), self.w - 1 - np.arange(self.w)) / (0.07 * self.w), 0, 1)
        ry = np.clip((self.h - 1 - np.arange(self.h)) / (0.05 * self.h), 0, 1)
        self.base = self.base.copy()
        self.base[..., 3] = (self.base[..., 3] * (ry[:, None] * rx[None, :]) ** 0.8).astype(np.uint8)
        e = meta["escala"]
        self.u = e * self.k  # pixels por unidade da foto original
        self.olhos = [(x * self.k, y * self.k) for x, y in meta["olhos"]]
        self.boca = (meta["boca"][0] * self.k, meta["boca"][1] * self.k)
        self.queixo = meta["queixo_y"] * self.k
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.xx, self.yy = xx, yy
        bx, by = self.boca
        gy = np.clip((yy - by) / (10 * self.u), 0, 1) * np.clip(1 - (yy - self.queixo) / (55 * self.u), 0, 1)
        gx = np.exp(-(((xx - bx) / (62 * self.u)) ** 2))
        self.peso = (gx * gy).astype(np.float32)
        self.pele = []
        for ox, oy in self.olhos:
            p = self.base[int(oy - 24 * self.u):int(oy - 20 * self.u), int(ox - 6 * self.u):int(ox + 6 * self.u), :3]
            self.pele.append(tuple(int(v) for v in p.reshape(-1, 3).mean(0)))
        self._olho = {}
        self._boca = {}

    # --- sprites (supersample 3×) ---
    def sprite_olho(self, lado: int, palpebra: float, gx: float, gy: float) -> np.ndarray:
        chave = (lado, round(palpebra, 2), round(gx, 1), round(gy, 1))
        if chave in self._olho:
            return self._olho[chave]
        s, u = 3, self.u * 3
        rx, ry = 19 * u, 12.5 * u
        tam = int(2 * rx + 12 * u), int(2 * ry + 14 * u)
        cx, cy = tam[0] / 2, tam[1] / 2 + 2 * u
        yy, xx = np.mgrid[0:tam[1], 0:tam[0]].astype(np.float32)
        en = 1 - ((xx - cx) / rx) ** 2 - ((yy - cy) / ry) ** 2
        dentro = en > 0
        z = np.sqrt(np.clip(en, 0, 1))
        # esclera (conta branca envernizada)
        nx, ny = (xx - cx) / rx, (yy - cy) / ry
        luz = np.clip(0.55 + 0.45 * (z * 0.8 - nx * 0.35 - ny * 0.45), 0, 1.1)
        cor = np.dstack([luz * 246, luz * 242, luz * 234])
        # íris e pupila
        ix, iy = cx + gx * 5 * u, cy + gy * 2 * u
        di = np.sqrt((xx - ix) ** 2 + (yy - iy) ** 2)
        ri = 9.5 * u
        iris = di < ri
        tom = np.clip(1 - di / ri, 0, 1)
        cor = np.where(iris[..., None], np.dstack([70 + 40 * tom, 45 + 25 * tom, 30 + 12 * tom]), cor)
        cor = np.where((di < 4.8 * u)[..., None], np.array([12, 10, 10], np.float32), cor)
        cor = np.where((di > ri - 1.2 * u)[..., None] & iris[..., None], np.array([40, 26, 20], np.float32), cor)
        # brilho especular
        dh = np.sqrt((xx - (ix - 3.5 * u)) ** 2 + (yy - (iy - 3.5 * u)) ** 2)
        cor = cor + (np.clip(1 - dh / (2.6 * u), 0, 1) ** 1.5)[..., None] * 255
        dh2 = np.sqrt((xx - (ix + 3 * u)) ** 2 + (yy - (iy + 3 * u)) ** 2)
        cor = cor + (np.clip(1 - dh2 / (1.3 * u), 0, 1))[..., None] * 140
        alfa = np.clip(en * 18, 0, 1)
        # pálpebra superior de massa (cor da pele, com borda escura e brilho)
        limite = cy - ry + (0.13 + 0.87 * palpebra) * 2 * ry
        tampa = (yy < limite) & dentro
        pele = np.array(self.pele[lado], np.float32)
        tz = np.clip((limite - yy) / (2 * ry), 0, 1)
        cor_tampa = pele * (0.92 + 0.12 * np.sqrt(tz))[..., None]
        cor = np.where(tampa[..., None], cor_tampa, cor)
        borda = (np.abs(yy - limite) < 1.6 * u) & dentro
        cor = np.where(borda[..., None], pele * 0.45, cor)
        brilho = (np.abs(yy - (limite - 3 * u)) < 1.0 * u) & dentro & (nx < 0.2)
        cor = np.where(brilho[..., None], np.minimum(pele * 1.25, 255), cor)
        # contorno de massa ao redor do olho (sombra de cavidade)
        anel = np.clip(1 - np.abs(en) * 9, 0, 1) * (en < 0.05)
        cor = cor * (1 - 0.35 * anel[..., None])
        alfa = np.maximum(alfa, anel * 0.5)
        img = np.dstack([np.clip(cor, 0, 255), alfa * 255]).astype(np.uint8)
        img = cv2.resize(img, (tam[0] // s, tam[1] // s), interpolation=cv2.INTER_AREA)
        self._olho[chave] = img
        return img

    def sprite_boca(self, abre: float, larg: float) -> np.ndarray:
        chave = (round(abre, 2), round(larg, 2))
        if chave in self._boca:
            return self._boca[chave]
        s, u = 3, self.u * 3
        rx = (21 + 5 * larg - 3 * abre) * u
        ry = (1.2 + 13 * abre) * u
        lab = 4.2 * u
        tam = int(2 * (rx + lab) + 8 * u), int(2 * (ry + lab) + 10 * u)
        cx, cy = tam[0] / 2, tam[1] / 2
        yy, xx = np.mgrid[0:tam[1], 0:tam[0]].astype(np.float32)
        # sorriso leve: centro da boca um pouco abaixo dos cantos
        curva = 2.2 * u * (1 - ((xx - cx) / (rx + lab)) ** 2)
        yc = yy - curva
        e_out = ((xx - cx) / (rx + lab)) ** 2 + ((yc - cy) / (ry + lab)) ** 2
        e_in = ((xx - cx) / max(rx, 1)) ** 2 + ((yc - cy) / max(ry, 0.6 * u)) ** 2
        labios = (e_out < 1) & (e_in >= 1)
        interior = e_in < 1
        # perfil do lábio (anel de massa)
        t = np.clip((1 - e_out) / 0.45, 0, 1)
        z = np.sqrt(t)
        ny = (yc - cy) / (ry + lab)
        luz = np.clip(0.62 + 0.5 * z - 0.35 * ny * np.sign(yc - cy) * 0.6 - 0.25 * ny, 0.35, 1.25)
        cor_lab = np.dstack([luz * 178, luz * 96, luz * 92])
        cor = np.zeros((tam[1], tam[0], 3), np.float32)
        cor = np.where(labios[..., None], cor_lab, cor)
        if abre > 0.06:
            prof = np.clip(1 - e_in, 0, 1)
            cor_int = np.dstack([70 - 30 * prof, 20 + 0 * prof, 26 + 0 * prof])
            cor = np.where(interior[..., None], cor_int, cor)
            if abre > 0.22:  # dentes de cima
                dentes = interior & (yc < cy - ry + (3 + 3 * abre) * u)
                cor = np.where(dentes[..., None], np.array([238, 232, 220], np.float32), cor)
            if abre > 0.35:  # língua
                lingua = interior & (((xx - cx) / (rx * 0.7)) ** 2 + ((yc - (cy + ry * 0.75)) / (ry * 0.55)) ** 2 < 1)
                cor = np.where(lingua[..., None], np.array([196, 92, 98], np.float32), cor)
        else:
            linha = (np.abs(yc - cy) < 1.1 * u) & (e_out < 0.92)
            cor = np.where(linha[..., None], np.array([92, 40, 40], np.float32), cor)
        alfa = np.clip((1 - e_out) * 14, 0, 1)
        img = np.dstack([np.clip(cor, 0, 255), alfa * 255]).astype(np.uint8)
        img = cv2.resize(img, (tam[0] // s, tam[1] // s), interpolation=cv2.INTER_AREA)
        self._boca[chave] = img
        return img

    def quadro(self, fala: float, larg: float, piscar: float, olhar: tuple[float, float], giro: float,
               inclina: float, sobe: float) -> np.ndarray:
        abre = min(1.0, fala)
        d = abre * 11 * self.u
        if d > 0.4:
            mapy = np.clip(self.yy - d * self.peso, 0, self.h - 1)
            img = cv2.remap(self.base, self.xx, mapy, cv2.INTER_LINEAR)
        else:
            img = self.base.copy()
        img = img.copy()
        bx, by = self.boca
        sb = self.sprite_boca(round(abre * 20) / 20, round(larg * 4) / 4)
        _colar_rgba(img, sb, int(bx - sb.shape[1] / 2), int(by - sb.shape[0] / 2 + d * 0.45))
        for lado, (ox, oy) in enumerate(self.olhos):
            so = self.sprite_olho(lado, round(piscar * 10) / 10, olhar[0], olhar[1])
            _colar_rgba(img, so, int(ox - so.shape[1] / 2), int(oy - so.shape[0] / 2))
        # movimento de cabeça: giro (achata em x e desloca), inclinação em torno do pescoço, respiração
        cx, cy = self.w / 2, self.h * 0.86
        m = cv2.getRotationMatrix2D((cx, cy), inclina, 1.0)
        m[0, 0] *= 1 - 0.018 * abs(giro)
        m[0, 2] += giro * 6 * self.u
        m[1, 2] -= sobe * 2.0 * self.u
        return cv2.warpAffine(img, m, (self.w, self.h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(0, 0, 0, 0))


def _colar_rgba(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    """Composição RGBA sobre RGBA (o boneco), mantendo o alfa do destino."""
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x0 >= x1 or y0 >= y1:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    a = s[..., 3:4] / 255
    d = dst[y0:y1, x0:x1].astype(np.float32)
    d[..., :3] = d[..., :3] + (s[..., :3] - d[..., :3]) * a
    d[..., 3:] = np.maximum(d[..., 3:], s[..., 3:])
    dst[y0:y1, x0:x1] = d.astype(np.uint8)


# ------------------------------------------------------------------ áudio e linha do tempo
def ler_wav(arq: Path) -> np.ndarray:
    with wave.open(str(arq)) as f:
        dados = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
        return dados.reshape(-1, f.getnchannels()).mean(axis=1).astype(np.float32) / 32768


def preparar_audio(sintetizar: bool) -> None:
    cfg = json.loads(CENAS.read_text(encoding="utf-8"))
    pasta = SAIDA / "audio"
    wavs = [pasta / f"{c['id']}.wav" for c in cfg["cenas"]]
    if sintetizar or not all(w.exists() for w in wavs):
        wavs = base_video.sintetizar(cfg["cenas"], cfg, pasta)
    partes, tempos, t = [np.zeros(int(TAXA * INICIO), np.float32)], [], INICIO
    for arq in wavs:
        a = ler_wav(arq)
        tempos.append((t, t + len(a) / TAXA))
        partes += [a, np.zeros(int(TAXA * PAUSA), np.float32)]
        t += len(a) / TAXA + PAUSA
    partes.append(np.zeros(int(TAXA * FIM), np.float32))
    audio = np.concatenate(partes)
    # leve compressão e normalização da voz
    pico = np.percentile(np.abs(audio), 99.9)
    audio = np.tanh(audio / max(pico, 1e-3) * 1.1) * 0.89
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(str(SAIDA / "narracao.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(TAXA)
        f.writeframes(pcm.tobytes())
    n = int(len(audio) / TAXA * FPS)
    passo = TAXA // FPS
    env = np.array([np.sqrt(np.mean(audio[i * passo:(i + 1) * passo] ** 2) + 1e-12) for i in range(n)])
    ref = np.percentile(env[env > 1e-3], 90)
    env = np.clip(env / ref, 0, 1.2)
    env[env < 0.1] = 0
    sv = env.copy()
    for i in range(1, n):
        sv[i] = env[i] if env[i] > sv[i - 1] else sv[i - 1] * 0.5 + env[i] * 0.5
    subs = base_video.legendas(cfg["cenas"], tempos)
    base_video.srt(subs, SAIDA / "SAD-GD_DemoDay_2026.srt")
    (SAIDA / "linha_do_tempo.json").write_text(json.dumps(
        {"duracao": len(audio) / TAXA, "quadros": n, "tempos": tempos, "envelope": sv.round(3).tolist(),
         "legendas": subs}, ensure_ascii=False), encoding="utf-8")
    print(f"áudio: {len(audio) / TAXA:.1f} s, {n} quadros")


# ------------------------------------------------------------------ cenas
class Video:
    def __init__(self):
        self.cfg = json.loads(CENAS.read_text(encoding="utf-8"))
        self.cenas = self.cfg["cenas"]
        lt = json.loads((SAIDA / "linha_do_tempo.json").read_text(encoding="utf-8"))
        self.dur, self.n, self.tempos = lt["duracao"], lt["quadros"], lt["tempos"]
        self.env = np.array(lt["envelope"], np.float32)
        self.subs = lt["legendas"]
        self.grande = Massinha(980)
        self.pequeno = Massinha(560)
        self.logo = self._logo()
        self.fundo_estudio = self._fundo_estudio()
        self.fundo_demo = self._fundo_demo()
        self.fundo_claro = self._fundo_claro()
        rnd = random.Random(42)
        self.piscadas, t = [], 1.2
        while t < self.dur:
            self.piscadas.append(t)
            t += rnd.uniform(2.6, 5.0)
        self.olhares, t = [], 0.0
        while t < self.dur:
            self.olhares.append((t, rnd.uniform(-0.5, 0.5), rnd.uniform(-0.3, 0.2)))
            t += rnd.uniform(1.2, 3.2)
        self._cache: dict = {}

    # --- fundos estáticos ---
    def _logo(self) -> np.ndarray:
        im = Image.open(LOGO).convert("RGBA")
        k = 64 / im.height
        return rgba(im.resize((int(im.width * k), 64), Image.LANCZOS))

    def _fundo_estudio(self) -> np.ndarray:
        f = gradiente(CREME, CREME2)
        img = Image.fromarray(f)
        bolhas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(bolhas)
        rnd = random.Random(5)
        for _ in range(14):
            r = rnd.randint(40, 150)
            x, y = rnd.randint(0, W), rnd.randint(0, H)
            cor = rnd.choice([(0, 122, 61, 40), (13, 44, 104, 34), (246, 190, 0, 46), (255, 255, 255, 70)])
            d.ellipse([x - r, y - r, x + r, y + r], fill=cor)
        img.paste(bolhas.filter(ImageFilter.GaussianBlur(38)), (0, 0), bolhas.filter(ImageFilter.GaussianBlur(38)))
        arr = np.asarray(img.convert("RGB")).astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        vin = 1 - 0.22 * (((xx - W * 0.45) / W) ** 2 + ((yy - H * 0.45) / H) ** 2) * 2
        arr *= vin[..., None]
        return np.clip(arr, 0, 255).astype(np.uint8)

    def _fundo_demo(self) -> np.ndarray:
        f = gradiente(AZUL, AZUL2).astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        brilho = np.exp(-(((xx - 300) / 700) ** 2 + ((yy - 200) / 500) ** 2)) * 30
        f += brilho[..., None]
        rnd = np.random.default_rng(2)
        f += rnd.normal(0, 2.0, (H, W, 1))
        return np.clip(f, 0, 255).astype(np.uint8)

    def _fundo_claro(self) -> np.ndarray:
        return gradiente((246, 243, 236), (232, 226, 214))

    # --- elementos com cache ---
    def cache(self, chave, fn):
        if chave not in self._cache:
            self._cache[chave] = fn()
        return self._cache[chave]

    @lru_cache(maxsize=8)
    def tela(self, nome: str) -> np.ndarray:
        return np.asarray(Image.open(TELAS / f"{nome}.png").convert("RGB"))

    # --- animação do boneco ---
    def estado_boneco(self, i: int, t: float) -> dict:
        fala = float(self.env[min(i, self.n - 1)])
        pisc = 0.0
        for tp in self.piscadas:
            dt = t - tp
            if 0 <= dt < 0.26:
                pisc = [0.5, 1, 1, 0.75, 0.4, 0.15, 0.0][min(6, int(dt * FPS))]
        olhar = (0.0, 0.0)
        for k in range(len(self.olhares) - 1, -1, -1):
            if self.olhares[k][0] <= t:
                olhar = self.olhares[k][1:]
                break
        larg = 0.5 + 0.5 * math.sin(t * 7.3) * math.sin(t * 2.9)
        giro = 0.9 * math.sin(t * 2 * math.pi / 6.5) + 0.5 * math.sin(t * 2 * math.pi / 2.1) * min(1, fala * 1.6)
        inclina = 1.4 * math.sin(t * 2 * math.pi / 7.7) + 0.9 * fala * math.sin(t * 5.1)
        sobe = math.sin(t * 2 * math.pi / 4.3) + 1.2 * fala * max(0, math.sin(t * 6.2))
        return dict(fala=fala, larg=larg, piscar=pisc, olhar=olhar, giro=giro, inclina=inclina, sobe=sobe)

    def boneco_grande(self, quadro: np.ndarray, est: dict, x: int, y: int) -> None:
        img = self.grande.quadro(**est)
        sm = self.cache("sombra_g", self._sombra_grande)
        colar(quadro, sm, x + int(self.grande.w * 0.05), y + self.grande.h - 100)
        colar(quadro, img, x, y)

    def _sombra_grande(self) -> np.ndarray:
        sm = np.zeros((120, int(self.grande.w * 0.9), 4), np.uint8)
        cv2.ellipse(sm, (sm.shape[1] // 2, 60), (sm.shape[1] // 2 - 30, 30), 0, 0, 360, (20, 15, 10, 130), -1)
        return cv2.GaussianBlur(sm, (0, 0), 16)

    def boneco_pip(self, quadro: np.ndarray, est: dict, cx: int, cy: int, r: int = 170) -> None:
        img = self.pequeno.quadro(**est)
        disco = self.cache(("disco", r), lambda: self._disco(r))
        colar(quadro, disco, cx - disco.shape[1] // 2, cy - disco.shape[0] // 2)
        # recorte circular: cabeça e ombros
        lado = 2 * r
        ox = int(self.pequeno.w / 2 - r)
        oy = int(self.pequeno.h * 0.02)
        rec = np.zeros((lado, lado, 4), np.uint8)
        sub = img[max(0, oy):oy + lado, max(0, ox):ox + lado]
        rec[:sub.shape[0], :sub.shape[1]] = sub
        mascara = self.cache(("masc", r), lambda: self._mascara_circulo(lado))
        rec[..., 3] = (rec[..., 3].astype(np.float32) * mascara).astype(np.uint8)
        colar(quadro, rec, cx - r, cy - r)
        anel = self.cache(("anel", r), lambda: self._anel(r))
        colar(quadro, anel, cx - anel.shape[1] // 2, cy - anel.shape[0] // 2)

    def _disco(self, r: int) -> np.ndarray:
        m = 30
        img = Image.new("RGBA", (2 * r + 2 * m, 2 * r + 2 * m), (0, 0, 0, 0))
        sm = Image.new("L", img.size, 0)
        ImageDraw.Draw(sm).ellipse([m, m + 12, m + 2 * r, m + 2 * r + 12], fill=140)
        img.paste((0, 0, 0, 255), mask=sm.filter(ImageFilter.GaussianBlur(14)))
        fundo = Image.fromarray(gradiente(CREME, CREME2, 2 * r, 2 * r)).convert("RGBA")
        mk = Image.new("L", (2 * r, 2 * r), 0)
        ImageDraw.Draw(mk).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
        img.paste(fundo, (m, m), mk)
        return rgba(img)

    def _mascara_circulo(self, lado: int) -> np.ndarray:
        yy, xx = np.mgrid[0:lado, 0:lado].astype(np.float32)
        d = np.sqrt((xx - lado / 2 + 0.5) ** 2 + (yy - lado / 2 + 0.5) ** 2)
        return np.clip(lado / 2 - d, 0, 1)

    def _anel(self, r: int) -> np.ndarray:
        s = 4
        img = Image.new("RGBA", ((2 * r + 20) * s, (2 * r + 20) * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([10 * s, 10 * s, (2 * r + 10) * s, (2 * r + 10) * s], outline=VERDE + (255,), width=8 * s)
        d.ellipse([16 * s, 16 * s, (2 * r + 4) * s, (2 * r + 4) * s], outline=(255, 255, 255, 200), width=2 * s)
        return rgba(img.resize((2 * r + 20, 2 * r + 20), Image.LANCZOS))

    # --- partes comuns ---
    def selo_capitulo(self, quadro: np.ndarray, k: int, claro: bool, alfa: float) -> None:
        cena = self.cenas[k]
        cor = TINTA if claro else BRANCO
        sel = self.cache(("selo", k, claro), lambda: texto_rgba(f"{k + 1:02d} · {cena['capitulo'].upper()}",
                                                                F_BD(24), (VERDE if claro else AMARELO)))
        colar(quadro, sel, 60, 46, alfa)
        del cor

    def legenda(self, quadro: np.ndarray, t: float) -> None:
        idx = next((j for j, (a, b, _) in enumerate(self.subs) if a <= t < b), None)
        if idx is None:
            return
        a, b, txt = self.subs[idx]
        alfa = min(1.0, (t - a) / 0.12, (b - t) / 0.12 + 0.6)
        img = self.cache(("leg", idx), lambda: self._legenda_img(txt))
        colar(quadro, img, (W - img.shape[1]) // 2, H - 26 - img.shape[0], alfa)

    def _legenda_img(self, txt: str) -> np.ndarray:
        f = F_SB(33)
        linhas = quebrar(txt, f, 1300)
        larg = int(max(f.getlength(li) for li in linhas)) + 56
        alt = 46 * len(linhas) + 22
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, larg - 1, alt - 1], 16, fill=(8, 16, 32, 200))
        for j, li in enumerate(linhas):
            d.text((larg / 2, 11 + 46 * j + 22), li, font=f, fill=BRANCO, anchor="mm")
        return rgba(img)

    def barra(self, quadro: np.ndarray, i: int) -> None:
        x = int(W * i / max(1, self.n - 1))
        quadro[H - 7:H, :x] = VERDE
        quadro[H - 7:H, x:] = (quadro[H - 7:H, x:].astype(np.float32) * 0.6).astype(np.uint8)

    # --- layouts ---
    def cena_apresentador(self, quadro, k, p, t_c, est):
        cena = self.cenas[k]
        quadro[:] = self.fundo_estudio
        self.selo_capitulo(quadro, k, True, suave(t_c / 0.4))
        colar(quadro, self.logo, W - self.logo.shape[1] - 50, 30, 0.95)
        self.boneco_grande(quadro, est, -70, H - self.grande.h + 60)
        # quadro de conteúdo à direita
        cx, cy, cw, ch = 960, 150, 900, 760
        c = self.cache(("cartao", cw, ch), lambda: cartao(cw, ch, (255, 255, 255, 246)))
        ent = suave(t_c / 0.5)
        colar(quadro, c, cx - 26 + int((1 - ent) * 60), cy - 26, ent)
        tit = self.cache(("tit", k), lambda: texto_rgba(cena["titulo"], F_TIT(64), AZUL, cw - 110))
        colar(quadro, tit, cx + 55, cy + 50, ent)
        y = cy + 60 + tit.shape[0]
        faixa = self.cache("faixa", lambda: _faixa(160, 8))
        colar(quadro, faixa, cx + 57, y, ent)
        y += 34
        if cena.get("subtitulo"):
            st = self.cache(("sub", k), lambda: texto_rgba(cena["subtitulo"], F_SB(30), (70, 80, 100), cw - 110, 6))
            colar(quadro, st, cx + 55, y, ent)
            y += st.shape[0] + 26
        if cena.get("metricas"):
            self._metricas(quadro, cena["metricas"], cx + 38, y + 6, p)
            return
        itens = cena.get("itens", [])
        for j, item in enumerate(itens):
            ap = suave((p * (len(itens) + 0.4) - j) * 2.2)
            if ap <= 0:
                continue
            ic = self.cache("check", lambda: _check(42))
            tx = self.cache(("item", k, j), lambda: texto_rgba(item, F_RG(33), TINTA, cw - 190, 4))
            dx = int((1 - ap) * 40)
            colar(quadro, ic, cx + 55 + dx, y + 2, ap)
            colar(quadro, tx, cx + 115 + dx, y, ap)
            y += max(tx.shape[0], 46) + 20

    def _metricas(self, quadro, metricas, x0, y0, p):
        n = len(metricas)
        for j, (valor, rot) in enumerate(metricas):
            ap = suave((p * (n + 0.5) - j) * 2.0)
            if ap <= 0:
                continue
            cx, cy = x0 + (j % 2) * 418, y0 + (j // 2) * 166
            card = self.cache(("met", j), lambda: self._card_metrica(valor, rot))
            colar(quadro, card, cx, cy + int((1 - ap) * 30), ap)

    def _card_metrica(self, valor, rot):
        img = Image.new("RGBA", (400, 152), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, 399, 151], 22, fill=(238, 246, 241, 255), outline=(190, 220, 200, 255), width=2)
        d.rounded_rectangle([0, 0, 12, 151], 6, fill=VERDE + (255,))
        d.text((36, 18), valor, font=F_TIT(62), fill=AZUL)
        d.text((38, 104), rot, font=F_SB(26), fill=(60, 70, 90))
        return rgba(img)

    def janela(self, quadro, conteudo: np.ndarray, alfa: float, rotulo: str = "SAD-GD · demonstração com o corpus acadêmico"):
        x, y, w, h = 430, 92, 1440, 846
        moldura = self.cache(("janela", rotulo), lambda: self._moldura(w, h, rotulo))
        colar(quadro, moldura, x - 30, y - 30, alfa)
        area = quadro[y + 40:y + h, x:x + w]
        if alfa >= 0.999:
            area[:] = conteudo
        else:
            area[:] = (area.astype(np.float32) * (1 - alfa) + conteudo.astype(np.float32) * alfa).astype(np.uint8)

    def _moldura(self, w, h, rotulo):
        img = Image.fromarray(cartao(w, h, (244, 246, 250, 255), 18, 30, 120))
        d = ImageDraw.Draw(img)
        m = 30
        d.rounded_rectangle([m, m, m + w, m + 40], 18, fill=(226, 230, 238))
        d.rectangle([m, m + 22, m + w, m + 40], fill=(226, 230, 238))
        for j, cor in enumerate([(236, 95, 90), (245, 190, 60), (98, 196, 102)]):
            d.ellipse([m + 18 + j * 24, m + 13, m + 32 + j * 24, m + 27], fill=cor)
        d.rounded_rectangle([m + 110, m + 7, m + w - 110, m + 33], 12, fill=(255, 255, 255))
        d.text((m + w / 2, m + 20), rotulo, font=F_RG(18), fill=(80, 90, 110), anchor="mm")
        return np.asarray(img)

    def recorte(self, img: np.ndarray, ret, cw=1440, ch=806) -> np.ndarray:
        x0, y0, x1, y1 = ret
        return cv2.resize(img[int(y0):int(y1), int(x0):int(x1)], (cw, ch), interpolation=cv2.INTER_AREA)

    def ajustar(self, foco, img_w, img_h, aspecto=1440 / 806):
        x0, y0, x1, y1 = foco
        w, h = x1 - x0, y1 - y0
        if w / h > aspecto:
            h = w / aspecto
        else:
            w = h * aspecto
        w, h = min(w, img_w), min(h, img_h)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0 = min(max(0, cx - w / 2), img_w - w)
        y0 = min(max(0, cy - h / 2), img_h - h)
        return (x0, y0, x0 + w, y0 + h)

    def conteudo_tomada(self, tom: dict, q: float, primeira: bool = True) -> np.ndarray:
        if tom["tela"] == "celular":
            return self.cache("celular", self._celulares)
        img = self.tela(tom["tela"])
        ih, iw = img.shape[:2]
        if "rolagem" in tom:
            x0, _, x1, _ = tom["foco"]
            hh = (x1 - x0) * 806 / 1440
            yy = tom["rolagem"][0] + (tom["rolagem"][1] - tom["rolagem"][0]) * suave(q)
            return self.recorte(img, (x0, yy, x1, yy + hh))
        alvo = self.ajustar(tom["foco"], iw, ih)
        if primeira:
            cheio = self.ajustar((0, 0, iw, ih), iw, ih)
        else:  # tomadas seguintes partem de perto do foco (transição sem salto de escala)
            x0, y0, x1, y1 = alvo
            mx, my = (x1 - x0) * 0.12, (y1 - y0) * 0.12
            cheio = self.ajustar((x0 - mx, y0 - my, x1 + mx, y1 + my), iw, ih)
        z = suave(min(1.0, q * 1.6)) * 0.92
        ret = tuple(a + (b - a) * z for a, b in zip(cheio, alvo))
        return self.recorte(img, ret)

    def _celulares(self) -> np.ndarray:
        fundo = gradiente((236, 240, 247), (214, 222, 236), 1440, 806)
        img = Image.fromarray(fundo).convert("RGBA")
        for j, nome in enumerate(["50_celular_painel", "51_celular_resposta"]):
            tel = Image.open(TELAS / f"{nome}.png").convert("RGB")
            hh = 690
            ww = int(tel.width * hh / tel.height)
            tel = tel.resize((ww, hh), Image.LANCZOS)
            x, y = 330 + j * 470, 58
            sm = Image.new("L", img.size, 0)
            ImageDraw.Draw(sm).rounded_rectangle([x - 16, y - 12 + 16, x + ww + 16, y + hh + 16 + 16], 46, fill=120)
            img.paste((0, 0, 0, 255), mask=sm.filter(ImageFilter.GaussianBlur(18)))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([x - 16, y - 12, x + ww + 16, y + hh + 16], 46, fill=(20, 22, 28))
            mk = Image.new("L", (ww, hh), 0)
            ImageDraw.Draw(mk).rounded_rectangle([0, 0, ww - 1, hh - 1], 34, fill=255)
            img.paste(tel, (x, y + 2), mk)
            d.rounded_rectangle([x + ww / 2 - 40, y - 4, x + ww / 2 + 40, y + 10], 7, fill=(20, 22, 28))
        return np.asarray(img.convert("RGB"))

    def coluna_esquerda(self, quadro, k, nota: str | None, alfa_nota: float, est, t_c):
        cena = self.cenas[k]
        self.selo_capitulo(quadro, k, False, suave(t_c / 0.4))
        tit = self.cache(("tit_d", k), lambda: texto_rgba(cena["titulo"], F_TIT(40), BRANCO, 330, 2))
        colar(quadro, tit, 60, 96, suave(t_c / 0.5))
        y = 110 + tit.shape[0]
        colar(quadro, self.cache("faixa_d", lambda: _faixa(110, 7)), 62, y, suave(t_c / 0.5))
        if nota:
            card = self.cache(("nota", nota), lambda: self._nota(nota))
            colar(quadro, card, 40, y + 34 + int((1 - alfa_nota) * 20), alfa_nota)
        self.boneco_pip(quadro, est, 215, 760, 165)

    def _nota(self, nota: str) -> np.ndarray:
        tx = texto_rgba(nota, F_SB(27), TINTA, 300, 4)
        w, h = 350, tx.shape[0] + 44
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 18, fill=(255, 255, 255, 245))
        d.rounded_rectangle([0, 0, 10, h - 1], 5, fill=AMARELO + (255,))
        arr = rgba(img).copy()
        colar_rgba_em_rgba(arr, tx, 28, 20)
        return arr

    def cena_demo(self, quadro, k, p, t_c, est, dur_c):
        cena = self.cenas[k]
        quadro[:] = self.fundo_demo
        toms = cena["tomadas"]
        n = len(toms)
        pos = p * n
        j = min(n - 1, int(pos))
        q = pos - j
        atual = self.conteudo_tomada(toms[j], q, j == 0)
        trans = 0.35 / max(0.5, dur_c / n)  # fração da tomada usada na transição
        if j > 0 and q < trans:
            ant = self.conteudo_tomada(toms[j - 1], 1.0, j - 1 == 0)
            a = suave(q / trans)
            atual = (ant.astype(np.float32) * (1 - a) + atual.astype(np.float32) * a).astype(np.uint8)
        self.janela(quadro, atual, suave(t_c / 0.45))
        alfa_nota = suave(q / min(1, trans * 1.6)) if j > 0 else suave(t_c / 0.6)
        self.coluna_esquerda(quadro, k, toms[j].get("nota"), alfa_nota, est, t_c)

    def cena_ferramentas(self, quadro, k, p, t_c, est):
        cena = self.cenas[k]
        quadro[:] = self.fundo_demo
        self.coluna_esquerda(quadro, k, None, 0, est, t_c)
        cartoes = cena["cartoes"]
        n = len(cartoes)
        for j, (tit, desc) in enumerate(cartoes):
            ap = suave((p * 1.35 * (n + 0.5) - j) * 1.6)
            if ap <= 0:
                continue
            img = self.cache(("ferr", j), lambda: self._cartao_ferramenta(tit, desc, j))
            x = 440 + (j % 4) * 362
            y = 92 + (j // 4) * 222
            colar(quadro, img, x, y + int((1 - ap) * 26), ap)
        for j, nome in enumerate(cena.get("telas", [])):
            ap = suave((p - 0.55 - j * 0.12) * 5)
            if ap <= 0:
                continue
            mini = self.cache(("mini", nome), lambda: self._miniatura(nome))
            colar(quadro, mini, 450 + j * 715, 548 + int((1 - ap) * 30), ap)

    def _cartao_ferramenta(self, tit, desc, j):
        cores = [VERDE, AZUL, (196, 98, 45), (120, 70, 160), VERDE, AZUL, (196, 98, 45), (120, 70, 160)]
        img = Image.new("RGBA", (346, 206), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, 345, 205], 22, fill=(255, 255, 255, 250))
        d.rounded_rectangle([22, 22, 70, 70], 14, fill=cores[j] + (255,))
        d.text((46, 46), str(j + 1), font=F_TIT(28), fill=BRANCO, anchor="mm")
        ft = F_BD(27)
        while ft.getlength(tit) > 240 and ft.size > 19:
            ft = F_BD(ft.size - 1)
        d.text((84, 46), tit, font=ft, fill=TINTA, anchor="lm")
        y = 92
        for li in quebrar(desc, F_RG(23), 300):
            d.text((24, y), li, font=F_RG(23), fill=(70, 80, 100))
            y += 30
        return rgba(img)

    def _miniatura(self, nome):
        im = Image.open(TELAS / f"{nome}.png").convert("RGB")
        w = 690
        im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS).crop((0, 0, w, 360))
        base = Image.fromarray(cartao(w, 360, (255, 255, 255, 255), 16, 24, 110))
        mk = Image.new("L", (w, 360), 0)
        ImageDraw.Draw(mk).rounded_rectangle([0, 0, w - 1, 359], 16, fill=255)
        base.paste(im, (24, 24), mk)
        return np.asarray(base)

    def cena_arquitetura(self, quadro, k, p, t_c, est):
        quadro[:] = self.fundo_demo
        self.coluna_esquerda(quadro, k, None, 0, est, t_c)
        img = self.cache("arq_fundo", lambda: cartao(1420, 846, (250, 251, 253, 255), 26, 30, 120))
        colar(quadro, img, 430 - 30, 92 - 30, suave(t_c / 0.4))
        etapas = self.cache("arq_etapas", self._etapas_arquitetura)
        for j, (limiar, sprite, x, y) in enumerate(etapas):
            ap = suave((p - limiar) * 7)
            if ap > 0:
                colar(quadro, sprite, x, y + int((1 - ap) * 16), ap)

    def _etapas_arquitetura(self):
        def caixa(txt, sub, cor, w=300, h=104):
            img = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
            sm = Image.new("L", img.size, 0)
            ImageDraw.Draw(sm).rounded_rectangle([6, 10, w + 6, h + 10], 18, fill=90)
            img.paste((0, 0, 0, 255), mask=sm.filter(ImageFilter.GaussianBlur(6)))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, w, h], 18, fill=cor + (255,))
            d.text((w / 2, 36 if sub else h / 2), txt, font=F_BD(28), fill=BRANCO, anchor="mm")
            if sub:
                yy = 66
                for li in quebrar(sub, F_RG(20), w - 24):
                    d.text((w / 2, yy), li, font=F_RG(20), fill=(235, 240, 250), anchor="mm")
                    yy += 24
            return rgba(img)

        def seta(x0, y0, x1, y1):
            minx, miny = min(x0, x1) - 20, min(y0, y1) - 20
            img = Image.new("RGBA", (abs(x1 - x0) + 40, abs(y1 - y0) + 40), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            a, b = (x0 - minx, y0 - miny), (x1 - minx, y1 - miny)
            d.line([a, b], fill=(120, 130, 150, 255), width=5)
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            pts = [b, (b[0] - 18 * math.cos(ang - 0.45), b[1] - 18 * math.sin(ang - 0.45)),
                   (b[0] - 18 * math.cos(ang + 0.45), b[1] - 18 * math.sin(ang + 0.45))]
            d.polygon(pts, fill=(120, 130, 150, 255))
            return rgba(img), minx, miny

        X, Y = 430, 92
        e = []
        cinza, roxo, laranja = (90, 100, 120), (120, 70, 160), (196, 98, 45)
        e.append((0.00, caixa("Pergunta", "texto ou voz (Whisper local)", cinza, 260), X + 40, Y + 330))
        s, sx, sy = seta(X + 300, Y + 382, X + 360, Y + 382)
        e.append((0.06, s, sx, sy))
        e.append((0.08, caixa("Roteador", "LangGraph: F1 simples, complexa ou decisão", AZUL, 260), X + 365, Y + 330))
        s, sx, sy = seta(X + 625, Y + 360, X + 700, Y + 200)
        e.append((0.15, s, sx, sy))
        s, sx, sy = seta(X + 625, Y + 405, X + 700, Y + 560)
        e.append((0.15, s, sx, sy))
        e.append((0.18, caixa("Busca híbrida", "BM25 + bge-m3 + reranker", VERDE, 290), X + 705, Y + 120))
        e.append((0.26, caixa("Fichas de contrato", "respostas em segundos", VERDE, 290), X + 1020, Y + 120))
        e.append((0.34, caixa("Especialistas", "Procurador · Advogado · Controlador · Fiscal · Gestor · Analista",
                              roxo, 290, 128), X + 705, Y + 500))
        e.append((0.42, caixa("Relator", "consensos, divergências, riscos, confiança", roxo, 290, 128),
                  X + 1020, Y + 500))
        s, sx, sy = seta(X + 1165, Y + 240, X + 1165, Y + 318)
        e.append((0.48, s, sx, sy))
        s, sx, sy = seta(X + 1165, Y + 495, X + 1165, Y + 440)
        e.append((0.48, s, sx, sy))
        e.append((0.50, caixa("Verificador de fontes", "frase sem prova é removida", laranja, 330, 100),
                  X + 1000, Y + 335))
        e.append((0.58, caixa("Resposta com fontes", "documento · página · trecho", AZUL, 330, 96), X + 365, Y + 560))
        s, sx, sy = seta(X + 995, Y + 400, X + 700, Y + 600)
        e.append((0.58, s, sx, sy))
        # chips dos modelos
        chips = ["Qwen 2.5 7B · Ollama", "bge-m3", "bge-reranker-v2-m3", "faster-whisper", "Tesseract 5",
                 "SQLite + sqlite-vec", "LangGraph", "LGPD · sem nuvem"]
        x, y = X + 40, Y + 715
        for j, c in enumerate(chips):
            f = F_SB(23)
            w = int(f.getlength(c)) + 40
            if x + w > X + 1400:
                x, y = X + 40, y + 56
            img = Image.new("RGBA", (w, 44), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, w - 1, 43], 22, fill=(230, 238, 250, 255), outline=(160, 180, 215, 255))
            d.text((w / 2, 22), c, font=f, fill=AZUL, anchor="mm")
            e.append((0.66 + j * 0.035, rgba(img), x, y))
            x += w + 14
        tit = texto_rgba("Modelos abertos, locais e gratuitos", F_BD(26), (70, 80, 100))
        e.append((0.64, tit, X + 40, Y + 672))
        return e

    def cena_fechamento(self, quadro, k, p, t_c, est):
        quadro[:] = self.fundo_estudio
        colar(quadro, self.logo, W - self.logo.shape[1] - 50, 30, 0.95)
        self.boneco_grande(quadro, est, -70, H - self.grande.h + 60)
        cx, cy, cw, ch = 960, 150, 900, 760
        c = self.cache(("cartao_f", cw, ch), lambda: cartao(cw, ch, AZUL + (250,)))
        colar(quadro, c, cx - 26, cy - 26, suave(t_c / 0.5))
        linhas = [("Pergunte.", 0.0), ("Confira a fonte.", 0.18), ("Decida.", 0.36)]
        y = cy + 70
        for txt, lim in linhas:
            ap = suave((p - lim) * 5)
            img = self.cache(("fech", txt), lambda: texto_rgba(txt, F_TIT(80), AMARELO if txt == "Decida." else BRANCO))
            colar(quadro, img, cx + 60, y, ap)
            y += 108
        info = [("Código-fonte", "github.com/danilodxavier/SGD"), ("Acesso na rede da SEMA", "sad.sema.mt.gov.br"),
                ("Princípio", "o sistema sugere, a gestão decide")]
        y += 30
        for j, (a, b) in enumerate(info):
            ap = suave((p - 0.45 - j * 0.1) * 5)
            img = self.cache(("info", j), lambda: self._linha_info(a, b))
            colar(quadro, img, cx + 60, y, ap)
            y += 92

    def _linha_info(self, a, b):
        img = Image.new("RGBA", (840, 80), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((0, 0), a.upper(), font=F_BD(22), fill=(150, 200, 255))
        d.text((0, 30), b, font=F_SB(36), fill=BRANCO)
        return rgba(img)

    # --- quadro completo ---
    def cena_em(self, t: float) -> int:
        k = 0
        for j, (ini, _) in enumerate(self.tempos):
            if t >= ini - PAUSA / 2:
                k = j
        return k

    def render_cena(self, quadro, k: int, t: float, i: int) -> None:
        ini, fim = self.tempos[k]
        ini_c = ini - (PAUSA / 2 if k else INICIO)
        fim_c = self.tempos[k + 1][0] - PAUSA / 2 if k + 1 < len(self.tempos) else self.dur
        p = min(1.0, max(0.0, (t - ini) / max(0.1, fim - ini)))
        t_c = t - ini_c
        est = self.estado_boneco(i, t)
        tipo = self.cenas[k]["tipo"]
        if tipo in ("apresentador", "metricas"):
            self.cena_apresentador(quadro, k, p, t_c, est)
        elif tipo == "demo":
            self.cena_demo(quadro, k, p, t_c, est, fim_c - ini_c)
        elif tipo == "ferramentas":
            self.cena_ferramentas(quadro, k, p, t_c, est)
        elif tipo == "arquitetura":
            self.cena_arquitetura(quadro, k, p, t_c, est)
        else:
            self.cena_fechamento(quadro, k, p, t_c, est)

    def quadro(self, i: int) -> np.ndarray:
        t = i / FPS
        k = self.cena_em(t)
        q = np.empty((H, W, 3), np.uint8)
        self.render_cena(q, k, t, i)
        ini_c = self.tempos[k][0] - (PAUSA / 2 if k else INICIO)
        if k > 0 and t - ini_c < 0.4:  # transição cruzada entre cenas
            q2 = np.empty((H, W, 3), np.uint8)
            self.render_cena(q2, k - 1, ini_c - 0.001, i)
            a = suave((t - ini_c) / 0.4)
            q = (q2.astype(np.float32) * (1 - a) + q.astype(np.float32) * a).astype(np.uint8)
        if t < 0.6:  # abertura em fade
            q = (q.astype(np.float32) * suave(t / 0.6)).astype(np.uint8)
        if t > self.dur - 0.8:
            q = (q.astype(np.float32) * suave((self.dur - t) / 0.8)).astype(np.uint8)
        self.legenda(q, t)
        self.barra(q, i)
        return q


def colar_rgba_em_rgba(dst, src, x, y):
    _colar_rgba(dst, src, x, y)


def _faixa(w, h):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w * 0.6, h - 1], h // 2, fill=VERDE + (255,))
    d.rounded_rectangle([w * 0.64, 0, w - 1, h - 1], h // 2, fill=AMARELO + (255,))
    return rgba(img)


def _check(t):
    s = 4
    img = Image.new("RGBA", (t * s, t * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, t * s - 1, t * s - 1], fill=VERDE + (255,))
    d.line([(t * s * 0.27, t * s * 0.52), (t * s * 0.44, t * s * 0.68), (t * s * 0.74, t * s * 0.34)],
           fill=BRANCO + (255,), width=int(t * s * 0.11), joint="curve")
    return rgba(img.resize((t, t), Image.LANCZOS))


# ------------------------------------------------------------------ execução
def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> None:
    acao = sys.argv[1] if len(sys.argv) > 1 else "ajuda"
    SAIDA.mkdir(parents=True, exist_ok=True)
    if acao == "audio":
        preparar_audio("--sintetizar" in sys.argv)
        return
    if acao == "previa":
        v = Video()
        for s in sys.argv[2].split(","):
            q = v.quadro(int(float(s) * FPS))
            Image.fromarray(q).save(SAIDA / f"previa_{s}s.png")
        print("prévias gravadas")
        return
    if acao == "parte":
        k, total = int(sys.argv[2]), int(sys.argv[3])
        v = Video()
        ini, fim = v.n * k // total, v.n * (k + 1) // total
        (SAIDA / "partes").mkdir(exist_ok=True)
        destino = SAIDA / "partes" / f"parte_{k:02d}.mp4"
        cmd = [ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt",
               "yuv420p", "-g", "50", str(destino)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(ini, fim):
            proc.stdin.write(v.quadro(i).tobytes())
            if (i - ini) % (FPS * 10) == 0:
                print(f"parte {k}: {i / FPS:6.1f}s (até {fim / FPS:.1f}s)", flush=True)
        proc.stdin.close()
        proc.wait()
        print(f"OK parte {k}: quadros {ini}-{fim}")
        return
    if acao == "juntar":
        partes = sorted((SAIDA / "partes").glob("parte_*.mp4"))
        lista = SAIDA / "partes" / "lista.txt"
        lista.write_text("".join(f"file '{p.name}'\n" for p in partes), encoding="utf-8")
        destino = SAIDA / "SAD-GD_DemoDay_2026.mp4"
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-i", str(SAIDA / "narracao.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", str(destino)], check=True)
        print("OK:", destino)
        return
    print(__doc__)


if __name__ == "__main__":
    main()
