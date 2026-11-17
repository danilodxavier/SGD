"""LLMProtegido (ADR-002/004, RNF-08): aplica a política de envio externo antes de qualquer chamada remota.

Provedor local: passa direto. Provedor remoto: exige autorização no .env e corpus apenas acadêmico (público ou
sintético); anonimiza todas as mensagens e restaura os marcadores na resposta, localmente.
"""
from dataclasses import replace

from app.application.anonimizacao import anonimizar, restaurar, restaurar_objeto
from app.domain.politicas import exigir_envio_permitido


class LLMProtegido:
    def __init__(self, llm, *, permitido_na_config: bool, origens):
        self._llm, self._permitido, self._origens = llm, permitido_na_config, set(origens)
        self.nome, self.remoto = llm.nome, llm.remoto

    def chat(self, mensagens, **kwargs):
        if not self._llm.remoto:
            return self._llm.chat(mensagens, **kwargs)
        mapa = {}
        anonimizadas = [{**m, "content": anonimizar(m["content"], mapa)[0]} for m in mensagens]
        exigir_envio_permitido(remoto=True, permitido_na_config=self._permitido, origens=self._origens,
                               anonimizado=True)
        r = self._llm.chat(anonimizadas, **kwargs)
        return replace(r, texto=restaurar(r.texto, mapa), json=restaurar_objeto(r.json, mapa))
