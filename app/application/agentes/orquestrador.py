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
from app.application.agentes.politica_llm import LLMComReserva, LLMProtegido
from app.application.agentes.roteador import rotear
from app.domain.politicas import avaliar_envio_externo

MAX_TRECHOS_F1 = 12  # trechos + aberturas que chegam à F1 (compressão de 1.200 caracteres mantém o prompt < contexto)
K_LISTA = 16  # perguntas de lista: documentos distintos (2 trechos/documento, 700 caracteres por trecho)


class Estado(TypedDict, total=False):
    pergunta: str
    decisao: Any
    trechos: list
    contexto_extra: str
    precedentes: list
    provedor_f2: dict
    falhas_remotas: Annotated[list, operator.add]
    agente: str
    pareceres: Annotated[list, operator.add]
    resposta: Any
    tempos: Annotated[list, operator.add]
    via_ficha: bool
    escopo: Any  # documentos do contrato citado (busca restrita quando a ficha não basta)


class Orquestrador:
    def __init__(self, recuperar, responder_f1, llm_especialistas, *, linha_do_tempo=None, precedentes=None,
                 tracer=None, checkpointer=None, k=8, llm_relator=None, llm_f2_remoto=None,
                 envio_externo_permitido=False, contexto_max_chars=0, fichas=None, escopo_contrato=None):
        """recuperar(pergunta, k) -> list[TrechoRecuperado]; responder_f1: ResponderF1;
        linha_do_tempo(documento_ids) -> str (resumo para F2);
        precedentes(pergunta, documento_ids) -> list[Precedente] (memória de decisões, RF-19);
        llm_relator: modelo do relator, se diferente do dos especialistas (Fase 10: especialistas menores);
        fichas(pergunta) -> resposta | None: ficha do contrato pré-processada (resposta em ~1 s, sem LLM);
        llm_f2_remoto: provedor em nuvem para a F2 (ex.: Gemini) — usado só se TODO o contexto (trechos e
        precedentes) for do corpus acadêmico e o envio estiver autorizado no .env; anonimizado; com reserva local."""
        self._recuperar, self._f1, self._llm = recuperar, responder_f1, llm_especialistas
        self._llm_relator = llm_relator or llm_especialistas
        self._remoto, self._envio_permitido = llm_f2_remoto, envio_externo_permitido
        self._tl, self._prec, self._tracer, self._k = linha_do_tempo, precedentes, tracer, k
        self._ctx = contexto_max_chars  # compressão do contexto dos especialistas e do relator (0 = desligada)
        self._fichas = fichas
        self._escopo = escopo_contrato  # escopo_contrato(pergunta) -> set[documento_id] | None
        g = StateGraph(Estado)
        g.add_node("rotear", self._no(self._rotear))
        if fichas is not None:
            g.add_node("ficha", self._no(self._ficha))
        g.add_node("recuperar", self._no(self._recuperar_no))
        g.add_node("responder_f1", self._no(self._responder_f1))
        g.add_node("contexto_f2", self._no(self._contexto_f2))
        g.add_node("especialista", self._no(self._especialista))
        g.add_node("relator", self._no(self._relator))
        g.add_edge(START, "rotear")
        if fichas is not None:
            g.add_edge("rotear", "ficha")
            g.add_conditional_edges("ficha", lambda s: END if s.get("via_ficha") else "recuperar", [END, "recuperar"])
        else:
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

    def _ficha(self, s):
        """Perguntas sobre um contrato conhecido (objeto, valor, vigência, fiscal, documentos de um tipo) são
        respondidas pela ficha pré-processada; decisões (F2) e o que a ficha não cobre seguem o caminho completo."""
        if self._fichas is None:
            return {"via_ficha": False}
        r = None if s["decisao"].rota == "F2" else self._fichas(s["pergunta"])
        if r is None:  # a ficha não basta: a busca fica no contrato citado (também na decisão)
            return {"via_ficha": False, "escopo": self._escopo(s["pergunta"]) if self._escopo else None}
        return {"via_ficha": True, "resposta": r, "trechos": list(r.fontes)}

    def _recuperar_no(self, s):
        if getattr(s.get("decisao"), "lista", False):
            try:  # pergunta de lista: mais documentos distintos (no máximo 2 trechos de cada)
                return {"trechos": self._recuperar(s["pergunta"], K_LISTA, max_por_documento=2)}
            except TypeError:  # recuperador sem diversificação (avaliações antigas)
                pass
        if s.get("escopo"):
            try:
                return {"trechos": self._recuperar(s["pergunta"], self._k, documentos=s["escopo"])}
            except TypeError:  # recuperador sem escopo (avaliações antigas)
                pass
        return {"trechos": self._recuperar(s["pergunta"], self._k)}

    def _responder_f1(self, s):
        """Até 12 trechos (antes 6: com as aberturas na frente, trechos relevantes ficavam de fora); perguntas de
        situação/histórico e de lista recebem a linha do tempo do grafo dos documentos recuperados."""
        decisao, trechos = s["decisao"], s["trechos"]
        lista = getattr(decisao, "lista", False)
        resumo = ""
        if self._tl and (decisao.rota == "F1_complexa" or lista):
            resumo = self._tl({t.documento_id for t in trechos}) or ""
        limite = K_LISTA if lista else MAX_TRECHOS_F1
        return {"resposta": self._f1.responder(s["pergunta"], trechos[:limite], linha_do_tempo=resumo, lista=lista)}

    def _contexto_f2(self, s):
        documentos = {t.documento_id for t in s["trechos"]}
        resumo = self._tl(documentos) if self._tl else ""
        precedentes = self._prec(s["pergunta"], documentos) if self._prec else []
        if precedentes:
            resumo += ("\n\nPRECEDENTES DA GESTÃO (decisões anteriores semelhantes; informam, não vinculam):\n"
                       + "\n\n".join(p.como_contexto() for p in precedentes))
        return {"contexto_extra": resumo.strip(), "precedentes": precedentes,
                "provedor_f2": self._decidir_provedor(s["trechos"], precedentes)}

    def _decidir_provedor(self, trechos, precedentes):
        if self._remoto is None:
            return {"provedor": "local", "motivo": "nenhum provedor remoto configurado", "origens": []}
        origens = {t.corpus_origem for t in trechos} | {p.decisao.corpus_origem for p in precedentes}
        d = avaliar_envio_externo(remoto=True, permitido_na_config=self._envio_permitido, origens=origens,
                                  anonimizado=True)
        return {"provedor": self._remoto.nome if d.permitido else "local", "motivo": d.motivo,
                "origens": sorted(origens)}

    def _llm_f2(self, s, local):
        """LLM da F2 para esta consulta: remoto protegido (com reserva local) ou o local."""
        p = s.get("provedor_f2") or {}
        if self._remoto is None or p.get("provedor", "local") == "local":
            return local
        protegido = LLMProtegido(self._remoto, permitido_na_config=self._envio_permitido, origens=p["origens"])
        return LLMComReserva(protegido, local)

    def _distribuir(self, s):
        agentes = s["decisao"].agentes
        if not agentes:
            return "relator"
        return [Send("especialista", {**s, "agente": a}) for a in agentes]

    def _especialista(self, s):
        llm = self._llm_f2(s, self._llm)
        parecer = executar_especialista(llm, s["agente"], s["pergunta"], s["trechos"], s.get("contexto_extra", ""),
                                        self._ctx)
        return {"pareceres": [parecer], "falhas_remotas": [getattr(llm, "falhas", 0)]}

    def _relator(self, s):
        llm = self._llm_f2(s, self._llm_relator)
        resposta = relatar_f2(llm, s["pergunta"], s["trechos"], s.get("pareceres", []), s.get("contexto_extra", ""),
                              s.get("precedentes", []), self._ctx)
        return {"resposta": resposta, "falhas_remotas": [getattr(llm, "falhas", 0)]}

    def executar(self, pergunta, thread_id=None):
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        estado = self.grafo.invoke({"pergunta": pergunta, "pareceres": [], "tempos": [], "falhas_remotas": []},
                                   config=config)
        if "provedor_f2" in estado:
            estado["provedor_f2"] = {**estado["provedor_f2"], "falhas_remotas": sum(estado.get("falhas_remotas", []))}
        return estado
