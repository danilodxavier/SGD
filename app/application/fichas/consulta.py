"""Resposta pela ficha do contrato — sem LLM no momento da pergunta (~1 s).

Responde quando reconhece (1) o contrato — pelo número (ou apelido) ou por um nome que só uma ficha contém (ex.:
"contrato da Alfa") — e (2) o assunto — objeto, partes, valor, vigência, fiscal/gestor ou documentos de um tipo
(empenhos, termos de recebimento, aditivos…), com filtro de ano. Cada afirmação cita o trecho de onde veio (o valor
da ficha foi conferido contra o trecho na extração). Sem contrato ou assunto reconhecido, ou sem o dado na ficha,
devolve None e a pergunta segue pelo caminho completo (busca + LLM).
"""
import re
import time
from dataclasses import dataclass, field

from app.application.fichas.agrupamento import (
    RE_CONTRATO_NO_TEXTO,
    RE_NUMERO,
    chave,
    chaves_no_texto,
    normalizar,
)
from app.domain import confianca as conf

ROTULO_TIPO = {
    "nota_empenho": ("nota de empenho", "notas de empenho"), "termo_recebimento": ("termo de recebimento",
                                                                                  "termos de recebimento"),
    "aditivo": ("termo aditivo", "termos aditivos"), "apostilamento": ("apostilamento", "apostilamentos"),
    "nota_fiscal": ("nota fiscal", "notas fiscais"), "pagamento": ("documento de pagamento", "documentos de pagamento"),
    "notificacao": ("notificação", "notificações"), "termo_rescisao": ("termo de rescisão", "termos de rescisão"),
    "portaria_designacao": ("portaria de designação", "portarias de designação"), "portaria": ("portaria", "portarias"),
    "extrato_publicacao": ("extrato de publicação", "extratos de publicação"),
    "relatorio_fiscalizacao": ("relatório de fiscalização", "relatórios de fiscalização"),
    "termo_paralisacao": ("termo de paralisação", "termos de paralisação"),
    "ordem_reinicio": ("ordem de reinício", "ordens de reinício"), "garantia": ("garantia", "garantias"),
    "contrato": ("instrumento contratual", "instrumentos contratuais"),
    "ordem_servico": ("ordem de serviço", "ordens de serviço"),
    "relatorio_apuracao": ("relatório de apuração", "relatórios de apuração"),
}
# (assunto, padrão na pergunta normalizada, campos da ficha, tipos de documento) — os de documento vêm primeiro
ASSUNTOS = [
    ("empenho", r"empenh", [], ["nota_empenho"]),
    ("recebimento", r"recebimento", [], ["termo_recebimento"]),
    ("rescisao", r"rescis|rescind", [], ["termo_rescisao"]),
    ("notificacao", r"notifica", [], ["notificacao"]),
    ("apuracao", r"apuracao|\bapurar\b|descumprimento contratual", [], ["relatorio_apuracao"]),
    ("apostilamento", r"apostil", [], ["apostilamento"]),
    ("nota_fiscal", r"notas? fisca|\bnf\b", [], ["nota_fiscal"]),
    ("pagamento", r"pagament|\bpago\b|\bpagos\b", [], ["pagamento"]),
    ("paralisacao", r"paralisa|suspens|extin", [],
     ["termo_paralisacao", "ordem_suspensao", "ordem_reinicio", "termo_retomada", "termo_rescisao"]),
    ("ordem_servico", r"orde(?:m|ns) de servic", [], ["ordem_servico"]),  # "os" sozinho é artigo: não serve
    # vigência antes de "aditivo": "após o termo aditivo, até quando vigora?" pergunta a data, não a lista
    ("vigencia", r"vigen|vigor|\bprazo\b|vence|vencimento|validade|ate quando|encerrad|termin",
     ["vigencia_atual_fim", "prazo_prorrogacao", "aditivo_vigencia", "vigencia", "vigencia_inicio", "vigencia_fim"],
     ["aditivo", "termo_rescisao"]),
    ("aditivo", r"aditiv", [], ["aditivo"]),
    ("fiscal", r"\bfiscal\b|fiscaliza", ["fiscal"], ["portaria_designacao"]),
    ("gestor", r"\bgestor", ["gestor"], ["portaria_designacao"]),
    # só o valor DO CONTRATO: "valor da garantia/multa/parcela" vai para o caminho completo
    ("valor", r"valor (global|total|do contrato|contratual|contratado|atual|atualizado)|quanto custa o contrato",
     ["valor_atual", "aditivo_valor", "valor_global"], []),
    ("contratada", r"empresa|contratad|fornecedor|cnpj", ["contratada", "cnpj_contratada"], []),
    ("objeto", r"sobre o que|do que trata|\bobjeto\b|qual (e )?o contrato|finalidade|trata o contrato|"
               r"o que e o contrato",
     ["objeto", "contratada", "numero"], []),
    # por último: "número da nota de empenho/do processo…" casa antes com o assunto do documento ou vai ao caminho
    # completo; aqui só "número do contrato" (rodada 17: "Qual o número do contrato com a Oracle?" levava 31 s no LLM)
    ("numero", r"\bnumero d[oe]s? contratos?\b", ["numero", "contratada"], []),
]
# perguntas sobre OUTROS documentos da pasta (não sobre os dados do contrato): a F1 com ficha também busca na pasta
DADOS_DO_CONTRATO = ("vigencia", "aditivo", "fiscal", "gestor")  # assuntos com documento, mas dados da ficha
RE_DOCUMENTOS_DA_PASTA = re.compile("|".join(a[1] for a in ASSUNTOS if a[3] and a[0] not in DADOS_DO_CONTRATO)
                                    + r"|oficio|processo|relatorio|parecer|medic|fatura|boleto|recibo|ateste|atesto")
# pergunta que PEDE um dado que a ficha guarda (com outras palavras que as dos assuntos): a ficha + janelas bastam.
# Só com pronome interrogativo no início e o dado presente na ficha do contrato ("prazo de garantia", "valor da
# multa" e "a contratada cumpriu...?" não são dados da ficha: seguem com os trechos dos documentos-chave)
RE_PEDE_DADO = re.compile(r"^(?:e\s+)?(?:qual|quais|quem|quando|ate quando|em que data|de quanto|quanto|que|o que|"
                          r"do que|sobre o que)\b")
DADOS_DA_FICHA = [
    (re.compile(r"empresa|contratad[ao]\b|fornecedor|razao social"), ("contratada",)),
    (re.compile(r"cnpj"), ("cnpj_contratada",)),
    (re.compile(r"\bobjeto\b|do que trata|finalidade"), ("objeto",)),
    (re.compile(r"valor (?:global|total|do contrato|contratual|contratado|atual|atualizado|anual|estimado)|"
                r"quanto custa"), ("valor_atual", "valor_global")),
    (re.compile(r"vigen|vigor|vence|termin|ate quando|prazo (?:de vigencia|do contrato|contratual)"),
     ("vigencia_atual_fim", "vigencia_fim", "vigencia")),
    (re.compile(r"assinad|assinatura|celebrad|firmad"), ("data_assinatura",)),
    (re.compile(r"\bfiscal"), ("fiscal",)),
    (re.compile(r"\bgestor"), ("gestor",)),
    (re.compile(r"\bnumero\b"), ("numero",)),
]


def pede_dado_da_ficha(pergunta: str, campos: dict) -> bool:
    texto = normalizar(pergunta)
    return bool(RE_PEDE_DADO.search(texto)) and any(
        padrao.search(texto) and any(c in campos for c in nomes) for padrao, nomes in DADOS_DA_FICHA)
PALAVRAS_VAZIAS = set("""qual quais como quando onde quem sobre trata contrato contratos para pela pelo com sem que
existe existem tem foi esta sera houve possui algum alguma ainda numero ano anos meses dias valor prazo vigencia
fiscal gestor empresa objeto empenho empenhos termo termos recebimento definitivo provisorio aditivo aditivos nota
notas fiscal fiscais pagamento pagamentos aberta aberto ordem servico atual atualmente documento documentos""".split())  # noqa: SIM905, E501
MAX_ITENS = 8
# assuntos de documento: a ficha responde existência/listas ("há…?", "quais…?"); conteúdo ("qual o percentual
# apostilado?") exige ler o documento → caminho completo (validação: 1/11 acertos sem essa regra)
FORMA_EXISTENCIA = re.compile(r"^(ha|tem|existe|existem|houve|foi|foram|quais|quantos|quantas|liste|listar|"
                              r"relacione|teve|tiveram|consta|constam|ja)\b|\b(algum|alguma|alguns|algumas)\b")
# pergunta sobre regra/procedimento ("quais documentos são exigidos para o pagamento?", "como deve ser feita a
# fiscalização?"): pede o conteúdo de normas e cláusulas, não o inventário das pastas (antes listava as notas fiscais)
RE_NORMATIVA = re.compile(r"exigid|exige|necessari|obrigatori|requisit|procediment|\bcomo (?:deve|devo|devem|se faz|"
                          r"se deve|fazer|e feit|sao feit)|o que (?:diz|preve|determina|estabelece)")
FORA_DA_FICHA = re.compile(r"preposto|representante|socio|responsavel tecnico|endereco|telefone|e-?mail|"
                           r"\bcpf\b|procurador")
ROTULO_ASSUNTO = {"paralisacao": ("documento de paralisação, suspensão ou extinção",
                                  "documentos de paralisação, suspensão ou extinção")}
TERMOS_TEXTO = {  # palavras (sem acento) que confirmam a ausência no texto da pasta antes de afirmá-la
    "nota_empenho": ["empenh"], "termo_recebimento": ["recebimento"], "termo_rescisao": ["rescis", "rescind"],
    "notificacao": ["notifica"], "apostilamento": ["apostil"], "nota_fiscal": ["nota fiscal", "notas fiscais"],
    "pagamento": ["pagament"], "termo_paralisacao": ["paralis"], "ordem_suspensao": ["suspens"],
    "ordem_reinicio": ["reinicio", "rein"], "termo_retomada": ["retomad"], "ordem_servico": ["ordem de servi"],
    "aditivo": ["aditiv"], "portaria_designacao": ["designa"], "extrato_publicacao": ["extrato"],
    "relatorio_fiscalizacao": ["relatorio de fiscaliza"], "garantia": ["garantia"],
    "relatorio_apuracao": ["apura"],
}
# "Quais contratos/processos estão em fase de renovação / vencem / vencidos / vigentes?" → panorama de vigência
RE_PANORAMA = re.compile(r"(fase de renova|renovac|renovar|a vencer|vencend|vencem|vencer|vencimento|expira|"
                         r"encerrad|vigentes|proximos? do (fim|vencimento))")
RE_PLURAL_CONTRATOS = re.compile(r"\b(quais|que|quantos)\b|\bcontratos\b|\bprocessos\b")
JANELA_RENOVACAO_DIAS = 120
# "Há pendência em algum contrato?" / "algum problema nos contratos?" → pontos de atenção pelas fichas
RE_PENDENCIA = re.compile(r"pendenc|pendent|irregularidad|pontos? de atencao")
RE_ALGUM_CONTRATO = re.compile(r"\b(algum|alguns|nos|dos|quais|que)\s+contratos?\b|\bcontratos\b")
EXECUCAO = ["nota_fiscal", "pagamento", "termo_recebimento", "nota_empenho"]
RE_TRANSVERSAL = re.compile(r"\b(quais|quantos|algum|alguns|em que|que)\s+contratos?\b|\bcontratos\b")
RE_NOME = re.compile(r"contrat\w*\s+(?:d[aoe]s?|com(?:\s+[ao])?|junto\s+[aà])\s+([a-z0-9][a-z0-9 .&-]{2,50})")


def _sem_numero_inconsistente(ficha: dict) -> dict:
    """Descarta o "número" extraído que não contém a chave do contrato (nº da pasta/inventário). Rodada 18: em 5 das
    17 fichas com número ele era de processo ou de outro contrato — e virava o cabeçalho "Contrato nº ..." das
    respostas e um falso documento-chave. Sem ele, todos os usos caem na chave (conferida pelo agrupamento)."""
    numero = (ficha.get("campos") or {}).get("numero")
    if not isinstance(numero, dict) or ficha.get("chave") in chaves_no_texto(str(numero.get("valor", "")),
                                                                             so_contrato=False):
        return ficha
    return {**ficha, "campos": {k: v for k, v in ficha["campos"].items() if k != "numero"}}


def _sem_acento_posicional(texto: str) -> str:
    """Minúsculas sem acento com o MESMO comprimento do original (posições valem nos dois)."""
    import unicodedata

    return "".join((unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode() or " ")[:1].lower()
                   for ch in texto)


def _data(iso: str | None) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else "data não identificada"


@dataclass
class RespostaFicha:
    """Mesmo formato da RespostaF1 (o orquestrador e a API tratam igual). A confiança é calculada pelo sistema em
    `responder` (app/domain/confianca.py) com os mesmos critérios do caminho pelo LLM; ressalvas da ficha entram
    como sinais em `observacoes`."""
    resposta: str
    classificacao: str
    confianca: float | None
    fontes: list
    lacunas: list = field(default_factory=list)
    modelo: str = "ficha-do-contrato"
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    observacoes: list = field(default_factory=list)
    bruto: dict | None = None
    confianca_modelo: float | None = None
    criterio_confianca: list = field(default_factory=list)
    trechos_examinados: int = 0


class ResponderPorFicha:
    def __init__(self, repositorio_fichas, repositorio_trechos, *, validade_s: float = 60.0, conflitos=None):
        """conflitos: ConflitosPort do grafo — se há contradição registrada sobre o campo perguntado (RF-09), a
        ficha não responde e o caminho completo apresenta as duas fontes."""
        self.fichas, self.trechos, self.validade = repositorio_fichas, repositorio_trechos, validade_s
        self.conflitos = conflitos
        self._cache, self._lido = [], 0.0

    def _todas(self) -> list[dict]:
        if time.time() - self._lido > self.validade:
            self._cache, self._lido = [_sem_numero_inconsistente(f) for f in self.fichas.todas()], time.time()
        return self._cache

    def localizar(self, pergunta: str) -> tuple[str | None, object]:
        """("ficha", f) | ("varias", [f…]) quando um nome casa com 2–5 contratos | ("desconhecido", chave) quando a
        pergunta cita um contrato de número sem ficha | (None, None)."""
        fichas = self._todas()
        if not fichas:
            return None, None
        texto = normalizar(pergunta)
        numeros = [chave(n, a) for n, a in RE_NUMERO.findall(texto)]
        for k in numeros:
            achadas = [f for f in fichas if f["chave"] == k] or [f for f in fichas if k in f.get("apelidos", [])]
            if len(achadas) == 1:
                return "ficha", achadas[0]
        if numeros:
            citados = [chave(n, a) for n, a in RE_CONTRATO_NO_TEXTO.findall(texto)]
            return ("desconhecido", citados[0]) if citados else (None, None)
        m = RE_NOME.search(texto)  # só o que vem depois de "contrato do/da/com…"
        palavras = [p for p in re.findall(r"[a-z0-9]{4,}", m.group(1)) if p not in PALAVRAS_VAZIAS] if m else []
        conjuntos = [{f["chave"] for f in fichas if re.search(rf"\b{re.escape(p)}", f.get("texto_busca") or "")}
                     for p in palavras]
        conjuntos = [c for c in conjuntos if c]
        if not conjuntos:
            return None, None
        comuns = set.intersection(*conjuntos)  # contratos que casam com todas as palavras do nome
        if len(comuns) == 1:
            return "ficha", next(f for f in fichas if f["chave"] in comuns)
        if 2 <= len(comuns) <= 5:
            return "varias", sorted((f for f in fichas if f["chave"] in comuns), key=lambda f: f["chave"])
        return None, None

    def escopo(self, pergunta: str) -> set[int] | None:
        """Documentos do contrato citado (pasta inteira; sem pasta, o inventário) — para a busca do caminho completo
        ficar no contrato quando a ficha não basta. None se a pergunta não identifica um contrato."""
        tipo, achado = self.localizar(pergunta)
        if tipo != "ficha":
            return None
        da_pasta = getattr(self.fichas, "documentos_da_pasta", None)
        ids = da_pasta(achado["pasta"]) if achado.get("pasta") and da_pasta else set()
        return ids or {d["documento_id"] for d in achado["documentos"]} or None

    def documentos_chave(self, pergunta: str) -> set[int] | None:
        """Documentos de onde vieram os dados da ficha do contrato citado (instrumento, extrato, aditivos, portaria
        de designação). Rodada 18: a pasta de um contrato chega a 800 documentos (até 190 cópias tipadas como
        "contrato" em processos de pagamento) e a busca geral trazia o documento certo em só 41% das perguntas;
        estes documentos entram primeiro na busca do caminho completo. None se a pergunta não identifica um contrato."""
        tipo, ficha = self.localizar(pergunta)
        if tipo != "ficha" or self._com_contradicao(ficha):
            return None
        ids = [v["trecho_id"] for k, v in ficha["campos"].items()
               if not k.startswith("_") and isinstance(v, dict) and v.get("trecho_id")]
        return {t.documento_id for t in self.trechos.obter(list(dict.fromkeys(ids)))} or None

    def contexto_f1(self, pergunta: str, janela: int = 100):
        """Para a F1 sobre um contrato com ficha, quando a ficha não respondeu sozinha (pergunta com outras palavras ou
        sobre outro dado): (texto da ficha com TODOS os dados conferidos e citações [T<id>], trechos de origem
        reduzidos a janelas LITERAIS de ±`janela` caracteres em torno de cada valor). Rodada 18: os trechos inteiros
        custavam ≈ 2.300 tokens (≈ 17 s de leitura nesta GPU); as janelas mantêm o valor citável e conferível pelo
        verificador (ele confere contra o texto que o modelo viu). None se a pergunta não identifica um contrato."""
        tipo, ficha = self.localizar(pergunta)
        if tipo != "ficha" or self._com_contradicao(ficha):
            return None
        c = ficha["campos"]
        pede = pede_dado_da_ficha(pergunta, c)
        # pergunta que pede um dado da ficha: só esse dado (e o nº do contrato) com a janela de origem — com todos os
        # dados, contratos com aditivos e portarias chegavam a 11 janelas (25–49 s)
        texto_n = normalizar(pergunta)
        pedidos = {n for padrao, nomes in DADOS_DA_FICHA if padrao.search(texto_n) for n in nomes} | {"numero"}
        linhas, valores = [], {}
        for nome in ("numero", "contratada", "cnpj_contratada", "objeto", "data_assinatura", "valor_global",
                     "valor_atual", "vigencia", "vigencia_inicio", "vigencia_fim", "vigencia_atual_fim",
                     "prazo_prorrogacao", "fiscal", "gestor"):
            item = c.get(nome)
            if not (isinstance(item, dict) and item.get("trecho_id")) or (pede and nome not in pedidos):
                continue
            valores.setdefault(item["trecho_id"], []).append(str(item["valor"]))
            atual = c.get("valor_atual")
            if nome == "valor_global" and isinstance(atual, dict) and atual.get("trecho_id"):
                # uma linha com os dois valores: com linhas separadas o modelo respondia só o atualizado (2/6)
                linhas.append(f"- Valor global: original R$ {str(item['valor']).removeprefix('R$').strip()} "
                              f"[T{item['trecho_id']}]; atualizado por aditivo: "
                              f"R$ {str(atual['valor']).removeprefix('R$').strip()} [T{atual['trecho_id']}]")
                continue
            if nome == "valor_atual" and isinstance(c.get("valor_global"), dict) and c["valor_global"].get("trecho_id"):
                continue  # já está na linha do valor global
            valor = _data(item["valor"]) if nome.startswith("aditivo_") else item["valor"]
            linhas.append(f"- {ROTULO_CAMPO.get(nome, nome)}: {valor} [T{item['trecho_id']}]")
        if not linhas:
            return None
        trechos = []
        for t in self.trechos.obter(list(valores)):
            texto, partes = t.texto, []
            base = _sem_acento_posicional(texto)
            for v in valores[t.id]:
                palavras = re.findall(r"\w+", _sem_acento_posicional(v))[:8]
                m = re.search(r"\W+".join(map(re.escape, palavras)), base) if palavras else None
                if m is None:
                    continue
                ini, fim = max(0, m.start() - janela), min(len(texto), m.end() + janela)
                partes.append((ini, fim))
            if not partes:  # valor não localizado literalmente: o trecho vai como está (a compressão o reduz)
                trechos.append(t)
                continue
            partes.sort()
            unidas = [list(partes[0])]
            for ini, fim in partes[1:]:
                if ini <= unidas[-1][1]:
                    unidas[-1][1] = max(unidas[-1][1], fim)
                else:
                    unidas.append([ini, fim])
            recorte = " […] ".join(texto[i:f].strip() for i, f in unidas)
            t.texto = ("[…] " if unidas[0][0] > 0 else "") + recorte + (" […]" if unidas[-1][1] < len(texto) else "")
            trechos.append(t)
        numero = (c.get("numero") or {}).get("valor") or ficha["chave"]
        texto = (f"FICHA DO CONTRATO Nº {numero} (dados conferidos contra os trechos citados; use-os e cite os mesmos "
                 f"[T<id>]):\n" + "\n".join(linhas))
        return texto, trechos, pede

    def contexto_decisao(self, pergunta: str, max_trechos: int = 4):
        """Para a decisão (F2) sobre um contrato com ficha: (texto da ficha com citações [T<id>], trechos de origem).
        Os trechos entram no contexto dos especialistas para que os dados da ficha possam ser citados e conferidos.
        None se a pergunta não identifica um contrato com ficha."""
        tipo, ficha = self.localizar(pergunta)
        if tipo != "ficha":
            return None
        c = ficha["campos"]
        linhas, ids = [], []

        def campo(rotulo, *nomes):
            for nome in nomes:
                item = c.get(nome)
                if item and len(ids) < max_trechos or (item and item.get("trecho_id") in ids):
                    if item.get("trecho_id") not in ids:
                        ids.append(item["trecho_id"])
                    valor = _data(item["valor"]) if nome.startswith("aditivo_") else item["valor"]
                    linhas.append(f"- {rotulo}: {valor} [T{item['trecho_id']}]")
                    return

        campo("Objeto", "objeto")
        campo("Valor", "valor_atual", "valor_global")
        campo("Vigência (término)", "vigencia_atual_fim", "vigencia_fim", "vigencia")
        campo("Fiscal", "fiscal")
        campo("Contratada", "contratada")
        campo("Gestor", "gestor")
        fim, fonte, _ = termino(ficha)
        if fim:
            import datetime as dt

            situacao = "vigente" if fim >= dt.date.today() else "vigência encerrada"
            linhas.append(f"- Situação pela data: {situacao} (término {fim:%d/%m/%Y}, {fonte})")
        contagem = {}
        for d in ficha["documentos"]:
            contagem[d["tipo"]] = contagem.get(d["tipo"], 0) + 1
        resumo_docs = ", ".join(f"{n} {ROTULO_TIPO.get(t, (t, t))[0 if n == 1 else 1]}" for t, n in
                                sorted(contagem.items(), key=lambda kv: -kv[1]) if t in ROTULO_TIPO)
        if resumo_docs:
            linhas.append(f"- Documentos na pasta do contrato: {resumo_docs}")
        numero = (c.get("numero") or {}).get("valor") or ficha["chave"]
        texto = (f"FICHA DO CONTRATO Nº {numero} (dados conferidos contra os trechos citados; use-os e cite os mesmos "
                 f"[T<id>]):\n" + "\n".join(linhas))
        return texto, self.trechos.obter(ids)

    def identificar(self, pergunta: str) -> dict | None:
        tipo, achado = self.localizar(pergunta)
        return achado if tipo == "ficha" else None

    def _varias(self, fichas, inicio):
        linhas, citados = [], []
        for f in fichas:
            c = f["campos"]
            numero = c.get("numero") or {}
            partes = [f"Contrato nº {numero.get('valor') or f['chave']}"
                      + (f" [T{numero['trecho_id']}]" if numero.get("trecho_id") else "")]
            if numero.get("trecho_id"):
                citados.append(numero["trecho_id"])
            for campo in ("contratada", "objeto"):
                if campo in c:
                    partes.append(f"{c[campo]['valor']} [T{c[campo]['trecho_id']}]")
                    citados.append(c[campo]["trecho_id"])
            linhas.append("- " + " — ".join(partes))
        resposta = f"Encontrei {len(fichas)} contratos que correspondem ao nome citado:\n" + "\n".join(linhas)
        return RespostaFicha(resposta, "fato", None, self.trechos.obter(list(dict.fromkeys(citados))),
                             ["Mais de um contrato corresponde ao nome: indique o número para detalhes."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:varios_contratos", "varios_contratos"])

    def _transversal(self, texto, inicio):
        """"Quais contratos tiveram notificação em 2025?": junta os inventários das fichas (só assuntos de tipo de
        documento — campos como fiscal ou valor por contrato exigem o número)."""
        assunto = next((a for a in ASSUNTOS if re.search(a[1], texto)), None)
        if assunto is None or not assunto[3] or assunto[2]:
            return None
        nome, _, _, tipos = assunto
        m_ano = re.search(r"\b(20\d{2})\b", RE_NUMERO.sub(" ", texto))
        ano = m_ano.group(1) if m_ano else None
        singular, plural = ROTULO_TIPO.get(tipos[0], (tipos[0], tipos[0]))
        periodo = f" em {ano}" if ano else ""
        achados = []
        for f in sorted(self._todas(), key=lambda f: f["chave"]):
            docs = [d for d in f["documentos"] if d["tipo"] in tipos and (not ano or str(d.get("data") or "")
                                                                           .startswith(ano))]
            if docs:
                achados.append((f, docs))
        if not achados:
            # ausência no acervo inteiro só com ano e se NENHUM trecho cita o assunto junto com o ano
            termos = [t for tipo in tipos for t in TERMOS_TEXTO.get(tipo, [])]
            verificar = getattr(self.fichas, "documento_do_tipo_no_ano", None) or getattr(self.fichas, "menciona_ano",
                                                                                            None)
            if not ano or verificar is None or not termos:
                return None
            if verificar(None, None, termos, ano):
                return self._transversal_candidatos(nome, tipos, ano, singular, inicio)
            resposta = (f"Não localizei {plural}{periodo} no acervo: nenhuma das {len(self._todas())} pastas de "
                        f"contrato tem documento desse tipo{periodo}, e nenhum trecho dos documentos cita o assunto "
                        f"junto com o ano {ano}.")
            return RespostaFicha(resposta, "ausencia", None, [], ["Conferido no inventário e no texto dos documentos."],
                                 latencia_ms=int((time.perf_counter() - inicio) * 1000),
                                 observacoes=["ficha_do_contrato", f"assunto:{nome}", "transversal"])
        ultimos = [docs[-1]["trecho_id"] for _, docs in achados if docs[-1].get("trecho_id")]
        trechos = {t.id: t for t in self.trechos.obter(ultimos)}
        linhas = []
        for f, docs in achados:
            c = f["campos"]
            ident = f"Contrato nº {(c.get('numero') or {}).get('valor') or f['chave']}" + (
                f" — {c['contratada']['valor']}" if "contratada" in c else "")
            t = trechos.get(docs[-1].get("trecho_id"))
            ultimo = f"; o mais recente: {_data(docs[-1].get('data'))}, {(t.titulo or t.arquivo) if t else ''}" \
                f" [T{docs[-1]['trecho_id']}]" if docs[-1].get("trecho_id") else ""
            linhas.append(f"- {ident}: {len(docs)} {singular if len(docs) == 1 else plural}{ultimo}")
        resposta = (f"{len(achados)} contrato(s) com {plural}{periodo} nas pastas do acervo:\n" + "\n".join(linhas))
        return RespostaFicha(resposta, "fato", None, list(trechos.values()),
                             ["Relação baseada na classificação automática dos documentos de cada pasta."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", f"assunto:{nome}", "transversal",
                                          "classificacao_automatica"])

    def _transversal_candidatos(self, nome, tipos, ano, singular, inicio):
        """Nenhum documento classificado no tipo e no ano, mas há documentos DATADOS do ano que começam citando o
        assunto: agrupa por contrato (o gestor sabe onde conferir). Só os sem data → caminho completo."""
        total, itens = self._candidatos(None, tipos, ano, limite=2000)
        do_ano = [d for d in itens if d["no_ano"]]
        if not do_ano:
            return None
        dono = {d["documento_id"]: f for f in self._todas() for d in f["documentos"]}
        grupos: dict[str, list] = {}
        for d in do_ano:  # já vêm do mais recente para o mais antigo
            f = dono.get(d["documento_id"])
            grupos.setdefault(f["chave"] if f else "", []).append((f, d))
        mais_recentes = [g[0][1]["trecho_id"] for g in grupos.values()]
        trechos = {t.id: t for t in self.trechos.obter(mais_recentes)}
        linhas = []
        for chave_grupo, docs in sorted(grupos.items(), key=lambda g: (g[0] == "", g[0]))[:MAX_ITENS]:
            f, d = docs[0]
            c = f["campos"] if f else {}
            ident = (f"Contrato nº {(c.get('numero') or {}).get('valor') or chave_grupo}" if f else
                     "Fora das pastas de contrato")
            t = trechos.get(d["trecho_id"])
            linhas.append(f"- {ident}: {len(docs)} documento(s); o mais recente: {_data(d['data'])}, "
                          f"{(t.titulo or t.arquivo) if t else 'documento'} [T{d['trecho_id']}]")
        sem_data = sum(1 for d in itens if not d["data"])
        resposta = (f"Nenhum documento do acervo foi classificado como {singular}"
                    f" em {ano}, mas {len(do_ano)} documento(s) datados de {ano} começam citando o assunto — confira "
                    f"por contrato:\n" + "\n".join(linhas))
        lacunas = ["Confira nesses documentos se algum é de fato o documento procurado: a classificação automática "
                   "não os reconheceu como tal."]
        if sem_data:
            lacunas.append(f"Outros {sem_data} documento(s) sem data identificada também citam o assunto.")
        return RespostaFicha(resposta, "candidatos", None, list(trechos.values()), lacunas,
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", f"assunto:{nome}", "transversal", "candidatos"])

    def _com_contradicao(self, ficha) -> bool:
        """Há contradição registrada no grafo entre documentos do contrato (qualquer campo)? Então a F1 segue o caminho
        anterior (busca na pasta + regra de conflito do grafo, RF-09): a ficha e os documentos-chave mostrariam um só
        valor (rodada 18: 4 perguntas de conflito do golden set viraram "fato" com o atalho)."""
        if self.conflitos is None:
            return False
        return bool(self.conflitos.entre([d["documento_id"] for d in ficha["documentos"]]))

    def _em_conflito(self, ficha, assunto) -> bool:
        campo = {"valor": "valor_global", "vigencia": "vigencia_fim"}.get(assunto)
        if self.conflitos is None or campo is None:
            return False
        ids = [d["documento_id"] for d in ficha["documentos"]]
        return any(getattr(c, "campo", None) == campo for c in self.conflitos.entre(ids))

    @staticmethod
    def _valor_confiavel(ficha) -> bool:
        """Sem aditivo/apostilamento, vale o valor do instrumento; com eles, só se o valor atualizado veio do mais
        recente (apostilamento de reajuste sem valor extraído → caminho completo)."""
        alteradores = sorted((d for d in ficha["documentos"] if d["tipo"] in ("aditivo", "apostilamento")),
                             key=lambda d: (d.get("data") or "", d["documento_id"]))
        if not alteradores:
            return True
        origem = (ficha["campos"].get("aditivo_valor") or {}).get("documento_id")
        return "valor_atual" in ficha["campos"] and origem == alteradores[-1]["documento_id"]

    def _mencionado(self, ficha, tipos) -> bool:
        """O texto dos documentos da pasta cita o assunto? (se sim, a ausência no inventário pode ser erro de
        classificação — não afirmar). Sem o método no repositório, por segurança, considera mencionado."""
        menciona = getattr(self.fichas, "menciona", None)
        termos = [t for tipo in tipos for t in TERMOS_TEXTO.get(tipo, [])]
        if menciona is None or not termos:
            return True
        return menciona(ficha.get("pasta"), [d["documento_id"] for d in ficha["documentos"]], termos)

    def _mencionado_ano(self, ficha, tipos, ano) -> bool:
        """Há documento do assunto no ano (pelo início do documento + data)? Sem o método, termo + ano no texto."""
        verificar = getattr(self.fichas, "documento_do_tipo_no_ano", None) or getattr(self.fichas, "menciona_ano",
                                                                                        None)
        termos = [t for tipo in tipos for t in TERMOS_TEXTO.get(tipo, [])]
        if verificar is None or not termos:
            return True
        return verificar(ficha.get("pasta"), [d["documento_id"] for d in ficha["documentos"]], termos, ano)

    def _candidatos(self, ficha, tipos, ano, limite=MAX_ITENS):
        """(total, itens) dos documentos cujo início cita o assunto e que são do ano (ou sem data)."""
        buscar = getattr(self.fichas, "candidatos_do_tipo_no_ano", None)
        termos = [t for tipo in tipos for t in TERMOS_TEXTO.get(tipo, [])]
        if buscar is None or not termos:
            return 0, []
        if ficha is None:
            return buscar(None, None, termos, ano, limite)
        return buscar(ficha.get("pasta"), [d["documento_id"] for d in ficha["documentos"]], termos, ano, limite)

    def _panorama(self, texto, inicio):
        """Situação de vigência de todos os contratos: encerrados, vencendo em até 120 dias (fase de renovação) e
        vigentes — pela vigência atual (aditivo), pelo término do instrumento ou calculada (início/assinatura +
        prazo). Cada data cita o trecho; datas calculadas e aditivos posteriores são sinalizados."""
        import datetime as dt

        hoje = dt.date.today()
        grupos = {"encerrados": [], "vencendo": [], "vigentes": [], "sem_data": []}
        citados = []
        for f in sorted(self._todas(), key=lambda f: f["chave"]):
            fim, fonte, trechos_ids = termino(f)
            c = f["campos"]
            ident = f"Contrato nº {(c.get('numero') or {}).get('valor') or f['chave']}" + (
                f" — {c['contratada']['valor']}" if "contratada" in c else "")
            if fim is None:
                grupos["sem_data"].append(f"- {ident}")
                continue
            citados += trechos_ids
            aviso = " (há termo aditivo posterior: pode ter sido prorrogado)" if aditivo_posterior(f, fonte) else ""
            linha = f"- {ident}: término {fim:%d/%m/%Y} ({fonte}){''.join(f' [T{t}]' for t in trechos_ids)}{aviso}"
            if fim < hoje:
                grupos["encerrados"].append((fim, linha))
            elif (fim - hoje).days <= JANELA_RENOVACAO_DIAS:
                grupos["vencendo"].append((fim, linha))
            else:
                grupos["vigentes"].append((fim, linha))
        if not any(grupos[g] for g in ("encerrados", "vencendo", "vigentes")):
            return None  # nenhuma ficha com data: o caminho completo procura nos documentos
        partes = []
        foco_renovacao = re.search(r"renova|vencend|a vencer|vencem|vencer|vencimento|expira|proximo", texto)
        ordem = ["vencendo", "encerrados", "vigentes"] if foco_renovacao else ["vigentes", "vencendo", "encerrados"]
        titulos = {"vencendo": f"Vencem nos próximos {JANELA_RENOVACAO_DIAS} dias (fase de renovação/nova contratação)",
                   "encerrados": "Vigência encerrada pela data", "vigentes": "Vigentes por mais de 120 dias"}
        for g in ordem:
            itens = [linha for _, linha in sorted(grupos[g])]
            partes.append(f"{titulos[g]}: {len(itens)}" + (":\n" + "\n".join(itens) if itens else "."))
        if grupos["sem_data"]:
            partes.append(f"Sem data de término identificada na ficha: {len(grupos['sem_data'])}.")
        resposta = (f"Situação de vigência dos {len(self._todas())} contratos do acervo em {hoje:%d/%m/%Y}:\n"
                    + "\n".join(partes))
        lacunas = ["Datas \"calculadas\" = início ou assinatura + prazo de vigência do instrumento.",
                   "Situação pela data; termos de rescisão ou aditivos posteriores podem alterá-la."]
        return RespostaFicha(resposta, "inferencia", None, self.trechos.obter(list(dict.fromkeys(citados))),
                             lacunas, latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:panorama_vigencia", "transversal"])

    def _pendencias(self, fichas, inicio, hoje=None):
        """"Há pendência em algum contrato?": pontos de atenção deduzidos das fichas, cada um com a fonte —
        vencimento próximo, execução datada depois do término, notificação/apuração recente e contrato vigente
        sem empenho no exercício. É inferência sobre datas e tipos automáticos: o gestor confere."""
        import datetime as dt

        hoje = hoje or dt.date.today()
        pontos, citados, sem_termino = [], [], 0
        for f in sorted(fichas, key=lambda f: f["chave"]):
            c = f["campos"]
            ident = f"Contrato nº {(c.get('numero') or {}).get('valor') or f['chave']}" + (
                f" — {c['contratada']['valor']}" if "contratada" in c else "")
            docs = f["documentos"]

            def ultimo(tipos, depois_de="", docs=docs):
                achados = [d for d in docs if d["tipo"] in tipos and str(d.get("data") or "") > depois_de]
                return len(achados), (max(achados, key=lambda d: d["data"]) if achados else None)

            def ref(d):
                if d and d.get("trecho_id"):
                    citados.append(d["trecho_id"])
                    return f" [T{d['trecho_id']}]"
                return ""

            itens = []
            fim, fonte, trechos_fim = termino(f)
            if fim is None:
                sem_termino += 1
            else:
                cita_fim = "".join(f" [T{t}]" for t in trechos_fim)
                posterior = aditivo_posterior(f, fonte)
                if hoje <= fim and (fim - hoje).days <= JANELA_RENOVACAO_DIAS:
                    citados.extend(trechos_fim)
                    itens.append(f"vigência termina em {fim:%d/%m/%Y} ({(fim - hoje).days} dias): decidir renovação "
                                 f"ou nova contratação{cita_fim}")
                elif fim < hoje:
                    n, d = ultimo(EXECUCAO, fim.isoformat())
                    if n and posterior:
                        citados.extend(trechos_fim)
                        itens.append(f"término pela ficha em {fim:%d/%m/%Y}{cita_fim}, mas há termo aditivo posterior "
                                     f"e {n} documento(s) de execução depois dessa data: conferir a prorrogação")
                    elif n:
                        citados.extend(trechos_fim)
                        itens.append(f"vigência encerrada em {fim:%d/%m/%Y}{cita_fim}, mas há {n} documento(s) de "
                                     f"execução datados depois (o mais recente: {_data(d['data'])}{ref(d)}): conferir "
                                     f"a cobertura contratual")
                if fim >= hoje:
                    empenhos = [d for d in docs if d["tipo"] == "nota_empenho"]
                    do_ano = [d for d in empenhos if str(d.get("data") or "").startswith(str(hoje.year))]
                    if empenhos and not do_ano and all(d.get("data") for d in empenhos):
                        d = max(empenhos, key=lambda d: d["data"])
                        itens.append(f"vigente, sem nota de empenho datada de {hoje.year} na pasta (a mais recente: "
                                     f"{_data(d['data'])}{ref(d)})")
            n, d = ultimo(["notificacao", "relatorio_apuracao"], (hoje - dt.timedelta(days=365)).isoformat())
            if n:
                itens.append(f"{n} notificação(ões)/relatório(s) de apuração nos últimos 12 meses (o mais recente: "
                             f"{_data(d['data'])}{ref(d)})")
            if itens:
                pontos.append(f"- {ident}:\n" + "\n".join(f"  • {i}" for i in itens))
        lacunas = ["Pontos de atenção deduzidos das datas e da classificação automática dos documentos de cada "
                   "pasta: confirme na pasta antes de agir."]
        if sem_termino:
            lacunas.append(f"{sem_termino} contrato(s) sem data de término identificada na ficha (vencimento não "
                           "avaliado).")
        if not pontos and sem_termino == len(fichas):
            return None  # nada avaliável nas fichas: não afirmar "sem pendências" — caminho completo
        alvo = "contrato" if len(fichas) == 1 else f"{len(fichas)} contratos do acervo"
        if pontos:
            resposta = (f"{len(pontos)} contrato(s) com pontos de atenção em {hoje:%d/%m/%Y} (entre os {alvo}):\n"
                        if len(fichas) > 1 else f"Pontos de atenção em {hoje:%d/%m/%Y}:\n") + "\n".join(pontos)
        else:
            resposta = (f"Não identifiquei pontos de atenção nas fichas ({alvo}) em {hoje:%d/%m/%Y}: nenhum "
                        f"vencimento em até {JANELA_RENOVACAO_DIAS} dias, execução após o término, notificação ou "
                        "apuração recente, nem contrato vigente sem empenho no exercício.")
        return RespostaFicha(resposta, "inferencia", None, self.trechos.obter(list(dict.fromkeys(citados))),
                             lacunas, latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:pendencias", "pendencias_por_regra"]
                             + (["transversal"] if len(fichas) > 1 else []))

    @staticmethod
    def _situacao_vigencia(ficha, linhas, lacunas):
        """Situação pela data (vigente/encerrada) e aviso se houver aditivo mais recente que o usado."""
        import datetime as dt

        c = ficha["campos"]
        aditivos = sorted((d for d in ficha["documentos"] if d["tipo"] == "aditivo"),
                          key=lambda d: (d.get("data") or "", d["documento_id"]))
        usado = (c.get("aditivo_vigencia") or {}).get("documento_id")
        fim = data_do_texto((c.get("vigencia_atual_fim") or c.get("vigencia_fim") or {}).get("valor", ""))
        if fim:
            hoje = dt.date.today()
            situacao = (f"vigente até {fim:%d/%m/%Y}" if fim >= hoje else f"vigência encerrada em {fim:%d/%m/%Y}")
            if any(d["tipo"] == "termo_rescisao" for d in ficha["documentos"]):
                situacao += " — há termo de rescisão na pasta (ver abaixo)"
            linhas.append(f"Situação pela data: {situacao}")
        elif "vigencia_fim" not in c and "vigencia_atual_fim" not in c:
            lacunas.append("Data de término não identificada.")
        if aditivos and (usado is None or aditivos[-1]["documento_id"] != usado):
            base = "do aditivo de prorrogação identificado" if usado else "do instrumento original"
            linhas.append(f"Atenção: as datas acima são {base}; há termo aditivo mais recente "
                          f"({_data(aditivos[-1].get('data'))}) que pode ter alterado a vigência — confira.")
            lacunas.append("Vigência atual depende do termo aditivo mais recente.")
        return linhas, lacunas

    def _numero_de_outro_documento(self, numero, info, inicio):
        trechos = {t.id: t for t in self.trechos.obter([d["trecho_id"] for d in info["documentos"]])}
        linhas = []
        for d in info["documentos"]:
            t = trechos.get(d["trecho_id"])
            tipo = ROTULO_TIPO.get(d["tipo"] or "", (d["tipo"] or "documento",))[0]
            linhas.append(f"- {_data(d.get('data'))}: {(t.titulo or t.arquivo) if t else tipo} ({tipo}) "
                          f"[T{d['trecho_id']}]")
        resposta = (f"Não localizei contrato com o nº {numero}: o número não aparece como número de contrato em nenhum "
                    f"documento do acervo, nem nas {len(self._todas())} pastas de contrato. Ele aparece em "
                    f"{info['trechos']} trecho(s) de outros documentos — por exemplo:\n" + "\n".join(linhas))
        return RespostaFicha(resposta, "ausencia", None, list(trechos.values()),
                             ["Confira se o número se refere a outro documento (apostilamento, empenho, extrato…)."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:numero_de_outro_documento"])

    def _desconhecido(self, numero, inicio):
        """Contrato citado sem ficha: afirma que não há contrato com esse número se ele não aparece em nenhum trecho
        — ou se aparece, mas nunca COMO número de contrato (então mostra onde aparece: apostilamento, extrato…)."""
        detalhar = getattr(self.fichas, "numero_no_acervo", None)
        if detalhar is not None:
            info = detalhar(numero)
            if info["trechos"] and not info["como_contrato"]:
                return self._numero_de_outro_documento(numero, info, inicio)
            if info["trechos"]:
                return None  # citado como contrato em algum documento: o caminho completo lê
        contar = getattr(self.fichas, "ocorrencias_numero", None)
        if detalhar is None and (contar is None or contar(numero) != 0):
            return None
        resposta = (f"Não localizei o Contrato nº {numero} no acervo indexado: o número não aparece em nenhum "
                    f"documento, e nenhum dos {len(self._todas())} contratos com pasta própria tem esse número.")
        return RespostaFicha(resposta, "ausencia", None, [], ["Confira o número do contrato informado."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:contrato_inexistente"])

    def responder(self, pergunta: str):
        """Resposta pela ficha (ou None: o caminho completo responde), com a confiança calculada pelo sistema."""
        r = self._responder(pergunta)
        return conf.aplicar(r, "ficha") if r is not None else None

    def _responder(self, pergunta: str):
        inicio = time.perf_counter()
        texto = normalizar(pergunta)
        tipo_local, achado = self.localizar(pergunta)
        if tipo_local == "desconhecido":
            return self._desconhecido(achado, inicio)
        if tipo_local == "varias":
            assunto = next((a for a in ASSUNTOS if re.search(a[1], texto)), None)
            if assunto and assunto[0] in ("objeto", "contratada", "numero"):
                return self._varias(achado, inicio)
            return None
        if RE_NORMATIVA.search(texto):
            return None  # regra ou procedimento: o caminho completo lê as cláusulas e normas
        # "pendência de pagamento/empenho…" tem assunto próprio: segue o fluxo do assunto
        if RE_PENDENCIA.search(texto) and not FORA_DA_FICHA.search(texto) and not any(
                re.search(a[1], texto) for a in ASSUNTOS):
            if tipo_local is None and RE_ALGUM_CONTRATO.search(texto) and self._todas():
                return self._pendencias(self._todas(), inicio)
            if tipo_local == "ficha":
                return self._pendencias([achado], inicio)
        if tipo_local is None and RE_PANORAMA.search(texto) and RE_PLURAL_CONTRATOS.search(texto):
            return self._panorama(texto, inicio)
        if tipo_local is None:
            assunto_doc = next((a for a in ASSUNTOS if re.search(a[1], texto)), None)
            existencia = bool(assunto_doc and assunto_doc[3] and not assunto_doc[2] and FORMA_EXISTENCIA.search(texto))
            if RE_TRANSVERSAL.search(texto) or existencia:  # "houve notificação em 2025?" sem contrato: todos
                return self._transversal(texto, inicio)
        if tipo_local != "ficha":
            return None
        ficha = achado
        assunto = next((a for a in ASSUNTOS if re.search(a[1], texto)), None)
        if assunto is None:
            return None
        nome, _, campos, tipos = assunto
        if FORA_DA_FICHA.search(texto):
            return None  # preposto, representante, endereço…: a ficha não guarda esses dados
        if self._em_conflito(ficha, nome):
            return None  # contradição registrada no grafo sobre este campo: o caminho completo mostra as fontes
        if tipos and not campos and not FORMA_EXISTENCIA.search(texto):
            return None  # pergunta sobre o CONTEÚDO de um documento: o caminho completo lê o documento
        if nome == "numero" and "numero" not in ficha["campos"]:
            return None  # sem o número conferido num trecho: o caminho completo procura nos documentos
        if nome == "valor" and not self._valor_confiavel(ficha):
            return None  # houve aditivo/apostilamento sem valor atualizado extraído: o caminho completo lê
        if nome == "vigencia" and "vigencia_atual_fim" in ficha["campos"]:
            tipos = ["termo_rescisao"]  # com a vigência atual extraída, a lista de aditivos só polui a resposta
        m_ano = re.search(r"\b(20\d{2})\b", RE_NUMERO.sub(" ", texto))  # ano do filtro, fora do nº do contrato
        ano = m_ano.group(1) if m_ano else None
        rotulo_contrato = f"Contrato nº {(ficha['campos'].get('numero') or {}).get('valor') or ficha['chave']}"
        linhas, citados = [], []

        def cita(trecho_id):
            if trecho_id:
                citados.append(trecho_id)
                return f" [T{trecho_id}]"
            return ""

        presentes = [c for c in campos if c in ficha["campos"]]
        if campos and not presentes and not tipos:
            return None  # a ficha não tem o dado: o caminho completo tenta nos documentos
        for c in presentes:
            item = ficha["campos"][c]
            valor = _data(item["valor"]) if c in ("aditivo_vigencia", "aditivo_valor") else item["valor"]
            linhas.append(f"{ROTULO_CAMPO.get(c, c)}: {valor}{cita(item.get('trecho_id'))}")
        lacunas, classificacao = [], "fato"
        if tipos:
            docs = [d for d in ficha["documentos"] if d["tipo"] in tipos and (not ano or str(d.get("data") or "")
                                                                               .startswith(ano))]
            singular, plural = ROTULO_ASSUNTO.get(nome) or ROTULO_TIPO.get(tipos[0], (tipos[0], tipos[0]))
            periodo = f" em {ano}" if ano else ""
            if docs:
                trechos = {t.id: t for t in self.trechos.obter([d["trecho_id"] for d in docs[-MAX_ITENS:]
                                                                 if d.get("trecho_id")])}
                linhas.append(f"{len(docs)} {singular if len(docs) == 1 else plural}{periodo} na pasta do contrato"
                              f"{' (os mais recentes):' if len(docs) > MAX_ITENS else ':'}")
                for d in docs[-MAX_ITENS:]:
                    t = trechos.get(d.get("trecho_id"))
                    descricao = (t.titulo or t.arquivo) if t else ROTULO_TIPO.get(d["tipo"], (d["tipo"],))[0]
                    linhas.append(f"- {_data(d.get('data'))}: {descricao}{cita(d.get('trecho_id'))}")
            elif not presentes and campos:
                return None  # pergunta sobre um dado (fiscal, vigência…) sem o dado nem documentos: caminho completo
            elif not presentes and ano and [d for d in ficha["documentos"] if d["tipo"] in tipos]:
                outros = [d for d in ficha["documentos"] if d["tipo"] in tipos]
                if any(not d.get("data") for d in outros):
                    return None  # algum documento do tipo sem data: não dá para confirmar o ano
                classificacao = "ausencia"
                linhas.append(f"Não localizei {plural}{periodo} na pasta do {rotulo_contrato}; há {len(outros)} "
                              f"{singular if len(outros) == 1 else plural} de outros anos — os mais recentes:")
                trechos = {t.id: t for t in self.trechos.obter([d["trecho_id"] for d in outros[-3:]
                                                                 if d.get("trecho_id")])}
                for d in outros[-3:]:
                    t = trechos.get(d.get("trecho_id"))
                    descricao = (t.titulo or t.arquivo) if t else singular
                    linhas.append(f"- {_data(d.get('data'))}: {descricao}{cita(d.get('trecho_id'))}")
                lacunas.append("Datas dos documentos extraídas automaticamente; confira a pasta do contrato.")
            elif not presentes and self._mencionado(ficha, tipos) and not (ano and not self._mencionado_ano(
                    ficha, tipos, ano)):
                # nada classificado, mas há documentos que COMEÇAM citando o assunto no ano (ou sem data): mostrar
                # esses documentos (antes: caminho completo, ~55 s, que terminava em recusa nas perguntas reais)
                total, itens = self._candidatos(ficha, tipos, ano) if ano else (0, [])
                if not itens:
                    return None  # sem ano: o caminho completo lê os documentos
                classificacao = "candidatos"
                linhas.append(f"Nenhum documento da pasta do {rotulo_contrato} foi classificado como {singular}"
                              f"{periodo}, mas {total} documento(s) começam citando o assunto e são de {ano} ou "
                              f"estão sem data identificada — confira"
                              f"{' (os mais recentes)' if total > len(itens) else ''}:")
                trechos = {t.id: t for t in self.trechos.obter([d["trecho_id"] for d in itens])}
                for d in itens:
                    t = trechos.get(d["trecho_id"])
                    descricao = (t.titulo or t.arquivo) if t else "documento"
                    linhas.append(f"- {_data(d['data']) if d['data'] else 'sem data identificada'}: {descricao}"
                                  f"{cita(d['trecho_id'])}")
                lacunas.append(f"Confira nesses documentos se algum é {singular}{periodo}: a classificação automática "
                               "não os reconheceu como tal.")
            elif not presentes:
                classificacao = "ausencia"
                linhas.append(f"Não localizei {plural}{periodo} entre os {len(ficha['documentos'])} documentos "
                              f"classificados da pasta do {rotulo_contrato}.")
                lacunas.append("A classificação do tipo de documento é automática; confira a pasta do contrato.")
        if not linhas:
            return None
        if nome == "vigencia":
            linhas, lacunas = self._situacao_vigencia(ficha, linhas, lacunas)
        cabecalho = f"{rotulo_contrato}" + (f" — {ficha['campos']['contratada']['valor']}"
                                            if "contratada" in ficha["campos"] and nome not in ("contratada", "numero")
                                            else "")
        corpo = [linha if linha.startswith("- ") or linha.endswith(":") else f"- {linha}" for linha in linhas]
        resposta = cabecalho + ":\n" + "\n".join(corpo)
        fontes = self.trechos.obter(list(dict.fromkeys(citados))) if citados else []
        return RespostaFicha(resposta, classificacao, None, fontes, lacunas,
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", f"assunto:{nome}"])


MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
                                     "setembro", "outubro", "novembro", "dezembro"], start=1)}


def data_do_texto(valor: str):
    """dd/mm/aaaa ou "dd de mês de aaaa" → date (None se não houver data completa)."""
    import datetime as dt

    t = normalizar(valor)
    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", t)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"\b(\d{1,2})\s*(?:o|º)?\s*de\s+([a-z]+)\s+de\s+(20\d{2})\b", t)
        if not m or m.group(2) not in MESES:
            return None
        d, mes, a = int(m.group(1)), MESES[m.group(2)], int(m.group(3))
    try:
        return dt.date(a, mes, d)
    except ValueError:
        return None


def _somar_meses(data, meses):
    import calendar
    import datetime as dt

    ano, mes = divmod(data.month - 1 + meses, 12)
    ano, mes = data.year + ano, mes + 1
    return dt.date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


def termino(ficha):
    """(data, fonte, [trechos]) do término: aditivo > instrumento > calculada; (None, None, []) se não há."""
    import datetime as dt

    c = ficha["campos"]
    for campo, fonte in (("vigencia_atual_fim", "vigência atual, por termo aditivo"), ("vigencia_fim", "instrumento")):
        data = data_do_texto((c.get(campo) or {}).get("valor", ""))
        if data:
            return data, fonte, [c[campo]["trecho_id"]]
    m = re.search(r"(\d{1,3})\s*(?:\([^)]*\))?\s*(mes|meses|ano|anos)\b", normalizar((c.get("vigencia") or {})
                                                                                    .get("valor", "")))
    for campo in ("vigencia_inicio", "data_assinatura"):
        inicio = data_do_texto((c.get(campo) or {}).get("valor", ""))
        if m and inicio:
            meses = int(m.group(1)) * (12 if m.group(2).startswith("ano") else 1)
            return (_somar_meses(inicio, meses) - dt.timedelta(days=1), f"calculada: {campo.replace('_', ' ')} + prazo",
                    [c[campo]["trecho_id"], c["vigencia"]["trecho_id"]])
    return None, None, []


def aditivo_posterior(ficha, fonte) -> bool:
    aditivos = sorted((d for d in ficha["documentos"] if d["tipo"] == "aditivo"),
                      key=lambda d: (d.get("data") or "", d["documento_id"]))
    if not aditivos:
        return False
    usado = (ficha["campos"].get("aditivo_vigencia") or {}).get("documento_id")
    return not (fonte and fonte.startswith("vigência atual") and usado == aditivos[-1]["documento_id"])


ROTULO_CAMPO = {"numero": "Número", "contratada": "Contratada", "cnpj_contratada": "CNPJ da contratada",
                "objeto": "Objeto", "data_assinatura": "Assinatura", "vigencia": "Vigência",
                "vigencia_inicio": "Início da vigência", "vigencia_fim": "Término da vigência",
                "valor_global": "Valor global (original, na assinatura)", "fiscal": "Fiscal", "gestor": "Gestor",
                "vigencia_atual_fim": "Vigência atual — prorrogada até", "prazo_prorrogacao": "Prorrogação",
                "aditivo_vigencia": "Termo aditivo da prorrogação (data)",
                "valor_atual": "Valor atual (após aditivo)", "aditivo_valor": "Termo aditivo do valor (data)"}
