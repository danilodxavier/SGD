"""Extração de metadados documentais por regras (SAD-044, RF-04): tipo, número, data, órgão, processo,
vigência e situação de normas. Tudo é extraído do texto do próprio documento — sem conhecimento externo."""
import re
import unicodedata
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


# --------------------------------------------------------------------------------------------------------------
# 2º nível (A1, acervo real): só é usado quando as regras estritas acima deixam o documento como "outro".
# Os documentos reais de execução contratual raramente começam a linha com "CONTRATO Nº": trazem "CONTRATO DE
# PRESTAÇÃO DE SERVIÇOS Nº …", "TERMO ADITIVO Nº 03 AO CONTRATO …", notas de empenho, DANFE, certidões etc.
# Os padrões rodam sobre a linha SEM acentos e em maiúsculas (_sem_acento); o título guardado é a linha original.
ORDINAIS_EXT = {"PRIMEIRO": 1, "SEGUNDO": 2, "TERCEIRO": 3, "QUARTO": 4, "QUINTO": 5, "SEXTO": 6, "SETIMO": 7,
                "OITAVO": 8, "NONO": 9, "DECIMO": 10}
NUM2 = r"N\s*\.?\s*[º°O]?\s*\.?\s*"  # Nº, N.º, No, N. — já sem acento e em maiúsculas
RE_NUMERO_ATO = re.compile(r"(\d{1,6}(?:\.\d{3})*/\d{2,4})")
RE_CONTRATO_NUM = re.compile(r"CONTRATO\b[^\n]{0,80}?\b" + NUM2 + r"(\d{1,6}/\d{2,4})")
REGRAS_SEGUNDO_NIVEL = [  # (tipo, padrão na linha, ancorado no início da linha?) — do mais específico ao genérico
    ("aditivo", re.compile(r"^(?:(\d{1,2})\s*[º°O]?\s*|(" + "|".join(ORDINAIS_EXT) + r")\s+)?TERMO\s+ADITIVO\b"), True),
    ("apostilamento", re.compile(r"^(?:TERMO\s+DE\s+)?APOSTILA(?:MENTO)?\b"), True),
    ("extrato_publicacao", re.compile(r"^EXTRATO\s+D[OEA]\b"), True),
    ("nota_empenho", re.compile(r"\bNOTA\s+DE\s+EMPENHO\b"), False),
    ("nota_fiscal", re.compile(r"\bDANFE\b|\bNOTA\s+FISCAL\b|\bNFS-?E\b"), False),
    ("pagamento", re.compile(r"\bORDEM\s+BANCARIA\b|\bNOTA\s+DE\s+LIQUIDACAO\b|\bLIQUIDACAO\s+D[AE]\s+DESPESA\b|"
                             r"\bREQUISICAO\s+DE\s+PAGAMENTO\b|\bCOMPROVANTE\s+DE\s+PAGAMENTO\b|"
                             r"\bPROCESSO\s+DE\s+PAGAMENTO\b"), False),
    ("certidao", re.compile(r"^CERTIDAO\b|\bCERTIFICADO\s+DE\s+REGULARIDADE\b"), False),
    ("termo_recebimento", re.compile(r"^TERMO\s+DE\s+RECEBIMENTO\b|^ATESTADO\s+DE\s+(?:RECEBIMENTO|EXECUCAO)\b|"
                                     r"^ATESTO\b"), False),
    ("relatorio_fiscalizacao", re.compile(r"^RELATORIO\b[^\n]{0,30}\bFISCAL(?:IZACAO)?\b"), True),
    ("relatorio", re.compile(r"^RELATORIO\b"), True),
    ("ata_registro_precos", re.compile(r"^ATA\s+DE\s+REGISTRO\s+DE\s+PRECOS?\b"), True),
    ("estudo_tecnico_preliminar", re.compile(r"\bESTUDO\s+TECNICO\s+PRELIMINAR\b"), False),
    ("termo_referencia", re.compile(r"^TERMO\s+DE\s+REFERENCIA\b"), True),
    ("proposta", re.compile(r"^PROPOSTA\s+(?:COMERCIAL|DE\s+PRECOS?|DE\s+FORNECIMENTO)\b"), True),
    ("garantia", re.compile(r"\bAPOLICE\b|\bSEGURO[\s-]+GARANTIA\b|\bCARTA\s+FIANCA\b"), False),
    ("portaria", re.compile(r"^PORTARIA\b"), True),
    ("oficio", re.compile(r"^OFICIO\b"), True),
    ("despacho", re.compile(r"^DESPACHO\b"), True),
    ("notificacao", re.compile(r"^NOTIFICACAO\b"), True),
    ("parecer_juridico", re.compile(r"^PARECER\b[^\n]{0,40}\bJURIDICO\b"), True),
    ("parecer", re.compile(r"^PARECER\b"), True),
    ("contrato", re.compile(r"^CONTRATO\b[^\n]{0,80}?\b" + NUM2 + r"\d{1,6}/\d{2,4}"), True),
]
COM_NUMERO = {"apostilamento", "extrato_publicacao", "portaria", "oficio", "ata_registro_precos", "contrato",
              "notificacao", "parecer", "parecer_juridico", "despacho"}
# pistas no NOME do arquivo (último recurso, sem acento e em maiúsculas)
REGRAS_NOME = [
    ("aditivo", re.compile(r"\bADITIVO\b|\bT\.?A\.?\s*\d")),
    ("apostilamento", re.compile(r"APOSTILA")),
    ("nota_empenho", re.compile(r"\bEMPENHO|\bNE\b|\d{4}NE\d")),
    ("nota_fiscal", re.compile(r"\bNF[SE]?\b|\bNFS-?E\b|NOTA\s+FISCAL|DANFE")),
    ("pagamento", re.compile(r"PAGAMENTO|LIQUIDACAO|\bOB\b|\d{4}OB\d")),
    ("certidao", re.compile(r"CERTID|\bCND\b|\bCNDT\b|\bCRF\b|REGULARIDADE")),
    ("termo_recebimento", re.compile(r"ATESTO|RECEBIMENTO")),
    ("relatorio_fiscalizacao", re.compile(r"RELATORIO[^/\\]{0,25}FISCAL")),
    ("relatorio", re.compile(r"RELATORIO")),
    ("portaria", re.compile(r"PORTARIA")),
    ("proposta", re.compile(r"PROPOSTA")),
    ("garantia", re.compile(r"GARANTIA|APOLICE")),
    ("termo_referencia", re.compile(r"TERMO\s+DE\s+REFERENCIA|\bTR\b")),
    ("oficio", re.compile(r"OFICIO")),
    ("contrato", re.compile(r"\bCONTRATO\b")),
]
EXTENSOES_PLANILHA = {".xlsx", ".xls", ".ods", ".csv"}


def _sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _segundo_nivel(linhas):
    """(tipo, numero, titulo) pelo 2º nível, ou None. Considera as 25 primeiras linhas não vazias."""
    for linha in linhas[:25]:
        norm = _sem_acento(linha).lstrip(" -–—•*:.")
        for tipo, padrao, _ancorado in REGRAS_SEGUNDO_NIVEL:
            m = padrao.search(norm)
            if not m:
                continue
            numero = None
            if tipo == "aditivo":
                n = m.group(1) or ORDINAIS_EXT.get(m.group(2) or "")
                if not n and (mn := re.search(r"ADITIVO\s+" + NUM2 + r"(\d{1,2})\b", norm)):
                    n = mn.group(1)
                contrato = RE_CONTRATO_NUM.search(norm)
                if n and contrato:
                    numero = f"{int(n)}º TA ao Contrato {contrato.group(1)}"
            elif tipo == "extrato_publicacao":
                if c := RE_CONTRATO_NUM.search(norm):
                    numero = c.group(1)
            elif tipo == "contrato":
                numero = RE_CONTRATO_NUM.search(norm).group(1)
            elif tipo in COM_NUMERO and (mn := RE_NUMERO_ATO.search(norm)):
                numero = mn.group(1)
            return tipo, numero, linha
    return None


def _pelo_nome(nome_arquivo, extensao):
    base = _sem_acento(re.split(r"[\\/]", nome_arquivo or "")[-1].rsplit(".", 1)[0]).replace("_", " ")
    for tipo, padrao in REGRAS_NOME:
        if base and padrao.search(base):
            return tipo
    return "planilha" if (extensao or "").lower() in EXTENSOES_PLANILHA else None


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


# Datas complementares (acervo real: 81% dos documentos ficavam sem data — o fecho raramente está no fim da última
# linha). Cascata medida contra os 1.120 documentos reais que já tinham data (FASE_12 §14): último fecho
# "Cidade, 10 de março de 2025" em qualquer ponto (ano igual em 98,5%), último "assinado ... dd/mm/aaaa" (93%),
# "data de emissão" (notas, empenhos, certidões), "em dd/mm/aaaa, às hh:mm" (SEI) e "Cuiabá, dd/mm/aaaa".
D_BR = r"(\d{2}/\d{2}/(?:19|20)\d{2})"
RE_FECHO_LIVRE = re.compile(r"[A-Za-zÀ-ú]{3,}(?:\s*[-/]\s*MT)?\s*,\s*(?:em\s+)?" + DATA_EXTENSO, re.I)
CASCATA_DATAS = [  # (padrão, usar a última ocorrência?)
    (re.compile(r"assinad[oa].{0,200}?" + D_BR, re.I | re.S), True),
    (re.compile(r"(?:data\s+(?:de\s+|da\s+)?emiss[ãa]o|emitid[oa]\s+em)\s*[:\-]?\s*" + D_BR, re.I), False),
    (re.compile(r"\bem\s+" + D_BR + r",?\s+(?:a|à)s\s+\d{1,2}[:h]", re.I), False),
    (re.compile(r"cuiab[áa]\s*(?:[-/]\s*mt)?\s*,?\s*(?:em\s+)?" + D_BR, re.I), False),
]


def data_complementar(texto: str, hoje: date | None = None) -> date | None:
    """Data do documento pela cascata acima; descarta datas impossíveis (antes de 1988 ou no futuro)."""
    hoje = hoje or date.today()

    def plausivel(d):
        return d is not None and date(1988, 1, 1) <= d <= hoje

    fechos = [d for m in RE_FECHO_LIVRE.finditer(texto) if plausivel(d := _data_extenso(*m.groups()))]
    if fechos:
        return fechos[-1]
    for padrao, ultima in CASCATA_DATAS:
        datas = [d for m in padrao.finditer(texto) if plausivel(d := _data_br(m.group(1)))]
        if datas:
            return datas[-1] if ultima else datas[0]
    return None


def extrair_metadados(texto: str, nome_arquivo: str | None = None, extensao: str | None = None) -> Metadados:
    md = Metadados()
    inicio = texto[:6000]
    linhas = [ln.strip() for ln in inicio.splitlines() if ln.strip()][:40]
    _titulo_estrito(md, linhas)
    if md.tipo_documental == "outro":
        if achado := _segundo_nivel(linhas):
            md.tipo_documental, md.numero, md.titulo = achado
        elif tipo := _pelo_nome(nome_arquivo, extensao):
            md.tipo_documental = tipo
    return _complementar(md, texto, inicio)


def _titulo_estrito(md, linhas):
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


def _complementar(md, texto, inicio):
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
    if md.data is None:
        md.data = data_complementar(texto)

    if md.titulo and especie:
        # a nota de revogação do ATO INTEIRO fica entre o título e o art. 1º; notas posteriores são de dispositivos
        apos_titulo = inicio[inicio.find(md.titulo) + len(md.titulo):][:2500]
        apos_titulo = RE_PRIMEIRO_ARTIGO.split(apos_titulo, maxsplit=1)[0]
        if m := RE_REVOGACAO_DOC.search(apos_titulo):
            md.situacao, md.evidencia_situacao = "revogada", m.group(1).strip()
    return md
