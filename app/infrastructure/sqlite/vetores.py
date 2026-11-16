"""VectorStorePort sobre sqlite-vec (ADR-006): busca exata por distância cosseno na tabela trechos_vec."""
import struct

from app.application.portas import ResultadoBusca

DIMENSAO = 1024


def serializar(vetor):
    if len(vetor) != DIMENSAO:
        raise ValueError(f"Vetor com {len(vetor)} dimensões; esperado {DIMENSAO}.")
    return struct.pack(f"{DIMENSAO}f", *map(float, vetor))


class SqliteVecStore:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def inserir(self, itens):
        conn = self._conexao()
        try:
            conn.executemany("DELETE FROM trechos_vec WHERE trecho_id = ?", [(tid,) for tid, _ in itens])
            conn.executemany("INSERT INTO trechos_vec (trecho_id, embedding) VALUES (?, ?)",
                             [(tid, serializar(v)) for tid, v in itens])
            conn.commit()
        finally:
            conn.close()

    def remover(self, trecho_ids):
        conn = self._conexao()
        try:
            conn.executemany("DELETE FROM trechos_vec WHERE trecho_id = ?", [(t,) for t in trecho_ids])
            conn.commit()
        finally:
            conn.close()

    def buscar(self, vetor, k, filtro_trechos=None):
        conn = self._conexao()
        try:
            pedir = k if not filtro_trechos else min(max(k * 10, 50), 4096)
            linhas = conn.execute(
                "SELECT trecho_id, distance FROM trechos_vec WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                (serializar(vetor), pedir)).fetchall()
        finally:
            conn.close()
        if filtro_trechos is not None:
            permitidos = set(filtro_trechos)
            linhas = [r for r in linhas if r[0] in permitidos]
        return [ResultadoBusca(r[0], round(1.0 - r[1], 6), "denso") for r in linhas[:k]]
