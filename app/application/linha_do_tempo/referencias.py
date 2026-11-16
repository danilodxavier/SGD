"""Referências entre documentos no texto ("Contrato nº 012/2023", "Lei nº 14.133, de 1º de abril de 2021"...).

Chave normalizada: (espécie, número). Para leis e decretos o número é só a parte numérica antes da barra
("1.410/2023" e "Decreto nº 1.410, de 18 de abril de 2023" → ("decreto", "1410")); para os demais atos o
número completo com ano ("012/2023").
"""
import re
import unicodedata
from dataclasses import dataclass

_ESPECIES = [
    (r"Lei\s+Complementar", "lei_complementar"), (r"Decreto[-\s]Lei", "decreto_lei"), (r"Lei", "lei"),
    (r"Decreto", "decreto"), (r"Portaria", "portaria"), (r"Instru[çc][ãa]o\s+Normativa", "instrucao_normativa"),
    (r"Orienta[çc][ãa]o\s+Normativa", "orientacao"), (r"Contrato", "contrato"), (r"Conv[êe]nio", "convenio"),
    (r"Notifica[çc][ãa]o", "notificacao"), (r"Parecer\s+Jur[íi]dico", "parecer_juridico"),
    (r"Termo\s+de\s+Refer[êe]ncia", "termo_referencia"), (r"Ordem\s+de\s+Suspens[ãa]o", "ordem_suspensao"),
    (r"Apostilamento", "apostilamento"),
]
RE_REFERENCIA = re.compile(
    r"\b(?P<especie>" + "|".join(f"(?:{p})" for p, _ in _ESPECIES) + r")"
    r"\s+n\.?\s*[º°o]\.?\s*(?P<numero>\d[\d./-]*\d|\d)", re.IGNORECASE)
# parte de um ato: "arts. 1º a 47-A da", "§§ 2º e 3º do art. 10 da", "dispositivos e seção da", "inciso III do"…
RE_PARCIAL = re.compile(r"(?:\barts?\.|§|\bincisos?\b|\bpar[áa]grafos?\b|\bal[íi]neas?\b|\bdispositivos?\b|"
                        r"\bse[çc][ãa]o\b|\bse[çc][õo]es\b|\bcap[íi]tulos?\b|\bcaput\b|\bitens?\b)"
                        r"[^.;]{0,60}\b(?:da|do)\s*$", re.IGNORECASE)
SO_NUMERO = {"lei", "lei_complementar", "decreto", "decreto_lei"}
TIPO_PARA_ESPECIE = {"portaria_designacao": "portaria"}
REFERIVEIS = {c for _, c in _ESPECIES}


@dataclass(frozen=True)
class Referencia:
    chave: tuple
    inicio: int
    fim: int
    parcial: bool  # "arts. 1º a 47-A da Lei nº ..." — atinge só parte do ato


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


_NOMES = {"lei complementar": "lei_complementar", "decreto lei": "decreto_lei", "lei": "lei", "decreto": "decreto",
          "portaria": "portaria", "instrucao normativa": "instrucao_normativa", "orientacao normativa": "orientacao",
          "contrato": "contrato", "convenio": "convenio", "notificacao": "notificacao",
          "parecer juridico": "parecer_juridico", "termo de referencia": "termo_referencia",
          "ordem de suspensao": "ordem_suspensao", "apostilamento": "apostilamento"}


def _especie(texto):
    return _NOMES.get(" ".join(_sem_acento(texto).replace("-", " ").split()))


def _numero(especie, numero):
    numero = numero.strip(".-/")
    if especie in SO_NUMERO:
        return re.sub(r"\D", "", numero.split("/")[0])
    return numero


def chave_documento(tipo_documental, numero):
    especie = TIPO_PARA_ESPECIE.get(tipo_documental, tipo_documental)
    if especie not in REFERIVEIS or not numero:
        return None
    return especie, _numero(especie, numero)


def encontrar_referencias(texto):
    refs = []
    for m in RE_REFERENCIA.finditer(texto):
        especie = _especie(m.group("especie"))
        if not especie:
            continue
        parcial = bool(RE_PARCIAL.search(texto[max(0, m.start() - 60):m.start()]))
        refs.append(Referencia((especie, _numero(especie, m.group("numero"))), m.start(), m.end(), parcial))
    return refs
