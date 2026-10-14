"""Verifica o contraste (WCAG 2.1) das combinações de cor usadas na interface.

Lê os tokens de frontend/css/tokens.css nos modos normal e alto contraste e confere cada par
texto/fundo declarado em PARES. Termina com código 1 se alguma combinação não atingir o mínimo.

    python scripts\\verificar_contraste.py            tabela no terminal
    python scripts\\verificar_contraste.py --markdown tabela em Markdown (para a documentação)
"""
import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[1] / "frontend" / "css" / "tokens.css"

# (uso na interface, token do texto/elemento, token do fundo, mínimo exigido)
# 4.5 = texto normal (WCAG 1.4.3) | 3.0 = texto grande e componentes de interface (WCAG 1.4.11)
PARES = [
    ("Texto padrão sobre a página", "--color-text", "--color-bg", 4.5),
    ("Texto padrão sobre cartões, tabelas e campos", "--color-text", "--color-surface", 4.5),
    ("Texto secundário sobre a página", "--color-text-muted", "--color-bg", 4.5),
    ("Texto secundário sobre cartões", "--color-text-muted", "--color-surface", 4.5),
    ("Texto secundário em cabeçalho de tabela", "--color-text-muted", "--color-surface-alt", 4.5),
    ("Links sobre cartões", "--color-link", "--color-surface", 4.5),
    ("Links sobre a página", "--color-link", "--color-bg", 4.5),
    ("Texto do botão primário", "--color-on-primary", "--color-primary", 4.5),
    ("Texto do botão primário (hover)", "--color-on-primary", "--color-primary-hover", 4.5),
    ("Botão secundário: texto azul sobre branco", "--color-primary", "--color-surface", 4.5),
    ("Item de menu ativo / destaque azul claro", "--color-primary", "--color-primary-light", 4.5),
    ("Cabeçalho institucional: nome do sistema e usuário", "--color-institutional-text", "--color-institutional-bg", 4.5),
    ("Cabeçalho institucional: subtítulo e perfil", "--color-text-muted", "--color-institutional-bg", 4.5),
    ("Menu lateral e rodapé: texto", "--color-header-text", "--color-header-bg", 4.5),
    ("Barra de acessibilidade: texto", "--color-header-text", "--color-header-bg-strong", 4.5),
    ("Mensagem de sucesso", "--color-success", "--color-success-bg", 4.5),
    ("Mensagem de alerta", "--color-warning", "--color-warning-bg", 4.5),
    ("Mensagem de erro", "--color-danger", "--color-danger-bg", 4.5),
    ("Erro de campo (texto vermelho sobre branco)", "--color-danger", "--color-surface", 4.5),
    ("Mensagem informativa", "--color-info", "--color-info-bg", 4.5),
    ("Etiqueta neutra", "--color-text", "--color-neutral-bg", 4.5),
    ("Painel de registros (logs)", "--color-code-text", "--color-code-bg", 4.5),
    ("Aviso flutuante (toast)", "--color-toast-text", "--color-toast-bg", 4.5),
    ("Ícone de situação: sucesso sobre cartão", "--color-success", "--color-surface", 3.0),
    ("Ícone de situação: alerta sobre cartão", "--color-warning", "--color-surface", 3.0),
    ("Ícone de situação: erro sobre cartão", "--color-danger", "--color-surface", 3.0),
    ("Contorno de campos e controles", "--color-border-strong", "--color-surface", 3.0),
    ("Contorno de campos sobre a página", "--color-border-strong", "--color-bg", 3.0),
    ("Indicador de foco sobre fundo claro", "--color-focus", "--color-surface", 3.0),
    ("Indicador de foco sobre a página", "--color-focus", "--color-bg", 3.0),
    ("Indicador de foco no cabeçalho institucional", "--color-focus", "--color-institutional-bg", 3.0),
    ("Indicador de foco no menu lateral e rodapé", "--color-focus-on-dark", "--color-header-bg", 3.0),
    ("Indicador de foco na barra de acessibilidade", "--color-focus-on-dark", "--color-header-bg-strong", 3.0),
]
# Observação: o foco é desenhado com afastamento (--focus-offset), de modo que o anel fica sobre o fundo
# da página/cartão e não sobre o próprio botão; por isso os pares de foco usam as cores de fundo.


def _blocks(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    normal = re.search(r":root\s*\{(.*?)\n\}", css, re.S).group(1)
    contrast = re.search(r':root\[data-contraste="alto"\]\s*\{(.*?)\n\}', css, re.S).group(1)
    parse = lambda block: dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block))  # noqa: E731
    return parse(normal), parse(contrast)


def _resolve(name, tokens, depth=0):
    value = tokens[name].strip()
    m = re.fullmatch(r"var\((--[\w-]+)\)", value)
    if m and depth < 10:
        return _resolve(m.group(1), tokens, depth + 1)
    return value


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def evaluate():
    normal, contrast = _blocks(TOKENS.read_text(encoding="utf-8"))
    modes = {"Normal": normal, "Alto contraste": {**normal, **contrast}}
    rows = []
    for mode, tokens in modes.items():
        for use, fg, bg, minimum in PARES:
            a, b = _resolve(fg, tokens), _resolve(bg, tokens)
            value = ratio(a, b)
            rows.append((mode, use, a, b, value, minimum, value >= minimum))
    return rows


def main():
    rows = evaluate()
    markdown = "--markdown" in sys.argv
    if markdown:
        print("| Modo | Uso | Texto/elemento | Fundo | Contraste | Mínimo | Resultado |")
        print("|---|---|---|---|---|---|---|")
    for mode, use, a, b, value, minimum, ok in rows:
        status = "✅ passa" if ok else "❌ FALHA"
        if markdown:
            print(f"| {mode} | {use} | `{a}` | `{b}` | {value:.2f}:1 | {minimum}:1 | {status} |")
        else:
            print(f"[{'OK' if ok else 'ERRO'}] {mode:<15} {value:5.2f}:1 (mín {minimum}) {use}  ({a} / {b})")
    failures = [r for r in rows if not r[6]]
    if not markdown:
        print(f"\nResultado: {len(rows) - len(failures)} de {len(rows)} combinações atendem ao mínimo.")
    return 1 if failures else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
