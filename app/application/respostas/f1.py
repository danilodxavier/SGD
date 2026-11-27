"""Caso de uso ResponderF1 (SAD-051): resposta com citação literal [T<id>], classificação e confiança.

Salvaguardas determinísticas (independentes do modelo):
  - sem trechos recuperados → ausência, sem chamar o LLM;
  - citações a trechos fora do contexto são descartadas;
  - resposta factual/inferencial/conflito sem nenhuma citação válida → mensagem institucional de ausência;
  - classificação "ausencia" sempre usa a mensagem institucional.
"""
import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Protocol

from app.application.portas import LLMPort
from app.domain import confianca as conf
from app.domain.politicas import MENSAGEM_AUSENCIA, MENSAGEM_CONFLITO, Classificacao


@dataclass(frozen=True)
class Conflito:
    origem: int  # documento que fixou o valor vigente
    destino: int  # documento que declara valor divergente
    campo: str  # valor_global | vigencia_fim
    valor_vigente: str
    valor_declarado: str
    trecho_origem: object | None = None  # TrechoRecuperado que contém o valor vigente
    trecho_destino: object | None = None  # TrechoRecuperado que contém o valor divergente


class ConflitosPort(Protocol):
    def entre(self, documentos: set) -> list: ...


CAMPOS_DA_PERGUNTA = {  # palavras da pergunta que tornam o conflito daquele campo relevante
    "valor_global": re.compile(r"\bvalor", re.I),
    "vigencia_fim": re.compile(r"vig[êe]ncia|t[ée]rmino|encerra|termina|prazo|at[ée] quando", re.I),
}
ROTULO_CAMPO = {"valor_global": "valor global", "vigencia_fim": "término da vigência"}

PROMPTS = Path(__file__).resolve().parents[1] / "agentes" / "prompts"
SCHEMAS = Path(__file__).resolve().parents[1] / "agentes" / "schemas"
RE_CITACAO = re.compile(r"\bT(\d+)\b")
CAMPOS_F1 = ("resposta", "classificacao", "confianca", "fontes", "lacunas")
# v4 (acervo real, 2026-11-21): "1 a 4 frases" produzia respostas secas, "recortes"; a equipe pediu respostas que
# expliquem o que os documentos dizem. Agora: resposta direta primeiro e, em seguida, os detalhes que a sustentam.
# v6 (rodada 18, gabarito real das fichas): respostas "sustentadas" mas com o dado errado (ex.: o órgão contratante no
# lugar da contratada) e longas demais — a geração de 150–330 tokens custava metade do tempo. Agora: o dado pedido,
# literal, no início da resposta; papéis explícitos; no máximo 3 detalhes.
INSTRUCAO_F1 = ("Modo F1: responda EXATAMENTE ao que foi perguntado: a \"resposta\" começa pelo dado pedido (nome, "
                "número, data, valor, CNPJ, objeto) copiado literalmente do trecho, sem rodeios. Atenção aos papéis: "
                "CONTRATANTE é o órgão público; CONTRATADA é a empresa ou pessoa contratada; fiscal e gestor são "
                "servidores designados. Datas de assinatura, publicação, início e término são fatos diferentes. "
                "Se houver valor original e valor atualizado por aditivo, informe os dois. "
                "Em seguida, apresente os detalhes dos documentos "
                "que a sustentam e que interessam à gestão (documento e nº, partes, objeto, datas, prazos, valores, "
                "situação) no campo \"detalhes\", citando os trechos no texto como [T<id>] "
                "e listando os mesmos ids em \"fontes\". Se a informação não estiver nos trechos, use "
                "classificacao \"ausencia\"; não deduza o fato perguntado de outro fato (ex.: data de publicação a "
                "partir da data de assinatura ou de início). Se os trechos divergirem sobre o fato perguntado, use "
                "\"conflito\" e "
                "apresente o conteúdo de cada fonte. A ficha entre parênteses de cada trecho (tipo, nº, processo, "
                "pasta) faz parte dos trechos: use-a para identificar o documento, o contrato e o fornecedor.")
INSTRUCAO_LISTA = ("A pergunta pede uma RELAÇÃO: em \"detalhes\", ponha um item por documento ou contrato dos "
                   "trechos que atende ao critério perguntado (examine TODOS os trechos), com nº, data e o que consta, "
                   "citando [T<id>] em cada item; na \"resposta\", diga quantos encontrou e que a relação se limita "
                   "aos documentos recuperados para a pergunta.")
INSTRUCAO_HISTORICO = ("A pergunta é sobre situação ou histórico: use a LINHA DO TEMPO (grafo documental) para ordenar "
                       "os documentos e explique a situação atual (vigente, prorrogado, encerrado, pendente etc.), "
                       "citando os trechos [T<id>] que comprovam cada passo; a linha do tempo orienta, mas a citação "
                       "deve ser de trecho.")
# A ordem importa: com schema estrito o Ollama emite as chaves em ordem alfabética e o modelo "decide" a
# classificação antes de redigir a resposta — recusas indevidas (validação: 17/27 factuais viraram ausência).
# Pedir JSON livre com a resposta primeiro corrigiu o comportamento (FASE_05 §4).
# v5 (acervo real): com só "resposta", o modelo escrevia 1 frase e gastava o resto em "fontes"; um campo próprio
# para os detalhes (lista) rende respostas completas. O texto final = resposta + detalhes (montado em `_validar`).
# Detalhe sem citação válida é descartado no código e cada número precisa constar do trecho citado na mesma frase
# (validação: sem essa disciplina a alucinação numérica foi de 0,023 para 0,231).
DETALHES = ("\"detalhes\" (lista de até 3 frases curtas, só as que sustentam a resposta — documento e nº, partes, "
            "objeto, datas, prazos, valores, situação —, cada uma terminando com a citação [T<id>] do trecho que "
            "contém literalmente aquele fato; não repita a resposta; lista vazia se for ausência)")
ORDEM_SAIDA = ("Responda SOMENTE com um objeto JSON com as chaves nesta ordem: \"resposta\" (a resposta direta, "
               "com citações [T<id>]), " + DETALHES + ", \"fontes\" (lista de ids), \"classificacao\" "
               "(fato|inferencia|conflito|ausencia), \"confianca\" (0 a 1), \"lacunas\" (lista).")
# v3 (acervo real): começando pela resposta, o modelo às vezes escreve a frase de recusa antes de examinar os trechos
# (R05, "Qual o contrato do <fornecedor>?": 8 trechos do contrato certo, 6 ids declarados em "fontes" e recusa).
# Só quando a 1ª leitura recusa, uma 2ª leitura lista antes as evidências. Usar essa ordem em toda pergunta custava
# classificação (0,936 → 0,830: mais "conflito") e latência (p50 9,5 → 17,9 s) no corpus acadêmico.
ORDEM_EVIDENCIAS = ("Responda SOMENTE com um objeto JSON com as chaves nesta ordem: \"evidencias\" (lista dos ids "
                    "dos trechos que tratam do assunto da pergunta, incluindo a ficha), \"resposta\" (a resposta "
                    "direta, com citações [T<id>], baseada nas evidências), " + DETALHES + ", \"fontes\" (lista de "
                    "ids), \"classificacao\" "
                    "(fato|inferencia|conflito|ausencia — ausencia só se \"evidencias\" estiver vazia), "
                    "\"confianca\" (0 a 1), \"lacunas\" (lista).")
VERSAO_INSTRUCAO = 6


def _corpo_prompt(arquivo: str) -> str:
    texto = (PROMPTS / arquivo).read_text(encoding="utf-8")
    return texto.split("---", 2)[2].strip() if texto.startswith("---") else texto.strip()


@cache
def partes_prompt(nome: str, versao: int = 1, versao_regras: int = 2) -> tuple[str, str]:
    """(regras comuns, instruções do papel) — separadas para o contexto compartilhado da F2 (cache de prefixo)."""
    return _corpo_prompt(f"_regras_comuns.v{versao_regras}.md"), _corpo_prompt(f"{nome}.v{versao}.md")


@cache
def carregar_prompt(nome: str, versao: int = 1, versao_regras: int = 2) -> str:
    regras, papel = partes_prompt(nome, versao, versao_regras)
    return regras + "\n\n" + papel


@cache
def schema_f1() -> dict:
    completo = json.loads((SCHEMAS / "relator.v1.json").read_text(encoding="utf-8"))
    return {"type": "object", "additionalProperties": False, "required": list(CAMPOS_F1),
            "properties": {c: completo["properties"][c] for c in CAMPOS_F1}}


def _frases(texto: str) -> list[str]:
    """Frases por pontuação e por linha (itens "- " dos detalhes são frases distintas, como no verificador)."""
    return [f.strip() for linha in texto.strip().splitlines()
            for f in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ\[])", linha.strip()) if f.strip()]


PALAVRAS_VAZIAS = {"qual", "quais", "quando", "como", "onde", "para", "pela", "pelo", "pelos", "pelas", "sobre",
                   "entre", "este", "esta", "esse", "essa", "isso", "aquele", "ainda", "também", "após", "ate", "até",
                   "devo", "deve", "pode", "seria", "foram", "está", "estão", "contrato", "documento", "documentos"}
PALAVRAS_VAZIAS_SEM_ACENTO = {unicodedata.normalize("NFKD", p).encode("ascii", "ignore").decode()
                              for p in PALAVRAS_VAZIAS}


def _termos(texto: str) -> set:
    """Palavras de 4+ letras, sem acento. Por radical (5 letras) foi pior: "contr" de "contratada" casa com
    "contrato", presente em quase toda frase, e o objeto saía do contexto (rodada 18: 14 → 8 de 18)."""
    sem = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return {p for p in re.findall(r"[a-z0-9/.-]{4,}", sem) if p not in PALAVRAS_VAZIAS_SEM_ACENTO}


# intenção da pergunta → padrão do dado procurado no trecho (rodada 18: a frase com a resposta muitas vezes não
# repete as palavras da pergunta — o CNPJ não traz a palavra "CNPJ" ao lado, a data de assinatura vem como
# "Cuiabá, 10 de maio de 2022" — e a compressão por termos descartava o valor: de 92% para 55–76% no contexto)
RE_DATA = r"\b\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{2,4}\b|\b\d{1,2}[ºo°]?\s+de\s+[a-zç]+\s+de\s+\d{4}"
INTENCOES = [
    (re.compile(r"\bvalor|quanto custa|pre[cç]o|montante|quanto (?:foi|é|e) pago", re.I), re.compile(r"R\$\s*\d")),
    (re.compile(r"\bquando\b|\bdata\b|assinad|assinatura|vig[eê]n|vigor|prazo|t[ée]rmin|at[ée] quando|venc", re.I),
     re.compile(RE_DATA + r"|\b\d+\s*\(?[a-z ]*\)?\s*(?:meses|dias|anos)\b", re.I)),
    (re.compile(r"cnpj", re.I), re.compile(r"\d{2}\.?\d{3}\.?\d{3}\s*/\s*\d{4}\s*-?\s*\d{2}")),
    (re.compile(r"empresa|contratad|fornecedor|raz[aã]o social", re.I),
     re.compile(r"\b(?:LTDA|EIRELI|EPP|S\.?/A|S\.A\.)\b|CONTRATADA|[Cc]ontratada|CNPJ")),
    (re.compile(r"\bn[uú]mero\b|\bn[ºo°]\b", re.I), re.compile(r"\bn[ºo°.]*\s*\d{1,4}\s*/\s*\d{4}", re.I)),
]  # só dados com FORMATO próprio: palavras como "objeto"/"fiscal" estão em dezenas de frases e empatariam todas


def _padroes(pergunta: str) -> list:
    return [padrao for intencao, padrao in INTENCOES if intencao.search(pergunta or "")]


def _janela(unidade: str, padroes, alvo, limite: int) -> str:
    """Recorte literal de uma frase longa demais em torno do 1º dado procurado (ou do 1º termo da pergunta)."""
    pos = min((m.start() for p in padroes for m in [p.search(unidade)] if m), default=None)
    if pos is None:
        sem = unicodedata.normalize("NFKD", unidade.lower()).encode("ascii", "ignore").decode()
        pos = min((sem.find(a) for a in alvo if sem.find(a) >= 0), default=0)
    ini = max(0, pos - limite // 3)
    trecho = unidade[ini:ini + limite]
    return ("[…] " if ini else "") + trecho.strip() + (" […]" if ini + limite < len(unidade) else "")


def comprimir(texto: str, pergunta: str | None, max_chars: int) -> str:
    """Compressão do contexto orientada pela pergunta (A3; prompt mestre §5): trechos reais sem estrutura chegam a
    2.400 caracteres e o LLM local lê o prompt a ≈ 135 tokens/s. Mantém, na ordem original, as frases que mais
    interessam à pergunta — termos em comum (por radical) e, com peso maior, o TIPO de dado pedido (valor, data,
    CNPJ, razão social, nº…) — até `max_chars`; frase longa demais entra recortada em torno do dado. Cortes viram
    "[…]". O texto mantido é literal."""
    texto = texto.strip()
    if not max_chars or len(texto) <= max_chars:
        return texto
    unidades = [u for linha in texto.splitlines() for u in _frases(linha)]
    alvo, padroes = _termos(pergunta or ""), _padroes(pergunta or "")
    notas = [(len(alvo & _termos(u)) + 3 * sum(1 for p in padroes if p.search(u)), -i) for i, u in enumerate(unidades)]
    if max(notas)[0] == 0:
        return texto[:max_chars].rsplit(" ", 1)[0] + " […]"
    escolhidas, total = {}, 0
    for nota, menos_i in sorted(notas, reverse=True):
        i, resta = -menos_i, max_chars - total
        if nota == 0 or resta < 40:
            break
        u = unidades[i]
        if len(u) + 4 > resta:
            if escolhidas or not any(p.search(u) for p in padroes):
                continue  # frase longa sem o dado procurado: fica de fora (como antes)
            u = _janela(u, padroes, alvo, resta - 10)  # frase longa COM o dado: entra recortada em torno dele
        escolhidas[i] = u
        total += len(u) + 4
    partes, anterior = [], -1
    for i in sorted(escolhidas):
        if i != anterior + 1:
            partes.append("[…]")
        partes.append(escolhidas[i])
        anterior = i
    if anterior != len(unidades) - 1:
        partes.append("[…]")
    return " ".join(partes)


def montar_contexto(trechos, pergunta: str | None = None, max_chars: int | None = None) -> str:
    """Cada trecho leva a ficha do documento (tipo, número, processo, pasta): um recorte do meio de um contrato
    não diz de qual contrato é — no acervo real o número e o fornecedor costumam estar só no nome da pasta."""
    blocos = []
    for t in trechos:
        numero, processo, pasta = getattr(t, "numero", None), getattr(t, "processo", None), getattr(t, "pasta", None)
        meta = " | ".join(str(x) for x in (
            t.titulo, f"tipo: {t.tipo_documental}" if t.tipo_documental else None,
            f"nº {numero}" if numero else None, f"processo: {processo}" if processo else None,
            t.dispositivo, f"pág. {t.pagina}" if t.pagina else None, t.data_documento,
            # pasta: só os 2 primeiros níveis (identificam o contrato e o fornecedor); os internos e "origem: real"
            # somavam ≈ 1.000 tokens por pergunta no acervo real (≈ 7 s de leitura) sem ajudar a responder
            f"pasta: {'/'.join(pasta.split('/')[:2])}" if pasta else None,
            f"origem: {t.corpus_origem}" if t.corpus_origem != "real" else None) if x)
        blocos.append(f"[{t.rotulo}] ({meta})\n{comprimir(t.texto, pergunta, max_chars or 0)}")
    return "\n\n".join(blocos)


def _com_detalhes(resposta: str, detalhes, rotulos_validos=None) -> str:
    """Resposta direta + detalhes; itens que já começam com "- " (relação) ficam um por linha. Detalhe sem citação
    a um trecho do contexto é descartado, assim como repetições (da resposta ou entre si)."""
    itens, vistos = [], {_norm_frase(resposta)}
    for d in detalhes if isinstance(detalhes, list) else []:
        item = str(d).strip()
        citados = {f"T{n}" for n in RE_CITACAO.findall(item)}
        if not item or (rotulos_validos is not None and not citados & rotulos_validos):
            continue
        chave = _norm_frase(item)
        if chave and not any(_parecidas(chave, v) for v in vistos if v):
            vistos.add(chave)
            itens.append(item)
    if not itens:
        return resposta
    if len(itens) >= 2 or any(i.startswith("- ") for i in itens):
        return (resposta + "\n" if resposta else "") + "\n".join(i if i.startswith("- ") else "- " + i for i in itens)
    return (resposta + " " + itens[0]).strip()


def _norm_frase(texto: str) -> str:
    """Frase sem citações, pontuação e caixa — para reconhecer o mesmo fato escrito duas vezes."""
    return " ".join(re.sub(r"\[?T\d+\]?|[^\w\s]", " ", texto.lower()).split())


def _sem_detalhes_reprovados(resposta, reprovadas):
    """Se o verificador só reprovou frases dos detalhes (não a resposta direta), devolve a resposta sem elas; senão
    None (a resposta direta errada merece a nova tentativa com o LLM)."""
    direta = [f.strip() for f in _frases(str((resposta.bruto or {}).get("resposta") or "")) if f.strip()]
    reprovadas = [r.strip() for r in reprovadas if r.strip()]
    if not direta or not reprovadas:
        return None
    if any(d in r.lstrip("- ") or r.lstrip("- ") in d for r in reprovadas for d in direta):
        return None
    restantes = [f for f in _frases(resposta.resposta) if f.strip() and f.strip() not in reprovadas]
    if not restantes:
        return None
    corpo = " ".join(f for f in restantes if not f.startswith("- "))
    itens = [f for f in restantes if f.startswith("- ")]
    texto = corpo + ("\n" + "\n".join(itens) if itens else "")
    citados = {f"T{n}" for n in RE_CITACAO.findall(texto)}
    fontes = [t for t in resposta.fontes if t.rotulo in citados] or resposta.fontes
    return replace(resposta, resposta=texto, fontes=fontes,
                   observacoes=resposta.observacoes + ["verificador_detalhes_removidos"])


def _reparar_citacoes(resposta, verificacao, trechos):
    """Frase reprovada só porque um número dela está em OUTRO trecho do contexto (não no que ela cita): acrescenta a
    citação desse trecho e o inclui nas fontes. Rodada 18: "valor original R$ X; atualizado R$ Y [T1]" citava só o
    trecho do original e a frase inteira era removida — com ela, o dado pedido. Nada sem fonte literal passa: o
    verificador confere de novo. None se não houver o que reparar."""
    from app.application.agentes.verificador import suporte
    from app.application.avaliacao.metricas_resposta import numeros_nao_suportados

    texto, fontes, mudou = resposta.resposta, list(resposta.fontes), False
    # só trechos que a resposta JÁ cita em outra frase: reparar com um trecho novo deixava passar dedução (golden set
    # V036: a data de assinatura apresentada como de publicação ganhava a citação do trecho da assinatura)
    citados_fora = {f"T{n}" for f in _frases(texto) for n in RE_CITACAO.findall(f)}
    for p in verificacao.problemas:
        m = re.search(r"'(.+?)'", p.detalhe)
        if p.tipo != "numero_sem_suporte" or not m or p.frase not in texto:
            continue
        da_frase = {f"T{n}" for n in RE_CITACAO.findall(p.frase)}
        candidatos = [t for t in trechos if t.rotulo in citados_fora - da_frase]
        origem = next((t for t in candidatos if not numeros_nao_suportados(m.group(1), [suporte(t)])), None)
        if origem is None or f"[{origem.rotulo}]" in p.frase:
            continue
        nova = re.sub(r"(\.?)\s*$", rf" [{origem.rotulo}]\1", p.frase, count=1)
        texto = texto.replace(p.frase, nova, 1)
        if origem not in fontes:
            fontes.append(origem)
        mudou = True
    if not mudou:
        return None
    return replace(resposta, resposta=texto, fontes=fontes, observacoes=resposta.observacoes + ["citacao_reparada"])


def _parecidas(a: str, b: str, limiar: float = 0.6) -> bool:
    """Mesmo fato com outras palavras (validação: o detalhe repetia a resposta direta reescrita). Frases com números
    diferentes nunca são o mesmo fato (rodada 18: "valor original R$ X" era descartado como repetição de "valor
    atualizado R$ Y")."""
    if set(re.findall(r"\d+", a)) - set(re.findall(r"\d+", b)):
        return False
    if a in b or b in a:
        return True
    pa, pb = set(a.split()), set(b.split())
    return bool(pa and pb) and len(pa & pb) / len(pa | pb) >= limiar


def _rotulo(f) -> str:
    """Tolera formatos de id ("T12", "[T12]", 12, "12")."""
    rotulo = str(f).strip().strip("[]").strip()
    return f"T{rotulo}" if rotulo.isdigit() else rotulo


@dataclass
class RespostaF1:
    """`confianca`: calculada pelo sistema ao final (app/domain/confianca.py), None em ausência/conflito;
    `confianca_modelo`: autoavaliação declarada pelo LLM — só para a auditoria, não entra no cálculo."""
    resposta: str
    classificacao: str
    confianca: float | None
    fontes: list
    lacunas: list = field(default_factory=list)
    modelo: str | None = None
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    observacoes: list = field(default_factory=list)
    bruto: dict | None = None
    confianca_modelo: float | None = None
    criterio_confianca: list = field(default_factory=list)
    trechos_examinados: int = 0


class ResponderF1:
    def __init__(self, llm: LLMPort, *, max_tokens: int = 700, versao_prompt: int = 3,
                 conflitos: ConflitosPort | None = None, verificador=None, contexto_max_chars: int = 0,
                 limiar_relevancia: float = 0.0):
        """`limiar_relevancia`: nota mínima do reranker (0–1) para chamar o LLM; abaixo dela em TODOS os trechos, a
        pergunta não trata de nada do acervo e é recusada sem LLM. 0 = desligado (só vale com notas do reranker)."""
        self.llm, self.max_tokens, self.versao = llm, max_tokens, versao_prompt
        self.contexto_max_chars = contexto_max_chars  # 0 = trechos inteiros (compressão desligada)
        self.conflitos = conflitos
        self.verificador = verificador  # callable(resposta, citados, pergunta) -> Verificacao
        self.limiar_relevancia = limiar_relevancia

    def responder(self, pergunta: str, trechos, *, linha_do_tempo: str = "", lista: bool = False,
                  ficha: str = "", max_chars: int | None = None) -> RespostaF1:
        """`linha_do_tempo`: resumo do grafo para perguntas de situação/histórico; `lista`: pergunta que pede uma
        relação de documentos (resposta em tópicos, trechos mais curtos para caber mais documentos); `ficha`: ficha
        conferida do contrato citado (vai antes dos trechos); `max_chars`: limite por trecho (padrão: o do construtor).
        A confiança é calculada pelo sistema no fim, a partir dos sinais registrados (verificador, leituras, fontes)."""
        resposta = self._responder(pergunta, trechos, linha_do_tempo=linha_do_tempo, lista=lista, ficha=ficha,
                                   max_chars=max_chars)
        extras = (["sem_verificador"] if self.verificador is None else []) + ([] if ficha else ["leitura_sem_ficha"])
        return conf.aplicar(resposta, "llm", trechos_examinados=len(trechos or []), sinais_extras=extras)

    def _responder(self, pergunta, trechos, *, linha_do_tempo="", lista=False, ficha="", max_chars=None) -> RespostaF1:
        if not trechos:
            return RespostaF1(MENSAGEM_AUSENCIA, Classificacao.AUSENCIA.value, None, [],
                              observacoes=["sem_trechos_recuperados"])
        # com a ficha, o contrato foi identificado (e os trechos de origem não têm nota do reranker): sem o limiar
        relevancia = max(getattr(t, "pontuacao", 1.0) for t in trechos)
        if self.limiar_relevancia and not ficha and relevancia < self.limiar_relevancia:
            # rodada 17 (2026-11-25): "Qual o nome do cachorro do prefeito?" levou 81 s (3 leituras do LLM) para
            # recusar. Calibração: fora do domínio ≤ 0,011; F1 respondível ≥ 0,66 (acadêmico) e real ≥ 0,08
            return RespostaF1(MENSAGEM_AUSENCIA, Classificacao.AUSENCIA.value, None, [],
                              ["Nenhum dos trechos mais próximos da pergunta trata do assunto perguntado."],
                              observacoes=["sem_trecho_relevante"])
        if self.conflitos is not None and (resposta := self._conflito(pergunta, trechos)):
            return resposta
        if max_chars is None:
            max_chars = min(self.contexto_max_chars or 700, 700) if lista else self.contexto_max_chars
        conteudo = (f"PERGUNTA: {pergunta}\n\n" + (f"{ficha}\n\n" if ficha else "")
                    + f"TRECHOS:\n{montar_contexto(trechos, pergunta, max_chars)}")
        if linha_do_tempo:
            conteudo += f"\n\nLINHA DO TEMPO (grafo documental):\n{linha_do_tempo}"
        usuario = {"role": "user", "content": conteudo}
        instrucao = INSTRUCAO_F1 + (" " + INSTRUCAO_LISTA if lista else "") + \
            (" " + INSTRUCAO_HISTORICO if linha_do_tempo else "")
        sistema = carregar_prompt("relator", self.versao) + "\n\n" + instrucao + "\n"
        mensagens = [{"role": "system", "content": sistema + ORDEM_SAIDA}, usuario]
        r = self.llm.chat(mensagens, max_tokens=self.max_tokens, temperatura=0.0, json_livre=True)
        resposta = self._validar(r.json if isinstance(r.json, dict) else {}, trechos, r)
        if resposta.classificacao == Classificacao.AUSENCIA.value:
            segunda = [{"role": "system", "content": sistema + ORDEM_EVIDENCIAS}, usuario]
            r2 = self.llm.chat(segunda, max_tokens=self.max_tokens, temperatura=0.0, json_livre=True)
            dados2 = r2.json if isinstance(r2.json, dict) else {}
            nova = self._validar(dados2, trechos, r2)
            evidencias = [e for e in (_rotulo(x) for x in dados2.get("evidencias") or []) if e in
                          {t.rotulo for t in trechos}]
            if nova.classificacao == Classificacao.AUSENCIA.value and evidencias:
                # contradição: apontou trechos sobre o assunto e recusou (oscila com o LLM local)
                segunda = segunda + [
                    {"role": "assistant", "content": json.dumps(dados2, ensure_ascii=False)},
                    {"role": "user", "content": "Você listou " + ", ".join(evidencias) + " como trechos que tratam "
                     "do assunto da pergunta, mas classificou \"ausencia\". Responda à pergunta com base nesses "
                     "trechos e na ficha deles, citando-os. Se ainda assim não for possível responder, mantenha "
                     "\"ausencia\" e diga em \"lacunas\" o que falta."}]
                r3 = self.llm.chat(segunda, max_tokens=self.max_tokens, temperatura=0.0, json_livre=True)
                terceira = self._validar(r3.json if isinstance(r3.json, dict) else {}, trechos, r3)
                terceira.tokens_entrada += nova.tokens_entrada
                terceira.tokens_saida += nova.tokens_saida
                terceira.latencia_ms += nova.latencia_ms
                terceira.observacoes = nova.observacoes + ["evidencias_contradizem_recusa"] + terceira.observacoes
                nova = terceira
            nova.tokens_entrada += resposta.tokens_entrada
            nova.tokens_saida += resposta.tokens_saida
            nova.latencia_ms += resposta.latencia_ms
            nova.observacoes = resposta.observacoes + ["segunda_leitura_evidencias"] + nova.observacoes
            resposta = nova
            if nova.classificacao != Classificacao.AUSENCIA.value:
                mensagens = segunda
        if self.verificador is None:
            return resposta
        return self._verificar(pergunta, trechos, mensagens, resposta)

    def _verificar(self, pergunta, trechos, mensagens, resposta):
        """RF-17: reprovada → uma nova tentativa com os problemas apontados; persistindo, remove as frases sem
        suporte; se nada sustentado restar, responde ausência."""
        v = self.verificador(resposta.resposta, resposta.fontes, pergunta)
        if v.aprovada:
            return resposta
        reparada = _reparar_citacoes(resposta, v, trechos)
        if reparada is not None:  # número literal de outro trecho do contexto: a citação certa é acrescentada
            v = self.verificador(reparada.resposta, reparada.fontes, pergunta)
            if v.aprovada:
                return reparada
            resposta = reparada
        enxuta = _sem_detalhes_reprovados(resposta, v.frases_reprovadas)
        if enxuta is not None:  # só detalhes reprovados: remove-os sem nova chamada ao LLM (≈ 26 s a menos)
            return enxuta
        problemas = "; ".join(f"{p.detalhe} (frase: \"{p.frase}\")" for p in v.problemas)
        correcao = mensagens + [
            {"role": "assistant", "content": json.dumps(resposta.bruto or {}, ensure_ascii=False)},
            {"role": "user", "content": "VERIFICAÇÃO DE FONTES reprovou a resposta: " + problemas + ". Reescreva "
             "usando SOMENTE valores, datas e situações que constam literalmente nos trechos. Se não constarem, "
             "use classificacao \"ausencia\"."}]
        r2 = self.llm.chat(correcao, max_tokens=self.max_tokens, temperatura=0.0, json_livre=True)
        nova = self._validar(r2.json if isinstance(r2.json, dict) else {}, trechos, r2)
        nova.tokens_entrada += resposta.tokens_entrada
        nova.tokens_saida += resposta.tokens_saida
        nova.latencia_ms += resposta.latencia_ms
        nova.observacoes = resposta.observacoes + ["verificador_nova_tentativa"] + nova.observacoes
        v2 = self.verificador(nova.resposta, nova.fontes, pergunta)
        if v2.aprovada:
            return nova
        restantes = [f for f in _frases(nova.resposta) if f not in v2.frases_reprovadas]
        citados = {f"T{n}" for f in restantes for n in RE_CITACAO.findall(f)}
        fontes = [t for t in nova.fontes if t.rotulo in citados] or ([t for t in nova.fontes] if restantes else [])
        if not restantes or not fontes:
            return RespostaF1(MENSAGEM_AUSENCIA, Classificacao.AUSENCIA.value, None, [], modelo=nova.modelo,
                              confianca_modelo=nova.confianca_modelo,
                              tokens_entrada=nova.tokens_entrada, tokens_saida=nova.tokens_saida,
                              latencia_ms=nova.latencia_ms,
                              observacoes=nova.observacoes + ["verificador_sem_afirmacao_sustentada"])
        nova.resposta = " ".join(restantes)
        nova.fontes = fontes
        nova.observacoes.append("verificador_frases_removidas")
        return nova

    def _conflito(self, pergunta, trechos):
        """RF-09: se o grafo registra contradição entre documentos do contexto sobre o campo perguntado, responde
        de forma determinística com as duas fontes (o sistema não escolhe o valor)."""
        documentos = {t.documento_id for t in trechos}
        relevantes = [c for c in self.conflitos.entre(documentos)
                      if CAMPOS_DA_PERGUNTA.get(c.campo) and CAMPOS_DA_PERGUNTA[c.campo].search(pergunta)]
        if not relevantes:
            return None
        linhas, fontes = [MENSAGEM_CONFLITO], []
        for c in relevantes:
            for doc_id, valor, papel, evidencia in ((c.origem, c.valor_vigente, "registro vigente", c.trecho_origem),
                                                    (c.destino, c.valor_declarado, "valor divergente",
                                                     c.trecho_destino)):
                do_doc = [t for t in trechos if t.documento_id == doc_id]
                # a citação precisa conter o valor: do contexto, senão a evidência registrada no grafo
                trecho = next((t for t in do_doc if valor in t.texto), None) or evidencia or do_doc[0]
                fontes.append(trecho)
                linhas.append(f"- {trecho.titulo or trecho.arquivo}: {ROTULO_CAMPO[c.campo]} = {valor} "
                              f"({papel}) [{trecho.rotulo}]")
        linhas.append("É necessária conferência documental.")
        unicos = list({t.id: t for t in fontes}.values())
        return RespostaF1("\n".join(linhas), Classificacao.CONFLITO.value, None, unicos, modelo="regra-conflito",
                          observacoes=["conflito_detectado_no_grafo"])

    def _validar(self, dados, trechos, r) -> RespostaF1:
        por_rotulo = {t.rotulo: t for t in trechos}
        observacoes = []
        classificacao = dados.get("classificacao") if dados.get("classificacao") in {c.value for c in Classificacao} \
            else Classificacao.FATO.value
        texto = _com_detalhes(str(dados.get("resposta") or "").strip(), dados.get("detalhes"), set(por_rotulo))
        # tolera formatos ("T12", "[T12]", 12, "12"); o id continua obrigado a existir no contexto
        declarados = [_rotulo(f) for f in dados.get("fontes") or []]
        no_texto = [f"T{n}" for n in RE_CITACAO.findall(texto)]
        citados = list(dict.fromkeys(declarados + no_texto))
        validos = [c for c in citados if c in por_rotulo]
        if len(validos) < len(citados):
            observacoes.append("citacoes_invalidas_descartadas")
        try:  # autoavaliação do modelo: só registrada na auditoria (o 7B local às vezes omite o campo)
            declarada = max(0.0, min(1.0, float(dados["confianca"])))
        except (KeyError, TypeError, ValueError):
            declarada = None
        if classificacao != Classificacao.AUSENCIA.value and not validos:
            observacoes.append("resposta_factual_sem_citacao_valida")
            classificacao = Classificacao.AUSENCIA.value
        if classificacao == Classificacao.AUSENCIA.value:
            texto, validos = MENSAGEM_AUSENCIA, []
        return RespostaF1(texto, classificacao, None, [por_rotulo[c] for c in validos],
                          list(dados.get("lacunas") or []), r.modelo, r.tokens_entrada, r.tokens_saida,
                          r.latencia_ms, observacoes, dados, confianca_modelo=declarada)
