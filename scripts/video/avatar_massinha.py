"""Boneco de massinha (plasticina) 3D a partir da foto do apresentador — 100% local.

Etapas (OpenCV + NumPy + SciPy, sem modelos de IA externos):
1. Segmentação da pessoa (GrabCut com dicas de primeiro plano/fundo) e contorno suavizado;
2. Simplificação em "placas" de massa: filtro bilateral + mean shift + quantização de cores (k-means em Lab);
3. Relevo: cada placa vira uma almofada (transformada de distância) somada a uma cúpula do corpo e ao relevo
   suave do rosto da foto — dá o volume esculpido;
4. Iluminação de massinha: luz principal, preenchimento e contorno, brilho especular ceroso, oclusão nos vincos
   e textura de digitais/ferramenta de modelar;
5. Olhos de "contas" brilhantes e boca de massinha substituível (animada no vídeo).

Saída: data/video/trabalho/massinha/{base.png, mascara.png, meta.json, previa.png} (fora do Git).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage as ndi

RAIZ = Path(__file__).resolve().parents[2]
FOTO = RAIZ / "data" / "video" / "foto.jpg"
SAIDA = RAIZ / "data" / "video" / "trabalho" / "massinha"
ESC = 2  # trabalha em 2× a foto (618 → 1236)

# Pontos da foto original (618×619)
OLHOS = [(258, 250), (368, 250)]
BOCA = (312, 352)
QUEIXO_Y = 432


def segmentar(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    m = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    s = ESC
    # Provável pessoa: cabeça (oval) + pescoço + ombros/camisa
    cv2.ellipse(m, (315 * s, 255 * s), (135 * s, 195 * s), 0, 0, 360, cv2.GC_PR_FGD, -1)
    pts = np.array([[200, 390], [430, 390], [470, 430], [600, 480], [618, 619], [10, 619], [40, 470], [160, 420]]) * s
    cv2.fillPoly(m, [pts.astype(np.int32)], cv2.GC_PR_FGD)
    for cx, cy in ((207, 272), (434, 270)):  # orelhas
        cv2.ellipse(m, (cx * s, cy * s), (13 * s, 40 * s), 0, 0, 360, cv2.GC_FGD, -1)
    # Certamente pessoa: miolo do rosto, cabelo central e camisa
    cv2.ellipse(m, (315 * s, 280 * s), (95 * s, 140 * s), 0, 0, 360, cv2.GC_FGD, -1)
    cv2.ellipse(m, (320 * s, 120 * s), (90 * s, 40 * s), 0, 0, 360, cv2.GC_FGD, -1)
    cv2.rectangle(m, (120 * s, 500 * s), (560 * s, 619 * s), cv2.GC_FGD, -1)
    cv2.rectangle(m, (255 * s, 420 * s), (380 * s, 520 * s), cv2.GC_FGD, -1)
    # Certamente fundo: laterais acima dos ombros e topo
    for x0, y0, x1, y1 in ((0, 0, 150, 400), (480, 0, 618, 400), (0, 0, 618, 45), (0, 400, 25, 470),
                           (0, 0, 205, 230), (445, 0, 618, 230)):
        cv2.rectangle(m, (x0 * s, y0 * s), (x1 * s, y1 * s), cv2.GC_BGD, -1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, m, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    masc = np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    # maior componente, buracos fechados, contorno arredondado (massa não tem fiapos)
    lab, n = ndi.label(masc > 0.5)
    if n > 1:
        maior = 1 + int(np.argmax(ndi.sum(masc, lab, range(1, n + 1))))
        masc = (lab == maior).astype(np.float32)
    masc = ndi.binary_fill_holes(masc > 0.5).astype(np.float32)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    masc = cv2.morphologyEx(masc, cv2.MORPH_OPEN, k)
    masc = cv2.morphologyEx(masc, cv2.MORPH_CLOSE, k)
    for cx, cy in ((208, 274), (433, 272)):
        cv2.ellipse(masc, (cx * s, cy * s), (12 * s, 31 * s), 0, 0, 360, 1.0, -1)
    masc = cv2.GaussianBlur(masc, (0, 0), 9)
    return np.clip((masc - 0.5) * 6 + 0.5, 0, 1)


def _almofada(reg: np.ndarray, R: float, amp: float) -> np.ndarray:
    d = ndi.distance_transform_edt(reg).astype(np.float32)
    r = np.clip(d / R, 0, 1)
    return np.where(reg, np.sqrt(1 - (1 - r) ** 2) * R * amp, 0).astype(np.float32)


def _limpar(reg: np.ndarray, abrir: int, fechar: int) -> np.ndarray:
    r = reg.astype(np.uint8)
    if fechar:
        r = cv2.morphologyEx(r, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (fechar, fechar)))
    if abrir:
        r = cv2.morphologyEx(r, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (abrir, abrir)))
    r = cv2.GaussianBlur(r.astype(np.float32), (0, 0), 3) > 0.5
    return r


def pecas(img: np.ndarray, masc: np.ndarray) -> dict[str, np.ndarray]:
    """Divide a pessoa em peças de massa: cabelo, sobrancelhas, barba, pele, camisa e acessório."""
    x = img.copy()
    for _ in range(3):
        x = cv2.bilateralFilter(x, 11, 40, 9)
    lab = cv2.cvtColor(x, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, A, B = lab[..., 0], lab[..., 1] - 128, lab[..., 2] - 128
    croma = np.sqrt(A ** 2 + B ** 2)
    dentro = masc > 0.5
    yy, xx = np.mgrid[0:masc.shape[0], 0:masc.shape[1]]
    y = yy / ESC
    xo = xx / ESC
    escuro = dentro & (L < 118)
    camisa = dentro & (croma < 14) & (L >= 118) & (y > 370)
    acessorio = escuro & (y > 540)
    cabelo = escuro & (y < 222)
    sobr = escuro & (y >= 212) & (y < 246) & (xo > 225) & (xo < 410)
    barba = escuro & (y >= 318) & (y < 470) & (xo > 225) & (xo < 405)
    olhos = np.zeros_like(dentro)
    for ox, oy in OLHOS:
        olhos |= ((xo - ox) / 30) ** 2 + ((y - oy) / 14) ** 2 < 1
    p = {"cabelo": _limpar(cabelo, 9, 25), "sobrancelhas": _limpar(sobr & ~olhos, 7, 11),
         "barba": _limpar(barba, 5, 13), "acessorio": _limpar(acessorio, 9, 15), "camisa": _limpar(camisa, 15, 31)}
    ocupado = np.zeros_like(dentro)
    for v in p.values():
        ocupado |= v
    pele = dentro & ~ocupado
    # faixas finas de pele entre a gola e a camisa viram camisa (massa não tem fiapos)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))
    larga = cv2.morphologyEx(pele.astype(np.uint8), cv2.MORPH_OPEN, k).astype(bool)
    fina = pele & ~larga & (y > 430)
    p["camisa"] = p["camisa"] | fina
    p["pele"] = pele & ~fina
    p["_lab"] = lab
    return p


def colorir(p: dict, masc: np.ndarray) -> np.ndarray:
    lab = p["_lab"]
    suave = cv2.GaussianBlur(lab, (0, 0), 14)
    muito_suave = cv2.GaussianBlur(lab, (0, 0), 40)
    cor = np.zeros_like(lab)
    pele_med = np.median(lab[p["pele"]], axis=0)
    pele = muito_suave * 0.3 + pele_med * 0.7
    pele[..., 0] = np.clip(pele[..., 0], 135, 196)
    pele[..., 1] = 128 + (pele[..., 1] - 128) * 1.25
    cor[...] = pele
    def chapada(nome, ajuste_l=0.0, mistura=0.25, satura=1.2):
        reg = p[nome]
        if reg.sum() == 0:
            return
        med = np.median(lab[reg], axis=0)
        c = suave * mistura + med * (1 - mistura)
        c[..., 0] += ajuste_l
        c[..., 1:] = 128 + (c[..., 1:] - 128) * satura
        cor[reg] = c[reg]
    chapada("cabelo", 18, 0.2, 1.35)
    chapada("sobrancelhas", 6, 0.1, 1.2)
    chapada("barba", 22, 0.35, 1.2)
    chapada("acessorio", 10, 0.0, 0.5)
    cam = p["camisa"]
    cor[cam] = np.array([236, 128, 131], np.float32)
    bgr = cv2.cvtColor(np.clip(cor, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    # bordas macias entre peças (massa encostada)
    return cv2.GaussianBlur(bgr, (0, 0), 1.2)


def relevo(p: dict, masc: np.ndarray) -> np.ndarray:
    yy, xx = np.mgrid[0:masc.shape[0], 0:masc.shape[1]].astype(np.float32)
    s = ESC
    d = ndi.distance_transform_edt(masc > 0.5).astype(np.float32)
    h = np.sqrt(np.clip(d, 0, 220) / 220) * 60
    cx, cy, rx, ry = 316 * s, 262 * s, 128 * s, 190 * s
    e = 1 - ((xx - cx) / rx) ** 2 - ((yy - cy) / ry) ** 2
    h += np.sqrt(np.clip(e, 0, 1)) * 120 * (masc > 0.5)
    # escultura do rosto: testa, sobrancelha, nariz, maçãs, queixo, lábios; olhos em cavidade
    formas = [(316, 175, 105, 55, 14), (316, 232, 100, 16, 9), (313, 292, 22, 52, 22), (313, 330, 30, 16, 16),
              (255, 318, 40, 30, 12), (372, 318, 40, 30, 12), (316, 410, 62, 36, 14), (313, 357, 40, 14, 6)]
    def suave(en):
        t = np.clip(en, 0, 1)
        return t * t * (3 - 2 * t)
    for fx, fy, frx, fry, alt in formas:
        en = 1 - ((xx - fx * s) / (frx * s * 1.25)) ** 2 - ((yy - fy * s) / (fry * s * 1.25)) ** 2
        h += suave(en) * alt
    for ox, oy in OLHOS:
        en = 1 - ((xx - ox * s) / (38 * s)) ** 2 - ((yy - oy * s) / (22 * s)) ** 2
        h -= suave(en) * 12
    # orelhas: concha com dobra interna
    for ox, oy, lado in ((208, 274, -1), (433, 272, 1)):
        en = 1 - ((xx - ox * s) / (12 * s)) ** 2 - ((yy - oy * s) / (31 * s)) ** 2
        dentro_or = 1 - ((xx - (ox - lado * 2) * s) / (6 * s)) ** 2 - ((yy - (oy + 2) * s) / (19 * s)) ** 2
        h += suave(en) * 18 - suave(dentro_or) * 6
    # peças sobrepostas
    h += _almofada(p["cabelo"], 34, 0.9)
    ang = np.deg2rad(-18)
    fios = np.sin((xx * np.cos(ang) + yy * np.sin(ang)) / 5.5 + np.sin(yy / 23) * 2) * 1.6
    h += np.where(p["cabelo"], fios, 0)
    h += _almofada(p["sobrancelhas"], 9, 1.1)
    h += _almofada(p["barba"], 10, 0.55)
    h += _almofada(p["acessorio"], 12, 0.8)
    cam = p["camisa"]
    h += _almofada(cam, 26, 0.8)
    lum = cv2.GaussianBlur(p["_lab"][..., 0], (0, 0), 12)
    h += np.where(cam, (lum - 200) * 0.18, 0)
    return cv2.GaussianBlur(h, (0, 0), 1.8) * (masc > 0.02)


def granulado(reg: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Barba de massinha: furinhos de palito."""
    pts = (rng.random(reg.shape) < 0.012) & reg
    return -cv2.GaussianBlur(pts.astype(np.float32), (0, 0), 1.3) * 9


def textura(shape: tuple[int, int], rng: np.random.Generator) -> np.ndarray:
    """Marcas de dedo e de espátula: ruído fino + arcos concêntricos esparsos."""
    t = cv2.GaussianBlur(rng.normal(0, 1, shape).astype(np.float32), (0, 0), 1.6) * 0.25
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    for _ in range(14):
        cx, cy = rng.uniform(0, shape[1]), rng.uniform(0, shape[0])
        raio = rng.uniform(18, 40)
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        ang = np.arctan2(yy - cy, xx - cx)
        anel = np.sin(d / 2.4) * np.exp(-((d / raio) ** 2)) * 0.35 * np.clip(np.cos(ang - rng.uniform(0, 6.3)), 0, 1)
        t += anel.astype(np.float32)
    return t


def iluminar(cor: np.ndarray, h: np.ndarray, masc: np.ndarray, tex: np.ndarray) -> np.ndarray:
    hh = h + tex
    gy, gx = np.gradient(hh)
    n = np.dstack([-gx, -gy, np.ones_like(hh) * 1.6])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    luzes = [((-0.55, -0.65, 0.75), 0.95, (1.0, 0.97, 0.92)),   # principal (cima-esquerda, quente)
             ((0.7, -0.1, 0.5), 0.35, (0.85, 0.9, 1.0)),          # preenchimento (fria)
             ((0.2, 0.9, 0.3), 0.15, (1.0, 0.95, 0.9))]           # rebatida de baixo
    base = cor.astype(np.float32) / 255
    base = cv2.cvtColor(base, cv2.COLOR_BGR2HSV)
    base[..., 1] = np.clip(base[..., 1] * 1.08, 0, 1)  # massinha levemente saturada
    base = cv2.cvtColor(base, cv2.COLOR_HSV2BGR)
    tot = np.zeros_like(base) + 0.20  # ambiente
    espec = np.zeros(hh.shape, np.float32)
    v = np.array([0, 0, 1.0])
    for d, inten, tint in luzes:
        L = np.array(d) / np.linalg.norm(d)
        ndl = np.clip((n @ L + 0.25) / 1.25, 0, 1)  # luz envolvente (subsuperfície)
        tot += ndl[..., None] * inten * np.array(tint[::-1], np.float32)
        hv = (L + v) / np.linalg.norm(L + v)
        espec += np.clip(n @ hv, 0, 1) ** 22 * inten * 0.28
    # oclusão nos vincos entre placas
    ao = np.clip((cv2.GaussianBlur(h, (0, 0), 6) - h) / 10, 0, 1)
    tot *= (1 - 0.55 * ao)[..., None]
    out = base * tot * 0.8 + espec[..., None] * np.array([0.95, 0.97, 1.0], np.float32)
    # contorno com luz de recorte e sombra de contato
    borda = np.clip(cv2.GaussianBlur(masc, (0, 0), 4) * (1 - cv2.erode(masc, np.ones((9, 9)))), 0, 1)
    out += borda[..., None] * 0.08
    return np.clip(out * 255, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ versão 2: personagem simpático
# Contorno do rosto medido na foto (altura, x esquerdo, x direito), suavizado — mantém o formato real
CONTORNO = [(150, 245, 392), (170, 228, 410), (200, 220, 418), (240, 216, 422), (280, 216, 422), (320, 222, 416),
            (350, 232, 405), (380, 246, 390), (405, 259, 378), (425, 276, 362), (440, 296, 342), (447, 318, 320)]
ORELHAS = [(213, 276), (426, 274)]
PIVO = (318, 452)          # ponto do queixo/pescoço em torno do qual a cabeça é ampliada
CABECA = 1.10              # cabeça um pouco maior: proporção de personagem
CABECA_X, CABECA_Y = 1.16, 1.04  # e mais arredondada (larga, menos comprida)
PELE_RGB = (232, 182, 150)
CABELO_RGB = (84, 56, 40)
BARBA_RGB = (118, 84, 62)
CAMISA_RGB = (238, 237, 233)


def _poligono_rosto(shape) -> np.ndarray:
    s = ESC
    esq = [(xl, y) for y, xl, _ in CONTORNO]
    dir_ = [(xr, y) for y, _, xr in CONTORNO][::-1]
    pts = np.array(esq + dir_, np.float32) * s
    m = np.zeros(shape, np.float32)
    cv2.fillPoly(m, [pts.astype(np.int32)], 1.0)
    cv2.ellipse(m, (int(318 * s), int(175 * s)), (int(92 * s), int(60 * s)), 0, 180, 360, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), 7)
    return m > 0.5


def _sobrancelhas_da_foto(p) -> list[list[float]]:
    """Extremos e espessura de cada sobrancelha na foto (a peça animada fica no mesmo lugar)."""
    lab, n = ndi.label(p["sobrancelhas"])
    itens = []
    for j in range(1, n + 1):
        ys, xs = np.where(lab == j)
        if len(xs) < 200:
            continue
        itens.append([xs.min() / ESC, xs.max() / ESC, ys.mean() / ESC, (ys.max() - ys.min()) / ESC])
    itens.sort()
    if len(itens) < 2:
        itens = [[236, 300, 229, 10], [334, 396, 229, 10]]
    return itens[:2]


def construir_v2(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    masc_foto = segmentar(img)
    p = pecas(img, masc_foto)
    H_, W_ = masc_foto.shape
    s = ESC
    yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32)
    y = yy / s

    def suave(en):
        t = np.clip(en, 0, 1)
        return t * t * (3 - 2 * t)

    def elip(cx, cy, rx, ry):
        return 1 - ((xx - cx * s) / (rx * s)) ** 2 - ((yy - cy * s) / (ry * s)) ** 2

    rosto = _poligono_rosto((H_, W_))
    orelhas = np.zeros_like(rosto)
    for ox, oy in ORELHAS:
        orelhas |= elip(ox, oy, 13, 29) > 0
    cab_foto = _limpar(p["cabelo"], 9, 31)
    cabelo = (cab_foto & (y < 236))
    barba = ndi.binary_fill_holes(_limpar(p["barba"], 7, 33)) & rosto & (y > 341)
    pesc = np.zeros((H_, W_), np.uint8)
    cv2.fillPoly(pesc, [(np.array([[278, 400], [358, 400], [368, 482], [268, 482]]) * s).astype(np.int32)], 1)
    pesc = pesc.astype(bool) | (p["pele"] & (y > 462))
    pesc = _limpar(pesc, 25, 31)
    camisa = _limpar(p["camisa"] | p["acessorio"] | ((masc_foto > 0.5) & (y > 470) & ~pesc), 15, 41)
    camisa = ndi.binary_fill_holes(camisa)
    pesc &= ~camisa

    # ---- cores (BGR)
    pele = np.array(PELE_RGB[::-1], np.float32)
    cor = np.broadcast_to(pele, (H_, W_, 3)).copy()
    for cx in (262, 374):  # bochechas rosadas
        b = suave(elip(cx, 335, 34, 24) * 1.2)[..., None]
        cor = cor * (1 - 0.38 * b) + np.array([150, 150, 236], np.float32) * 0.38 * b
    lum = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 6)
    med = np.median(lum[p["pele"] & (y > 250) & (y < 320)])
    rala = np.clip((med - lum) / 45, 0, 1) * (y > 345) * rosto * suave(1 - elip(318, 330, 70, 40))
    cor = cor * (1 - 0.32 * rala[..., None]) + np.array([120, 140, 170], np.float32) * 0.32 * rala[..., None]
    cor[pesc] = pele * 0.93
    cor[barba] = np.array(BARBA_RGB[::-1], np.float32)
    cor[cabelo] = np.array(CABELO_RGB[::-1], np.float32)
    cor[camisa] = np.array(CAMISA_RGB[::-1], np.float32)
    cor = cv2.GaussianBlur(cor, (0, 0), 1.2)

    # ---- relevo do corpo
    hb = np.zeros((H_, W_), np.float32)
    hb += _almofada(camisa, 40, 0.9)
    lum_c = cv2.GaussianBlur(p["_lab"][..., 0], (0, 0), 5)
    hb += np.where(camisa, (lum_c - 200) * 0.34, 0)  # gola e dobras da polo
    hb += np.where(pesc, 18, 0) + _almofada(pesc, 46, 0.9)

    # ---- relevo da cabeça
    cab_m = rosto | orelhas | cabelo
    d = ndi.distance_transform_edt(rosto).astype(np.float32)
    hh = np.where(rosto, np.sqrt(np.clip(d / (60 * s), 0, 1)) * 70, 0).astype(np.float32)
    hh += suave(elip(318, 290, 120, 175)) * 70 * rosto
    formas = [  # (cx, cy, rx, ry, altura): testa, nariz, ponta, asas, maçãs do sorriso, queixo, lábio, arco
        (318, 190, 95, 45, 12), (318, 287, 13, 38, 16), (318, 322, 19, 16, 30), (301, 330, 10, 8, 12),
        (335, 330, 10, 8, 12), (262, 332, 34, 25, 16), (374, 332, 34, 25, 16), (318, 430, 38, 22, 14),
        (318, 352, 40, 13, 6), (318, 236, 92, 12, 8)]
    for cx, cy, rx, ry, alt in formas:
        hh += suave(elip(cx, cy, rx * 1.2, ry * 1.2)) * alt
    for ox, oy in OLHOS:
        hh -= suave(elip(ox, oy + 2, 36, 21)) * 10
    hh = np.where(orelhas & ~rosto, 0, hh)
    for (ox, oy), lado in zip(ORELHAS, (-1, 1)):
        hh += suave(elip(ox, oy, 13, 29)) * 46 - suave(elip(ox - lado * 2, oy + 2, 6, 17)) * 8
    hh += _almofada(cabelo, 36, 1.1)
    hh += np.where(cabelo, suave(elip(330, 112, 105, 52)) * 34, 0)  # topete
    u = (xx - 318 * s) * np.cos(0.35) + (yy - 60 * s) * np.sin(0.35)
    fios = np.sin(u / 6.5 + np.sin(yy / 31) * 1.6) * 2.0  # mechas penteadas para cima e para o lado
    hh += np.where(cabelo, fios, 0)
    hh += _almofada(barba, 9, 0.5)
    hh += 40  # cabeça à frente do corpo

    # ---- ampliar a cabeça em torno do queixo (cor, relevo e máscara)
    px, py = PIVO[0] * s, PIVO[1] * s
    M = np.float32([[CABECA_X, 0, px * (1 - CABECA_X)], [0, CABECA_Y, py * (1 - CABECA_Y)]])
    ac = cv2.warpAffine(cab_m.astype(np.float32), M, (W_, H_), flags=cv2.INTER_LINEAR)
    cc = cv2.warpAffine(cor, M, (W_, H_), flags=cv2.INTER_LINEAR)
    hc = cv2.warpAffine(hh, M, (W_, H_), flags=cv2.INTER_LINEAR)
    bc = cv2.warpAffine(barba.astype(np.float32), M, (W_, H_), flags=cv2.INTER_LINEAR) > 0.5
    ac = np.clip((cv2.GaussianBlur(ac, (0, 0), 1.5) - 0.5) * 4 + 0.5, 0, 1)
    corpo = cv2.GaussianBlur((camisa | pesc).astype(np.float32), (0, 0), 2.5)
    corpo = np.clip((corpo - 0.5) * 4 + 0.5, 0, 1)
    a = ac[..., None]
    cor_f = cc * a + cor * (1 - a)
    h_f = hc * ac + hb * (1 - ac)
    masc = np.maximum(ac, corpo)
    sombra = cv2.GaussianBlur(ac, (0, 0), 14) * (1 - ac) * (corpo > 0.5)
    cor_f *= (1 - 0.35 * sombra)[..., None]

    rng = np.random.default_rng(3)
    tex = textura((H_, W_), rng) + granulado(bc, rng)
    clay = iluminar(np.clip(cor_f, 0, 255).astype(np.uint8), h_f, masc, tex)

    def tf(x, y_):
        return [PIVO[0] + (x - PIVO[0]) * CABECA_X, PIVO[1] + (y_ - PIVO[1]) * CABECA_Y]

    sob = _sobrancelhas_da_foto(p)
    meta = {"escala": ESC, "cabeca": CABECA,
            "olhos": [[v * ESC for v in tf(x, y_)] for x, y_ in OLHOS],
            "boca": [v * ESC for v in tf(*BOCA)],
            "queixo_y": tf(0, QUEIXO_Y)[1] * ESC,
            "sobrancelhas": [[tf(x0, yc)[0] * ESC, tf(x1, yc)[0] * ESC, tf(0, yc)[1] * ESC,
                              max(9.0, esp) * CABECA * ESC] for x0, x1, yc, esp in sob],
            "pele": list(PELE_RGB), "tamanho": [W_, H_]}
    return clay, masc, meta


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    foto = cv2.imread(str(FOTO))
    img = cv2.resize(foto, None, fx=ESC, fy=ESC, interpolation=cv2.INTER_CUBIC)
    clay, masc, meta = construir_v2(img)
    rgba = np.dstack([clay, (masc * 255).astype(np.uint8)])
    cv2.imwrite(str(SAIDA / "base.png"), rgba)
    cv2.imwrite(str(SAIDA / "mascara.png"), (masc * 255).astype(np.uint8))
    (SAIDA / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    fundo = np.full_like(clay, (150, 190, 215))
    a = masc[..., None]
    prev = (clay * a + fundo * (1 - a)).astype(np.uint8)
    cv2.imwrite(str(SAIDA / "previa.png"), cv2.resize(prev, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA))
    print("ok", img.shape, [[round(v) for v in s_] for s_ in meta["sobrancelhas"]])


if __name__ == "__main__":
    main()
