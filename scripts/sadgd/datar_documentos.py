"""Completa a data dos documentos já indexados que ficaram sem data (regras de `data_complementar`, Fase 12 §14).

Lê o texto dos trechos de cada documento sem data, aplica a cascata de datas e grava `data_documento`. Não
reindexa nada nem altera originais. Imprime só contagens. Depois, rode `gerar_fichas.py` (o inventário das fichas
é atualizado com as novas datas, sem LLM) e `construir_grafo.py` (linha do tempo).

Uso: python scripts/sadgd/datar_documentos.py [--simular]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--simular", action="store_true", help="só conta, sem gravar")
    a = p.parse_args()

    from app.application.ingestao.metadados import data_complementar
    from app.core.config import settings
    from app.infrastructure.sqlite.conexao import conectar

    conn = conectar(settings.database_path, vetores=False)
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM documentos WHERE data_documento IS NULL OR data_documento = ''")]
        anos, novas = Counter(), []
        for did in ids:
            texto = "\n".join(r[0] for r in conn.execute(
                "SELECT texto FROM trechos WHERE documento_id = ? ORDER BY ordem", (did,)))
            if d := data_complementar(texto):
                novas.append((d.isoformat(), did))
                anos[d.year] += 1
        if not a.simular:
            conn.executemany("UPDATE documentos SET data_documento = ? WHERE id = ?", novas)
            conn.commit()
    finally:
        conn.close()
    print(f"[{'SIMULAÇÃO' if a.simular else 'OK'}] sem data: {len(ids)}; datados agora: {len(novas)}; "
          f"continuam sem data: {len(ids) - len(novas)}")
    print("  por ano: " + ", ".join(f"{k}={v}" for k, v in sorted(anos.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
