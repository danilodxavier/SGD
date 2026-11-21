"""Verificador de fontes determinístico (SAD-072, RF-17): a resposta só passa se cada afirmação crítica estiver
sustentada pelos trechos citados.

Checagens (sem LLM, reprodutíveis):
  1. numero_sem_suporte — número, data, valor ou identificador ausente dos trechos citados (e da pergunta);
  2. vigencia_contraria_a_fonte — afirma que um ato está vigente quando a fonte citada registra sua revogação;
  3. afirmacao_contraditoria — afirma e nega a vigência na mesma frase ("vigente, pois foi revogado").
"""
import re
from dataclasses import dataclass, field

from app.application.avaliacao.metricas import normalizar
from app.application.avaliacao.metricas_resposta import numeros_nao_suportados
from app.domain.politicas import MENSAGEM_AUSENCIA

RE_CITACAO_FRASE = re.compile(r"\bT(\d+)\b")
RE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ\[])")
AFIRMA_VIGENCIA = re.compile(r"(?<!nao )(?<!nao esta )(?<!nao mais )\b(?:ainda )?(?:esta|continua|permanece|segue|"
                             r"encontra-se)\s+(?:em vigor|vigente)\b|^(?!.*\bnao\b).*\be vigente\b")
NEGA_VIGENCIA = re.compile(r"\bnao (?:esta|continua|permanece|mais)\b.{0,20}\b(?:vigente|em vigor)|\brevogad")
FONTE_REVOGADA = re.compile(r"revogad[oa]s?\s+pel[oa]|\bfica(?:m)? revogad")


@dataclass
class Problema:
    tipo: str
    detalhe: str
    frase: str


@dataclass
class Verificacao:
    aprovada: bool
    problemas: list = field(default_factory=list)

    @property
    def frases_reprovadas(self):
        return list(dict.fromkeys(p.frase for p in self.problemas))


def suporte(t) -> str:
    """O que o modelo viu de um trecho citado: corpo + ficha do documento (a mesma de `montar_contexto`)."""
    return " ".join(str(x) for x in (t.texto, t.titulo, t.dispositivo, t.data_documento, getattr(t, "numero", None),
                                      getattr(t, "processo", None), getattr(t, "pasta", None)) if x)


def frases(texto: str) -> list[str]:
    """Frases por pontuação e por linha (itens "- " de uma relação são frases distintas)."""
    return [f.strip() for linha in texto.strip().splitlines() for f in RE_FRASE.split(linha) if f.strip()]


def verificar(resposta: str, citados, pergunta: str = "") -> Verificacao:
    if not resposta.strip() or resposta.strip() == MENSAGEM_AUSENCIA:
        return Verificacao(True)
    problemas = []
    suportes = [suporte(t) for t in citados]
    por_rotulo = {t.rotulo: suporte(t) for t in citados}
    fontes_revogam = any(t.revogado or t.situacao_norma == "revogada" or FONTE_REVOGADA.search(normalizar(t.texto))
                         for t in citados)
    for frase in frases(resposta):
        # frase com citação própria: o número precisa estar nos trechos que ELA cita (respostas com detalhes)
        proprios = [por_rotulo[f"T{n}"] for n in RE_CITACAO_FRASE.findall(frase) if f"T{n}" in por_rotulo]
        for numero in numeros_nao_suportados(frase, proprios or suportes, pergunta):
            problemas.append(Problema("numero_sem_suporte", f"'{numero}' não consta dos trechos citados", frase))
        norm = normalizar(frase)
        afirma = AFIRMA_VIGENCIA.search(norm)
        if afirma and NEGA_VIGENCIA.search(norm):
            problemas.append(Problema("afirmacao_contraditoria", "afirma e nega a vigência na mesma frase", frase))
        elif afirma and fontes_revogam:
            problemas.append(Problema("vigencia_contraria_a_fonte",
                                      "afirma vigência, mas a fonte citada registra revogação", frase))
    return Verificacao(not problemas, problemas)
