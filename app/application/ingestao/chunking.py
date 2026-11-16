"""Chunking estrutural de textos jurídicos e administrativos (SAD-043, RF-03).

Unidades de primeiro nível: artigos (normas) e cláusulas (contratos). Subdispositivos reconhecidos: parágrafos,
parágrafo único, incisos, alíneas e itens numerados de cláusula. Títulos/capítulos/seções formam o caminho
hierárquico. Cada trecho guarda o texto LITERAL do documento e os offsets no texto concatenado das páginas,
para citação exata. Artigos longos são divididos nos limites dos subdispositivos; textos sem estrutura são
divididos por parágrafos. Python puro: sem I/O (ADR-013).
"""
import re
from dataclasses import dataclass, field

MAX_CARACTERES = 2400  # ~600 tokens: cabe no contexto do reranker e mantém o trecho citável

_ORD = r"(?:º|°|o(?=[\s.\-–]))"
RE_ARTIGO = re.compile(
    r"^Art\.\s*(?P<num>\d{1,3}(?:\.\d{3})+|\d+)\s*" + _ORD
    + r"?\s*(?:-\s*(?P<letra>[A-Z]{1,2}))?\s*\.?\s+(?P<resto>\S.*)?$",
    re.S)
# "Art. 5º da Lei nº …" no início da linha é citação; "Art. 56. Das decisões …" é artigo legítimo
RE_CITACAO = re.compile(
    r"^(?:(?:da|do|das|dos|de)\s+(?:\S+\s+){0,2}?(?:Lei|Decreto|Constitui|C[óo]digo|Medida|Portaria|Instru|"
    r"Resolu|Emenda|Ato\b|referid|mencionad|citad)|(?:desta|deste|dessa|desse|daquel)\w*\s)", re.I)
RE_PARAGRAFO = re.compile(r"^§\s*(?P<num>\d+)\s*" + _ORD + r"?")
RE_PAR_UNICO = re.compile(r"^Par[áa]grafo\s+[úu]nico", re.I)
RE_INCISO = re.compile(r"^(?P<rom>[IVXLC]+)\s*[-–—]\s*\S")
RE_ALINEA = re.compile(r"^(?P<letra>[a-z])\)\s")
RE_CLAUSULA = re.compile(r"^CL[ÁA]USULA\s+(?P<ord>[A-ZÇÃÁÉÍÓÚÂÊÔÕ ]+?|\d+\s*[ªº°a]?)\s*[-–—:.]\s*", re.I)
RE_ITEM = re.compile(r"^(?P<item>\d+\.\d+(?:\.\d+)?)\.?\s+\S")
RE_TITULO = re.compile(r"^(?P<tipo>LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+"
                       r"(?P<num>[IVXLC]+|[ÚU]NIC[OA])\b", re.I)
NIVEL_TITULO = {"livro": 0, "titulo": 1, "capitulo": 2, "secao": 3, "subsecao": 4}
RE_REVOGADO = re.compile(r"\[REVOGADO\]|^\s*\(?\s*Revogad[oa]s?\b", re.I)


@dataclass(frozen=True)
class Pagina:
    texto: str
    numero: int | None = None


@dataclass
class Trecho:
    ordem: int
    texto: str
    inicio: int
    fim: int
    pagina: int | None
    dispositivo: str | None
    tipo_dispositivo: str  # artigo | clausula | preambulo | livre
    caminho: str | None = None
    subdispositivos: list = field(default_factory=list)
    contexto: str = ""  # caput da unidade: usado para enriquecer o embedding, não altera o texto citado
    revogado: bool = False


@dataclass
class _Linha:
    texto: str
    inicio: int
    fim: int
    sub: str | None = None  # rótulo do subdispositivo que esta linha abre
    revogada: bool = False


@dataclass
class _Unidade:
    rotulo: str | None
    tipo: str
    caminho: str | None
    linhas: list = field(default_factory=list)


def _sem_acento(s):
    return (s.lower().replace("í", "i").replace("ç", "c").replace("ã", "a").replace("ú", "u"))


def _rotulo_artigo(m):
    num = m.group("num")
    base = f"art. {num}º" if "." not in num and int(num) < 10 else f"art. {num}"
    return f"{base}-{m.group('letra')}" if m.group("letra") else base


def _rotulo_clausula(m):
    ordem = " ".join(m.group("ord").split()).lower()
    return f"cláusula {ordem}"


def _linhas(texto):
    pos = 0
    for bruta in texto.splitlines(keepends=True):
        yield bruta, pos
        pos += len(bruta)


def dividir(paginas, max_caracteres=MAX_CARACTERES):
    """Divide as páginas em trechos estruturais. Offsets referem-se a "".join(p.texto for p in paginas)."""
    texto = "".join(p.texto for p in paginas)
    limites, pos = [], 0
    for p in paginas:
        limites.append((pos, p.numero))
        pos += len(p.texto)

    def pagina_de(offset):
        numero = limites[0][1] if limites else None
        for inicio, n in limites:
            if inicio <= offset:
                numero = n
        return numero

    unidades = _unidades(texto)
    trechos = []
    for u in unidades:
        if not u.linhas:
            continue
        if u.tipo in ("artigo", "clausula"):
            pedacos = _dividir_unidade(u, max_caracteres)
        else:
            pedacos = _dividir_livre(u, max_caracteres)
        for inicio, fim, rotulo, subs, revogado in pedacos:
            fatia = texto[inicio:fim]
            if not fatia.strip():
                continue
            caminho = u.caminho if u.tipo in ("artigo", "clausula") else None
            if caminho and rotulo and rotulo != u.rotulo:
                caminho = caminho.rsplit(" > ", 1)[0] + " > " + rotulo if " > " in caminho else rotulo
            trechos.append(Trecho(len(trechos) + 1, fatia, inicio, fim, pagina_de(inicio), rotulo, u.tipo, caminho,
                                  subs, _contexto(u), revogado))
    return trechos


def _contexto(u):
    if u.tipo not in ("artigo", "clausula"):
        return ""
    return " ".join(u.linhas[0].texto.split())[:300]


def _unidades(texto):
    unidades = [_Unidade(None, "preambulo", None)]
    hierarquia = {}  # nível -> rótulo exibido
    pendente_titulo = None
    atual_tipo = None
    for bruta, inicio in _linhas(texto):
        linha = bruta.replace("\xa0", " ").strip()
        fim = inicio + len(bruta)
        if pendente_titulo is not None:
            nivel, rotulo = pendente_titulo
            pendente_titulo = None
            if linha and not _abre_dispositivo(linha) and len(linha) < 150:
                hierarquia[nivel] = f"{rotulo} – {linha}"
                unidades[-1].linhas.append(_Linha(bruta, inicio, fim))
                continue
        m_tit = RE_TITULO.match(linha)
        if m_tit and len(linha) < 120:
            nivel = NIVEL_TITULO[_sem_acento(m_tit.group("tipo")).replace("ã", "a")]
            for n in [n for n in hierarquia if n >= nivel]:
                del hierarquia[n]
            hierarquia[nivel] = linha
            pendente_titulo = (nivel, linha)
            unidades[-1].linhas.append(_Linha(bruta, inicio, fim))
            continue
        m_art = RE_ARTIGO.match(linha)
        if m_art and not (m_art.group("resto") and RE_CITACAO.match(m_art.group("resto"))):
            rotulo = _rotulo_artigo(m_art)
            caminho = " > ".join([hierarquia[n] for n in sorted(hierarquia)] + [rotulo])
            unidades.append(_Unidade(rotulo, "artigo", caminho))
            atual_tipo = "artigo"
            unidades[-1].linhas.append(_Linha(bruta, inicio, fim, revogada=_revogada(m_art.group("resto") or "")))
            continue
        m_cl = RE_CLAUSULA.match(linha)
        if m_cl:
            rotulo = _rotulo_clausula(m_cl)
            caminho = " > ".join([hierarquia[n] for n in sorted(hierarquia)] + [rotulo])
            unidades.append(_Unidade(rotulo, "clausula", caminho))
            atual_tipo = "clausula"
            unidades[-1].linhas.append(_Linha(bruta, inicio, fim))
            continue
        u = unidades[-1]
        sub = None
        if atual_tipo == "artigo" and u.tipo == "artigo":
            sub = _sub_artigo(linha, u)
        elif atual_tipo == "clausula" and u.tipo == "clausula":
            m_it = RE_ITEM.match(linha)
            sub = f"{u.rotulo}, item {m_it.group('item')}" if m_it else None
        u.linhas.append(_Linha(bruta, inicio, fim, sub=sub, revogada=_revogada(linha)))
    if len(unidades) == 1:
        unidades[0].tipo = "livre"
    return unidades


def _abre_dispositivo(linha):
    return bool(RE_ARTIGO.match(linha) or RE_CLAUSULA.match(linha) or RE_TITULO.match(linha))


def _revogada(texto):
    return bool(RE_REVOGADO.search(texto[:80]))


def _sub_artigo(linha, u):
    if m := RE_PARAGRAFO.match(linha):
        return f"{u.rotulo}, § {m.group('num')}º"
    if RE_PAR_UNICO.match(linha):
        return f"{u.rotulo}, parágrafo único"
    if m := RE_INCISO.match(linha):
        return f"{u.rotulo}, {m.group('rom')}"
    if m := RE_ALINEA.match(linha):
        inciso = next((ln.sub for ln in reversed(u.linhas) if ln.sub and RE_INCISO_ROTULO.search(ln.sub)), None)
        base = inciso.split(", ")[:2] if inciso else [u.rotulo]
        return ", ".join(base + [m.group("letra")])
    return None


RE_INCISO_ROTULO = re.compile(r", [IVXLC]+$")


def _blocos(u):
    """Agrupa as linhas em blocos: [caput] + um bloco por subdispositivo (com suas linhas de continuação)."""
    blocos = [[u.linhas[0]]]
    for ln in u.linhas[1:]:
        if ln.sub:
            blocos.append([ln])
        else:
            blocos[-1].append(ln)
    return blocos


def _curto(rotulo_sub, rotulo_unidade):
    return rotulo_sub[len(rotulo_unidade) + 2:] if rotulo_sub.startswith(rotulo_unidade + ", ") else rotulo_sub


def _dividir_unidade(u, maximo):
    total = u.linhas[-1].fim - u.linhas[0].inicio
    subs = [ln.sub for ln in u.linhas if ln.sub]
    revogado = u.linhas[0].revogada
    if total <= maximo:
        return [(u.linhas[0].inicio, u.linhas[-1].fim, u.rotulo, subs, revogado)]
    pedacos, grupo = [], []

    def fechar(grupo, primeiro):
        inicio, fim = grupo[0][0].inicio, grupo[-1][-1].fim
        subs_g = [ln.sub for bloco in grupo for ln in bloco if ln.sub]
        if primeiro:
            rotulo = u.rotulo
        elif len(subs_g) == 1:
            rotulo = f"{u.rotulo}, {_curto(subs_g[0], u.rotulo)}"
        else:
            rotulo = f"{u.rotulo}, {_curto(subs_g[0], u.rotulo)} a {_curto(subs_g[-1], u.rotulo)}"
        rev = all(ln.revogada for bloco in grupo for ln in bloco if ln.texto.strip()) if not primeiro else revogado
        return inicio, fim, rotulo, subs_g, rev

    for bloco in _blocos(u):
        tamanho = bloco[-1].fim - bloco[0].inicio
        atual = (grupo[-1][-1].fim - grupo[0][0].inicio) if grupo else 0
        if grupo and atual + tamanho > maximo:
            pedacos.append(fechar(grupo, not pedacos))
            grupo = []
        if tamanho > maximo:  # subdispositivo isolado maior que o limite: quebra por espaço
            for ini, fim in _quebrar_intervalo(bloco[0].inicio, bloco[-1].fim, _texto_bloco(bloco), maximo):
                rotulo = bloco[0].sub or u.rotulo
                pedacos.append((ini, fim, rotulo if pedacos or not bloco[0].sub else u.rotulo,
                                [bloco[0].sub] if bloco[0].sub else [], revogado))
            continue
        grupo.append(bloco)
    if grupo:
        pedacos.append(fechar(grupo, not pedacos))
    return pedacos


def _texto_bloco(bloco):
    return "".join(ln.texto for ln in bloco)


def _quebrar_intervalo(inicio, fim, texto, maximo):
    partes, pos = [], 0
    while pos < len(texto):
        if len(texto) - pos <= maximo:
            partes.append((inicio + pos, fim))
            break
        corte = max(texto.rfind("\n", pos, pos + maximo), texto.rfind(". ", pos, pos + maximo) + 1,
                    texto.rfind(" ", pos, pos + maximo))
        if corte <= pos:
            corte = pos + maximo
        partes.append((inicio + pos, inicio + corte))
        pos = corte
    return partes


def _dividir_livre(u, maximo):
    """Agrupa parágrafos (separados por linha em branco) até o limite; parágrafo maior é quebrado por espaço."""
    paragrafos, atual = [], []
    for ln in u.linhas:
        if ln.texto.strip():
            atual.append(ln)
        elif atual:
            atual.append(ln)  # mantém a linha em branco no paragrafo para preservar a contiguidade
            paragrafos.append(atual)
            atual = []
        elif paragrafos:
            paragrafos[-1].append(ln)
    if atual:
        paragrafos.append(atual)
    pedacos, ini, fim = [], None, None
    for par in paragrafos:
        p_ini, p_fim = par[0].inicio, par[-1].fim
        if ini is not None and p_fim - ini > maximo:
            pedacos.append((ini, fim, None, [], False))
            ini = None
        if p_fim - p_ini > maximo:
            texto = "".join(ln.texto for ln in par)
            for a, b in _quebrar_intervalo(p_ini, p_fim, texto, maximo):
                pedacos.append((a, b, None, [], False))
            continue
        if ini is None:
            ini = p_ini
        fim = p_fim
    if ini is not None:
        pedacos.append((ini, fim, None, [], False))
    return pedacos
