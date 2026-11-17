"""Faithfulness com LLM-juiz (Fase 10): fração das frases da resposta sustentadas pelos trechos citados
(definição por afirmação, como no RAGAS). O juiz deve ser de outra família de modelos (evita autoavaliação) e é
calibrado com respostas corrompidas de propósito (rótulos conhecidos por construção)."""
import random
import re

from app.domain.politicas import AVISO_DECISAO, MENSAGEM_AUSENCIA, MENSAGEM_CONFLITO

ORDEM_JUIZ = ('Responda SOMENTE com um objeto JSON: {"frases": [{"n": <número da frase>, "sustentada": true|false, '
              '"motivo": "<até 15 palavras>"}]}, com um item para cada frase numerada, na mesma ordem.')
SISTEMA_JUIZ = (
    "Você é um auditor rigoroso de fidelidade documental. Para cada FRASE numerada da RESPOSTA, decida se ela é "
    "SUSTENTADA pelos TRECHOS: todos os fatos, números, datas, valores, nomes e situações de vigência da frase "
    "precisam constar nos trechos (paráfrase e cálculo simples são aceitos). Se a frase traz algo que não está nos "
    "trechos, contradiz os trechos ou inverte o sentido deles, ela NÃO é sustentada. Marcadores de citação como "
    "[T123] não contam como fato. Não use conhecimento externo. " + ORDEM_JUIZ)

RE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\"“(])")
RE_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
INVERSOES = [(" é ", " não é "), (" foi ", " não foi "), (" vigente", " revogado"), (" revogad", " vigent"),
             (" prorrog", " rescind"), (" acréscimo", " supressão"), (" positivo", " negativo")]
INVENCOES = ["Além disso, o documento prevê multa diária de 7% sobre o valor total em caso de atraso.",
             "A execução foi fiscalizada pela Controladoria-Geral da União em 2019.",
             "O contrato também foi prorrogado por mais 36 meses por meio do 9º termo aditivo.",
             "Conforme o mesmo documento, a contratada é a empresa Horizonte Azul Engenharia S.A."]


ABREVIACOES = re.compile(r"(?:\b(?:art|arts|inc|incs|al|n|nº|no|pág|p|cap|fl|fls|sr|sra|dr|dra|ltda|s\.a)|§)\.$",
                         re.IGNORECASE)


def frases(resposta: str) -> list[str]:
    # mensagens institucionais (aviso, conflito) não são afirmações sobre os documentos
    texto = resposta.replace(AVISO_DECISAO, " ").replace(MENSAGEM_CONFLITO, " ").strip()
    partes = []
    for p in (p.strip() for p in RE_FRASE.split(texto) if p.strip()):
        if partes and (ABREVIACOES.search(partes[-1]) or re.fullmatch(r"(?:\[T\d+\]\s*)+\.?", p)):
            partes[-1] = f"{partes[-1]} {p}"  # "art. 106" ou citação solta não iniciam nova frase
        else:
            partes.append(p)
    return [p for p in partes if re.sub(r"\[T\d+\]|\W", "", p) and not p.startswith(MENSAGEM_AUSENCIA[:30])]


def mensagens_juiz(pergunta, resposta, trechos):
    lista = frases(resposta)
    numeradas = "\n".join(f"{i}. {f}" for i, f in enumerate(lista, start=1))
    contexto = "\n\n".join(f"[{t.rotulo}] {t.titulo or ''} — {t.dispositivo or ''}\n{t.texto}" for t in trechos)
    return lista, [{"role": "system", "content": SISTEMA_JUIZ},
                   {"role": "user", "content": f"PERGUNTA: {pergunta}\n\nTRECHOS:\n{contexto or '(nenhum trecho)'}"
                                               f"\n\nRESPOSTA (frases numeradas):\n{numeradas}"}]


def interpretar(saida: dict | None, n_frases: int) -> list[bool]:
    """Veredito por frase; item ausente ou ilegível conta como NÃO sustentado (conservador)."""
    vereditos = [False] * n_frases
    for item in (saida or {}).get("frases") or []:
        try:
            i = int(item.get("n")) - 1
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= i < n_frases:
            v = item.get("sustentada")
            vereditos[i] = v is True or str(v).strip().lower() in ("true", "sim", "yes")
    return vereditos


def corromper(resposta: str, tipo: str, semente: int) -> str | None:
    """Versão sabidamente infiel da resposta (None se o tipo não se aplica)."""
    rnd = random.Random(semente)  # noqa: S311 - reprodutibilidade experimental, não criptografia
    if tipo == "numero":
        nums = [m for m in RE_NUMERO.finditer(resposta) if not re.search(r"\[T$", resposta[:m.start()])]
        if not nums:
            return None
        m = rnd.choice(nums)
        digitos = [i for i, c in enumerate(m.group()) if c.isdigit()]
        i = rnd.choice(digitos)
        novo = list(m.group())
        novo[i] = str((int(novo[i]) + rnd.randint(1, 8)) % 10)
        return resposta[:m.start()] + "".join(novo) + resposta[m.end():]
    if tipo == "inversao":
        for a, b in INVERSOES:
            if a in resposta:
                return resposta.replace(a, b, 1)
        return None
    if tipo == "invencao":
        corpo = resposta.replace(AVISO_DECISAO, "").rstrip()
        return f"{corpo} {rnd.choice(INVENCOES)}"
    raise ValueError(tipo)


def kappa(rotulos, previstos):
    """κ de Cohen para rótulos binários."""
    n = len(rotulos)
    if not n:
        return None
    acordo = sum(a == b for a, b in zip(rotulos, previstos, strict=True)) / n
    p1, q1 = sum(rotulos) / n, sum(previstos) / n
    esperado = p1 * q1 + (1 - p1) * (1 - q1)
    return round((acordo - esperado) / (1 - esperado), 4) if esperado < 1 else None
