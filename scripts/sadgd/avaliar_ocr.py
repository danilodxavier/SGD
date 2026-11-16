"""SAD-042 — Avaliação de OCR (RF-02): CER (taxa de erro por caractere) do Windows OCR e do Tesseract nos PDFs
digitalizados do corpus sintético, contra o texto de referência do gabarito. Meta: CER <= 10%.

Uso: python scripts/sadgd/avaliar_ocr.py [--saida avaliacao/execucoes/ocr.json]
"""
import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.core.config import settings  # noqa: E402
from app.ingestion import extractor, ocr  # noqa: E402


def normalizar(texto):
    texto = unicodedata.normalize("NFC", texto)
    return " ".join(texto.split())


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def main(saida=None):
    settings.ocr_enabled = True
    gabarito = json.loads((RAIZ / "corpus/sintetico/GABARITO.json").read_text(encoding="utf-8"))
    digitalizados = [d for d in gabarito["documentos"] if d["formato"] == "pdf_digitalizado"]
    resultado = {"documentos": len(digitalizados), "motores": {}}
    for nome, motor in ocr.ENGINES.items():
        disponivel, mensagem = motor.available(refresh=True)
        if not disponivel:
            resultado["motores"][nome] = {"disponivel": False, "mensagem": mensagem}
            continue
        erros = total = 0
        por_doc, inicio = [], time.perf_counter()
        for d in digitalizados:
            r = extractor.extract(RAIZ / "corpus" / d["arquivo"], ocr_engine=motor)
            ref, hip = normalizar(d["texto_referencia"]), normalizar(r.full_text)
            dist = levenshtein(ref, hip)
            erros, total = erros + dist, total + len(ref)
            por_doc.append({"id": d["id"], "status": r.status, "cer": round(dist / max(len(ref), 1), 4)})
        resultado["motores"][nome] = {"disponivel": True, "rotulo": motor.label,
                                      "cer_global": round(erros / max(total, 1), 4),
                                      "segundos": round(time.perf_counter() - inicio, 1), "por_documento": por_doc}
    validos = {k: v for k, v in resultado["motores"].items() if v.get("disponivel")}
    resultado["melhor"] = min(validos, key=lambda k: validos[k]["cer_global"]) if validos else None
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if saida:
        Path(saida).parent.mkdir(parents=True, exist_ok=True)
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida")
    main(parser.parse_args().saida)
