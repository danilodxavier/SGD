"""Caso de uso ResponderF1 (SAD-051): resposta com citação literal [T<id>], classificação e confiança.

Salvaguardas determinísticas (independentes do modelo):
  - sem trechos recuperados → ausência, sem chamar o LLM;
  - citações a trechos fora do contexto são descartadas;
  - resposta factual/inferencial/conflito sem nenhuma citação válida → mensagem institucional de ausência;
  - classificação "ausencia" sempre usa a mensagem institucional.
"""
import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Protocol

from app.application.portas import LLMPort
from app.domain.politicas import MENSAGEM_AUSENCIA, MENSAGEM_CONFLITO, Classificacao


@dataclass(frozen=True)
class Conflito:
    origem: int  # documento que fixou o valor vigente
    destino: int  # documento que declara valor divergente
    campo: str  # valor_global | vigencia_fim
    valor_vigente: str
    valor_declarado: str
    trecho_origem: object | None = None  # TrechoRecuperado que contém o valor vigente
    trecho_destino: object | None = None  # TrechoRecuperado que contém o valor divergente


class ConflitosPort(Protocol):
    def entre(self, documentos: set) -> list: ...


CAMPOS_DA_PERGUNTA = {  # palavras da pergunta que tornam o conflito daquele campo relevante
    "valor_global": re.compile(r"\bvalor", re.I),
    "vigencia_fim": re.compile(r"vig[êe]ncia|t[ée]rmino|encerra|termina|prazo|at[ée] quando", re.I),
}
ROTULO_CAMPO = {"valor_global": "valor global", "vigencia_fim": "término da vigência"}

PROMPTS = Path(__file__).resolve().parents[1] / "agentes" / "prompts"
SCHEMAS = Path(__file__).resolve().parents[1] / "agentes" / "schemas"
RE_CITACAO = re.compile(r"\bT(\d+)\b")
CAMPOS_F1 = ("resposta", "classificacao", "confianca", "fontes", "lacunas")
INSTRUCAO_F1 = ("Modo F1: responda somente à pergunta, em 1 a 4 frases, citando os trechos no texto como [T<id>] "
                "e listando os mesmos ids em \"fontes\". Se a informação não estiver nos trechos, use "
                "classificacao \"ausencia\". Se os trechos divergirem sobre o fato perguntado, use \"conflito\" e "
                "apresente o conteúdo de cada fonte.")
# A ordem importa: com schema estrito o Ollama emite as chaves em ordem alfabética e o modelo "decide" a
# classificação antes de redigir a resposta — recusas indevidas (validação: 17/27 factuais viraram ausência).
# Pedir JSON livre com a resposta primeiro corrigiu o comportamento (FASE_05 §4).
ORDEM_SAIDA = ("Responda SOMENTE com um objeto JSON com as chaves nesta ordem: \"resposta\" (texto com citações "
               "[T<id>]), \"fontes\" (lista de ids), \"classificacao\" (fato|inferencia|conflito|ausencia), "
               "\"confianca\" (0 a 1), \"lacunas\" (lista).")
VERSAO_INSTRUCAO = 2


@cache
def carregar_prompt(nome: str, versao: int = 1) -> str:
    def corpo(arquivo):
        texto = (PROMPTS / arquivo).read_text(encoding="utf-8")
        return texto.split("---", 2)[2].strip() if texto.startswith("---") else texto.strip()

    return corpo(f"_regras_comuns.v{versao}.md") + "\n\n" + corpo(f"{nome}.v{versao}.md")


@cache
def schema_f1() -> dict:
    completo = json.loads((SCHEMAS / "relator.v1.json").read_text(encoding="utf-8"))
    return {"type": "object", "additionalProperties": False, "required": list(CAMPOS_F1),
            "properties": {c: completo["properties"][c] for c in CAMPOS_F1}}


def montar_contexto(trechos) -> str:
    blocos = []
    for t in trechos:
        meta = " | ".join(str(x) for x in (t.titulo, t.dispositivo, f"pág. {t.pagina}" if t.pagina else None,
                                           t.data_documento, f"origem: {t.corpus_origem}") if x)
        blocos.append(f"[{t.rotulo}] ({meta})\n{t.texto.strip()}")
    return "\n\n".join(blocos)


@dataclass
class RespostaF1:
    resposta: str
    classificacao: str
    confianca: float
    fontes: list
    lacunas: list = field(default_factory=list)
    modelo: str | None = None
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    observacoes: list = field(default_factory=list)
    bruto: dict | None = None


class ResponderF1:
    def __init__(self, llm: LLMPort, *, max_tokens: int = 500, versao_prompt: int = 1,
                 conflitos: ConflitosPort | None = None):
        self.llm, self.max_tokens, self.versao = llm, max_tokens, versao_prompt
        self.conflitos = conflitos

    def responder(self, pergunta: str, trechos) -> RespostaF1:
        if not trechos:
            return RespostaF1(MENSAGEM_AUSENCIA, Classificacao.AUSENCIA.value, 0.0, [],
                              observacoes=["sem_trechos_recuperados"])
        if self.conflitos is not None and (resposta := self._conflito(pergunta, trechos)):
            return resposta
        mensagens = [
            {"role": "system", "content": carregar_prompt("relator", self.versao) + "\n\n" + INSTRUCAO_F1 + "\n"
                + ORDEM_SAIDA},
            {"role": "user", "content": f"PERGUNTA: {pergunta}\n\nTRECHOS:\n{montar_contexto(trechos)}"},
        ]
        r = self.llm.chat(mensagens, max_tokens=self.max_tokens, temperatura=0.0, json_livre=True)
        dados = r.json if isinstance(r.json, dict) else {}
        return self._validar(dados, trechos, r)

    def _conflito(self, pergunta, trechos):
        """RF-09: se o grafo registra contradição entre documentos do contexto sobre o campo perguntado, responde
        de forma determinística com as duas fontes (o sistema não escolhe o valor)."""
        documentos = {t.documento_id for t in trechos}
        relevantes = [c for c in self.conflitos.entre(documentos)
                      if CAMPOS_DA_PERGUNTA.get(c.campo) and CAMPOS_DA_PERGUNTA[c.campo].search(pergunta)]
        if not relevantes:
            return None
        linhas, fontes = [MENSAGEM_CONFLITO], []
        for c in relevantes:
            for doc_id, valor, papel, evidencia in ((c.origem, c.valor_vigente, "registro vigente", c.trecho_origem),
                                                    (c.destino, c.valor_declarado, "valor divergente",
                                                     c.trecho_destino)):
                do_doc = [t for t in trechos if t.documento_id == doc_id]
                # a citação precisa conter o valor: do contexto, senão a evidência registrada no grafo
                trecho = next((t for t in do_doc if valor in t.texto), None) or evidencia or do_doc[0]
                fontes.append(trecho)
                linhas.append(f"- {trecho.titulo or trecho.arquivo}: {ROTULO_CAMPO[c.campo]} = {valor} "
                              f"({papel}) [{trecho.rotulo}]")
        linhas.append("É necessária conferência documental.")
        unicos = list({t.id: t for t in fontes}.values())
        return RespostaF1("\n".join(linhas), Classificacao.CONFLITO.value, 0.9, unicos, modelo="regra-conflito",
                          observacoes=["conflito_detectado_no_grafo"])

    def _validar(self, dados, trechos, r) -> RespostaF1:
        por_rotulo = {t.rotulo: t for t in trechos}
        observacoes = []
        classificacao = dados.get("classificacao") if dados.get("classificacao") in {c.value for c in Classificacao} \
            else Classificacao.FATO.value
        texto = str(dados.get("resposta") or "").strip()
        # tolera formatos ("T12", "[T12]", 12, "12"); o id continua obrigado a existir no contexto
        declarados = []
        for f in dados.get("fontes") or []:
            rotulo = str(f).strip().strip("[]").strip()
            declarados.append(f"T{rotulo}" if rotulo.isdigit() else rotulo)
        no_texto = [f"T{n}" for n in RE_CITACAO.findall(texto)]
        citados = list(dict.fromkeys(declarados + no_texto))
        validos = [c for c in citados if c in por_rotulo]
        if len(validos) < len(citados):
            observacoes.append("citacoes_invalidas_descartadas")
        try:
            confianca = max(0.0, min(1.0, float(dados.get("confianca", 0.0))))
        except (TypeError, ValueError):
            confianca = 0.0
        if classificacao != Classificacao.AUSENCIA.value and not validos:
            observacoes.append("resposta_factual_sem_citacao_valida")
            classificacao = Classificacao.AUSENCIA.value
        if classificacao == Classificacao.AUSENCIA.value:
            texto, validos, confianca = MENSAGEM_AUSENCIA, [], min(confianca, 0.3)
        return RespostaF1(texto, classificacao, confianca, [por_rotulo[c] for c in validos],
                          list(dados.get("lacunas") or []), r.modelo, r.tokens_entrada, r.tokens_saida,
                          r.latencia_ms, observacoes, dados)
