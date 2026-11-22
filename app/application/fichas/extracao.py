"""Extração da ficha de um contrato com o LLM local — feita uma vez, fora do horário de uso (gerar_fichas.py).

Entrada: trechos do instrumento (abertura + cláusulas de objeto, vigência, valor e fiscalização) e das portarias de
designação mais recentes. Saída: cada campo com o valor e o trecho citado. Salvaguarda determinística: o valor só é
aceito se constar do trecho citado (literal; para o objeto, ≥ 70% das palavras) — o que não confere é descartado.
"""
import re

from app.application.fichas.agrupamento import normalizar

CAMPOS = {
    "numero": "número do contrato, como escrito",
    "contratada": "razão social da empresa contratada",
    "cnpj_contratada": "CNPJ da contratada",
    "objeto": "objeto do contrato (cláusula do objeto, resumido nas palavras do texto)",
    "data_assinatura": "data de assinatura",
    "vigencia": "prazo de vigência como escrito (ex.: 12 (doze) meses)",
    "vigencia_inicio": "data de início da vigência",
    "vigencia_fim": "data de término da vigência",
    "valor_global": "valor global/total do contrato (R$)",
    "fiscal": "nome do fiscal do contrato",
    "gestor": "nome do gestor do contrato",
}
PALAVRAS_CHAVE = {
    "objeto": r"\bobjeto\b",
    "vigencia": r"vigencia|\bprazo\b",
    "valor": r"\bvalor\b|r\$|\bpreco\b",
    "fiscal": r"\bfiscal\b|\bgestor\b|fiscaliza|acompanhamento",
}
MAX_CARACTERES = 900
# 2ª passada (2026-11-21): só os campos que faltaram, em fontes que costumam resumi-los — extrato de publicação
# (contratada, objeto, valor, vigência) e portarias de designação (fiscal, gestor)
COMPLEMENTAVEIS = ("contratada", "cnpj_contratada", "data_assinatura", "vigencia", "vigencia_inicio", "vigencia_fim",
                   "valor_global", "fiscal", "gestor")
# Vigência atual: do termo aditivo mais recente que prorroga o prazo
CAMPOS_ADITIVO = {
    "vigencia_atual_fim": "nova data final da vigência após a prorrogação, como escrita",
    "prazo_prorrogacao": "período da prorrogação, como escrito (ex.: 12 (doze) meses)",
    "valor_atual": "novo valor global do contrato após o aditivo (R$), como escrito",
}
PALAVRAS_ADITIVO = r"prorrog|vigencia|\bprazo\b|\bvalor\b|r\$|acresc|supress"


def sistema(campos: dict) -> str:
    return ("Você extrai dados de contratos administrativos a partir dos TRECHOS fornecidos, identificados como "
            "[T<id>]. Use SOMENTE o que está escrito nos trechos; copie valores, datas e nomes exatamente como "
            "aparecem; não deduza nem calcule. Se um campo não constar, use null. Responda SOMENTE com um objeto JSON "
            "cujas chaves são: " + ", ".join(f'"{c}" ({d})' for c, d in campos.items())
            + '. Cada chave tem o valor {"valor": "<texto copiado>", "trecho": "T<id>"} ou null.')


SISTEMA = sistema(CAMPOS)


def janela(texto: str, padrao: str | None, tamanho: int = MAX_CARACTERES) -> str:
    """Trecho literal com até `tamanho` caracteres, centrado na palavra-chave (cortes marcados com […])."""
    texto = texto.strip()
    if len(texto) <= tamanho:
        return texto
    m = re.search(padrao, normalizar(texto)) if padrao else None
    inicio = max(0, (m.start() if m else 0) - tamanho // 4)
    fim = min(len(texto), inicio + tamanho)
    return ("[…] " if inicio else "") + texto[inicio:fim] + (" […]" if fim < len(texto) else "")


def selecionar_trechos(trechos_instrumento: list, trechos_portarias: list, max_trechos: int = 8) -> list:
    """trechos_*: [(id, texto)] em ordem. Abertura (2 primeiros) + melhor trecho por palavra-chave + portarias."""
    escolhidos: dict[int, str] = {}
    for tid, texto in trechos_instrumento[:2]:
        escolhidos[tid] = janela(texto, None)
    for padrao in PALAVRAS_CHAVE.values():
        for tid, texto in trechos_instrumento:
            if tid not in escolhidos and re.search(padrao, normalizar(texto)):
                escolhidos[tid] = janela(texto, padrao)
                break
    for tid, texto in trechos_portarias:
        if len(escolhidos) >= max_trechos:
            break
        escolhidos.setdefault(tid, janela(texto, PALAVRAS_CHAVE["fiscal"]))
    return list(escolhidos.items())[:max_trechos]


def mensagens(trechos: list, campos: dict | None = None) -> list:
    corpo = "\n\n".join(f"[T{tid}]\n{texto}" for tid, texto in trechos)
    return [{"role": "system", "content": sistema(campos) if campos else SISTEMA},
            {"role": "user", "content": f"TRECHOS:\n{corpo}"}]


def trechos_complemento(fontes: list[list], faltantes: list[str], ja_enviados: set, max_trechos: int = 8) -> list:
    """fontes: listas de [(id, texto)] em ordem de preferência (extratos, portarias, resto do instrumento). Escolhe
    trechos com palavras-chave dos campos que faltam, ainda não enviados na 1ª passada."""
    padroes = [PALAVRAS_CHAVE["vigencia"]] if any(c.startswith("vigencia") for c in faltantes) else []
    padroes += [PALAVRAS_CHAVE["valor"]] if "valor_global" in faltantes else []
    padroes += [PALAVRAS_CHAVE["fiscal"]] if {"fiscal", "gestor"} & set(faltantes) else []
    padroes += [r"contratad|cnpj|assinatura"] if {"contratada", "cnpj_contratada", "data_assinatura"} & set(faltantes) \
        else []
    escolhidos: dict[int, str] = {}
    for fonte in fontes:
        for tid, texto in fonte:
            if len(escolhidos) >= max_trechos:
                return list(escolhidos.items())
            if tid in ja_enviados or tid in escolhidos:
                continue
            norm = normalizar(texto)
            achou = next((p for p in padroes if re.search(p, norm)), None)
            if achou:
                escolhidos[tid] = janela(texto, achou)
    return list(escolhidos.items())


def trechos_aditivo(trechos_doc: list, max_trechos: int = 4) -> list:
    """Abertura do aditivo + trechos que falam de prorrogação/vigência."""
    escolhidos = {tid: janela(texto, None) for tid, texto in trechos_doc[:1]}
    for tid, texto in trechos_doc[1:]:
        if len(escolhidos) >= max_trechos:
            break
        if re.search(PALAVRAS_ADITIVO, normalizar(texto)):
            escolhidos[tid] = janela(texto, PALAVRAS_ADITIVO)
    return list(escolhidos.items())


def _confere(campo: str, valor: str, texto: str) -> bool:
    v, t = normalizar(valor), normalizar(texto)
    if not v or len(v) < 2:
        return False
    if v in t:
        return True
    if campo == "objeto":  # resumo nas palavras do texto: exige que quase todas as palavras estejam no trecho
        palavras = [p for p in re.findall(r"\w+", v) if len(p) > 3]
        return bool(palavras) and sum(p in t for p in palavras) / len(palavras) >= 0.7
    return False


def validar(dados: dict, trechos: list, campos=None) -> dict:
    """Mantém só os campos cujo valor consta do trecho citado (que precisa estar entre os enviados)."""
    por_id = {f"T{tid}": texto for tid, texto in trechos}
    aceitos = {}
    for campo in campos or CAMPOS:
        item = dados.get(campo)
        if not isinstance(item, dict):
            continue
        valor = str(item.get("valor") or "").strip()
        rotulo = str(item.get("trecho") or "").strip().strip("[]")
        rotulo = f"T{rotulo}" if rotulo.isdigit() else rotulo
        if valor and rotulo in por_id and _confere(campo, valor, por_id[rotulo]):
            aceitos[campo] = {"valor": valor, "trecho_id": int(rotulo[1:])}
    return aceitos
