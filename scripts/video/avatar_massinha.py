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
    base[..., 1] = np.clip(base[..., 1] * 1.25, 0, 1)  # massinha é saturada
    base = cv2.cvtColor(base, cv2.COLOR_HSV2BGR)
    tot = np.zeros_like(base) + 0.22  # ambiente
    espec = np.zeros(hh.shape, np.float32)
    v = np.array([0, 0, 1.0])
    for d, inten, tint in luzes:
        L = np.array(d) / np.linalg.norm(d)
        ndl = np.clip((n @ L + 0.25) / 1.25, 0, 1)  # luz envolvente (subsuperfície)
        tot += ndl[..., None] * inten * np.array(tint[::-1], np.float32)
        hv = (L + v) / np.linalg.norm(L + v)
        espec += np.clip(n @ hv, 0, 1) ** 38 * inten * 0.55
    # oclusão nos vincos entre placas
    ao = np.clip((cv2.GaussianBlur(h, (0, 0), 6) - h) / 10, 0, 1)
    tot *= (1 - 0.55 * ao)[..., None]
    out = base * tot + espec[..., None] * np.array([0.95, 0.97, 1.0], np.float32)
    # contorno com luz de recorte e sombra de contato
    borda = np.clip(cv2.GaussianBlur(masc, (0, 0), 4) * (1 - cv2.erode(masc, np.ones((9, 9)))), 0, 1)
    out += borda[..., None] * 0.08
    return np.clip(out * 255, 0, 255).astype(np.uint8)


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    foto = cv2.imread(str(FOTO))
    img = cv2.resize(foto, None, fx=ESC, fy=ESC, interpolation=cv2.INTER_CUBIC)
    masc = segmentar(img)
    p = pecas(img, masc)
    cor = colorir(p, masc)
    h = relevo(p, masc)
    rng = np.random.default_rng(3)
    tex = textura(masc.shape, rng) + granulado(p["barba"], rng)
    clay = iluminar(cor, h, masc, tex)
    rgba = np.dstack([clay, (masc * 255).astype(np.uint8)])
    cv2.imwrite(str(SAIDA / "base.png"), rgba)
    cv2.imwrite(str(SAIDA / "mascara.png"), (masc * 255).astype(np.uint8))
    meta = {"escala": ESC, "olhos": [[x * ESC, y * ESC] for x, y in OLHOS], "boca": [BOCA[0] * ESC, BOCA[1] * ESC],
            "queixo_y": QUEIXO_Y * ESC, "tamanho": [img.shape[1], img.shape[0]]}
    (SAIDA / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    fundo = np.full_like(clay, (150, 190, 215))
    a = masc[..., None]
    prev = (clay * a + fundo * (1 - a)).astype(np.uint8)
    cv2.imwrite(str(SAIDA / "previa.png"), cv2.resize(prev, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA))
    print("ok", img.shape)


if __name__ == "__main__":
    main()
