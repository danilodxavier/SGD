"""Orquestrador multiagentes em LangGraph (ADR-003, RF-15 a RF-18).

  START → rotear → recuperar ─┬─ F1_simples / F1_complexa → responder_f1 (conflitos do grafo + verificador) → END
                              └─ F2 → contexto_f2 (linha do tempo + precedentes da memória de decisões)
                                    → [especialista × N, em paralelo via Send]
                                    → relator (6 elementos de RF-20; verificado) → END

Somente os especialistas escolhidos pelo roteador são acionados (nunca todos). Cada nó gera um span (TracerPort).
"""
import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.application.agentes.especialistas import executar_especialista, relatar_f2
from app.application.agentes.roteador import rotear


class Estado(TypedDict, total=False):
    pergunta: str
    decisao: Any
    trechos: list
    contexto_extra: str
    precedentes: list
    agente: str
    pareceres: Annotated[list, operator.add]
    resposta: Any
    tempos: Annotated[list, operator.add]


class Orquestrador:
    def __init__(self, recuperar, responder_f1, llm_especialistas, *, linha_do_tempo=None, precedentes=None,
                 tracer=None, checkpointer=None, k=8, llm_relator=None):
        """recuperar(pergunta, k) -> list[TrechoRecuperado]; responder_f1: ResponderF1;
        linha_do_tempo(documento_ids) -> str (resumo para F2);
        precedentes(pergunta, documento_ids) -> list[Precedente] (memória de decisões, RF-19);
        llm_relator: modelo do relator, se diferente do dos especialistas (Fase 10: especialistas menores)."""
        self._recuperar, self._f1, self._llm = recuperar, responder_f1, llm_especialistas
        self._llm_relator = llm_relator or llm_especialistas
        self._tl, self._prec, self._tracer, self._k = linha_do_tempo, precedentes, tracer, k
        g = StateGraph(Estado)
        g.add_node("rotear", self._no(self._rotear))
        g.add_node("recuperar", self._no(self._recuperar_no))
        g.add_node("responder_f1", self._no(self._responder_f1))
        g.add_node("contexto_f2", self._no(self._contexto_f2))
        g.add_node("especialista", self._no(self._especialista))
        g.add_node("relator", self._no(self._relator))
        g.add_edge(START, "rotear")
        g.add_edge("rotear", "recuperar")
        g.add_conditional_edges("recuperar", lambda s: "contexto_f2" if s["decisao"].rota == "F2" else "responder_f1",
                                ["contexto_f2", "responder_f1"])
        g.add_edge("responder_f1", END)
        g.add_conditional_edges("contexto_f2", self._distribuir, ["especialista", "relator"])
        g.add_edge("especialista", "relator")
        g.add_edge("relator", END)
        self.grafo = g.compile(checkpointer=checkpointer)

    def _no(self, funcao):
        nome = funcao.__name__.strip("_").replace("_no", "")

        def executar(estado):
            inicio = time.perf_counter()
            if self._tracer is None:
                saida = funcao(estado)
            else:
                with self._tracer.span(nome) as span:
                    saida = funcao(estado)
                    span.atributos["agente"] = estado.get("agente")
            return {**saida, "tempos": [(nome if nome != "especialista" else f"especialista:{estado.get('agente')}",
                                         int((time.perf_counter() - inicio) * 1000))]}
        executar.__name__ = nome
        return executar

    def _rotear(self, s):
        return {"decisao": rotear(s["pergunta"])}

    def _recuperar_no(self, s):
        return {"trechos": self._recuperar(s["pergunta"], self._k)}

    def _responder_f1(self, s):
        return {"resposta": self._f1.responder(s["pergunta"], s["trechos"][:6])}

    def _contexto_f2(self, s):
        documentos = {t.documento_id for t in s["trechos"]}
        resumo = self._tl(documentos) if self._tl else ""
        precedentes = self._prec(s["pergunta"], documentos) if self._prec else []
        if precedentes:
            resumo += ("\n\nPRECEDENTES DA GESTÃO (decisões anteriores semelhantes; informam, não vinculam):\n"
                       + "\n\n".join(p.como_contexto() for p in precedentes))
        return {"contexto_extra": resumo.strip(), "precedentes": precedentes}

    def _distribuir(self, s):
        agentes = s["decisao"].agentes
        if not agentes:
            return "relator"
        return [Send("especialista", {**s, "agente": a}) for a in agentes]

    def _especialista(self, s):
        return {"pareceres": [executar_especialista(self._llm, s["agente"], s["pergunta"], s["trechos"],
                                                    s.get("contexto_extra", ""))]}

    def _relator(self, s):
        return {"resposta": relatar_f2(self._llm_relator, s["pergunta"], s["trechos"], s.get("pareceres", []),
                                       s.get("contexto_extra", ""), s.get("precedentes", []))}

    def executar(self, pergunta, thread_id=None):
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        return self.grafo.invoke({"pergunta": pergunta, "pareceres": [], "tempos": []}, config=config)
