"""Tracer padrão: grava cada etapa (nó do grafo, chamada de modelo) na tabela `spans` (ADR-009).

É a fonte de verdade para latência p50/p95 e tokens por consulta; o Phoenix é apenas visualização opcional.
"""
import json
import time
from contextlib import contextmanager
from datetime import datetime

from app.application.portas import Span


class SqliteTracer:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    @contextmanager
    def span(self, no, *, consulta_id=None, modelo=None):
        registro = Span(no=no, consulta_id=consulta_id, modelo=modelo)
        inicio_iso = datetime.now().isoformat(timespec="milliseconds")
        inicio = time.perf_counter()
        erro = None
        try:
            yield registro
        except Exception as exc:
            erro = type(exc).__name__
            raise
        finally:
            latencia = int((time.perf_counter() - inicio) * 1000)
            conn = self._conexao()
            try:
                conn.execute(
                    "INSERT INTO spans (consulta_id, no, modelo, tokens_entrada, tokens_saida, latencia_ms, erro, "
                    "atributos, inicio) VALUES (?,?,?,?,?,?,?,?,?)",
                    (registro.consulta_id, registro.no, registro.modelo, registro.tokens_entrada,
                     registro.tokens_saida, latencia, erro,
                     json.dumps(registro.atributos, ensure_ascii=False) if registro.atributos else None, inicio_iso),
                )
                conn.commit()
            finally:
                conn.close()


def percentis_latencia(conn, no=None, percentis=(50, 95)):
    """Latência por percentil (método nearest-rank) a partir da tabela spans."""
    sql, params = "SELECT latencia_ms FROM spans", ()
    if no:
        sql, params = sql + " WHERE no = ?", (no,)
    valores = sorted(r[0] for r in conn.execute(sql, params))
    if not valores:
        return {p: None for p in percentis}
    resultado = {}
    for p in percentis:
        indice = max(0, -(-p * len(valores) // 100) - 1)  # ceil(p*n/100) - 1
        resultado[p] = valores[indice]
    return resultado
