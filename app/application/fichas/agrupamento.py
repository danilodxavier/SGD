"""Agrupa os documentos do acervo por contrato (chave = número normalizado, ex.: 012/2023).

Acervo real: a pasta de 1º nível identifica o contrato (19 de 23 pastas trazem nº/ano no nome — achado A2); todos os
documentos dela pertencem ao contrato. Sem pasta própria (corpus acadêmico), o documento é ligado pelo número citado
no título ou na abertura ("TERMO ADITIVO AO CONTRATO Nº 044/2023").
"""
import re
import unicodedata
from dataclasses import dataclass, field

RE_NUMERO = re.compile(r"(?<![\d/])(\d{1,4})\s*[/\-._]\s*(20\d{2})(?!\d)")
RE_CONTRATO_NO_TEXTO = re.compile(
    r"contrato\s*(?:administrativo\s*)?(?:n[º°o]?\.?\s*|numero\s*)?(\d{1,4})\s*[/\-.]\s*(20\d{2})(?!\d)", re.I)
TIPOS_LIGADOS_PELO_TEXTO = {"contrato", "aditivo", "apostilamento", "termo_rescisao", "termo_recebimento",
                            "nota_empenho", "ordem_reinicio", "ordem_suspensao", "termo_paralisacao", "termo_retomada",
                            "notificacao", "extrato_publicacao", "portaria_designacao", "relatorio_fiscalizacao"}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(texto.split())


def chave(numero, ano) -> str:
    return f"{int(numero):03d}/{int(ano)}"


def chaves_no_texto(texto: str, so_contrato: bool = True) -> list[str]:
    padrao = RE_CONTRATO_NO_TEXTO if so_contrato else RE_NUMERO
    return list(dict.fromkeys(chave(n, a) for n, a in padrao.findall(normalizar(texto))))


def pasta_de_contrato(caminho_relativo: str) -> tuple[str | None, str | None]:
    """(pasta de 1º nível, chave) quando a pasta traz exatamente um nº/ano; senão (pasta, None)."""
    partes = str(caminho_relativo or "").replace("\\", "/").split("/")
    if len(partes) < 2:
        return None, None
    numeros = list(dict.fromkeys(chave(n, a) for n, a in RE_NUMERO.findall(partes[0])))
    return partes[0], (numeros[0] if len(numeros) == 1 else None)


@dataclass
class DocumentoAcervo:
    id: int
    caminho_relativo: str
    tipo: str | None
    titulo: str | None
    data: str | None
    abertura: str = ""        # 1º trecho (até ~600 caracteres), para achar o número citado
    primeiro_trecho: int | None = None


@dataclass
class GrupoContrato:
    chave: str
    pasta: str | None = None
    documentos: list = field(default_factory=list)


def agrupar(documentos: list[DocumentoAcervo]) -> dict[str, GrupoContrato]:
    grupos: dict[str, GrupoContrato] = {}
    for d in documentos:
        pasta, k = pasta_de_contrato(d.caminho_relativo)
        if k is None and (d.tipo or "") in TIPOS_LIGADOS_PELO_TEXTO:
            citadas = chaves_no_texto(f"{d.titulo or ''} {d.abertura[:600]}")
            k, pasta = (citadas[0], None) if len(citadas) == 1 else (None, None)
        if k is None:
            continue
        g = grupos.setdefault(k, GrupoContrato(k, pasta))
        g.pasta = g.pasta or pasta
        g.documentos.append(d)
    return grupos


def documento_principal(grupo: GrupoContrato) -> DocumentoAcervo | None:
    """O instrumento do contrato: tipo "contrato" que cita o próprio número; o mais antigo."""
    contratos = [d for d in grupo.documentos if d.tipo == "contrato"]
    citam = [d for d in contratos if grupo.chave in chaves_no_texto(f"{d.titulo or ''} {d.abertura}")]
    candidatos = citam or contratos
    if not candidatos:
        return None
    return sorted(candidatos, key=lambda d: (d.data or "9999", d.id))[0]
