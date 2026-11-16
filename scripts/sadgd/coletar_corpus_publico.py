"""SAD-040 — Coleta do corpus público (ADR-002) a partir de fontes oficiais listadas em corpus_publico_fontes.csv.

Cada arquivo só é aceito se a página baixada contiver o identificador esperado do ato (coluna `validacao`).
Gera corpus/publico/<esfera>/<especie>/<arquivo> e corpus/MANIFESTO.csv (origem, data de coleta, SHA-256, licença).
Atos oficiais não têm proteção autoral (Lei 9.610/1998, art. 8º, IV).

Uso: python scripts/sadgd/coletar_corpus_publico.py [--forcar]
"""
import argparse
import csv
import hashlib
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTES = Path(__file__).with_name("corpus_publico_fontes.csv")
DESTINO = RAIZ / "corpus" / "publico"
MANIFESTO = RAIZ / "corpus" / "MANIFESTO.csv"
LICENCA = "Ato oficial — sem proteção autoral (Lei 9.610/1998, art. 8º, IV)"
CABECALHO = ["arquivo", "corpus_origem", "url", "especie", "numero", "ano", "esfera", "tema", "coletado_em",
             "sha256", "bytes", "licenca"]
AGENTE = "SAD-GD-corpus-academico/1.0 (projeto academico; coleta pontual de atos oficiais)"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def decodificar(dados: bytes) -> str:
    for codificacao in ("utf-8", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin-1", "replace")


def baixar(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("somente https")
    requisicao = urllib.request.Request(url, headers={"User-Agent": AGENTE})  # noqa: S310 - https verificado acima
    try:
        with urllib.request.urlopen(requisicao, timeout=60) as resposta:  # noqa: S310 - URLs da lista curada (https)
            return resposta.read()
    except (ConnectionResetError, urllib.error.URLError) as exc:
        if not isinstance(getattr(exc, "reason", exc), ConnectionResetError) or sys.platform != "win32":
            raise
        # O portal recusa a conexão TLS do Python, mas aceita o cliente HTTP do Windows (verificado em 2026-11-16).
        return _baixar_windows(url)


def _baixar_windows(url: str) -> bytes:
    import subprocess
    import tempfile

    temporario = RAIZ / "data" / "cache" / "coleta"
    temporario.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=temporario, suffix=".htm", delete=False) as tmp:
        caminho = Path(tmp.name)
    try:
        comando = ("$ProgressPreference='SilentlyContinue'; "
                   # agente padrão do PowerShell: o portal recusa identificadores desconhecidos
                   f"Invoke-WebRequest -Uri '{url}' -OutFile '{caminho}' -UseBasicParsing -TimeoutSec 90")
        subprocess.run(["powershell", "-NoProfile", "-Command", comando],  # noqa: S603, S607
                       check=True, capture_output=True, timeout=120)
        return caminho.read_bytes()
    finally:
        caminho.unlink(missing_ok=True)


def main(forcar=False):
    linhas_manifesto = []
    if MANIFESTO.exists():
        with MANIFESTO.open(encoding="utf-8", newline="") as f:
            linhas_manifesto = [r for r in csv.DictReader(f) if r["corpus_origem"] != "publico"]

    aceitos, falhas = [], []
    with FONTES.open(encoding="utf-8", newline="") as f:
        fontes = [r for r in csv.DictReader(f) if r["url"].strip()]
    for fonte in fontes:
        destino = DESTINO / fonte["esfera"] / fonte["especie"] / fonte["arquivo"]
        try:
            if destino.exists() and not forcar:
                dados = destino.read_bytes()
            else:
                if not fonte["url"].startswith("https://"):
                    raise ValueError("somente https")
                dados = baixar(fonte["url"])
                time.sleep(1.0)  # cortesia com o servidor oficial
            texto = normalizar(decodificar(dados))
            esperado = normalizar(fonte["validacao"])
            if esperado not in texto:
                raise ValueError(f"identificador '{fonte['validacao']}' ausente no conteúdo")
            if len(dados) < 2000:
                raise ValueError("conteúdo muito curto")
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(dados)
            aceitos.append({
                "arquivo": destino.relative_to(RAIZ / "corpus").as_posix(), "corpus_origem": "publico",
                "url": fonte["url"], "especie": fonte["especie"], "numero": fonte["numero"], "ano": fonte["ano"],
                "esfera": fonte["esfera"], "tema": fonte["tema"],
                "coletado_em": datetime.now().isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados), "licenca": LICENCA,
            })
            print(f"[OK] {fonte['arquivo']} ({len(dados) // 1024} KB)")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, subprocess.SubprocessError) as exc:
            falhas.append((fonte["arquivo"], fonte["url"], str(exc)))
            print(f"[FALHA] {fonte['arquivo']}: {exc}")

    MANIFESTO.parent.mkdir(parents=True, exist_ok=True)
    with MANIFESTO.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CABECALHO)
        escritor.writeheader()
        for linha in sorted(linhas_manifesto + aceitos, key=lambda r: r["arquivo"]):
            escritor.writerow({k: linha.get(k, "") for k in CABECALHO})

    relatorio = RAIZ / "corpus" / "coleta_publico_falhas.csv"
    with relatorio.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["arquivo", "url", "motivo"])
        escritor.writerows(falhas)
    print(f"\nAceitos: {len(aceitos)} | Falhas: {len(falhas)} (ver {relatorio.relative_to(RAIZ)})")
    return 0 if aceitos else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forcar", action="store_true", help="baixa novamente mesmo se o arquivo existir")
    sys.exit(main(parser.parse_args().forcar))
