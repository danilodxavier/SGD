"""SAD-041 — Gerador determinístico do corpus sintético (ADR-002) com gabarito.

Ente fictício: "Estado de Vale Verde". Todos os nomes, números, CNPJ e CPF são inventados; cada documento
traz o aviso de documento fictício. Saídas:
  corpus/sintetico/<processo>/<arquivo>.{docx,pdf,txt}
  corpus/sintetico/GABARITO.json  — metadados, dispositivos, fatos, relações (8 classes) e contradições
  linhas "sintetico" em corpus/MANIFESTO.csv

Uso: python scripts/sadgd/gerar_corpus_sintetico.py
"""
import csv
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "corpus" / "sintetico"
MANIFESTO = RAIZ / "corpus" / "MANIFESTO.csv"
CABECALHO = ["arquivo", "corpus_origem", "url", "especie", "numero", "ano", "esfera", "tema", "coletado_em",
             "sha256", "bytes", "licenca"]

ESTADO = "ESTADO DE VALE VERDE"
ORGAO = "Secretaria de Estado de Gestão Pública"
SIGLA = "SEGEP/VV"
AVISO = ("DOCUMENTO FICTÍCIO — corpus acadêmico SAD-GD. Não corresponde a ato oficial; "
         "nomes, números, CNPJ e CPF são inventados.")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
ORDINAIS = ["PRIMEIRA", "SEGUNDA", "TERCEIRA", "QUARTA", "QUINTA", "SEXTA", "SÉTIMA", "OITAVA", "NONA", "DÉCIMA",
            "DÉCIMA PRIMEIRA", "DÉCIMA SEGUNDA", "DÉCIMA TERCEIRA", "DÉCIMA QUARTA", "DÉCIMA QUINTA"]
ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def cnpj(base8: str) -> str:
    """CNPJ fictício com dígitos verificadores válidos (formato), a partir de 8 dígitos-base."""
    numeros = [int(c) for c in base8 + "0001"]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        resto = sum(n * p for n, p in zip(numeros, pesos, strict=False)) % 11
        numeros.append(0 if resto < 2 else 11 - resto)
    s = "".join(map(str, numeros))
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


def cpf(base9: str) -> str:
    numeros = [int(c) for c in base9]
    for inicio in (10, 11):
        resto = sum(n * p for n, p in zip(numeros, range(inicio, 1, -1), strict=False)) % 11
        numeros.append(0 if resto < 2 else 11 - resto)
    s = "".join(map(str, numeros))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def extenso(d: date) -> str:
    dia = "1º" if d.day == 1 else str(d.day)
    return f"{dia} de {MESES[d.month - 1]} de {d.year}"


def br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def moeda(v: float) -> str:
    inteiro, centavos = f"{v:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def mais_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    dias = [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(ano, mes, min(d.day, dias[mes - 1]))


@dataclass
class Bloco:
    rotulo: str  # dispositivo de primeiro nível (ex.: "art. 3º", "cláusula segunda") ou "" para texto livre
    tipo: str  # artigo | clausula | livre
    titulo: str  # linha de abertura como aparece no documento
    linhas: list = field(default_factory=list)  # (rotulo_subdispositivo | None, texto)


@dataclass
class Doc:
    id: str
    processo: str
    arquivo: str
    formato: str  # docx | pdf | txt | pdf_digitalizado
    tipo_documental: str
    numero: str
    data: date
    titulo: str
    preambulo: list
    blocos: list
    fecho: list
    fatos: dict = field(default_factory=dict)
    especie: str = ""


DOCS: list[Doc] = []
RELACOES: list[dict] = []
CONTRADICOES: list[dict] = []


def rel(origem, destino, tipo, evidencia):
    RELACOES.append({"origem": origem, "destino": destino, "tipo": tipo, "evidencia": evidencia})


def assinatura(cargo, nome):
    return ["", f"{nome}", f"{cargo}"]


# ---------------------------------------------------------------- modelos de documentos

def contrato(pid, ident, numero, ano_proc, objeto, contratada, base_cnpj, valor, inicio, meses, formato="docx",
             extra_clausulas=(), representante="Marina Duarte Falcão"):
    fim = mais_meses(inicio, meses) - timedelta(days=1)
    c = cnpj(base_cnpj)
    processo = f"SEGEP-PRO-{ano_proc}/{int(numero.split('/')[0]):05d}"
    cl = [
        ("DO OBJETO", [f"O presente contrato tem por objeto a {objeto}, conforme especificações do Termo de "
                       f"Referência e da proposta da CONTRATADA, que integram este instrumento."]),
        ("DA VIGÊNCIA", [f"O prazo de vigência deste contrato é de {meses} ({_num_ext(meses)}) meses, com início "
                         f"em {br(inicio)} e término em {br(fim)}, podendo ser prorrogado na forma da lei.",
                         "A prorrogação dependerá de justificativa, de pesquisa de preços que demonstre a "
                         "vantajosidade e de manifestação favorável do fiscal do contrato."]),
        ("DO VALOR", [f"O valor global do contrato é de {moeda(valor)}, para todo o período de vigência.",
                      f"O valor mensal estimado é de {moeda(round(valor / meses, 2))}."]),
        ("DA DOTAÇÃO ORÇAMENTÁRIA", ["As despesas correrão à conta do Programa de Trabalho 04.122.0001.2001, "
                                     "Natureza de Despesa 3.3.90.39, Fonte 1.500."]),
        ("DO PAGAMENTO", ["O pagamento será efetuado em até 30 (trinta) dias contados do atesto da nota fiscal "
                          "pelo fiscal do contrato.",
                          "Nenhum pagamento será realizado sem a comprovação da regularidade fiscal e trabalhista "
                          "da CONTRATADA."]),
        ("DO REAJUSTE", ["Os preços serão reajustáveis após 12 (doze) meses da data do orçamento estimado, pelo "
                         "Índice de Preços ao Consumidor Amplo (IPCA), mediante apostilamento."]),
        ("DA FISCALIZAÇÃO", ["A execução será acompanhada por fiscal designado em portaria, que anotará em "
                             "registro próprio as ocorrências e determinará a regularização das faltas."]),
        ("DAS SANÇÕES", ["Pela inexecução total ou parcial, a CONTRATADA ficará sujeita às sanções de advertência, "
                         "multa de até 10% (dez por cento) do valor do contrato, impedimento de licitar e "
                         "declaração de inidoneidade, assegurados o contraditório e a ampla defesa."]),
        *extra_clausulas,
        ("DA EXTINÇÃO", ["O contrato poderá ser extinto antecipadamente nas hipóteses previstas em lei, "
                         "mediante decisão fundamentada e prévia notificação da CONTRATADA."]),
        ("DO FORO", ["Fica eleito o foro da Comarca da Capital do Estado de Vale Verde para dirimir as questões "
                     "decorrentes deste contrato."]),
    ]
    blocos = []
    for i, (tit, paras) in enumerate(cl):
        rot = f"cláusula {ORDINAIS[i].lower()}"
        linhas = [(f"{rot}, item {i + 1}.{j + 1}", f"{i + 1}.{j + 1}. {p}") for j, p in enumerate(paras)]
        blocos.append(Bloco(rot, "clausula", f"CLÁUSULA {ORDINAIS[i]} – {tit}", linhas))
    doc = Doc(ident, pid, f"{ident}_contrato_{numero.replace('/', '-')}", formato, "contrato", numero, inicio,
              f"CONTRATO Nº {numero}",
              [f"PROCESSO Nº {processo}",
               f"CONTRATO Nº {numero} QUE ENTRE SI CELEBRAM O {ESTADO}, POR MEIO DA {ORGAO.upper()}, E A EMPRESA "
               f"{contratada.upper().rstrip('.')}.",
               f"O {ESTADO}, por meio da {ORGAO} ({SIGLA}), doravante CONTRATANTE, e a empresa {contratada}, inscrita "
               f"no CNPJ sob o nº {c}, neste ato representada por {representante}, doravante CONTRATADA, resolvem "
               f"celebrar o presente contrato, com fundamento na Lei nº 14.133, de 1º de abril de 2021, mediante "
               f"as cláusulas seguintes."],
              blocos,
              [f"Capital do Estado de Vale Verde, {extenso(inicio - timedelta(days=2))}.",
               *assinatura("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"),
               *assinatura(f"Representante legal de {contratada}", representante)],
              fatos={"objeto": objeto, "contratada": contratada, "cnpj": c, "valor_global": moeda(valor),
                     "vigencia_inicio": br(inicio), "vigencia_fim": br(fim), "processo": processo,
                     "data_assinatura": br(inicio - timedelta(days=2))})
    DOCS.append(doc)
    return doc


def _num_ext(n):
    return {6: "seis", 12: "doze", 24: "vinte e quatro", 18: "dezoito", 30: "trinta", 3: "três", 4: "quatro",
            60: "sessenta", 90: "noventa", 120: "cento e vinte"}.get(n, str(n))


def termo_aditivo(pid, ident, ordem, contrato_doc, data_ass, clausulas, formato="docx", fatos=None):
    nomes = ["PRIMEIRO", "SEGUNDO", "TERCEIRO", "QUARTO"]
    numero = f"{ordem}º TA ao Contrato {contrato_doc.numero}"
    blocos = []
    for i, (tit, paras) in enumerate(clausulas):
        rot = f"cláusula {ORDINAIS[i].lower()}"
        linhas = [(f"{rot}, item {i + 1}.{j + 1}", f"{i + 1}.{j + 1}. {p}") for j, p in enumerate(paras)]
        blocos.append(Bloco(rot, "clausula", f"CLÁUSULA {ORDINAIS[i]} – {tit}", linhas))
    doc = Doc(ident, pid, f"{ident}_{ordem}o_termo_aditivo_{contrato_doc.numero.replace('/', '-')}", formato,
              "aditivo", numero, data_ass, f"{nomes[ordem - 1]} TERMO ADITIVO AO CONTRATO Nº {contrato_doc.numero}",
              [f"PROCESSO Nº {contrato_doc.fatos['processo']}",
               f"{nomes[ordem - 1]} TERMO ADITIVO AO CONTRATO Nº {contrato_doc.numero}, celebrado entre o "
               f"{ESTADO}, por meio da {ORGAO}, e a empresa {contrato_doc.fatos['contratada']}, inscrita no CNPJ "
               f"sob o nº {contrato_doc.fatos['cnpj']}."],
              blocos,
              [f"Capital do Estado de Vale Verde, {extenso(data_ass)}.",
               *assinatura("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda")],
              fatos=fatos or {})
    DOCS.append(doc)
    return doc


def documento_livre(pid, ident, tipo, numero, data_doc, titulo, paragrafos, formato="txt", fatos=None,
                    assinante=("Fiscal do Contrato", "Rogério Antunes Siqueira")):
    blocos = [Bloco("", "livre", "", [(None, p) for p in paragrafos])]
    doc = Doc(ident, pid, f"{ident}_{tipo}_{numero.replace('/', '-').replace(' ', '_')}", formato, tipo, numero,
              data_doc, titulo, [f"{ORGAO.upper()} — {SIGLA}"], blocos,
              [f"Capital do Estado de Vale Verde, {extenso(data_doc)}.", *assinatura(*assinante)], fatos=fatos or {})
    DOCS.append(doc)
    return doc


def norma(pid, ident, especie, numero, data_doc, ementa, artigos, formato="docx", fatos=None, autoridade=None):
    """artigos: lista de (caput, [(tipo, texto)]) com tipo em paragrafo|unico|inciso."""
    nomes = {"lei": "LEI", "decreto": "DECRETO", "portaria": "PORTARIA", "instrucao_normativa": "INSTRUÇÃO NORMATIVA",
             "orientacao": "ORIENTAÇÃO NORMATIVA"}
    blocos = []
    for i, (caput, subs) in enumerate(artigos, start=1):
        rot_art = f"art. {i}º" if i < 10 else f"art. {i}"
        cabeca = f"Art. {i}º" if i < 10 else f"Art. {i}."
        linhas, par, inc = [], 0, 0
        for tipo, texto in subs:
            if tipo == "inciso":
                rom = ROMANOS[inc]
                inc += 1
                linhas.append((f"{rot_art}, {rom}", f"{rom} – {texto}"))
            elif tipo == "unico":
                linhas.append((f"{rot_art}, parágrafo único", f"Parágrafo único. {texto}"))
            else:
                par += 1
                linhas.append((f"{rot_art}, § {par}º", f"§ {par}º {texto}"))
        blocos.append(Bloco(rot_art, "artigo", f"{cabeca} {caput}", linhas))
    titulo = f"{nomes[especie]} Nº {numero}, DE {extenso(data_doc).upper()}"
    autoridade = autoridade or ("O GOVERNADOR DO ESTADO DE VALE VERDE, no uso das atribuições que lhe confere a "
                                "Constituição Estadual," if especie in ("decreto", "lei")
                                else "O SECRETÁRIO DE ESTADO DE GESTÃO PÚBLICA, no uso de suas atribuições legais,")
    verbo = "DECRETA:" if especie == "decreto" else ("Faço saber que a Assembleia Legislativa aprovou e eu "
                                                      "sanciono a seguinte Lei:" if especie == "lei" else "RESOLVE:")
    doc = Doc(ident, pid, f"{ident}_{especie}_{numero.replace('/', '-')}", formato, especie, numero, data_doc, titulo,
              [ementa, autoridade, verbo], blocos,
              [f"Capital do Estado de Vale Verde, {extenso(data_doc)}.",
               *assinatura("Governador do Estado" if especie in ("decreto", "lei")
                           else "Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda")],
              fatos=fatos or {}, especie=especie)
    DOCS.append(doc)
    return doc


# ---------------------------------------------------------------- processos

def gerar():
    # P01 — Limpeza: contrato → 1º TA (prorrogação) → apostilamento (reajuste) → 2º TA (acréscimo) →
    #        notificação → rescisão (ruptura)
    c = contrato("P01_limpeza", "S001", "012/2023", 2023, "prestação de serviços continuados de limpeza e "
                 "conservação predial na sede da SEGEP/VV", "Brilho Serviços Gerais Ltda.", "41258763",
                 1_200_000.00, date(2023, 3, 1), 12)
    ta1 = termo_aditivo("P01_limpeza", "S002", 1, c, date(2024, 2, 20), [
        ("DO OBJETO", ["O presente termo aditivo tem por objeto a prorrogação da vigência do Contrato nº 012/2023."]),
        ("DA PRORROGAÇÃO", ["Fica prorrogada a vigência do Contrato nº 012/2023 por 12 (doze) meses, passando o "
                            "término de 29/02/2024 para 28/02/2025."]),
        ("DA RATIFICAÇÃO", ["Ficam ratificadas as demais cláusulas do contrato original não alteradas por este "
                            "termo."])], fatos={"vigencia_fim": "28/02/2025", "prorrogacao_meses": 12})
    rel("S001", "S002", "aditivo", "Fica prorrogada a vigência do Contrato nº 012/2023 por 12 (doze) meses")
    ap = documento_livre("P01_limpeza", "S003", "apostilamento", "001/2024", date(2024, 3, 15),
                         "APOSTILAMENTO Nº 001/2024 AO CONTRATO Nº 012/2023",
                         ["Fica apostilado ao Contrato nº 012/2023 o reajuste anual dos preços pelo IPCA acumulado "
                          "de 4,50% (quatro inteiros e cinquenta centésimos por cento), conforme a cláusula sexta.",
                          "Em razão do reajuste, o valor mensal passa de R$ 100.000,00 para R$ 104.500,00, a partir "
                          "de 01/03/2024.", "Ficam mantidas as demais condições contratuais."],
                         formato="pdf", fatos={"valor_mensal": "R$ 104.500,00", "indice": "IPCA 4,50%"},
                         assinante=("Coordenador de Contratos", "Paulo Henrique Veloso"))
    rel("S001", "S003", "alteracao", "o valor mensal passa de R$ 100.000,00 para R$ 104.500,00")
    ta2 = termo_aditivo("P01_limpeza", "S004", 2, c, date(2024, 8, 5), [
        ("DO OBJETO", ["O presente termo aditivo tem por objeto o acréscimo quantitativo de 10% (dez por cento) "
                       "sobre o valor inicial atualizado do Contrato nº 012/2023, para inclusão do anexo "
                       "administrativo."]),
        ("DO VALOR", ["Em decorrência do acréscimo, o valor mensal passa a ser de R$ 114.950,00 e o valor global "
                      "remanescente do período é acrescido de R$ 73.150,00."]),
        ("DA RATIFICAÇÃO", ["Ficam ratificadas as demais cláusulas."])], formato="pdf",
        fatos={"valor_mensal": "R$ 114.950,00", "acrescimo": "10%"})
    rel("S001", "S004", "aditivo", "acréscimo quantitativo de 10% (dez por cento) sobre o valor inicial atualizado")
    nt = documento_livre("P01_limpeza", "S005", "notificacao", "023/2024", date(2024, 10, 2),
                         "NOTIFICAÇÃO Nº 023/2024 — CONTRATO Nº 012/2023",
                         ["Notificamos a empresa Brilho Serviços Gerais Ltda. de que, nas vistorias de 16/09/2024 a "
                          "27/09/2024, foram constatadas faltas de postos de serviço em 9 (nove) dias úteis.",
                          "Fica concedido o prazo de 5 (cinco) dias úteis para apresentação de defesa prévia, sob "
                          "pena de aplicação das sanções previstas na cláusula oitava do contrato."])
    rel("S001", "S005", "continuacao", "foram constatadas faltas de postos de serviço")
    rs = documento_livre("P01_limpeza", "S006", "termo_rescisao", "002/2024", date(2024, 11, 18),
                         "TERMO DE RESCISÃO UNILATERAL DO CONTRATO Nº 012/2023",
                         ["Considerando a Notificação nº 023/2024 e a ausência de defesa no prazo concedido, fica "
                          "rescindido unilateralmente o Contrato nº 012/2023, a partir de 30/11/2024.",
                          "A CONTRATADA fica sujeita à multa de 5% (cinco por cento) sobre o valor do contrato, sem "
                          "prejuízo da apuração de outras responsabilidades."],
                         formato="docx", fatos={"data_extincao": "30/11/2024"},
                         assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S001", "S006", "ruptura", "fica rescindido unilateralmente o Contrato nº 012/2023")
    rel("S005", "S006", "continuacao", "Considerando a Notificação nº 023/2024")
    _ = (ta1, ap, ta2, nt, rs)

    # P02 — TI: contrato → suspensão (ruptura) → ordem de reinício (retomada) → 1º TA prazo
    c2 = contrato("P02_ti", "S010", "031/2023", 2023, "prestação de serviços de suporte técnico e sustentação "
                  "do sistema de protocolo eletrônico", "Nuvem Clara Tecnologia S.A.", "63014527", 960_000.00,
                  date(2023, 7, 1), 12, formato="pdf")
    documento_livre("P02_ti", "S011", "ordem_suspensao", "004/2023", date(2023, 10, 10),
                         "ORDEM DE SUSPENSÃO Nº 004/2023 — CONTRATO Nº 031/2023",
                         ["Fica suspensa, a partir de 11/10/2023, a execução do Contrato nº 031/2023, em razão da "
                          "migração da infraestrutura do datacenter, por até 60 (sessenta) dias.",
                          "Durante a suspensão não haverá medição nem pagamento de serviços."], formato="txt",
                         assinante=("Gestor do Contrato", "Luciana Prado Monteiro"))
    rel("S010", "S011", "ruptura", "Fica suspensa, a partir de 11/10/2023, a execução do Contrato nº 031/2023")
    documento_livre("P02_ti", "S012", "ordem_reinicio", "005/2023", date(2023, 12, 4),
                         "ORDEM DE REINÍCIO Nº 005/2023 — CONTRATO Nº 031/2023",
                         ["Concluída a migração, fica retomada a execução do Contrato nº 031/2023 a partir de "
                          "05/12/2023, com devolução do prazo de 55 (cinquenta e cinco) dias de suspensão."],
                         formato="txt", assinante=("Gestor do Contrato", "Luciana Prado Monteiro"))
    rel("S011", "S012", "retomada", "fica retomada a execução do Contrato nº 031/2023 a partir de 05/12/2023")
    termo_aditivo("P02_ti", "S013", 1, c2, date(2024, 6, 20), [
        ("DO OBJETO", ["Prorrogação da vigência do Contrato nº 031/2023 por 12 (doze) meses, acrescida da devolução "
                       "do prazo de suspensão."]),
        ("DA VIGÊNCIA", ["A vigência passa a encerrar-se em 24/08/2025."])], fatos={"vigencia_fim": "24/08/2025"})
    rel("S010", "S013", "aditivo", "Prorrogação da vigência do Contrato nº 031/2023 por 12 (doze) meses")

    # P03 — Vigilância: contrato → relatório com valor divergente (contradição) → 1º TA
    c3 = contrato("P03_vigilancia", "S020", "044/2023", 2023, "prestação de serviços de vigilância patrimonial "
                  "armada e desarmada", "Guardião Segurança Patrimonial Ltda.", "27840396", 2_340_000.00,
                  date(2023, 9, 1), 24)
    documento_livre("P03_vigilancia", "S021", "relatorio_fiscalizacao", "007/2024", date(2024, 3, 8),
                         "RELATÓRIO DE FISCALIZAÇÃO Nº 007/2024 — CONTRATO Nº 044/2023",
                         ["O Contrato nº 044/2023, de valor global de R$ 2.430.000,00, foi executado regularmente no "
                          "período de janeiro e fevereiro de 2024.",
                          "Não foram registradas ocorrências relevantes. Recomenda-se a manutenção dos postos."],
                         formato="docx", fatos={"valor_global_declarado": "R$ 2.430.000,00"})
    rel("S020", "S021", "contradicao", "de valor global de R$ 2.430.000,00")
    CONTRADICOES.append({"documentos": ["S020", "S021"], "campo": "valor_global",
                         "valores": {"S020": "R$ 2.340.000,00", "S021": "R$ 2.430.000,00"}})
    termo_aditivo("P03_vigilancia", "S022", 1, c3, date(2025, 8, 15), [
        ("DO OBJETO", ["Prorrogação do Contrato nº 044/2023 por mais 12 (doze) meses."]),
        ("DA VIGÊNCIA", ["O término da vigência passa de 31/08/2025 para 31/08/2026."]),
        ("DO VALOR", ["O valor do período prorrogado é de R$ 1.216.800,00."])], formato="pdf",
        fatos={"vigencia_fim": "31/08/2026", "valor_prorrogacao": "R$ 1.216.800,00"})
    rel("S020", "S022", "aditivo", "Prorrogação do Contrato nº 044/2023 por mais 12 (doze) meses")

    # P04 — Portarias internas: Portaria 010/2023 → Portaria 025/2024 (alteração) → Portaria 040/2025 (revogação)
    p1 = norma("P04_portarias_fiscalizacao", "S030", "portaria", "010/2023", date(2023, 2, 14),
               "Dispõe sobre a designação e as atribuições dos fiscais de contratos no âmbito da SEGEP/VV.", [
                   ("Esta Portaria disciplina a fiscalização dos contratos administrativos da SEGEP/VV.", []),
                   ("Compete ao fiscal técnico do contrato:", [
                       ("inciso", "acompanhar a execução do objeto e registrar as ocorrências;"),
                       ("inciso", "atestar as notas fiscais no prazo de 5 (cinco) dias úteis;"),
                       ("inciso", "comunicar ao gestor as falhas que demandem aplicação de sanções.")]),
                   ("O fiscal será designado por portaria específica para cada contrato.", [
                       ("paragrafo", "A designação recairá preferencialmente em servidor efetivo."),
                       ("paragrafo", "O fiscal substituto atuará nas ausências do titular.")]),
                   ("Esta Portaria entra em vigor na data de sua publicação.", [])])
    p2 = norma("P04_portarias_fiscalizacao", "S031", "portaria", "025/2024", date(2024, 5, 6),
               "Altera a Portaria nº 010/2023, que dispõe sobre a fiscalização de contratos.", [
                   ("O inciso II do art. 2º da Portaria nº 010/2023 passa a vigorar com a seguinte redação: "
                    "\"II – atestar as notas fiscais no prazo de 3 (três) dias úteis;\"", []),
                   ("Esta Portaria entra em vigor na data de sua publicação.", [])])
    rel("S030", "S031", "alteracao", "O inciso II do art. 2º da Portaria nº 010/2023 passa a vigorar com a seguinte "
                                     "redação")
    p3 = norma("P04_portarias_fiscalizacao", "S032", "portaria", "040/2025", date(2025, 3, 10),
               "Institui o Manual de Gestão e Fiscalização de Contratos e revoga as Portarias nº 010/2023 e "
               "nº 025/2024.", [
                   ("Fica instituído o Manual de Gestão e Fiscalização de Contratos da SEGEP/VV.", []),
                   ("O fiscal técnico atestará as notas fiscais no prazo de 2 (dois) dias úteis.", []),
                   ("Ficam revogadas a Portaria nº 010/2023 e a Portaria nº 025/2024.", []),
                   ("Esta Portaria entra em vigor na data de sua publicação.", [])], formato="pdf")
    rel("S030", "S032", "revogacao", "Ficam revogadas a Portaria nº 010/2023 e a Portaria nº 025/2024")
    rel("S031", "S032", "revogacao", "Ficam revogadas a Portaria nº 010/2023 e a Portaria nº 025/2024")
    _ = (p1, p2, p3)

    # P05 — Instruções normativas: IN 01/2022 substituída integralmente pela IN 03/2025 (substituição)
    in1 = norma("P05_in_pesquisa_precos", "S040", "instrucao_normativa", "01/2022", date(2022, 6, 1),
                "Estabelece procedimentos para a pesquisa de preços nas contratações da SEGEP/VV.", [
                    ("A pesquisa de preços observará, no mínimo, 3 (três) cotações válidas.", [
                        ("unico", "Admite-se número inferior mediante justificativa da autoridade competente.")]),
                    ("São parâmetros da pesquisa:", [
                        ("inciso", "painel de preços governamental;"),
                        ("inciso", "contratações similares de outros entes nos últimos 12 meses;"),
                        ("inciso", "cotações diretas com fornecedores.")]),
                    ("Esta Instrução Normativa entra em vigor na data de sua publicação.", [])], formato="docx")
    in3 = norma("P05_in_pesquisa_precos", "S041", "instrucao_normativa", "03/2025", date(2025, 4, 2),
                "Dispõe sobre a pesquisa de preços e substitui integralmente a Instrução Normativa nº 01/2022.", [
                    ("Esta Instrução Normativa substitui integralmente a Instrução Normativa nº 01/2022.", []),
                    ("A pesquisa de preços observará, no mínimo, 4 (quatro) cotações válidas, priorizando o painel "
                     "de preços governamental.", [
                        ("paragrafo", "Cotações com mais de 180 (cento e oitenta) dias serão desconsideradas."),
                        ("paragrafo", "A justificativa para número inferior será aprovada pelo ordenador de "
                                      "despesas.")]),
                    ("Esta Instrução Normativa entra em vigor na data de sua publicação.", [])], formato="docx")
    rel("S040", "S041", "substituicao", "substitui integralmente a Instrução Normativa nº 01/2022")
    CONTRADICOES.append({"documentos": ["S040", "S041"], "campo": "numero_minimo_cotacoes",
                         "valores": {"S040": "3", "S041": "4"}, "observacao": "resolvida por substituição"})
    _ = (in1, in3)

    # P06 — Lei estadual fictícia → decreto que a regulamenta → decreto posterior que revoga o anterior
    lei = norma("P06_lei_estadual_compras", "S050", "lei", "11.205/2022", date(2022, 11, 23),
                "Dispõe sobre normas gerais de compras sustentáveis no Estado de Vale Verde.", [
                    ("As contratações públicas estaduais observarão critérios de sustentabilidade ambiental.", []),
                    ("São critérios de sustentabilidade, entre outros:", [
                        ("inciso", "menor impacto sobre recursos naturais;"),
                        ("inciso", "preferência por materiais recicláveis;"),
                        ("inciso", "eficiência energética.")]),
                    ("O Poder Executivo regulamentará esta Lei no prazo de 180 (cento e oitenta) dias.", []),
                    ("Esta Lei entra em vigor na data de sua publicação.", [])], formato="pdf")
    d1 = norma("P06_lei_estadual_compras", "S051", "decreto", "1.410/2023", date(2023, 4, 18),
               "Regulamenta a Lei nº 11.205, de 23 de novembro de 2022, que dispõe sobre compras sustentáveis.", [
                   ("Este Decreto regulamenta a Lei nº 11.205, de 23 de novembro de 2022.", []),
                   ("Os termos de referência deverão conter seção específica de critérios de sustentabilidade.", [
                       ("unico", "A ausência da seção deverá ser justificada pelo requisitante.")]),
                   ("Este Decreto entra em vigor na data de sua publicação.", [])])
    rel("S050", "S051", "regulamenta", "Este Decreto regulamenta a Lei nº 11.205, de 23 de novembro de 2022")
    d2 = norma("P06_lei_estadual_compras", "S052", "decreto", "2.087/2025", date(2025, 2, 11),
               "Regulamenta a Lei nº 11.205, de 23 de novembro de 2022, e revoga o Decreto nº 1.410, de 18 de abril "
               "de 2023.", [
                   ("Este Decreto regulamenta a Lei nº 11.205, de 23 de novembro de 2022, quanto às compras "
                    "sustentáveis.", []),
                   ("Os termos de referência conterão matriz de critérios de sustentabilidade com pontuação "
                    "mínima.", []),
                   ("Fica revogado o Decreto nº 1.410, de 18 de abril de 2023.", []),
                   ("Este Decreto entra em vigor na data de sua publicação.", [])], formato="txt")
    rel("S051", "S052", "revogacao", "Fica revogado o Decreto nº 1.410, de 18 de abril de 2023")
    rel("S050", "S052", "regulamenta", "Este Decreto regulamenta a Lei nº 11.205, de 23 de novembro de 2022")
    _ = (lei, d1, d2)

    # P07 — Manutenção predial: contrato → 1º TA (vigência até 30/06/2025) → apostilamento com data divergente
    c7 = contrato("P07_manutencao", "S060", "058/2023", 2023, "prestação de serviços de manutenção predial "
                  "preventiva e corretiva", "Construtora Alicerce Forte Ltda.", "52713608", 780_000.00,
                  date(2023, 7, 1), 12, formato="docx")
    termo_aditivo("P07_manutencao", "S061", 1, c7, date(2024, 6, 10), [
        ("DO OBJETO", ["Prorrogação da vigência do Contrato nº 058/2023 por 12 (doze) meses."]),
        ("DA VIGÊNCIA", ["O término da vigência passa de 30/06/2024 para 30/06/2025."])],
        fatos={"vigencia_fim": "30/06/2025"})
    rel("S060", "S061", "aditivo", "Prorrogação da vigência do Contrato nº 058/2023 por 12 (doze) meses")
    documento_livre("P07_manutencao", "S062", "apostilamento", "004/2024", date(2024, 9, 2),
                    "APOSTILAMENTO Nº 004/2024 AO CONTRATO Nº 058/2023",
                    ["Registra-se o reajuste de 3,90% (três inteiros e noventa centésimos por cento) pelo IPCA.",
                     "Para fins de registro, a vigência do Contrato nº 058/2023 encerra-se em 30/07/2025."],
                    formato="pdf_digitalizado", fatos={"vigencia_fim_declarada": "30/07/2025"},
                    assinante=("Coordenador de Contratos", "Paulo Henrique Veloso"))
    rel("S061", "S062", "contradicao", "a vigência do Contrato nº 058/2023 encerra-se em 30/07/2025")
    CONTRADICOES.append({"documentos": ["S061", "S062"], "campo": "vigencia_fim",
                         "valores": {"S061": "30/06/2025", "S062": "30/07/2025"}})

    # P08 — Obra: contrato → paralisação (ruptura) → retomada → 1º TA valor → medição
    c8 = contrato("P08_obra_escola", "S070", "072/2024", 2024, "execução de obra de reforma e ampliação da "
                  "Escola Estadual Pedra Azul", "Engenharia Horizonte Ltda.", "38506214", 3_850_000.00,
                  date(2024, 2, 1), 18, formato="pdf",
                  extra_clausulas=[("DO CRONOGRAMA", ["A execução observará o cronograma físico-financeiro anexo, "
                                                      "com 6 (seis) etapas de medição."])])
    documento_livre("P08_obra_escola", "S071", "termo_paralisacao", "001/2024", date(2024, 6, 3),
                    "TERMO DE PARALISAÇÃO Nº 001/2024 — CONTRATO Nº 072/2024",
                    ["Fica paralisada a obra objeto do Contrato nº 072/2024 a partir de 04/06/2024, em razão de "
                     "chuvas intensas que comprometeram as fundações.", "O prazo de execução ficará suspenso "
                     "durante a paralisação."], formato="pdf_digitalizado",
                    assinante=("Engenheiro Fiscal", "Tatiana Rezende Coutinho"))
    rel("S070", "S071", "ruptura", "Fica paralisada a obra objeto do Contrato nº 072/2024")
    documento_livre("P08_obra_escola", "S072", "ordem_reinicio", "002/2024", date(2024, 8, 19),
                    "ORDEM DE REINÍCIO Nº 002/2024 — CONTRATO Nº 072/2024",
                    ["Fica autorizada a retomada da obra objeto do Contrato nº 072/2024 a partir de 20/08/2024, com "
                     "devolução de 77 (setenta e sete) dias ao prazo de execução."], formato="txt",
                    assinante=("Engenheiro Fiscal", "Tatiana Rezende Coutinho"))
    rel("S071", "S072", "retomada", "Fica autorizada a retomada da obra objeto do Contrato nº 072/2024")
    termo_aditivo("P08_obra_escola", "S073", 1, c8, date(2024, 12, 9), [
        ("DO OBJETO", ["Acréscimo de serviços de drenagem não previstos no projeto básico do Contrato nº "
                       "072/2024."]),
        ("DO VALOR", ["O valor global do contrato passa de R$ 3.850.000,00 para R$ 4.235.000,00, representando "
                      "acréscimo de 10% (dez por cento)."])], formato="docx",
        fatos={"valor_global": "R$ 4.235.000,00"})
    rel("S070", "S073", "aditivo", "O valor global do contrato passa de R$ 3.850.000,00 para R$ 4.235.000,00")
    documento_livre("P08_obra_escola", "S074", "boletim_medicao", "04/2025", date(2025, 3, 5),
                    "BOLETIM DE MEDIÇÃO Nº 04/2025 — CONTRATO Nº 072/2024",
                    ["Medição da 4ª etapa do cronograma físico-financeiro: execução acumulada de 62% (sessenta e "
                     "dois por cento).", "Valor da medição: R$ 412.300,00."], formato="txt",
                    fatos={"valor_medicao": "R$ 412.300,00"},
                    assinante=("Engenheiro Fiscal", "Tatiana Rezende Coutinho"))
    rel("S072", "S074", "continuacao", "Medição da 4ª etapa do cronograma físico-financeiro")

    # P09 — Instrução de compra: termo de referência → parecer jurídico → despacho → contrato
    documento_livre("P09_compra_mobiliario", "S080", "termo_referencia", "015/2024", date(2024, 4, 3),
                    "TERMO DE REFERÊNCIA Nº 015/2024 — AQUISIÇÃO DE MOBILIÁRIO",
                    ["Objeto: aquisição de 300 (trezentas) cadeiras ergonômicas e 120 (cento e vinte) estações de "
                     "trabalho.", "Valor estimado: R$ 486.000,00, conforme pesquisa de preços com 4 (quatro) "
                     "cotações.", "Critério de sustentabilidade: madeira certificada e embalagens recicláveis."],
                    formato="docx", fatos={"valor_estimado": "R$ 486.000,00"},
                    assinante=("Requisitante", "Cláudia Ferraz Nogueira"))
    documento_livre("P09_compra_mobiliario", "S081", "parecer_juridico", "118/2024", date(2024, 5, 7),
                    "PARECER JURÍDICO Nº 118/2024 — PROCESSO SEGEP-PRO-2024/00081",
                    ["Trata-se de análise prévia da contratação descrita no Termo de Referência nº 015/2024.",
                     "Opina-se pela regularidade do procedimento, condicionada à juntada da declaração de "
                     "disponibilidade orçamentária.", "É o parecer, sub censura."], formato="pdf",
                    assinante=("Procuradora do Estado", "Beatriz Almeida Toledo"))
    rel("S080", "S081", "continuacao", "análise prévia da contratação descrita no Termo de Referência nº 015/2024")
    documento_livre("P09_compra_mobiliario", "S082", "despacho", "233/2024", date(2024, 5, 14),
                    "DESPACHO Nº 233/2024 — PROCESSO SEGEP-PRO-2024/00081",
                    ["Acolho o Parecer Jurídico nº 118/2024 e autorizo a abertura do pregão eletrônico, após a "
                     "juntada da declaração orçamentária solicitada."], formato="txt",
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S081", "S082", "continuacao", "Acolho o Parecer Jurídico nº 118/2024")
    c9 = contrato("P09_compra_mobiliario", "S083", "081/2024", 2024, "aquisição de mobiliário corporativo",
                  "Móveis Ergonomia do Cerrado Ltda.", "71092384", 452_700.00, date(2024, 7, 1), 6, formato="docx")
    rel("S082", "S083", "continuacao", "aquisição de mobiliário corporativo")
    _ = c9

    # P10 — Convênio: termo → denúncia (ruptura) → novo termo de retomada
    documento_livre("P10_convenio_capacitacao", "S090", "convenio", "007/2023", date(2023, 5, 2),
                    "CONVÊNIO Nº 007/2023 — CAPACITAÇÃO DE SERVIDORES",
                    ["Convênio entre a SEGEP/VV e o Instituto Vale Verde de Educação Continuada para capacitação "
                     "de 600 (seiscentos) servidores em gestão de contratos.",
                     "Valor do repasse: R$ 320.000,00, em 4 (quatro) parcelas.", "Vigência: 02/05/2023 a "
                     "01/05/2025."], formato="pdf",
                    fatos={"valor_repasse": "R$ 320.000,00", "vigencia_fim": "01/05/2025"},
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    documento_livre("P10_convenio_capacitacao", "S091", "denuncia_convenio", "001/2024", date(2024, 4, 22),
                    "TERMO DE DENÚNCIA DO CONVÊNIO Nº 007/2023",
                    ["Fica denunciado o Convênio nº 007/2023, com interrupção das turmas a partir de 30/04/2024, "
                     "por pendência na prestação de contas da 2ª parcela.",
                     "O convenente deverá restituir os saldos não aplicados."], formato="docx",
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S090", "S091", "ruptura", "Fica denunciado o Convênio nº 007/2023")
    documento_livre("P10_convenio_capacitacao", "S092", "termo_retomada", "001/2025", date(2025, 2, 3),
                    "TERMO DE RETOMADA DAS AÇÕES DO CONVÊNIO Nº 007/2023",
                    ["Aprovada a prestação de contas da 2ª parcela, ficam retomadas as ações de capacitação "
                     "previstas no Convênio nº 007/2023 a partir de 10/02/2025, restando 210 (duzentos e dez) "
                     "servidores a capacitar."], formato="txt",
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S091", "S092", "retomada", "ficam retomadas as ações de capacitação previstas no Convênio nº 007/2023")

    # P11 — Orientação normativa interna fundamentada em lei federal pública e decisões da gestão (precedentes)
    norma("P11_orientacoes_decisoes", "S100", "orientacao", "02/2024", date(2024, 1, 15),
          "Orienta sobre prorrogação de contratos de serviços contínuos.", [
              ("A prorrogação de contratos de serviços contínuos observará o art. 107 da Lei nº 14.133, de 1º de "
               "abril de 2021.", []),
              ("A instrução do processo de prorrogação conterá:", [
                  ("inciso", "manifestação do fiscal sobre a qualidade da execução;"),
                  ("inciso", "pesquisa de preços que demonstre vantajosidade;"),
                  ("inciso", "comprovação de regularidade fiscal e trabalhista;"),
                  ("inciso", "disponibilidade orçamentária.")]),
              ("Esta Orientação entra em vigor na data de sua publicação.", [])], formato="docx")
    rel("PUB:lei14133_2021", "S100", "fundamenta", "observará o art. 107 da Lei nº 14.133, de 1º de abril de 2021")
    documento_livre("P11_orientacoes_decisoes", "S101", "decisao_gestao", "DG-004/2024", date(2024, 2, 26),
                    "DECISÃO DA GESTÃO DG-004/2024 — PRORROGAÇÃO DO CONTRATO Nº 012/2023",
                    ["Contexto: pedido de prorrogação do Contrato nº 012/2023 (limpeza), com registro de 2 (duas) "
                     "advertências no período.",
                     "Decisão: prorrogar por 12 (doze) meses, condicionada a plano de ação da contratada e "
                     "fiscalização quinzenal.",
                     "Fundamentos: Orientação Normativa nº 02/2024 e pesquisa de preços favorável.",
                     "Resultado posterior: a contratada voltou a descumprir o contrato, que foi rescindido em "
                     "novembro de 2024. Avaliação do resultado: negativo."], formato="txt",
                    fatos={"decisao": "prorrogar com condicionantes", "avaliacao_resultado": "negativo"},
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S100", "S101", "fundamenta", "Fundamentos: Orientação Normativa nº 02/2024")
    documento_livre("P11_orientacoes_decisoes", "S102", "decisao_gestao", "DG-011/2025", date(2025, 7, 30),
                    "DECISÃO DA GESTÃO DG-011/2025 — PRORROGAÇÃO DO CONTRATO Nº 044/2023",
                    ["Contexto: pedido de prorrogação do Contrato nº 044/2023 (vigilância), sem ocorrências "
                     "relevantes e com preços abaixo da média de mercado.",
                     "Decisão: prorrogar por 12 (doze) meses.",
                     "Fundamentos: Orientação Normativa nº 02/2024, relatório de fiscalização favorável.",
                     "Resultado posterior: execução regular. Avaliação do resultado: positivo."], formato="txt",
                    fatos={"decisao": "prorrogar", "avaliacao_resultado": "positivo"},
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S100", "S102", "fundamenta", "Fundamentos: Orientação Normativa nº 02/2024")

    # P12 — Documentos com dados pessoais fictícios (anonimização, Fase 7) e ofício digitalizado
    documento_livre("P12_pessoal", "S110", "oficio", "321/2024", date(2024, 9, 12),
                    "OFÍCIO Nº 321/2024/SEGEP/VV",
                    [f"Encaminhamos o requerimento do servidor Joaquim Pereira Lins, CPF {cpf('123456789')}, "
                     "e-mail joaquim.lins@exemplo.vv.gov, telefone (99) 98877-1122, referente à designação como "
                     "fiscal do Contrato nº 072/2024.",
                     "Solicitamos manifestação no prazo de 10 (dez) dias."], formato="pdf_digitalizado",
                    fatos={"cpf": cpf("123456789"), "email": "joaquim.lins@exemplo.vv.gov"},
                    assinante=("Chefe de Gabinete", "Renata Lobo Sampaio"))
    documento_livre("P12_pessoal", "S111", "portaria_designacao", "112/2024", date(2024, 9, 20),
                    "PORTARIA Nº 112/2024 — DESIGNAÇÃO DE FISCAL",
                    [f"Designar o servidor Joaquim Pereira Lins, matrícula 204.551, CPF {cpf('123456789')}, para "
                     "atuar como fiscal técnico do Contrato nº 072/2024.",
                     f"Designar a servidora Ana Clara Moura Teles, matrícula 198.207, CPF {cpf('987654321')}, "
                     "como fiscal substituta."], formato="pdf_digitalizado",
                    fatos={"fiscal_titular": "Joaquim Pereira Lins"},
                    assinante=("Secretário de Estado de Gestão Pública", "Henrique Bastos Lacerda"))
    rel("S110", "S111", "continuacao", "para atuar como fiscal técnico do Contrato nº 072/2024")


# ---------------------------------------------------------------- famílias paramétricas (semente fixa)

OBJETOS = [
    ("prestação de serviços de copeiragem e recepção", "Servir Bem Apoio Administrativo Ltda.", "18273645"),
    ("locação de veículos com motorista para apoio às fiscalizações", "Rota Segura Locadora Ltda.", "29384756"),
    ("fornecimento de combustível por meio de cartão magnético", "Abastece Vale Verde Ltda.", "30495867"),
    ("prestação de serviços de manutenção de aparelhos de ar-condicionado", "Clima Frio Refrigeração Ltda.",
     "41506978"),
    ("prestação de serviços de outsourcing de impressão", "Imprime Fácil Soluções Ltda.", "52617089"),
    ("prestação de serviços de telefonia móvel corporativa", "Conecta Norte Telecomunicações S.A.", "63728190"),
    ("prestação de serviços de dedetização e controle de pragas", "Ambiente Limpo Saneamento Ltda.", "74839201"),
    ("fornecimento de água mineral em garrafões de 20 litros", "Fonte Serrana Águas Ltda.", "85940312"),
    ("prestação de serviços de digitalização de acervo documental", "Arquivo Vivo Gestão Documental Ltda.",
     "96051423"),
    ("prestação de serviços de jardinagem e paisagismo", "Verde Vida Paisagismo Ltda.", "17162534"),
]
FORMATOS = ["docx", "pdf", "txt"]


def familias_contratos(rng):
    seq = 200  # S201+ (S001–S111: processos manuais; S301+: famílias de normas)
    for i, (objeto, empresa, base) in enumerate(OBJETOS):
        pid = f"F{i + 1:02d}_contrato_{objeto.split()[3] if len(objeto.split()) > 3 else 'servico'}"
        pid = pid.replace("ç", "c").replace("ã", "a").replace("ó", "o").replace("é", "e")
        ano = 2022 + i % 3
        inicio = date(ano, 1 + (i * 2) % 12, 1)
        valor = float(rng.randrange(180, 2400) * 1000)
        meses = rng.choice([12, 12, 24])
        numero = f"{120 + i:03d}/{ano}"

        def novo_id():
            nonlocal seq
            seq += 1
            return f"S{seq:03d}"

        c = contrato(pid, novo_id(), numero, ano, objeto, empresa, base, valor, inicio, meses,
                     formato=FORMATOS[i % 3])
        fim = mais_meses(inicio, meses) - timedelta(days=1)
        novo_fim = mais_meses(fim + timedelta(days=1), 12) - timedelta(days=1)
        ta = termo_aditivo(pid, novo_id(), 1, c, fim - timedelta(days=20), [
            ("DO OBJETO", [f"Prorrogação da vigência do Contrato nº {numero} por 12 (doze) meses."]),
            ("DA VIGÊNCIA", [f"O término da vigência passa de {br(fim)} para {br(novo_fim)}."])],
            formato=FORMATOS[(i + 1) % 3], fatos={"vigencia_fim": br(novo_fim)})
        rel(c.id, ta.id, "aditivo", f"Prorrogação da vigência do Contrato nº {numero} por 12 (doze) meses")

        if rng.random() < 0.8:
            pct = rng.choice(["3,85%", "4,12%", "4,62%", "5,10%"])
            ap = documento_livre(pid, novo_id(), "apostilamento", f"{10 + i:03d}/{ano + 1}",
                                 mais_meses(inicio, 12) + timedelta(days=10),
                                 f"APOSTILAMENTO Nº {10 + i:03d}/{ano + 1} AO CONTRATO Nº {numero}",
                                 [f"Fica apostilado ao Contrato nº {numero} o reajuste pelo IPCA de {pct}, "
                                  f"alterando os preços unitários a partir do 13º mês de execução.",
                                  "Ficam mantidas as demais condições contratuais."],
                                 formato=FORMATOS[(i + 2) % 3], fatos={"reajuste": pct},
                                 assinante=("Coordenador de Contratos", "Paulo Henrique Veloso"))
            rel(c.id, ap.id, "alteracao", f"Fica apostilado ao Contrato nº {numero} o reajuste pelo IPCA de {pct}")

        if rng.random() < 0.6:
            divergente = moeda(valor * rng.choice([1.05, 1.1, 0.9]))
            rf = documento_livre(pid, novo_id(), "relatorio_fiscalizacao", f"{30 + i:03d}/{ano + 1}",
                                 mais_meses(inicio, 8), f"RELATÓRIO DE FISCALIZAÇÃO Nº {30 + i:03d}/{ano + 1} — "
                                 f"CONTRATO Nº {numero}",
                                 [f"O Contrato nº {numero}, de valor global de {divergente}, foi executado "
                                  "regularmente no período avaliado.",
                                  "Não há pendências de pagamento nem ocorrências graves."],
                                 formato="pdf_digitalizado" if i in (2, 7) else FORMATOS[i % 3],
                                 fatos={"valor_global_declarado": divergente})
            rel(c.id, rf.id, "contradicao", f"de valor global de {divergente}")
            CONTRADICOES.append({"documentos": [c.id, rf.id], "campo": "valor_global",
                                 "valores": {c.id: moeda(valor), rf.id: divergente}})

        if rng.random() < 0.5:
            d_susp = mais_meses(inicio, 4)
            sp = documento_livre(pid, novo_id(), "ordem_suspensao", f"{40 + i:03d}/{ano}", d_susp,
                                 f"ORDEM DE SUSPENSÃO Nº {40 + i:03d}/{ano} — CONTRATO Nº {numero}",
                                 [f"Fica suspensa a execução do Contrato nº {numero} a partir de "
                                  f"{br(d_susp + timedelta(days=1))}, por contingenciamento orçamentário."],
                                 formato="txt", assinante=("Gestor do Contrato", "Luciana Prado Monteiro"))
            rel(c.id, sp.id, "ruptura", f"Fica suspensa a execução do Contrato nº {numero}")
            d_rein = d_susp + timedelta(days=45)
            rn = documento_livre(pid, novo_id(), "ordem_reinicio", f"{50 + i:03d}/{ano}", d_rein,
                                 f"ORDEM DE REINÍCIO Nº {50 + i:03d}/{ano} — CONTRATO Nº {numero}",
                                 [f"Fica retomada a execução do Contrato nº {numero} a partir de "
                                  f"{br(d_rein + timedelta(days=1))}, com devolução do prazo suspenso."],
                                 formato="txt", assinante=("Gestor do Contrato", "Luciana Prado Monteiro"))
            rel(sp.id, rn.id, "retomada", f"Fica retomada a execução do Contrato nº {numero}")

        if rng.random() < 0.5:
            d_not = mais_meses(inicio, 15)
            nt = documento_livre(pid, novo_id(), "notificacao", f"{60 + i:03d}/{ano + 1}", d_not,
                                 f"NOTIFICAÇÃO Nº {60 + i:03d}/{ano + 1} — CONTRATO Nº {numero}",
                                 [f"Notificamos a empresa {empresa} pelo descumprimento reiterado de prazos de "
                                  f"atendimento previstos no Contrato nº {numero}.",
                                  "Fica concedido o prazo de 5 (cinco) dias úteis para defesa prévia."],
                                 formato=FORMATOS[i % 3])
            rel(c.id, nt.id, "continuacao", f"pelo descumprimento reiterado de prazos de atendimento previstos no "
                                            f"Contrato nº {numero}")
            rs = documento_livre(pid, novo_id(), "termo_rescisao", f"{70 + i:03d}/{ano + 1}",
                                 d_not + timedelta(days=30), f"TERMO DE RESCISÃO DO CONTRATO Nº {numero}",
                                 [f"Fica rescindido o Contrato nº {numero}, a partir de "
                                  f"{br(d_not + timedelta(days=40))}, por inexecução parcial."],
                                 formato="docx", assinante=("Secretário de Estado de Gestão Pública",
                                                            "Henrique Bastos Lacerda"))
            rel(c.id, rs.id, "ruptura", f"Fica rescindido o Contrato nº {numero}")
            num_novo = f"{200 + i:03d}/{ano + 1}"
            novo = contrato(pid, novo_id(), num_novo, ano + 1, objeto + " (contratação substituta)",
                            empresa.replace("Ltda.", "Serviços Ltda.") if "Ltda." in empresa else empresa + " II",
                            str(int(base) + 1111).zfill(8), valor * 1.08, d_not + timedelta(days=41), 12,
                            formato=FORMATOS[(i + 1) % 3],
                            extra_clausulas=[("DA SUBSTITUIÇÃO", [f"Este contrato substitui o Contrato nº {numero}, "
                                                                  "rescindido, para a continuidade do serviço."])])
            rel(c.id, novo.id, "substituicao", f"Este contrato substitui o Contrato nº {numero}")


def familias_normas(rng):
    temas = [("horário de expediente e atendimento ao público", "08h às 18h", "07h às 17h"),
             ("uso de veículos oficiais", "até 22h", "até 20h"),
             ("teletrabalho dos servidores", "2 (dois) dias por semana", "3 (três) dias por semana"),
             ("concessão de diárias", "R$ 280,00", "R$ 320,00"),
             ("gestão de riscos nas contratações", "anual", "semestral")]
    seq = 300
    for i, (tema, antes, depois) in enumerate(temas):
        pid = f"N{i + 1:02d}_normas_{tema.split()[0]}"
        ano = 2021 + i % 3
        base = f"{60 + i:03d}/{ano}"

        def novo_id():
            nonlocal seq
            seq += 1
            return f"S{seq:03d}"

        p1 = norma(pid, novo_id(), "portaria", base, date(ano, 3 + i, 10),
                   f"Disciplina o {tema} no âmbito da SEGEP/VV.", [
                       (f"Esta Portaria disciplina o {tema} no âmbito da SEGEP/VV.", []),
                       (f"Fica estabelecido o parâmetro de {antes} para o {tema}.", [
                           ("paragrafo", "Exceções serão autorizadas pelo Secretário Adjunto."),
                           ("paragrafo", "As chefias imediatas acompanharão o cumprimento desta norma.")]),
                       ("Compete à unidade de gestão de pessoas:", [
                           ("inciso", "divulgar esta Portaria;"), ("inciso", "monitorar sua aplicação;")]),
                       ("Esta Portaria entra em vigor na data de sua publicação.", [])], formato=FORMATOS[i % 3])
        num2 = f"{80 + i:03d}/{ano + 1}"
        p2 = norma(pid, novo_id(), "portaria", num2, date(ano + 1, 2 + i, 5),
                   f"Altera a Portaria nº {base}.", [
                       (f"O art. 2º da Portaria nº {base} passa a vigorar com o parâmetro de {depois}.", []),
                       ("Esta Portaria entra em vigor na data de sua publicação.", [])], formato=FORMATOS[(i + 1) % 3])
        rel(p1.id, p2.id, "alteracao", f"O art. 2º da Portaria nº {base} passa a vigorar com o parâmetro de {depois}")
        num3 = f"{95 + i:03d}/{ano + 2}"
        if i % 2 == 0:
            p3 = norma(pid, novo_id(), "portaria", num3, date(ano + 2, 1 + i, 20),
                       f"Disciplina integralmente o {tema} e substitui a Portaria nº {base}.", [
                           (f"Esta Portaria substitui integralmente a Portaria nº {base}.", []),
                           (f"O parâmetro para o {tema} passa a ser definido em plano anual aprovado pelo "
                            "Secretário.", []),
                           ("Esta Portaria entra em vigor na data de sua publicação.", [])], formato="docx")
            rel(p1.id, p3.id, "substituicao", f"Esta Portaria substitui integralmente a Portaria nº {base}")
        else:
            p3 = norma(pid, novo_id(), "portaria", num3, date(ano + 2, 1 + i, 20),
                       f"Revoga a Portaria nº {base} e a Portaria nº {num2}.", [
                           (f"Ficam revogadas a Portaria nº {base} e a Portaria nº {num2}.", []),
                           ("Esta Portaria entra em vigor na data de sua publicação.", [])], formato="txt")
            rel(p1.id, p3.id, "revogacao", f"Ficam revogadas a Portaria nº {base} e a Portaria nº {num2}")
            rel(p2.id, p3.id, "revogacao", f"Ficam revogadas a Portaria nº {base} e a Portaria nº {num2}")
        if rng.random() < 0.6:
            pub = rng.choice(["PUB:lei9784_1999", "PUB:lei8112_1990", "PUB:lei14133_2021"])
            lei_txt = {"PUB:lei9784_1999": "Lei nº 9.784, de 29 de janeiro de 1999",
                       "PUB:lei8112_1990": "Lei nº 8.112, de 11 de dezembro de 1990",
                       "PUB:lei14133_2021": "Lei nº 14.133, de 1º de abril de 2021"}[pub]
            ori = norma(pid, novo_id(), "orientacao", f"{10 + i:02d}/{ano + 1}", date(ano + 1, 6, 1),
                        f"Orienta a aplicação da Portaria nº {base}.", [
                            (f"A aplicação da Portaria nº {base} observará a {lei_txt}.", []),
                            ("Esta Orientação entra em vigor na data de sua publicação.", [])], formato="txt")
            rel(pub, ori.id, "fundamenta", f"observará a {lei_txt}")
            rel(p1.id, ori.id, "continuacao", f"Orienta a aplicação da Portaria nº {base}")


# ---------------------------------------------------------------- renderização

def linhas_documento(d: Doc):
    """Texto final, linha a linha, e o gabarito de dispositivos na ordem em que aparecem."""
    saida = [AVISO, "", ESTADO, ORGAO.upper(), "", d.titulo, ""]
    saida += [p for p in d.preambulo] + [""]
    dispositivos = []
    for b in d.blocos:
        if b.tipo != "livre":
            saida.append(b.titulo)
            dispositivos.append({"rotulo": b.rotulo, "tipo": b.tipo, "inicio": b.titulo[:40]})
        for rot, texto in b.linhas:
            saida.append(texto)
            if rot and b.tipo != "livre":
                dispositivos.append({"rotulo": rot, "tipo": "sub", "inicio": texto[:40]})
        saida.append("")
    saida += d.fecho
    return saida, dispositivos


def salvar_txt(caminho, linhas):
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def salvar_docx(caminho, linhas, d: Doc):
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.core_properties.title = d.titulo
    doc.core_properties.author = "SAD-GD — corpus sintético"
    doc.core_properties.created = datetime(d.data.year, d.data.month, d.data.day)
    for linha in linhas:
        p = doc.add_paragraph(linha)
        if linha in (d.titulo, ESTADO):
            p.runs[0].bold = True if p.runs else None
        for run in p.runs:
            run.font.size = Pt(11)
    doc.save(caminho)


def _fonte():
    for nome in ("arial.ttf", "DejaVuSans.ttf"):
        for pasta in (Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")):
            if (pasta / nome).is_file():
                return pasta / nome
    raise RuntimeError("Fonte TrueType não encontrada (Arial ou DejaVu Sans).")


def salvar_pdf(caminho, linhas, d: Doc):
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_creation_date(datetime(d.data.year, d.data.month, d.data.day))
    pdf.set_title(d.titulo)
    pdf.set_author("SAD-GD — corpus sintético")
    pdf.add_font("Base", "", str(_fonte()))
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    pdf.set_font("Base", size=11)
    for linha in linhas:
        if linha:
            pdf.multi_cell(0, 6, linha, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.ln(3)
    pdf.output(str(caminho))


def salvar_pdf_digitalizado(caminho, linhas, d: Doc):
    """Simula documento escaneado: texto renderizado como imagem (sem camada de texto) em 200 dpi."""
    import textwrap

    from fpdf import FPDF
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    largura, altura, margem = 1654, 2339, 140  # A4 em 200 dpi
    fonte = ImageFont.truetype(str(_fonte()), 30)
    paginas, y = [], margem
    img = Image.new("L", (largura, altura), 255)
    desenho = ImageDraw.Draw(img)
    for linha in linhas:
        partes = textwrap.wrap(linha, 92) or [""]
        for parte in partes:
            if y > altura - margem:
                paginas.append(img)
                img = Image.new("L", (largura, altura), 255)
                desenho = ImageDraw.Draw(img)
                y = margem
            desenho.text((margem, y), parte, fill=25, font=fonte)
            y += 44
    paginas.append(img)
    pdf = FPDF(format="A4")
    pdf.set_creation_date(datetime(d.data.year, d.data.month, d.data.day))
    temporarios = []
    for i, pagina in enumerate(paginas):
        pagina = pagina.rotate(0.4, fillcolor=255).filter(ImageFilter.GaussianBlur(0.6))  # leve ruído de scanner
        tmp = caminho.with_name(f".{caminho.stem}_p{i}.png")
        pagina.save(tmp)
        temporarios.append(tmp)
        pdf.add_page()
        pdf.image(str(tmp), x=0, y=0, w=210, h=297)
    pdf.output(str(caminho))
    for tmp in temporarios:
        tmp.unlink()


def main():
    import random

    gerar()
    rng = random.Random(20261116)  # noqa: S311 - semente fixa para corpus reprodutível (sem uso criptográfico)
    familias_contratos(rng)
    familias_normas(rng)
    DESTINO.mkdir(parents=True, exist_ok=True)
    for item in DESTINO.iterdir():  # limpa o conteúdo gerado anteriormente, preservando a pasta
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    gabarito_docs, manifesto, textos = [], [], {}
    agora = datetime.now().isoformat(timespec="seconds")
    for d in DOCS:
        pasta = DESTINO / d.processo
        pasta.mkdir(exist_ok=True)
        extensao = {"docx": ".docx", "pdf": ".pdf", "pdf_digitalizado": ".pdf", "txt": ".txt"}[d.formato]
        caminho = pasta / f"{d.arquivo}{extensao}"
        linhas, dispositivos = linhas_documento(d)
        textos[d.id] = "\n".join(linhas)
        if d.formato == "docx":
            salvar_docx(caminho, linhas, d)
        elif d.formato == "pdf":
            salvar_pdf(caminho, linhas, d)
        elif d.formato == "pdf_digitalizado":
            salvar_pdf_digitalizado(caminho, linhas, d)
        else:
            salvar_txt(caminho, linhas)
        relativo = caminho.relative_to(RAIZ / "corpus").as_posix()
        dados = caminho.read_bytes()
        gabarito_docs.append({
            "id": d.id, "arquivo": relativo, "processo": d.processo, "formato": d.formato,
            "tipo_documental": d.tipo_documental, "especie": d.especie or None, "numero": d.numero,
            "data": d.data.isoformat(), "titulo": d.titulo, "orgao": SIGLA, "fatos": d.fatos,
            "dispositivos": dispositivos,
            "texto_referencia": "\n".join(linhas) if d.formato == "pdf_digitalizado" else None,
        })
        manifesto.append({"arquivo": relativo, "corpus_origem": "sintetico", "url": "",
                          "especie": d.especie or d.tipo_documental, "numero": d.numero, "ano": d.data.year,
                          "esfera": "estadual_ficticia", "tema": d.processo, "coletado_em": agora,
                          "sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados),
                          "licenca": "Gerado pelo projeto SAD-GD (fictício)"})
    ids = [d.id for d in DOCS]
    assert len(ids) == len(set(ids)), "identificadores de documento repetidos"
    # autoverificação: toda evidência ocorre literalmente no documento de destino
    for r in RELACOES:
        assert r["destino"] in textos and r["evidencia"] in textos[r["destino"]], f"evidência ausente: {r}"
        assert r["origem"].startswith("PUB:") or r["origem"] in textos, f"origem desconhecida: {r}"
    gabarito = {"versao": 1,
                "convencao_relacoes": "o documento de DESTINO contém a evidência e age sobre a ORIGEM "
                                      "(ex.: destino adita/altera/revoga/substitui/regulamenta/retoma/contradiz/"
                                      "dá continuidade à origem; destino é fundamentado pela origem). "
                                      "'PUB:<arquivo>' referencia documento do corpus público.",
                "gerado_por": "scripts/sadgd/gerar_corpus_sintetico.py", "aviso": AVISO,
                "documentos": gabarito_docs, "relacoes": RELACOES, "contradicoes": CONTRADICOES}
    (DESTINO / "GABARITO.json").write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")

    existentes = []
    if MANIFESTO.exists():
        with MANIFESTO.open(encoding="utf-8", newline="") as f:
            existentes = [r for r in csv.DictReader(f) if r["corpus_origem"] != "sintetico"]
    with MANIFESTO.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CABECALHO)
        escritor.writeheader()
        for linha in sorted(existentes + manifesto, key=lambda r: r["arquivo"]):
            escritor.writerow({k: linha.get(k, "") for k in CABECALHO})

    tipos = {}
    for r in RELACOES:
        tipos[r["tipo"]] = tipos.get(r["tipo"], 0) + 1
    print(f"Documentos: {len(DOCS)} | Processos: {len({d.processo for d in DOCS})} | Relações: {len(RELACOES)} "
          f"{dict(sorted(tipos.items()))} | Contradições: {len(CONTRADICOES)} | "
          f"Digitalizados: {sum(d.formato == 'pdf_digitalizado' for d in DOCS)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
