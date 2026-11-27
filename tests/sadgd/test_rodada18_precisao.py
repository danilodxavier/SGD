"""Rodada 18 (2026-11-26): precisão e tempo da F1 sobre contratos (gabarito real das fichas: 25% → 95% no teste).

Cobre: documentos-chave e janelas literais da ficha no contexto, número inconsistente descartado, compressão pelo
tipo de dado pedido, busca dentro dos documentos-chave e a montagem do contexto no orquestrador.
"""
from app.application.agentes.orquestrador import Orquestrador
from app.application.fichas.consulta import ResponderPorFicha, pede_dado_da_ficha
from app.application.recuperacao.hibrida import recuperar_dentro
from app.application.recuperacao.regras import TrechoRecuperado
from app.application.respostas.f1 import comprimir

PREAMBULO = ("CONTRATO Nº 012/2023, que entre si celebram o ESTADO, por meio da SECRETARIA, doravante CONTRATANTE, e "
             "a empresa ALFA SISTEMAS LTDA, inscrita no CNPJ sob o nº 12.345.678/0001-90, doravante CONTRATADA, "
             "para a prestação de serviços de suporte técnico. " + "Cláusula genérica sem dados. " * 30)
TEXTOS = {11: PREAMBULO, 12: "CLÁUSULA TERCEIRA — O valor global é de R$ 120.000,00 (cento e vinte mil reais).",
          13: "Fica acrescido o valor, passando o valor global a R$ 150.000,00.",
          21: "Portaria: designa FULANO DE TAL como fiscal do contrato."}
DOC = {11: 1, 12: 1, 13: 2, 21: 3}


def tr(i, texto=None, pontuacao=0.0):
    return TrechoRecuperado(i, DOC.get(i, i), texto or TEXTOS.get(i, f"texto {i}"), "a.pdf", "CT 012-2023/a.pdf",
                            f"Documento {i}", None, None, "contrato", "real", None, False, None, pontuacao=pontuacao)


class RepoTrechos:
    def obter(self, ids):
        return [tr(i) for i in ids]

    def iniciais(self, documento_ids, ate_ordem=4):
        por_doc = {}
        for i, d in DOC.items():
            if d in documento_ids:
                por_doc.setdefault(d, []).append(tr(i))
        return por_doc


class RepoFichas:
    def __init__(self, fichas):
        self._f = fichas

    def todas(self):
        return self._f


FICHA = {"chave": "012/2023", "apelidos": [], "texto_busca": "ct 012-2023 alfa sistemas suporte", "documentos": [],
         "campos": {"numero": {"valor": "012/2023", "trecho_id": 11},
                    "contratada": {"valor": "ALFA SISTEMAS LTDA", "trecho_id": 11},
                    "cnpj_contratada": {"valor": "12.345.678/0001-90", "trecho_id": 11},
                    "valor_global": {"valor": "R$ 120.000,00", "trecho_id": 12},
                    "valor_atual": {"valor": "R$ 150.000,00", "trecho_id": 13},
                    "fiscal": {"valor": "FULANO DE TAL", "trecho_id": 21}}}


def fichas(f=FICHA):
    return ResponderPorFicha(RepoFichas([f]), RepoTrechos())


def test_pede_dado_so_com_interrogativo_e_dado_presente_na_ficha():
    c = FICHA["campos"]
    assert pede_dado_da_ficha("Qual empresa foi contratada no contrato 012/2023?", c)
    assert pede_dado_da_ficha("Quem é o fiscal do contrato 012/2023?", c)
    assert not pede_dado_da_ficha("Qual o prazo de garantia do contrato 012/2023?", c)  # não é dado da ficha
    assert not pede_dado_da_ficha("Qual o valor da multa do contrato 012/2023?", c)
    assert not pede_dado_da_ficha("A contratada cumpriu o prazo no contrato 012/2023?", c)  # não pede um dado
    assert not pede_dado_da_ficha("Quem é o gestor do contrato 012/2023?", c)  # a ficha não tem o gestor


def test_contexto_f1_janelas_literais_so_do_dado_pedido_e_valor_com_original_e_atualizado():
    texto, trechos, pede = fichas().contexto_f1("Qual o valor global do contrato 012/2023?")
    assert pede and "original R$ 120.000,00 [T12]" in texto and "atualizado por aditivo: R$ 150.000,00 [T13]" in texto
    assert "FULANO" not in texto and {t.id for t in trechos} == {11, 12, 13}  # nº (T11) + os dois valores
    janela = next(t for t in trechos if t.id == 11)
    assert len(janela.texto) < len(PREAMBULO) and "012/2023" in janela.texto  # recorte em torno do nº
    assert janela.texto.replace("[…] ", "").replace(" […]", "") in PREAMBULO  # literal


def test_contexto_f1_sem_dado_pedido_traz_a_ficha_inteira():
    texto, trechos, pede = fichas().contexto_f1("A contratada do contrato 012/2023 entregou os serviços?")
    assert not pede and "FULANO DE TAL [T21]" in texto and "CNPJ" in texto


def test_numero_que_nao_confere_com_a_chave_e_descartado():
    f = {**FICHA, "campos": {**FICHA["campos"], "numero": {"valor": "SEMA-PRO-2022/01234", "trecho_id": 31}}}
    r = fichas(f).responder("Qual o objeto do contrato 012/2023?")
    assert r is None or "SEMA-PRO" not in r.resposta
    assert 31 not in (fichas(f).documentos_chave("Qual a empresa do contrato 012/2023?") or set())  # doc do nº
    assert "Contrato nº 012/2023" in fichas(f).contexto_f1("Qual a empresa do contrato 012/2023?")[0].replace(
        "FICHA DO CONTRATO Nº", "Contrato nº")


def test_compressao_guarda_o_dado_do_tipo_pedido_mesmo_sem_as_palavras_da_pergunta():
    texto = ("Considerando o processo administrativo e as disposições gerais aplicáveis ao caso concreto. " * 8
             + "Inscrição 12.345.678/0001-90 junto à Receita. " + "Outras disposições finais e transitórias. " * 8)
    curto = comprimir(texto, "Qual o CNPJ da contratada do contrato 012/2023?", 300)
    assert "12.345.678/0001-90" in curto and len(curto) <= 340


def test_frase_longa_com_o_dado_entra_recortada_em_torno_dele():
    longa = "Pelo presente instrumento, " + "as partes ajustam cláusulas e condições diversas, " * 40 + \
        "pelo valor global de R$ 120.000,00, conforme proposta."
    curto = comprimir(longa, "Qual o valor global do contrato?", 400)
    assert "R$ 120.000,00" in curto and len(curto) < 450


class Reranker:
    def pontuar(self, consulta, textos):
        return [0.9 if "valor" in t.lower() else 0.1 for t in textos]


def test_busca_dentro_dos_documentos_chave_traz_a_abertura_e_os_mais_relevantes():
    achados = recuperar_dentro(RepoTrechos(), Reranker(), "Qual o valor global?", {1, 2}, k=3)
    ids = [t.id for t in achados]
    assert ids[:2] == [11, 13]  # aberturas dos documentos 1 e 2 primeiro
    assert 12 in ids  # o trecho do valor, pela nota do reranker


def test_orquestrador_dado_da_ficha_usa_so_ficha_e_janelas_sem_buscar_na_pasta():
    chamadas = []
    f = fichas()

    def recuperar(p, k, **kw):
        chamadas.append(kw)
        return [tr(99, "trecho da pasta", 0.9)]

    class F1:
        def responder(self, pergunta, trechos, **kw):
            self.trechos, self.kw = trechos, kw
            return None

    f1 = F1()
    orq = Orquestrador(recuperar, f1, None, fichas=lambda p: None, escopo_contrato=f.escopo,
                       documentos_chave=f.documentos_chave, ficha_f1=f.contexto_f1,
                       recuperar_dentro=lambda p, d, k: recuperar_dentro(RepoTrechos(), Reranker(), p, d, k))
    orq.executar("Qual o CNPJ da empresa contratada no contrato 012/2023?")
    assert {t.id for t in f1.trechos} == {11} and "CNPJ" in f1.kw["ficha"] and f1.kw["max_chars"] == 500
    assert chamadas == []  # sem busca na pasta inteira
    orq.executar("Houve pagamento em março no contrato 012/2023?")  # outro documento da pasta: busca normal
    assert chamadas and 99 in {t.id for t in f1.trechos}
    chamadas.clear()  # não pede um dado da ficha (golden V045): ficha + documentos-chave + busca na pasta
    orq.executar("Após a interrupção do contrato 012/2023, quando as atividades foram retomadas?")
    assert chamadas and 99 in {t.id for t in f1.trechos} and f1.kw.get("ficha")


class Conflitos:
    def __init__(self, ha):
        self.ha = ha

    def entre(self, documentos):
        return ["conflito"] if self.ha else []


def test_contrato_com_contradicao_no_grafo_nao_usa_o_atalho_da_ficha():
    """Golden set: 4 perguntas de conflito viraram "fato" quando a ficha mostrava um só valor."""
    f = {**FICHA, "documentos": [{"documento_id": 1, "tipo": "contrato", "data": None, "trecho_id": 11}]}
    com = ResponderPorFicha(RepoFichas([f]), RepoTrechos(), conflitos=Conflitos(True))
    sem = ResponderPorFicha(RepoFichas([f]), RepoTrechos(), conflitos=Conflitos(False))
    pergunta = "Qual o valor global do contrato 012/2023?"
    assert com.contexto_f1(pergunta) is None and com.documentos_chave(pergunta) is None
    assert sem.contexto_f1(pergunta) is not None and sem.documentos_chave(pergunta)
