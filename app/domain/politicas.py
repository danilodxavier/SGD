"""Políticas de domínio: classificação de respostas, mensagens institucionais e envio externo (ADR-002, ADR-004)."""
from dataclasses import dataclass
from enum import StrEnum

from app.domain.documentos import CorpusOrigem

MENSAGEM_AUSENCIA = "Não localizei essa informação nos documentos disponibilizados."
MENSAGEM_CONFLITO = ("Foram identificadas informações divergentes entre os documentos. "
                     "A aplicação apresenta as fontes e os respectivos conteúdos para conferência.")
AVISO_DECISAO = "O sistema sugere; a decisão cabe à gestão."
AVISO_INFERENCIA = "Esta conclusão decorre da relação entre os documentos localizados."


class Classificacao(StrEnum):
    FATO = "fato"
    INFERENCIA = "inferencia"
    CONFLITO = "conflito"
    AUSENCIA = "ausencia"


ORIGENS_PERMITIDAS_FORA = frozenset({CorpusOrigem.PUBLICO, CorpusOrigem.SINTETICO})


class PoliticaEnvioExternoViolada(PermissionError):
    """Tentativa de enviar conteúdo a provedor externo fora da política."""


@dataclass(frozen=True)
class DecisaoEnvio:
    permitido: bool
    motivo: str


def avaliar_envio_externo(*, remoto: bool, permitido_na_config: bool, origens, anonimizado: bool) -> DecisaoEnvio:
    """Conteúdo só sai da máquina se: autorizado no .env, todos os trechos forem do corpus acadêmico e anonimizados."""
    if not remoto:
        return DecisaoEnvio(True, "provedor local")
    if not permitido_na_config:
        return DecisaoEnvio(False, "envio externo desativado (AI_ALLOW_REMOTE=false)")
    origens = set(origens)
    if not origens:
        return DecisaoEnvio(False, "origem dos trechos desconhecida")
    if CorpusOrigem.REAL in origens:
        return DecisaoEnvio(False, "há trechos com origem 'real'; dados reais não saem da máquina")
    if not origens <= ORIGENS_PERMITIDAS_FORA:
        return DecisaoEnvio(False, "origem não autorizada para envio externo")
    if not anonimizado:
        return DecisaoEnvio(False, "conteúdo não anonimizado")
    return DecisaoEnvio(True, "corpus acadêmico anonimizado e envio autorizado")


def exigir_envio_permitido(**kwargs) -> None:
    decisao = avaliar_envio_externo(**kwargs)
    if not decisao.permitido:
        raise PoliticaEnvioExternoViolada(decisao.motivo)
