"""Captura as telas do SAD-GD para o vídeo e o guia em PDF — somente com o corpus ACADÊMICO.

Sobe uma instância de demonstração isolada (127.0.0.1, porta própria) com uma cópia do banco acadêmico
(`data/database/sadgd_academico.db`) e o acervo `corpus/`; nenhum dado real aparece nas telas. Navega com o
Microsoft Edge do sistema (Playwright, `channel="msedge"`) em 1600×900 com escala 1,2 → PNG 1920×1080.

Uso (na raiz do projeto, em etapas curtas por causa da RAM):
    .venv\\Scripts\\python.exe scripts\\video\\capturar_telas.py --etapa basicas
    .venv\\Scripts\\python.exe scripts\\video\\capturar_telas.py --etapa f1
    .venv\\Scripts\\python.exe scripts\\video\\capturar_telas.py --etapa voz
    .venv\\Scripts\\python.exe scripts\\video\\capturar_telas.py --etapa f2

Saídas: data/video/telas/*.png (fora do Git). A senha do usuário de demonstração é gerada e gravada em
data/video/trabalho/demo_credenciais.txt (fora do Git).
"""
from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
TRAB = RAIZ / "data" / "video" / "trabalho"
TELAS = RAIZ / "data" / "video" / "telas"
PORTA = 8011
URL = f"http://127.0.0.1:{PORTA}"
PY = str(RAIZ / ".venv" / "Scripts" / "python.exe")


def ambiente() -> dict:
    env = dict(os.environ)
    env.update({
        "DATABASE_PATH": str(TRAB / "demo.db"),
        "DATA_DIR": str(TRAB / "dados"),
        "APP_HOST": "127.0.0.1",
        "APP_PORT": str(PORTA),
        "ALLOWED_HOSTS": "127.0.0.1,localhost",
        "DOCUMENTS_ROOT": str(RAIZ / "corpus"),
        "AUTO_INDEX": "false",
        "AI_ALLOW_REMOTE": "false",
        "SADGD_LLM_F2": "local",
        "SSL_CERTFILE": "",
        "SSL_KEYFILE": "",
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def preparar(recriar: bool) -> tuple[str, str]:
    TRAB.mkdir(parents=True, exist_ok=True)
    TELAS.mkdir(parents=True, exist_ok=True)
    (TRAB / "dados" / "logs").mkdir(parents=True, exist_ok=True)
    banco = TRAB / "demo.db"
    if recriar or not banco.exists():
        shutil.copy2(RAIZ / "data" / "database" / "sadgd_academico.db", banco)
    cred = TRAB / "demo_credenciais.txt"
    if cred.exists() and not recriar:
        usuario, senha = cred.read_text(encoding="utf-8").split()[:2]
    else:
        usuario, senha = "gestor.demo", "Demo-" + secrets.token_urlsafe(10)
        cred.write_text(f"{usuario} {senha}\n", encoding="utf-8")
    codigo = (
        "from app.core import auth\n"
        f"u = auth.get_user_by_username({usuario!r})\n"
        f"if u is None: auth.create_user({usuario!r}, 'Gestor da SEMA (demonstração)', 'admin', {senha!r}, "
        "must_change_password=False)\n")
    subprocess.run([PY, "-c", codigo], cwd=RAIZ, env=ambiente(), check=True)
    return usuario, senha


def subir_servidor() -> subprocess.Popen:
    log = open(TRAB / "servidor_demo.log", "ab")
    proc = subprocess.Popen([PY, "-m", "app", "--sem-navegador"], cwd=RAIZ, env=ambiente(), stdout=log,
                            stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            with urllib.request.urlopen(URL + "/health", timeout=2) as r:
                if r.status == 200:
                    return proc
        except Exception:
            time.sleep(1)
    proc.kill()
    raise SystemExit("servidor de demonstração não respondeu")


def salvar(page, nome: str, pagina_inteira: bool = False) -> None:
    page.wait_for_timeout(500)
    page.screenshot(path=str(TELAS / f"{nome}.png"), full_page=pagina_inteira)
    print("tela:", nome, flush=True)


def entrar(page, usuario: str, senha: str, capturar: bool = False) -> None:
    page.goto(URL)
    page.wait_for_selector("#login-form:not(.hidden)")
    if capturar:
        salvar(page, "00_login")
    page.fill("#login-username", usuario)
    page.fill("#login-password", senha)
    page.click("#login-form button[type=submit]")
    page.wait_for_selector("#menu")
    page.wait_for_timeout(1500)


def ir(page, view: str) -> None:
    page.click(f'.nav-item[data-view="{view}"]')
    page.wait_for_timeout(1200)


def perguntar(page, texto: str, limite_s: int) -> float:
    page.goto(URL)
    page.wait_for_selector("#menu")
    page.wait_for_timeout(800)
    ir(page, "perguntar")
    page.fill("#sg-pergunta", texto)
    t = time.time()
    page.click("#sg-enviar")
    page.wait_for_selector("#sg-resultado .panel.answer", timeout=limite_s * 1000)
    page.wait_for_timeout(800)
    return time.time() - t


def rolar_ate(page, seletor: str, ajuste: int = -90) -> None:
    page.evaluate("""([s, a]) => { const e = document.querySelector(s); if (!e) return;
        const y = e.getBoundingClientRect().top + window.scrollY + a;
        const c = document.querySelector('.content') || document.scrollingElement;
        window.scrollTo(0, y); if (c && c.scrollTo) c.scrollTo(0, y); }""", [seletor, ajuste])
    page.wait_for_timeout(600)


def etapa_basicas(page, usuario, senha) -> None:
    entrar(page, usuario, senha, capturar=True)
    salvar(page, "01_painel")
    ir(page, "perguntar")
    salvar(page, "02_perguntar_vazio")
    ir(page, "acervo")
    salvar(page, "10_acervo")
    page.select_option("#ac-tipo", index=1)
    page.wait_for_timeout(1000)
    salvar(page, "11_acervo_filtro")
    page.select_option("#ac-tipo", index=0)
    ir(page, "linha")
    opcoes = page.eval_on_selector_all("#tl-processo option", "os => os.map(o => [o.value, o.textContent])")
    alvo = next((v for v, t in opcoes if "031/2023" in t), None) or next((v for v, t in opcoes if "012/2023" in t), None) \
        or (opcoes[1][0] if len(opcoes) > 1 else None)
    if alvo:
        page.select_option("#tl-processo", alvo)
        page.wait_for_timeout(2500)
    salvar(page, "20_linha_do_tempo")
    salvar(page, "21_linha_do_tempo_inteira", pagina_inteira=True)
    ir(page, "decisoes")
    salvar(page, "30_decisoes")
    page.fill("#dc-pergunta", "prorrogação de contrato de vigilância com advertências")
    page.click("#dc-busca button[type=submit]")
    page.wait_for_selector("#dc-precedentes .loading", state="detached", timeout=180000)
    page.wait_for_timeout(800)
    salvar(page, "31_precedentes")
    ir(page, "usuarios")
    salvar(page, "40_usuarios")
    ir(page, "configuracoes")
    salvar(page, "41_configuracoes")
    page.goto(URL + "/static/acessibilidade.html")
    page.wait_for_timeout(1000)
    salvar(page, "42_acessibilidade")


def etapa_f1(page, usuario, senha) -> None:
    entrar(page, usuario, senha)
    s = perguntar(page, "Qual o valor global do Contrato nº 044/2023?", 240)
    print(f"F1 ficha: {s:.1f}s", flush=True)
    salvar(page, "03_f1_resposta")
    botao = page.locator("#sg-resultado button[data-trecho]").first
    if botao.count():
        botao.click()
        page.wait_for_timeout(1500)
        salvar(page, "04_f1_trecho")
        page.keyboard.press("Escape")
    for nome, q in (("05_f1_vigencia", "O Decreto nº 7.892/2013 ainda está em vigor?"),
                    ("05b_f1_prazo", "Quando termina a vigência do Contrato nº 012/2023?"),
                    ("05c_f1_sequencia", "Qual a sequência de eventos do Contrato nº 031/2023?"),
                    ("06_f1_sem_evidencia", "Qual o nome do cachorro do prefeito de Cuiabá?")):
        s = perguntar(page, q, 300)
        print(f"{nome}: {s:.1f}s", flush=True)
        rolar_ate(page, "#sg-resultado", -120)
        salvar(page, nome)


def etapa_voz(navegador_fn, usuario, senha) -> None:
    wav = TRAB / "pergunta_voz.wav"
    if not wav.exists():
        import win32com.client as w
        voz = w.Dispatch("SAPI.SpVoice")
        cat = w.Dispatch("SAPI.SpObjectTokenCategory")
        cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", False)
        toks = cat.EnumerateTokens()
        voz.Voice = next(toks.Item(i) for i in range(toks.Count) if "Daniel" in toks.Item(i).GetDescription())
        fs, fmt = w.Dispatch("SAPI.SpFileStream"), w.Dispatch("SAPI.SpAudioFormat")
        fmt.Type = 22  # 16 kHz 16 bits mono
        fs.Format = fmt
        fs.Open(str(wav), 3)
        voz.AudioOutputStream = fs
        voz.Speak("<silence msec='1500'/>", 8)
        voz.Speak("Quando termina a vigência do contrato doze barra dois mil e vinte e três?")
        voz.Speak("<silence msec='2500'/>", 8)
        fs.Close()
    nav, ctx = navegador_fn([f"--use-file-for-fake-audio-capture={wav}", "--use-fake-device-for-media-stream",
                             "--use-fake-ui-for-media-stream"])
    ctx.grant_permissions(["microphone"], origin=URL)
    page = ctx.new_page()
    entrar(page, usuario, senha)
    ir(page, "perguntar")
    page.click("#sg-voz")
    page.wait_for_timeout(2500)
    salvar(page, "07_voz_gravando")
    page.wait_for_timeout(4000)
    page.click("#sg-voz")
    page.wait_for_function("document.querySelector('#sg-pergunta').value.length > 10", timeout=90000)
    page.wait_for_timeout(800)
    print("transcrito:", page.input_value("#sg-pergunta"), flush=True)
    salvar(page, "08_voz_transcrita")
    page.click("#sg-enviar")
    page.wait_for_selector("#sg-resultado .panel.answer", timeout=240000)
    page.wait_for_timeout(800)
    salvar(page, "09_voz_resposta")
    # Acesso pelo celular (mesma aplicação web, layout responsivo).
    cel = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2.5, is_mobile=True,
                          has_touch=True)
    p2 = cel.new_page()
    entrar(p2, usuario, senha)
    p2.screenshot(path=str(TELAS / "50_celular_painel.png"))
    try:
        p2.click("#menu-toggle, .menu-toggle, button[aria-controls=menu]", timeout=2000)
        p2.wait_for_timeout(600)
        p2.click('.nav-item[data-view="perguntar"]', timeout=3000)
    except Exception:
        p2.evaluate("document.querySelector('.nav-item[data-view=perguntar]').click()")
    p2.wait_for_timeout(1000)
    p2.fill("#sg-pergunta", "Quando termina a vigência do Contrato nº 012/2023?")
    p2.click("#sg-enviar")
    p2.wait_for_selector("#sg-resultado .panel.answer", timeout=240000)
    p2.wait_for_timeout(800)
    p2.screenshot(path=str(TELAS / "51_celular_resposta.png"))
    print("tela: celular", flush=True)


def etapa_f2(page, usuario, senha) -> None:
    entrar(page, usuario, senha)
    s = perguntar(page, "Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?", 540)
    print(f"F2: {s:.1f}s", flush=True)
    salvar(page, "12_f2_topo")
    salvar(page, "13_f2_inteira", pagina_inteira=True)
    for nome, sel in (("14_f2_elementos", ".sg-elementos"), ("15_f2_riscos", "#sg-resultado .section-title"),
                      ("16_f2_pareceres", ".sg-parecer")):
        if page.locator(sel).count():
            rolar_ate(page, sel)
            salvar(page, nome)
    abre = page.locator(".sg-parecer summary").first
    if abre.count():
        abre.click()
        page.wait_for_timeout(800)
        rolar_ate(page, ".sg-parecer")
        salvar(page, "17_f2_parecer_aberto")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", required=True, choices=["basicas", "f1", "voz", "f2"])
    ap.add_argument("--recriar", action="store_true", help="copia de novo o banco acadêmico e recria o usuário")
    args = ap.parse_args()
    usuario, senha = preparar(args.recriar)
    proc = subir_servidor()
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            abertos = []

            def navegador(extras=()):
                nav = pw.chromium.launch(channel="msedge", headless=True, args=list(extras))
                ctx = nav.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1.2,
                                      locale="pt-BR")
                abertos.append(nav)
                return nav, ctx

            if args.etapa == "voz":
                etapa_voz(navegador, usuario, senha)
            else:
                _, ctx = navegador()
                page = ctx.new_page()
                {"basicas": etapa_basicas, "f1": etapa_f1, "f2": etapa_f2}[args.etapa](page, usuario, senha)
            for n in abertos:
                n.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
