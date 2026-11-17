"""SAD-074 — Avaliação da anonimização (RF-25): recall de nomes de pessoas físicas, CPF e e-mail no corpus sintético
(os nomes fictícios do gerador são o gabarito) e amostra do que foi mascarado como pessoa no corpus público
(para revisão manual de falsos positivos).

Uso: python scripts/sadgd/avaliar_anonimizacao.py [--saida avaliacao/execucoes/fase7_anonimizacao.json]
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.anonimizacao import _nomes, anonimizar  # noqa: E402
from app.core.config import settings  # noqa: E402

PESSOAS_FICTICIAS = ["Henrique Bastos Lacerda", "Marina Duarte Falcão", "Rogério Antunes Siqueira",
                     "Paulo Henrique Veloso", "Luciana Prado Monteiro", "Tatiana Rezende Coutinho",
                     "Cláudia Ferraz Nogueira", "Beatriz Almeida Toledo", "Renata Lobo Sampaio",
                     "Joaquim Pereira Lins", "Ana Clara Moura Teles"]


def main(saida=None):
    conn = sqlite3.connect(settings.database_path)
    sint = [r[0] for r in conn.execute("SELECT t.texto FROM trechos t JOIN documentos d ON d.id = t.documento_id "
                                       "WHERE d.corpus_origem = 'sintetico'")]
    publ = [r[0] for r in conn.execute("SELECT t.texto FROM trechos t JOIN documentos d ON d.id = t.documento_id "
                                       "WHERE d.corpus_origem = 'publico'")]
    conn.close()
    total = ocultos = 0
    falhas = Counter()
    cpf_total = cpf_ok = email_total = email_ok = 0
    for texto in sint:
        anon, _ = anonimizar(texto)
        for nome in PESSOAS_FICTICIAS:
            n = texto.count(nome)
            total += n
            ocultos += n - anon.count(nome)
            if anon.count(nome):
                falhas[nome] += anon.count(nome)
        for cpf in re.findall(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto):
            cpf_total += 1
            cpf_ok += cpf not in anon
        for email in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", texto):
            email_total += 1
            email_ok += email not in anon
    mascarados_publicos = Counter()
    for texto in publ:
        for a, b in _nomes(texto):
            mascarados_publicos[texto[a:b]] += 1
    resultado = {
        "recall_nomes": round(ocultos / total, 4) if total else None, "ocorrencias_nomes": total,
        "nomes_nao_mascarados": dict(falhas),
        "recall_cpf": round(cpf_ok / cpf_total, 4) if cpf_total else None, "cpf": cpf_total,
        "recall_email": round(email_ok / email_total, 4) if email_total else None, "emails": email_total,
        "publico_mascarados_como_pessoa": mascarados_publicos.most_common(40),
    }
    print(json.dumps({k: v for k, v in resultado.items() if k != "publico_mascarados_como_pessoa"},
                     ensure_ascii=False, indent=2))
    print("Público — mascarados como pessoa (top 40):")
    for nome, n in resultado["publico_mascarados_como_pessoa"]:
        print(f"  {n:3}  {nome}")
    if saida:
        Path(saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida")
    main(ap.parse_args().saida)
