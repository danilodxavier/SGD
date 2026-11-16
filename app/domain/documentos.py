"""Documentos e trechos indexados."""
from dataclasses import dataclass
from enum import StrEnum


class CorpusOrigem(StrEnum):
    """Origem do documento; controla o que pode sair da máquina (ADR-002)."""

    PUBLICO = "publico"
    SINTETICO = "sintetico"
    REAL = "real"


class TipoDocumental(StrEnum):
    CONTRATO = "contrato"
    ADITIVO = "aditivo"
    APOSTILAMENTO = "apostilamento"
    CONSTITUICAO = "constituicao"
    LEI = "lei"
    DECRETO = "decreto"
    INSTRUCAO_NORMATIVA = "instrucao_normativa"
    PORTARIA = "portaria"
    ORIENTACAO = "orientacao"
    PARECER = "parecer"
    ACORDAO = "acordao"
    OFICIO = "oficio"
    DESPACHO = "despacho"
    NOTA_TECNICA = "nota_tecnica"
    TERMO_REFERENCIA = "termo_referencia"
    EDITAL = "edital"
    NOTIFICACAO = "notificacao"
    OUTRO = "outro"


class TipoDispositivo(StrEnum):
    ARTIGO = "artigo"
    PARAGRAFO = "paragrafo"
    INCISO = "inciso"
    ALINEA = "alinea"
    CLAUSULA = "clausula"
    SUBCLAUSULA = "subclausula"
    SECAO = "secao"
    LIVRE = "livre"


@dataclass(frozen=True)
class Trecho:
    id: int
    documento_id: int
    texto: str
    pagina: int | None = None
    dispositivo: str | None = None
    tipo_dispositivo: TipoDispositivo = TipoDispositivo.LIVRE
    caminho: str | None = None

    @property
    def rotulo(self) -> str:
        """Identificador usado nos prompts e citações (ex.: T42)."""
        return f"T{self.id}"
