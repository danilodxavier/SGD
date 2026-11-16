"""Extração de metadados documentais por regras (SAD-044, RF-04): tipo, número, data, órgão, processo,
vigência e situação de normas. Tudo é extraído do texto do próprio documento — sem conhecimento externo."""
import re
from dataclasses import dataclass
from datetime import date

from app.domain.normas import EspecieNormativa

MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                     "setembro", "outubro", "novembro", "dezembro"], start=1)}
MESES["marco"] = 3
NUM = r"N\s*[º°o]\.?\s*"
DATA_EXTENSO = r"(\d{1,2})\s*[º°o]?\s+DE\s+([A-ZÇa-zç]+)\s+DE\s+(\d{4})"

# (tipo, padrão do título, grupo do número) — ordem do mais específico para o mais genérico
REGRAS_TITULO = [
    ("aditivo", re.compile(r"\b(PRIMEIRO|SEGUNDO|TERCEIRO|QUARTO|QUINTO|\d+\s*[º°o])\s+TERMO\s+ADITIVO\s+AO\s+"
                           r"CONTRATO\s+" + NUM + r"([\d./-]+)", re.I), None),
    ("apostilamento", re.compile(r"^APOSTILAMENTO\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("termo_rescisao", re.compile(r"^TERMO\s+DE\s+RESCIS[ÃA]O", re.I), None),
    ("termo_paralisacao", re.compile(r"^TERMO\s+DE\s+PARALISA[ÇC][ÃA]O\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("termo_retomada", re.compile(r"^TERMO\s+DE\s+RETOMADA", re.I), None),
    ("denuncia_convenio", re.compile(r"^TERMO\s+DE\s+DEN[ÚU]NCIA", re.I), None),
    ("termo_referencia", re.compile(r"^TERMO\s+DE\s+REFER[ÊE]NCIA\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("ordem_suspensao", re.compile(r"^ORDEM\s+DE\s+SUSPENS[ÃA]O\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("ordem_reinicio", re.compile(r"^ORDEM\s+DE\s+REIN[ÍI]CIO\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("relatorio_fiscalizacao", re.compile(r"^RELAT[ÓO]RIO\s+DE\s+FISCALIZA[ÇC][ÃA]O\s+" + NUM + r"([\d./-]+)",
                                          re.I), 1),
    ("boletim_medicao", re.compile(r"^BOLETIM\s+DE\s+MEDI[ÇC][ÃA]O\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("parecer_juridico", re.compile(r"^PARECER\s+JUR[ÍI]DICO\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("parecer", re.compile(r"^PARECER\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("despacho", re.compile(r"^DESPACHO\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("decisao_gestao", re.compile(r"^DECIS[ÃA]O\s+DA\s+GEST[ÃA]O\s+([A-Z]{1,4}-[\d./-]+)", re.I), 1),
    ("oficio", re.compile(r"^OF[ÍI]CIO\s+" + NUM + r"([\d./-]+?)(?:/[A-Z]|\s|$)", re.I), 1),
    ("notificacao", re.compile(r"^NOTIFICA[ÇC][ÃA]O\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("convenio", re.compile(r"^CONV[ÊE]NIO\s+" + NUM + r"([\d./-]+)", re.I), 1),
    ("portaria_designacao", re.compile(r"^PORTARIA\s+" + NUM + r"([\d./-]+)\s*[—–-]\s*DESIGNA", re.I), 1),
    ("portaria", re.compile(r"^PORTARIA\s+" + NUM + r"([\d./-]+?),?\s", re.I), 1),
    ("instrucao_normativa", re.compile(r"^INSTRU[ÇC][ÃA]O\s+NORMATIVA\s+" + NUM + r"([\d./-]+?),?\s", re.I), 1),
    ("orientacao", re.compile(r"^ORIENTA[ÇC][ÃA]O\s+NORMATIVA\s+" + NUM + r"([\d./-]+?),?\s", re.I), 1),
    ("constituicao", re.compile(r"^CONSTITUI[ÇC][ÃA]O\s+DA\s+REP[ÚU]BLICA\s+FEDERATIVA\s+DO\s+BRASIL"
                                r"(?:\s+DE\s+(\d{4}))?", re.I), 1),
    ("lei_complementar", re.compile(r"^LEI\s+COMPLEMENTAR\s+" + NUM + r"([\d.]+)", re.I), 1),
    ("decreto_lei", re.compile(r"^DECRETO-LEI\s+" + NUM + r"([\d.]+)", re.I), 1),
    ("decreto", re.compile(r"^DECRETO\s+" + NUM + r"([\d./]+?),?\s", re.I), 1),
    ("lei", re.compile(r"^LEI\s+" + NUM + r"([\d./]+?),?\s", re.I), 1),
    ("contrato", re.compile(r"^CONTRATO\s+" + NUM + r"([\d./-]+)", re.I), 1),
]
ORDINAL = {"PRIMEIRO": 1, "SEGUNDO": 2, "TERCEIRO": 3, "QUARTO": 4, "QUINTO": 5}
ESPECIE = {"constituicao": EspecieNormativa.CONSTITUICAO, "lei_complementar": EspecieNormativa.LEI_COMPLEMENTAR,
           "lei": EspecieNormativa.LEI, "decreto_lei": EspecieNormativa.LEI, "decreto": EspecieNormativa.DECRETO,
           "instrucao_normativa": EspecieNormativa.INSTRUCAO_NORMATIVA, "portaria": EspecieNormativa.PORTARIA,
           "orientacao": EspecieNormativa.ORIENTACAO, "parecer": EspecieNormativa.PARECER,
           "parecer_juridico": EspecieNormativa.PARECER}
ORGAOS = [("SEGEP/VV", re.compile(r"SEGEP/VV|Secretaria de Estado de Gest[ãa]o P[úu]blica", re.I)),
          ("Presidência da República", re.compile(r"Presid[êe]ncia da Rep[úu]blica", re.I))]
RE_PROCESSO = re.compile(r"PROCESSO\s+(?:" + NUM + r")?([A-Z][A-Z0-9-]*-\d{4}/\d+|\d[\d./-]{6,})", re.I)
RE_VIGENCIA = re.compile(r"in[íi]cio\s+em\s+(\d{2}/\d{2}/\d{4})\s+e\s+t[ée]rmino\s+em\s+(\d{2}/\d{2}/\d{4})", re.I)
RE_FECHO = re.compile(r",\s*" + DATA_EXTENSO + r"\.?\s*$", re.I | re.M)
RE_REVOGACAO_DOC = re.compile(r"\(\s*(Revogad[oa]\s+pel[oa]\s+[^)]{3,120})\)", re.I)
RE_PRIMEIRO_ARTIGO = re.compile(r"^\s*Art\.\s*1\s*(?:º|°|o)?\b", re.M)


@dataclass
class Metadados:
    tipo_documental: str = "outro"
    numero: str | None = None
    titulo: str | None = None
    data: date | None = None
    orgao: str | None = None
    processo: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    especie: str | None = None
    nivel_hierarquico: int | None = None
    situacao: str | None = None  # None = sem evidência no documento; "revogada" somente com nota explícita
    evidencia_situacao: str | None = None


def _data_extenso(dia, mes, ano):
    mes = MESES.get(mes.lower().replace("ç", "c") if mes.lower() == "março" else mes.lower())
    try:
        return date(int(ano), mes, int(dia)) if mes else None
    except ValueError:
        return None


def _data_br(texto):
    d, m, a = (int(x) for x in texto.split("/"))
    try:
        return date(a, m, d)
    except ValueError:
        return None


def extrair_metadados(texto: str) -> Metadados:
    md = Metadados()
    inicio = texto[:6000]
    linhas = [ln.strip() for ln in inicio.splitlines() if ln.strip()][:40]

    for linha in linhas:
        for tipo, padrao, grupo in REGRAS_TITULO:
            m = padrao.search(linha) if tipo == "aditivo" else padrao.match(linha)
            if not m:
                continue
            md.tipo_documental, md.titulo = tipo, linha
            if tipo == "aditivo":
                ordem = m.group(1).upper()
                n = ORDINAL.get(ordem) or int(re.sub(r"\D", "", ordem))
                md.numero = f"{n}º TA ao Contrato {m.group(2).rstrip('.,')}"
            elif grupo is not None and m.group(grupo):
                md.numero = m.group(grupo).rstrip(".,")
            elif tipo == "constituicao":
                md.numero = "1988" if "1988" in linha else None
            if mt := re.search(DATA_EXTENSO, linha, re.I):
                md.data = _data_extenso(*mt.groups())
            break
        if md.titulo:
            break

    if md.tipo_documental == "constituicao" and not md.numero:
        md.numero = "1988"
    especie = ESPECIE.get(md.tipo_documental)
    if especie:
        md.especie, md.nivel_hierarquico = md.tipo_documental, especie.nivel

    for nome, padrao in ORGAOS:
        if padrao.search(inicio):
            md.orgao = nome
            break
    if m := RE_PROCESSO.search(inicio):
        md.processo = m.group(1).rstrip(".,")
    if m := RE_VIGENCIA.search(texto[:20000]):
        md.vigencia_inicio, md.vigencia_fim = _data_br(m.group(1)), _data_br(m.group(2))
    if md.data is None and md.tipo_documental == "contrato" and md.vigencia_inicio:
        md.data = md.vigencia_inicio
    if md.data is None and (m := RE_FECHO.search(texto[-3000:] if len(texto) > 3000 else texto)):
        md.data = _data_extenso(*m.groups())

    if md.titulo and especie:
        # a nota de revogação do ATO INTEIRO fica entre o título e o art. 1º; notas posteriores são de dispositivos
        apos_titulo = inicio[inicio.find(md.titulo) + len(md.titulo):][:2500]
        apos_titulo = RE_PRIMEIRO_ARTIGO.split(apos_titulo, maxsplit=1)[0]
        if m := RE_REVOGACAO_DOC.search(apos_titulo):
            md.situacao, md.evidencia_situacao = "revogada", m.group(1).strip()
    return md
