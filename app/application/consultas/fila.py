"""Fila de consultas com acompanhamento (implantação na rede, 2026-11-21).

O LLM local atende uma pergunta por vez (GPU de 6 GB). Com vários gestores ao mesmo tempo, a pergunta espera; em vez
de uma requisição HTTP presa por minutos, a consulta entra numa fila FIFO com um único executor e a interface
acompanha posição, etapa atual e tempo decorrido (tempo percebido), recebendo o resultado quando fica pronto.
"""
import itertools
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field

ETAPAS = {
    "rotear": "Entendendo a pergunta",
    "ficha": "Consultando a ficha do contrato",
    "recuperar": "Buscando nos documentos",
    "responder_f1": "Redigindo a resposta e conferindo as fontes",
    "contexto_f2": "Montando linha do tempo e precedentes",
    "especialista": "Ouvindo os agentes especialistas",
    "relator": "Consolidando a recomendação e conferindo as fontes",
}


@dataclass
class Consulta:
    id: int
    usuario_id: int
    pergunta: str
    criada: float = field(default_factory=time.time)
    estado: str = "fila"  # fila | processando | concluida | erro
    etapa: str | None = None
    iniciada: float | None = None
    concluida: float | None = None
    resultado: dict | None = None
    erro: str | None = None
    extras: dict = field(default_factory=dict)  # ex.: IP de origem, uso do cache

    def como_dict(self, posicao: int | None) -> dict:
        agora = time.time()
        return {"id": self.id, "estado": self.estado, "posicao": posicao, "etapa": self.etapa,
                "etapa_descricao": ETAPAS.get((self.etapa or "").split(":")[0]),
                "espera_s": round((self.iniciada or agora) - self.criada, 1),
                "decorrido_s": round((self.concluida or agora) - self.criada, 1),
                "resultado": self.resultado, "erro": self.erro}


class FilaDeConsultas:
    """FIFO com um executor; `executar(consulta, ao_mudar_etapa) -> dict` faz o trabalho pesado."""

    def __init__(self, executar, *, reter_s: int = 1800):
        self._executar, self._reter = executar, reter_s
        self._fila: deque[Consulta] = deque()
        self._todas: dict[int, Consulta] = {}
        self._ids = itertools.count(1)
        self._cond = threading.Condition()
        self._executor = None

    def enfileirar(self, usuario_id: int, pergunta: str, **extras) -> Consulta:
        with self._cond:
            self._limpar()
            c = Consulta(next(self._ids), usuario_id, pergunta, extras=extras)
            self._todas[c.id] = c
            self._fila.append(c)
            if self._executor is None or not self._executor.is_alive():
                self._executor = threading.Thread(target=self._laco, name="fila-consultas", daemon=True)
                self._executor.start()
            self._cond.notify()
            return c

    def situacao(self, consulta_id: int, usuario_id: int) -> dict | None:
        """Só o dono vê a própria consulta (perguntas da alta gestão não vazam entre usuários)."""
        with self._cond:
            c = self._todas.get(consulta_id)
            if c is None or c.usuario_id != usuario_id:
                return None
            posicao = next((i + 1 for i, x in enumerate(self._fila) if x.id == c.id), None)
            return c.como_dict(posicao)

    def tamanho(self) -> int:
        with self._cond:
            return len(self._fila)

    def _laco(self):
        while True:
            with self._cond:
                while not self._fila:
                    if not self._cond.wait(timeout=60):
                        self._executor = None
                        return
                c = self._fila[0]
                c.estado, c.iniciada = "processando", time.time()

            def mudar_etapa(nome, consulta=c):
                consulta.etapa = nome

            try:
                resultado, erro = self._executar(c, mudar_etapa), None
            except Exception as exc:  # noqa: BLE001 - a falha é devolvida ao usuário de forma genérica
                resultado, erro = None, f"Falha ao processar a pergunta ({type(exc).__name__})."
            with self._cond:
                self._fila.popleft()
                c.resultado, c.erro, c.concluida = resultado, erro, time.time()
                c.estado = "erro" if erro else "concluida"

    def _limpar(self):
        limite = time.time() - self._reter
        for i in [i for i, c in self._todas.items() if c.concluida and c.concluida < limite]:
            del self._todas[i]


class TracerComProgresso:
    """Envolve um tracer (spans por nó do grafo) e informa a etapa atual à fila."""

    def __init__(self, tracer, ao_mudar_etapa):
        self._tracer, self._mudar = tracer, ao_mudar_etapa

    @contextmanager
    def span(self, no, **kw):
        self._mudar(no)
        with self._tracer.span(no, **kw) as s:
            yield s
