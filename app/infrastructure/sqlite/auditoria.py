"""Auditoria de consultas (SAD-075, RF-24) e tracer vinculado à consulta (ADR-009).

A pergunta é guardada apenas como hash SHA-256 (LGPD); registram-se rota, agentes, classificação, confiança,
tokens, latência, fontes citadas (aprovadas pelo verificador) e pareceres com validade do schema."""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime

from app.core.config import settings


class AuditoriaSqlite:
    def __init__(self, conexao_factory):
        self._conexao = conexao_factory

    def iniciar(self, usuario_id, pergunta, ip=None) -> int:
        conn = self._conexao()
        try:
            agora = datetime.now().isoformat(timespec="seconds")
            cid = conn.execute("INSERT INTO consultas (usuario_id, pergunta_hash, versao_sistema, criado_em) "
                               "VALUES (?, ?, ?, ?)", (usuario_id, hashlib.sha256(pergunta.encode()).hexdigest(),
                                                       settings.versao_sistema, agora)).lastrowid
            conn.execute("INSERT INTO auditoria (usuario_id, acao, alvo, ip, criado_em) "
                         "VALUES (?, 'consulta', ?, ?, ?)",
                         (usuario_id, f"consulta:{cid}", ip, agora))
            conn.commit()
            return cid
        finally:
            conn.close()

    def concluir(self, consulta_id, estado, latencia_ms):
        decisao, resposta = estado.get("decisao"), estado.get("resposta")
        pareceres = estado.get("pareceres") or []
        tokens_in = getattr(resposta, "tokens_entrada", 0) + sum(p.tokens_entrada for p in pareceres)
        tokens_out = getattr(resposta, "tokens_saida", 0) + sum(p.tokens_saida for p in pareceres)
        classificacao = getattr(resposta, "classificacao", None) or (getattr(resposta, "dados", {}) or {}).get(
            "classificacao")
        confianca = getattr(resposta, "confianca", None)
        if confianca is None:
            confianca = (getattr(resposta, "dados", {}) or {}).get("confianca")
        conn = self._conexao()
        try:
            conn.execute("UPDATE consultas SET rota = ?, agentes = ?, classificacao = ?, confianca = ?, "
                         "tokens_entrada = ?, tokens_saida = ?, latencia_ms = ? WHERE id = ?",
                         (decisao.rota if decisao else None, json.dumps(decisao.agentes if decisao else []),
                          classificacao, confianca, tokens_in, tokens_out, latencia_ms, consulta_id))
            conn.executemany("INSERT INTO consulta_fontes (consulta_id, trecho_id, aprovada_verificador) "
                             "VALUES (?, ?, 1)", [(consulta_id, t.id) for t in getattr(resposta, "fontes", [])])
            conn.executemany("INSERT INTO pareceres (consulta_id, agente, versao_prompt, saida_json, valido) "
                             "VALUES (?, ?, 'v1', ?, ?)",
                             [(consulta_id, p.agente, json.dumps(p.dados, ensure_ascii=False), int(p.valido_reparado))
                              for p in pareceres])
            conn.commit()
        finally:
            conn.close()


def concluir_por_cache(fabrica, consulta_id, payload, latencia_ms):
    """Consulta respondida pelo cache semântico: sem tokens de LLM; rota e fontes vêm da resposta reaproveitada."""
    conn = fabrica()
    try:
        conn.execute("UPDATE consultas SET rota = ?, agentes = ?, classificacao = ?, confianca = ?, latencia_ms = ?, "
                     "cache_hit = 1 WHERE id = ?",
                     (payload.get("rota"), json.dumps(payload.get("agentes") or []),
                      payload.get("classificacao") or (payload.get("recomendacao") or {}).get("classificacao"),
                      payload.get("confianca"), latencia_ms, consulta_id))
        conn.executemany("INSERT INTO consulta_fontes (consulta_id, trecho_id, aprovada_verificador) VALUES (?, ?, 1)",
                         [(consulta_id, f["trecho_id"]) for f in payload.get("fontes", [])])
        conn.commit()
    finally:
        conn.close()


class TracerDaConsulta:
    """Liga os spans de um tracer (ex.: SqliteTracer) a uma consulta específica."""

    def __init__(self, tracer, consulta_id):
        self._tracer, self._consulta = tracer, consulta_id

    @contextmanager
    def span(self, no, *, consulta_id=None, modelo=None):
        with self._tracer.span(no, consulta_id=self._consulta, modelo=modelo) as s:
            yield s
