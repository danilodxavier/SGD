"""Regras puras da recuperação: termos da pergunta, expressão FTS5, fusão RRF e filtro de vigência (RF-14)."""
import re
import unicodedata
from dataclasses import dataclass, field

from app.application.portas import ResultadoBusca

_PALAVRAS_VAZIAS = """
a ao aos as até com como da das de do dos e é em entre esta este esse essa estão foi foram há isso já la mais me
na nas no nos o os ou para pela pelas pelo pelos por qual quais quando que quem se sem ser são seu sua sobre tem
um uma umas uns onde existe existem favor informe mostre liste diga nº n° numero número ainda está qual quais
foi deve devo pode posso houve teve sendo seja será sobre segundo conforme cujo cuja este esta isto aquele
"""
PALAVRAS_VAZIAS = set(_PALAVRAS_VAZIAS.split())
RE_TERMO = re.compile(r"\d[\d./-]*\d|\w+", re.UNICODE)


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def termos_da_pergunta(pergunta: str) -> list[str]:
    termos = []
    for bruto in RE_TERMO.findall(pergunta):
        t = bruto.lower()
        if t in PALAVRAS_VAZIAS or _sem_acento(t) in PALAVRAS_VAZIAS:
            continue
        if len(t) < 3 and not t.isdigit():
            continue
        if t not in termos:
            termos.append(t)
    return termos


def consulta_fts(termos: list[str]) -> str | None:
    """Expressão FTS5 (OR entre termos). Palavras longas usam prefixo para tolerar flexões."""
    partes = []
    for t in termos:
        citado = '"' + t.replace('"', '""') + '"'
        if t.isalpha() and len(t) >= 5:
            citado += "*"
        partes.append(citado)
    return " OR ".join(partes) if partes else None


def fundir_rrf(listas, k: int = 60) -> list[ResultadoBusca]:
    """Reciprocal Rank Fusion: soma 1/(k + posição) de cada lista (posição a partir de 1)."""
    pontos = {}
    for lista in listas:
        for posicao, r in enumerate(lista, start=1):
            pontos[r.trecho_id] = pontos.get(r.trecho_id, 0.0) + 1.0 / (k + posicao)
    ordenados = sorted(pontos.items(), key=lambda kv: (-kv[1], kv[0]))
    return [ResultadoBusca(tid, p, "rrf") for tid, p in ordenados]


@dataclass
class TrechoRecuperado:
    id: int
    documento_id: int
    texto: str
    arquivo: str
    caminho_relativo: str
    titulo: str | None
    dispositivo: str | None
    pagina: int | None
    tipo_documental: str | None
    corpus_origem: str
    data_documento: str | None
    revogado: bool
    situacao_norma: str | None
    pontuacao: float = 0.0
    caminho: str | None = None
    subdispositivos: list = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return f"T{self.id}"


def filtrar_vigencia(trechos):
    """Separa o que pode fundamentar respostas atuais do que é apenas histórico (dispositivo tachado ou norma
    revogada, conforme evidência no próprio documento)."""
    atuais, historico = [], []
    for t in trechos:
        (historico if t.revogado or t.situacao_norma == "revogada" else atuais).append(t)
    return atuais, historico
