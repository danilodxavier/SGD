"""Fichas de contrato: agrupamento, extração conferida, consulta sem LLM e atalho no orquestrador."""
from app.application.fichas.agrupamento import (
    DocumentoAcervo,
    agrupar,
    chaves_no_texto,
    documento_principal,
    pasta_de_contrato,
)
from app.application.fichas.consulta import ResponderPorFicha
from app.application.fichas.extracao import selecionar_trechos, validar
from app.application.fichas.gerar import GerarFichas, apelidos
from app.application.recuperacao.regras import TrechoRecuperado


def doc(i, rel, tipo, titulo="", data=None, abertura=""):
    return DocumentoAcervo(i, rel, tipo, titulo, data, abertura, i * 10)


def test_numero_normalizado_pasta_e_texto():
    assert pasta_de_contrato("CT 12-2023 EMPRESA X/Empenhos/a.pdf") == ("CT 12-2023 EMPRESA X", "012/2023")
    assert pasta_de_contrato("Diversos/a.pdf") == ("Diversos", None)
    assert pasta_de_contrato("a.pdf") == (None, None)
    assert chaves_no_texto("PRIMEIRO TERMO ADITIVO AO CONTRATO Nº 44/2023") == ["044/2023"]
    assert chaves_no_texto("Processo 123/2023") == []  # só número de CONTRATO liga documento sem pasta


def test_agrupa_por_pasta_ou_pelo_numero_citado_e_acha_o_instrumento():
    docs = [doc(1, "CT 012-2023 X/contrato.pdf", "contrato", "CONTRATO Nº 012/2023", "2022-03-01"),
            doc(2, "CT 012-2023 X/Empenhos/ne.pdf", "nota_empenho", data="2023-01-10"),
            doc(3, "sintetico/F04/aditivo.txt", "aditivo", "TERMO ADITIVO AO CONTRATO Nº 044/2023"),
            doc(4, "sintetico/F04/contrato.txt", "contrato", "CONTRATO Nº 044/2023", "2023-09-01"),
            doc(5, "sintetico/F04/lei.txt", "lei", "LEI Nº 14.133/2021")]
    g = agrupar(docs)
    assert set(g) == {"012/2023", "044/2023"} and g["012/2023"].pasta == "CT 012-2023 X"
    assert [d.id for d in g["012/2023"].documentos] == [1, 2] and documento_principal(g["044/2023"]).id == 4


def test_extracao_so_aceita_valor_que_consta_do_trecho_citado():
    trechos = [(1, "CONTRATO Nº 012/2023 celebrado com a EMPRESA X LTDA."),
               (2, "CLÁUSULA PRIMEIRA – DO OBJETO: prestação de serviços de limpeza predial."),
               (3, "O valor global é de R$ 120.000,00.")]
    dados = {"numero": {"valor": "012/2023", "trecho": "T1"}, "contratada": {"valor": "EMPRESA X LTDA.", "trecho": "1"},
             "objeto": {"valor": "serviços de limpeza predial", "trecho": "T2"},
             "valor_global": {"valor": "R$ 999.000,00", "trecho": "T3"},  # inventado: não consta
             "fiscal": {"valor": "Fulano", "trecho": "T9"}}  # trecho que não foi enviado
    aceitos = validar(dados, trechos)
    assert set(aceitos) == {"numero", "contratada", "objeto"} and aceitos["contratada"]["trecho_id"] == 1


def test_selecao_de_trechos_abertura_palavras_chave_e_portarias():
    instrumento = [(1, "CONTRATO"), (2, "Preâmbulo"), (3, "Cláusula do objeto"), (4, "O prazo de vigência"),
                   (5, "Valor global R$ 1,00"), (6, "Do fiscal do contrato")]
    ids = [t for t, _ in selecionar_trechos(instrumento, [(90, "Portaria designa fiscal")])]
    assert ids[:2] == [1, 2] and {3, 4, 5, 6, 90} <= set(ids)


class RepoFichas:
    def __init__(self, fichas):
        self._f = {f["chave"]: f for f in fichas}

    def todas(self):
        return list(self._f.values())


class RepoTrechos:
    def obter(self, ids):
        return [TrechoRecuperado(i, i, f"texto {i}", "a.pdf", "p/a.pdf", f"Documento {i}", None, None, None, "real",
                                 None, False, None) for i in ids]


FICHA = {"chave": "012/2023", "apelidos": ["010/2024"], "texto_busca": "ct 012-2023 alfa do brasil suporte",
         "campos": {"numero": {"valor": "012/2023", "trecho_id": 11}, "objeto": {"valor": "suporte técnico",
                                                                                 "trecho_id": 12},
                    "contratada": {"valor": "ALFA SISTEMAS", "trecho_id": 11}},
         "documentos": [{"documento_id": 1, "tipo": "nota_empenho", "data": "2024-02-01", "trecho_id": 21},
                        {"documento_id": 2, "tipo": "nota_empenho", "data": "2025-03-05", "trecho_id": 22},
                        {"documento_id": 3, "tipo": "aditivo", "data": "2025-01-10", "trecho_id": 23}]}
OUTRA = {"chave": "015/2023", "apelidos": [], "texto_busca": "ct 015-2023 limpeza", "campos": {}, "documentos": []}


def responder(pergunta):
    return ResponderPorFicha(RepoFichas([FICHA, OUTRA]), RepoTrechos()).responder(pergunta)


def test_responde_objeto_pelo_numero_ou_pelo_nome_com_citacao():
    r = responder("Sobre o que trata o contrato 12/2023?")
    assert r.classificacao == "fato" and "suporte técnico [T12]" in r.resposta and "ficha_do_contrato" in r.observacoes
    assert [t.id for t in r.fontes] == [12, 11]
    assert "suporte técnico" in responder("Qual o contrato da Alfa?").resposta
    assert responder("Qual o objeto do contrato 010/2024?").resposta.startswith("Contrato nº 012/2023")  # apelido


def test_documentos_por_tipo_com_filtro_de_ano_e_ausencia_explicita():
    r = responder("Há empenho para o contrato 012/2023 em 2025?")
    assert "1 nota de empenho em 2025" in r.resposta and "[T22]" in r.resposta and "[T21]" not in r.resposta
    assert responder("Há notificação para o contrato 012/2023?") is None  # repositório sem checagem de texto

    class SemMencao(RepoFichas):
        def __init__(self, fichas, cita):
            super().__init__(fichas)
            self.cita = cita

        def menciona(self, pasta, ids, termos):
            return self.cita

    vazio = ResponderPorFicha(SemMencao([FICHA], False), RepoTrechos()).responder(
        "Há notificação para o contrato 012/2023?")
    assert vazio.classificacao == "ausencia" and "Não localizei notificações" in vazio.resposta and vazio.lacunas
    citado = ResponderPorFicha(SemMencao([FICHA], True), RepoTrechos()).responder(
        "Há notificação para o contrato 012/2023?")
    assert citado is None  # o texto da pasta fala em notificação: a classificação pode ter falhado
    outro_ano = responder("Houve empenho para o contrato 012/2023 em 2023?")
    assert outro_ano.classificacao == "ausencia" and "de outros anos" in outro_ano.resposta
    assert "[T22]" in outro_ano.resposta


def test_sem_contrato_assunto_ou_dado_segue_o_caminho_completo():
    assert responder("Quem é o fiscal do contrato 099/2026?") is None    # número desconhecido
    assert responder("Há pendência em algum contrato?") is None          # sem contrato identificado
    assert responder("O contrato 012/2023 é bom?") is None               # assunto não reconhecido
    assert responder("Qual o valor do contrato 012/2023?") is None       # dado ausente da ficha
    assert responder("Quais processos estão em fase de renovação?") is None


def test_vigencia_avisa_que_aditivos_podem_ter_prorrogado():
    ficha = {**FICHA, "campos": {**FICHA["campos"], "vigencia": {"valor": "12 meses", "trecho_id": 13}}}
    r = ResponderPorFicha(RepoFichas([ficha]), RepoTrechos()).responder("Até quando vigora o contrato 012/2023?")
    assert "12 meses [T13]" in r.resposta and "aditivo" in r.resposta and "Vigência atual depende" in r.lacunas[-1]


class RepoGerar:
    def __init__(self, docs, trechos):
        self.docs, self.trechos_por_doc, self.salvas = docs, trechos, {}

    def documentos_acervo(self):
        return self.docs

    def trechos_do_documento(self, documento_id):
        return self.trechos_por_doc.get(documento_id, [])

    def ficha(self, chave):
        return self.salvas.get(chave)

    def salvar(self, ficha):
        self.salvas[ficha["chave"]] = ficha


class LLMExtrator:
    nome, remoto = "falso", False

    def __init__(self):
        self.chamadas = 0

    def chat(self, mensagens, **kw):
        from app.application.portas import RespostaLLM

        self.chamadas += 1
        dados = {"numero": {"valor": "012/2023", "trecho": "T10"},
                 "objeto": {"valor": "limpeza predial", "trecho": "T10"}}
        return RespostaLLM("{}", "falso", 10, 10, 1, json=dados)


def test_gerar_extrai_uma_vez_e_depois_so_atualiza_o_inventario():
    docs = [doc(1, "CT 012-2023 X/c.pdf", "contrato", "CONTRATO Nº 012/2023"),
            doc(2, "CT 012-2023 X/e.pdf", "nota_empenho", data="2024-01-01")]
    repo, llm = RepoGerar(docs, {1: [(10, "CONTRATO Nº 012/2023 — objeto: limpeza predial.")]}), LLMExtrator()
    r1 = GerarFichas(repo, llm).executar()
    assert r1["extraidas"] == 1 and set(repo.salvas["012/2023"]["campos"]) == {"numero", "objeto"}
    assert "limpeza predial" in repo.salvas["012/2023"]["texto_busca"]
    repo.docs.append(doc(3, "CT 012-2023 X/e2.pdf", "nota_empenho", data="2025-01-01"))
    r2 = GerarFichas(repo, llm).executar()
    assert r2["puladas"] == 1 and llm.chamadas == 1 and len(repo.salvas["012/2023"]["documentos"]) == 3


def test_apelido_ambiguo_fica_de_fora():
    docs = [doc(1, "CT 012-2023 X/c.pdf", "contrato", "", abertura="CONTRATO Nº 012/2023 renova o contrato nº 10/2020"),
            doc(2, "CT 015-2023 Y/c.pdf", "contrato", "", abertura="CONTRATO Nº 015/2023 ref. contrato nº 10/2020"),
            doc(3, "CT 015-2023 Y/d.pdf", "aditivo", "", abertura="aditivo ao contrato nº 11/2021")]
    assert apelidos(agrupar(docs)) == {"011/2021": "015/2023"}


def test_orquestrador_responde_pela_ficha_sem_buscar_nem_chamar_o_llm():
    from app.application.agentes.orquestrador import Orquestrador
    from app.application.respostas.f1 import ResponderF1

    class Proibido:
        nome, remoto = "proibido", False

        def chat(self, *a, **k):
            raise AssertionError("não deveria chamar o LLM")

    def recuperar(*a, **k):
        raise AssertionError("não deveria buscar")

    orq = Orquestrador(recuperar, ResponderF1(Proibido()), Proibido(), fichas=responder)
    estado = orq.executar("Sobre o que trata o contrato 012/2023?")
    assert estado["via_ficha"] and "suporte técnico" in estado["resposta"].resposta
    assert [n for n, _ in estado["tempos"]] == ["rotear", "ficha"]


class RepoFichasComContagem(RepoFichas):
    def __init__(self, fichas, ocorrencias):
        super().__init__(fichas)
        self.ocorrencias = ocorrencias

    def ocorrencias_numero(self, chave):
        return self.ocorrencias.get(chave, 0)


def test_nome_com_varios_contratos_lista_os_candidatos():
    a = {**FICHA, "chave": "012/2023", "texto_busca": "ct 012-2023 alfa suporte"}
    b = {**FICHA, "chave": "050/2023", "texto_busca": "ct 050-2023 alfa licencas", "campos": {}, "apelidos": []}
    r = ResponderPorFicha(RepoFichas([a, b, OUTRA]), RepoTrechos()).responder("Qual o contrato da Alfa?")
    assert r.resposta.startswith("Encontrei 2 contratos") and "050/2023" in r.resposta and r.lacunas


def test_contrato_inexistente_so_e_afirmado_se_o_numero_nao_aparece_em_nenhum_trecho():
    repo = RepoFichasComContagem([FICHA, OUTRA], {"098/2025": 3})
    r = ResponderPorFicha(repo, RepoTrechos()).responder("Quem é o fiscal do contrato 099/2026?")
    assert r.classificacao == "ausencia" and "099/2026" in r.resposta and r.fontes == []
    assert ResponderPorFicha(repo, RepoTrechos()).responder("Quem é o fiscal do contrato 098/2025?") is None
    assert ResponderPorFicha(repo, RepoTrechos()).responder("O que diz o processo 999/2024?") is None  # não é contrato


def test_ordem_de_servico_e_reconhecida_pelo_titulo():
    from app.application.fichas.gerar import inventario

    g = agrupar([doc(1, "CT 012-2023 X/c.pdf", "contrato", "CONTRATO Nº 012/2023"),
                 doc(2, "CT 012-2023 X/os.pdf", "oficio", "ORDEM DE SERVIÇO Nº 3/2026", "2026-02-01")])
    tipos = {d["documento_id"]: d["tipo"] for d in inventario(g["012/2023"])}
    assert tipos == {1: "contrato", 2: "ordem_servico"}
    ficha = {**FICHA, "documentos": [{"documento_id": 2, "tipo": "ordem_servico", "data": "2026-02-01",
                                      "trecho_id": 20}]}
    r = ResponderPorFicha(RepoFichas([ficha]), RepoTrechos()).responder(
        "Foi aberta ordem de serviço para o contrato 012/2023 no ano de 2026?")
    assert "1 ordem de serviço em 2026" in r.resposta


def test_pergunta_transversal_junta_os_inventarios_das_fichas():
    b = {**OUTRA, "documentos": [{"documento_id": 9, "tipo": "nota_empenho", "data": "2025-06-01", "trecho_id": 90}]}
    r = ResponderPorFicha(RepoFichas([FICHA, b]), RepoTrechos()).responder("Quais contratos tiveram empenho em 2025?")
    assert r.resposta.startswith("2 contrato(s) com notas de empenho em 2025") and "[T22]" in r.resposta
    assert "[T90]" in r.resposta and "transversal" in r.observacoes
    assert ResponderPorFicha(RepoFichas([FICHA, b]), RepoTrechos()).responder("Quais contratos tiveram rescisão?") \
        is None  # ausência no acervo inteiro não se afirma pela classificação
    assert ResponderPorFicha(RepoFichas([FICHA]), RepoTrechos()).responder("Quais contratos têm fiscal?") is None


class LLMComplemento(LLMExtrator):
    def chat(self, mensagens, **kw):
        from app.application.portas import RespostaLLM

        self.chamadas += 1
        sistema = mensagens[0]["content"]
        if "vigencia_atual_fim" in sistema:
            dados = {"vigencia_atual_fim": {"valor": "31/08/2099", "trecho": "T50"}}
        elif '"fiscal"' in sistema:
            dados = {"fiscal": {"valor": "Maria Souza", "trecho": "T40"},
                     "valor_global": {"valor": "R$ 5,00", "trecho": "T40"}}  # valor não consta do T40
        else:
            dados = {"numero": {"valor": "012/2023", "trecho": "T10"}, "objeto": {"valor": "limpeza predial",
                                                                                 "trecho": "T10"}}
        return RespostaLLM("{}", "falso", 10, 10, 1, json=dados)


def test_segunda_passada_completa_campos_e_vigencia_atual_uma_vez_so():
    docs = [doc(1, "CT 012-2023 X/c.pdf", "contrato", "CONTRATO Nº 012/2023", "2023-01-01"),
            doc(4, "CT 012-2023 X/p.pdf", "portaria_designacao", "PORTARIA", "2023-02-01"),
            doc(5, "CT 012-2023 X/a.pdf", "aditivo", "PRIMEIRO TERMO ADITIVO", "2024-01-01")]
    trechos = {1: [(10, "CONTRATO Nº 012/2023 — objeto: limpeza predial.")],
               4: [(40, "Designa a servidora Maria Souza como fiscal do contrato.")],
               5: [(50, "TERMO ADITIVO"), (51, "Fica prorrogada a vigência até 31/08/2099.")]}
    trechos[5] = [(50, "Fica prorrogada a vigência do contrato até 31/08/2099.")]
    repo, llm = RepoGerar(docs, trechos), LLMComplemento()
    gerar = GerarFichas(repo, llm)
    gerar.executar()
    c = gerar.complementar()
    campos = repo.salvas["012/2023"]["campos"]
    assert c["complementadas"] == 1 and c["vigencia_atual"] == 1
    assert campos["fiscal"]["valor"] == "Maria Souza" and "valor_global" not in campos
    assert campos["vigencia_atual_fim"]["valor"] == "31/08/2099" and campos["aditivo_vigencia"]["documento_id"] == 5
    chamadas = llm.chamadas
    assert gerar.complementar()["complementadas"] == 0 and llm.chamadas == chamadas  # já feito: não repete


def test_vigencia_atual_mostra_situacao_e_so_avisa_se_ha_aditivo_mais_recente():
    base = {**FICHA, "documentos": [{"documento_id": 3, "tipo": "aditivo", "data": "2025-01-10", "trecho_id": 23}]}
    base["campos"] = {**FICHA["campos"], "vigencia_atual_fim": {"valor": "31/08/2099", "trecho_id": 24},
                      "aditivo_vigencia": {"valor": "2025-01-10", "trecho_id": 23, "documento_id": 3}}
    r = ResponderPorFicha(RepoFichas([base]), RepoTrechos()).responder("O contrato 012/2023 está vigente?")
    assert "prorrogada até: 31/08/2099 [T24]" in r.resposta and "vigente até 31/08/2099" in r.resposta
    assert "Atenção" not in r.resposta and "10/01/2025" in r.resposta
    novo = {**base, "documentos": base["documentos"] + [{"documento_id": 7, "tipo": "aditivo", "data": "2026-05-01",
                                                          "trecho_id": 70}]}
    r2 = ResponderPorFicha(RepoFichas([novo]), RepoTrechos()).responder("O contrato 012/2023 foi encerrado?")
    assert "Atenção" in r2.resposta and "01/05/2026" in r2.resposta
    vencido = {**base, "campos": {**base["campos"], "vigencia_atual_fim": {"valor": "31/12/2020", "trecho_id": 24}}}
    r3 = ResponderPorFicha(RepoFichas([vencido]), RepoTrechos()).responder("O contrato 012/2023 foi encerrado?")
    assert "vigência encerrada em 31/12/2020" in r3.resposta


def test_pergunta_de_conteudo_valor_alterado_e_garantia_seguem_o_caminho_completo():
    assert responder("Qual reajuste foi apostilado ao contrato 012/2023?") is None
    assert responder("Qual o valor da garantia do contrato 012/2023?") is None
    com_valor = {**FICHA, "campos": {**FICHA["campos"], "valor_global": {"valor": "R$ 100,00", "trecho_id": 14}}}
    assert ResponderPorFicha(RepoFichas([com_valor]), RepoTrechos()).responder(
        "Qual o valor global do contrato 012/2023?") is None  # há aditivo e não há valor atualizado
    atualizado = {**com_valor, "campos": {**com_valor["campos"],
                                          "valor_atual": {"valor": "R$ 125,00", "trecho_id": 25},
                                          "aditivo_valor": {"valor": "2025-01-10", "trecho_id": 23,
                                                            "documento_id": 3}}}
    r = ResponderPorFicha(RepoFichas([atualizado]), RepoTrechos()).responder(
        "Qual o valor global do contrato 012/2023?")
    assert "R$ 125,00 [T25]" in r.resposta and "R$ 100,00 [T14]" in r.resposta and "10/01/2025" in r.resposta


def test_contradicao_registrada_e_dados_fora_da_ficha_seguem_o_caminho_completo():
    class Conflito:
        campo = "valor_global"

    class Grafo:
        def entre(self, ids):
            return [Conflito()]

    sem_alterador = {**FICHA, "documentos": [], "campos": {**FICHA["campos"],
                                                           "valor_global": {"valor": "R$ 100,00", "trecho_id": 14}}}
    assert ResponderPorFicha(RepoFichas([sem_alterador]), RepoTrechos()).responder(
        "Qual o valor global do contrato 012/2023?") is not None
    assert ResponderPorFicha(RepoFichas([sem_alterador]), RepoTrechos(), conflitos=Grafo()).responder(
        "Qual o valor global do contrato 012/2023?") is None
    assert responder("Qual o nome do preposto da contratada no contrato 012/2023?") is None
