"""Anonimização LGPD reversível (SAD-074, RF-25): CPF, e-mail, telefone, matrícula e nomes de pessoas físicas.

Nomes de pessoas: sequência iniciada por prenome brasileiro comum seguida de 1 a 4 sobrenomes (com "de/da/dos…"),
o que evita mascarar pessoas jurídicas e órgãos. CNPJ não é mascarado (pessoa jurídica). Os marcadores
([PESSOA_1], [CPF_1]…) permitem restaurar a resposta localmente.
"""
import re

PRENOMES = set((  # noqa: SIM905 - lista legível em linhas
    "adriana adriano alessandra alexandre alice aline amanda ana andre andrea andreia angela antonia antonio "
    "augusto beatriz benedito bernardo bianca bruna bruno caio camila carla carlos carolina cassia catarina cecilia "
    "celia cesar cicero claudia claudio cristiane cristina daniel daniela danilo debora denise diego diogo douglas "
    "eduardo elaine elias eliane elisa emanuel enzo erica fabiana fabio fatima felipe fernanda fernando flavia "
    "flavio francisca francisco gabriel gabriela gilberto giovana gisele gustavo helena heloisa henrique hugo igor "
    "isabel isabela ivan jaqueline joana joao joaquim jorge jose josefa julia juliana julio karina larissa laura "
    "leandro leonardo leticia lucas luciana luciano lucia luis luiz luiza manoel marcela marcelo marcia marcio "
    "marcos margarida maria mariana marina mario marta mateus matheus mauricio miguel milena monica natalia nelson "
    "nicolas otavio patricia paula paulo pedro priscila rafael rafaela raimundo raquel regina renata renato ricardo "
    "roberta roberto rodrigo rogerio ronaldo rosa rosana rubens samuel sandra sebastiao sergio silvia simone sonia "
    "sueli tatiana teresa thiago tiago valeria vanessa vera vicente vinicius vitor vitoria viviane wagner "
    "wellington yasmin "
).split())
CONECTORES = {"de", "da", "do", "das", "dos", "e"}
SEM_ACENTO = str.maketrans("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ", "aaaaeeiooouc" + "AAAAEEIOOOUC")

PADROES = [
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("TELEFONE", re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}\b")),
    ("MATRICULA", re.compile(r"(?<=matr[íi]cula )\d[\d./-]{2,}\d", re.I)),
]
RE_PALAVRA_MAIUSCULA = re.compile(r"\b[A-ZÁÂÃÉÊÍÓÔÕÚÇ][a-záâãéêíóôõúç]+\b")


def _nomes(texto):
    """Spans (início, fim) de nomes de pessoas: prenome conhecido + 1 a 4 sobrenomes capitalizados."""
    spans = []
    for m in RE_PALAVRA_MAIUSCULA.finditer(texto):
        if m.group().translate(SEM_ACENTO).lower() not in PRENOMES or (spans and m.start() < spans[-1][1]):
            continue
        fim, sobrenomes, pos = m.end(), 0, m.end()
        while True:
            # sobrenomes na mesma linha; "De"/"Da" maiúsculos também são conectores ("Carlos De Souza")
            seguinte = re.match(r"[ \t]+([A-ZÁÂÃÉÊÍÓÔÕÚÇ][a-záâãéêíóôõúç]+|(?:de|da|do|das|dos|e)(?=[ \t]+"
                                r"[A-ZÁÂÃÉÊÍÓÔÕÚÇ]))", texto[pos:])
            if not seguinte:
                break
            pos += seguinte.end()
            if seguinte.group(1).lower() in CONECTORES:
                continue  # "de/da/dos" só contam se vier um sobrenome depois (fim não avança)
            sobrenomes += 1
            fim = pos
            if sobrenomes >= 4:
                break
        if sobrenomes >= 1:
            spans.append((m.start(), fim))
    return spans


def anonimizar(texto: str, mapa: dict | None = None):
    """Devolve (texto_anonimizado, mapa marcador→original). O mapa pode ser compartilhado entre mensagens."""
    mapa = {} if mapa is None else mapa
    reverso = {v: k for k, v in mapa.items()}
    achados = [(m.start(), m.end(), tipo) for tipo, padrao in PADROES for m in padrao.finditer(texto)]
    achados += [(a, b, "PESSOA") for a, b in _nomes(texto)]
    achados.sort()
    saida, pos = [], 0
    for inicio, fim, tipo in achados:
        if inicio < pos:
            continue
        original = texto[inicio:fim]
        if original not in reverso:
            n = sum(1 for k in mapa if k.startswith(f"[{tipo}_")) + 1
            marcador = f"[{tipo}_{n}]"
            mapa[marcador], reverso[original] = original, marcador
        saida += [texto[pos:inicio], reverso[original]]
        pos = fim
    saida.append(texto[pos:])
    return "".join(saida), mapa


def restaurar(texto: str, mapa: dict) -> str:
    for marcador, original in mapa.items():
        texto = texto.replace(marcador, original)
    return texto


def restaurar_objeto(obj, mapa):
    if isinstance(obj, str):
        return restaurar(obj, mapa)
    if isinstance(obj, list):
        return [restaurar_objeto(x, mapa) for x in obj]
    if isinstance(obj, dict):
        return {k: restaurar_objeto(v, mapa) for k, v in obj.items()}
    return obj
