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

from app.application.fichas.agrupamento import RE_CONTRATO_NO_TEXTO, RE_NUMERO, chave, normalizar

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
}
# (assunto, padrão na pergunta normalizada, campos da ficha, tipos de documento) — os de documento vêm primeiro
ASSUNTOS = [
    ("empenho", r"empenh", [], ["nota_empenho"]),
    ("recebimento", r"recebimento", [], ["termo_recebimento"]),
    ("rescisao", r"rescis|rescind", [], ["termo_rescisao"]),
    ("notificacao", r"notifica", [], ["notificacao"]),
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
]
PALAVRAS_VAZIAS = set("""qual quais como quando onde quem sobre trata contrato contratos para pela pelo com sem que
existe existem tem foi esta sera houve possui algum alguma ainda numero ano anos meses dias valor prazo vigencia
fiscal gestor empresa objeto empenho empenhos termo termos recebimento definitivo provisorio aditivo aditivos nota
notas fiscal fiscais pagamento pagamentos aberta aberto ordem servico atual atualmente documento documentos""".split())  # noqa: SIM905, E501
MAX_ITENS = 8
# assuntos de documento: a ficha responde existência/listas ("há…?", "quais…?"); conteúdo ("qual o percentual
# apostilado?") exige ler o documento → caminho completo (validação: 1/11 acertos sem essa regra)
FORMA_EXISTENCIA = re.compile(r"^(ha|tem|existe|existem|houve|foi|foram|quais|quantos|quantas|liste|listar|"
                              r"relacione|teve|tiveram|consta|constam|ja)\b|\b(algum|alguma|alguns|algumas)\b")
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
}
RE_TRANSVERSAL = re.compile(r"\b(quais|quantos|algum|alguns|em que|que)\s+contratos?\b|\bcontratos\b")
RE_NOME = re.compile(r"contrat\w*\s+(?:d[aoe]s?|com(?:\s+[ao])?|junto\s+[aà])\s+([a-z0-9][a-z0-9 .&-]{2,50})")


def _data(iso: str | None) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else "data não identificada"


@dataclass
class RespostaFicha:
    """Mesmo formato da RespostaF1 (o orquestrador e a API tratam igual)."""
    resposta: str
    classificacao: str
    confianca: float
    fontes: list
    lacunas: list = field(default_factory=list)
    modelo: str = "ficha-do-contrato"
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    observacoes: list = field(default_factory=list)
    bruto: dict | None = None


class ResponderPorFicha:
    def __init__(self, repositorio_fichas, repositorio_trechos, *, validade_s: float = 60.0, conflitos=None):
        """conflitos: ConflitosPort do grafo — se há contradição registrada sobre o campo perguntado (RF-09), a
        ficha não responde e o caminho completo apresenta as duas fontes."""
        self.fichas, self.trechos, self.validade = repositorio_fichas, repositorio_trechos, validade_s
        self.conflitos = conflitos
        self._cache, self._lido = [], 0.0

    def _todas(self) -> list[dict]:
        if time.time() - self._lido > self.validade:
            self._cache, self._lido = self.fichas.todas(), time.time()
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

    def identificar(self, pergunta: str) -> dict | None:
        tipo, achado = self.localizar(pergunta)
        return achado if tipo == "ficha" else None

    def _varias(self, fichas, inicio):
        linhas, citados = [], []
        for f in fichas:
            c = f["campos"]
            partes = [f"Contrato nº {(c.get('numero') or {}).get('valor') or f['chave']}"]
            for campo in ("contratada", "objeto"):
                if campo in c:
                    partes.append(f"{c[campo]['valor']} [T{c[campo]['trecho_id']}]")
                    citados.append(c[campo]["trecho_id"])
            linhas.append("- " + " — ".join(partes))
        resposta = f"Encontrei {len(fichas)} contratos que correspondem ao nome citado:\n" + "\n".join(linhas)
        return RespostaFicha(resposta, "fato", 0.85, self.trechos.obter(list(dict.fromkeys(citados))),
                             ["Mais de um contrato corresponde ao nome: indique o número para detalhes."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:varios_contratos"])

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
            return None  # ausência no acervo inteiro não se afirma pela classificação: o caminho completo procura
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
        return RespostaFicha(resposta, "fato", 0.8, list(trechos.values()),
                             ["Relação baseada na classificação automática dos documentos de cada pasta."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", f"assunto:{nome}", "transversal"])

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

    def _desconhecido(self, numero, inicio):
        """Contrato citado sem ficha: só afirma ausência se o número não aparece em NENHUM trecho do acervo."""
        contar = getattr(self.fichas, "ocorrencias_numero", None)
        if contar is None or contar(numero) != 0:
            return None
        resposta = (f"Não localizei o Contrato nº {numero} no acervo indexado: o número não aparece em nenhum "
                    f"documento, e nenhum dos {len(self._todas())} contratos com pasta própria tem esse número.")
        return RespostaFicha(resposta, "ausencia", 0.7, [], ["Confira o número do contrato informado."],
                             latencia_ms=int((time.perf_counter() - inicio) * 1000),
                             observacoes=["ficha_do_contrato", "assunto:contrato_inexistente"])

    def responder(self, pergunta: str):
        inicio = time.perf_counter()
        texto = normalizar(pergunta)
        tipo_local, achado = self.localizar(pergunta)
        if tipo_local == "desconhecido":
            return self._desconhecido(achado, inicio)
        if tipo_local == "varias":
            assunto = next((a for a in ASSUNTOS if re.search(a[1], texto)), None)
            return self._varias(achado, inicio) if assunto and assunto[0] in ("objeto", "contratada") else None
        if tipo_local is None and RE_TRANSVERSAL.search(texto):
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
            elif not presentes and self._mencionado(ficha, tipos):
                return None  # nada classificado, mas o texto da pasta cita o assunto (ou há filtro de ano): ler
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
                                            if "contratada" in ficha["campos"] and nome != "contratada" else "")
        corpo = [linha if linha.startswith("- ") or linha.endswith(":") else f"- {linha}" for linha in linhas]
        resposta = cabecalho + ":\n" + "\n".join(corpo)
        fontes = self.trechos.obter(list(dict.fromkeys(citados))) if citados else []
        return RespostaFicha(resposta, classificacao, 0.9 if classificacao == "fato" else 0.6, fontes, lacunas,
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


ROTULO_CAMPO = {"numero": "Número", "contratada": "Contratada", "cnpj_contratada": "CNPJ da contratada",
                "objeto": "Objeto", "data_assinatura": "Assinatura", "vigencia": "Vigência",
                "vigencia_inicio": "Início da vigência", "vigencia_fim": "Término da vigência",
                "valor_global": "Valor global", "fiscal": "Fiscal", "gestor": "Gestor",
                "vigencia_atual_fim": "Vigência atual — prorrogada até", "prazo_prorrogacao": "Prorrogação",
                "aditivo_vigencia": "Termo aditivo da prorrogação (data)",
                "valor_atual": "Valor atual (após aditivo)", "aditivo_valor": "Termo aditivo do valor (data)"}
