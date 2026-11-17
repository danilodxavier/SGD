"""Fase 10 — Latência de uma consulta respondida pelo cache semântico (banco temporário; LLM substituído).

Mede o tempo do endpoint /api/sadgd/perguntar (auditoria + versão do acervo + busca no cache) quando a pergunta
já foi respondida. Uso: python scripts/sadgd/medir_cache.py [--repeticoes 30]
"""
import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def main(repeticoes):
    from app.application.agentes.roteador import rotear
    from app.application.respostas.f1 import RespostaF1
    from app.core import database
    from app.core.config import settings
    from app.interfaces.api import perguntar as api
    from tests.helpers import HEADERS, logged_client

    pasta = Path(tempfile.mkdtemp(dir=RAIZ / "data" / "cache"))
    settings.database_path, settings.data_dir = pasta / "cache.db", pasta / "data"
    database.init_db()

    class Instantaneo:
        def __init__(self, tracer):
            pass

        def executar(self, pergunta):
            return {"decisao": rotear(pergunta), "pareceres": [], "tempos": [],
                    "resposta": RespostaF1("Resposta.", "fato", 0.9, [], tokens_entrada=2400, tokens_saida=110)}

    api._componentes["fabrica_orquestrador"] = Instantaneo
    tempos = []
    with logged_client() as c:
        for n in range(repeticoes):
            pergunta = f"Qual o valor global do Contrato nº {n:03d}/2023?"
            c.post("/api/sadgd/perguntar", json={"pergunta": pergunta}, headers=HEADERS)
            r = c.post("/api/sadgd/perguntar", json={"pergunta": pergunta}, headers=HEADERS).json()
            assert r["cache"] is True
            tempos.append(r["latencia_ms"])
    resultado = {"repeticoes": repeticoes, "p50_ms": statistics.median(tempos),
                 "p95_ms": sorted(tempos)[int(0.95 * (len(tempos) - 1))], "max_ms": max(tempos)}
    print(json.dumps(resultado))
    (RAIZ / "avaliacao" / "execucoes" / "fase10_cache_latencia.json").write_text(json.dumps(resultado, indent=2),
                                                                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeticoes", type=int, default=30)
    sys.exit(main(ap.parse_args().repeticoes))
