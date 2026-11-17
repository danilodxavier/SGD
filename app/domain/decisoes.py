"""Memória de decisões da gestão (RF-19): decisões anteriores e seus resultados viram precedentes.

Um precedente nunca decide por si: informa o que foi decidido em caso semelhante e como terminou, para que a gestão
pondere. Resultado negativo é sinal de alerta; resultado pendente ainda não ensina nada."""
from dataclasses import dataclass, field
from enum import StrEnum


class AvaliacaoResultado(StrEnum):
    POSITIVO = "positivo"
    NEGATIVO = "negativo"
    NEUTRO = "neutro"
    PENDENTE = "pendente"


LICOES = {
    AvaliacaoResultado.POSITIVO: "resultado positivo — a solução funcionou no caso anterior",
    AvaliacaoResultado.NEGATIVO: "ATENÇÃO: resultado negativo — avaliar o que deu errado antes de repetir",
    AvaliacaoResultado.NEUTRO: "resultado neutro — sem ganho ou prejuízo claro",
    AvaliacaoResultado.PENDENTE: "resultado ainda não avaliado — precedente fraco",
}


@dataclass
class Decisao:
    titulo: str
    decisao: str
    data: str  # ISO 8601
    contexto: str = ""
    fundamentos: str = ""
    resultado: str = ""
    avaliacao_resultado: AvaliacaoResultado = AvaliacaoResultado.PENDENTE
    codigo: str | None = None
    processo_id: int | None = None
    decisor_perfil: str | None = None
    corpus_origem: str = "real"
    consulta_id: int | None = None
    id: int | None = None
    documento_ids: list = field(default_factory=list)

    def texto_indexavel(self) -> str:
        partes = (self.titulo, self.contexto, f"Decisão: {self.decisao}", f"Fundamentos: {self.fundamentos}",
                  f"Resultado: {self.resultado}")
        return "\n".join(p for p in partes if p and not p.endswith(": "))

    def __post_init__(self):
        self.avaliacao_resultado = AvaliacaoResultado(self.avaliacao_resultado)
        if not self.titulo.strip() or not self.decisao.strip():
            raise ValueError("Decisão exige título e texto da decisão.")


@dataclass
class Precedente:
    decisao: Decisao
    pontuacao: float
    rotulo: str  # "P<id>", citável pelo relator

    @property
    def licao(self) -> str:
        return LICOES[self.decisao.avaliacao_resultado]

    def como_contexto(self) -> str:
        d = self.decisao
        linhas = [f"[{self.rotulo}] {d.titulo} ({d.data})", f"Contexto: {d.contexto}" if d.contexto else "",
                  f"Decisão: {d.decisao}", f"Fundamentos: {d.fundamentos}" if d.fundamentos else "",
                  f"Resultado: {d.resultado or 'não registrado'} — {self.licao}"]
        return "\n".join(x for x in linhas if x)

    def resumo(self) -> dict:
        d = self.decisao
        return {"id": self.rotulo, "codigo": d.codigo, "titulo": d.titulo, "data": d.data, "decisao": d.decisao,
                "resultado": d.resultado, "avaliacao_resultado": d.avaliacao_resultado.value, "licao": self.licao,
                "pontuacao": round(self.pontuacao, 4)}
