"""Orquestrador LangGraph (Fase 7) com LLM e recuperador falsos."""
import json
import threading

from app.application.agentes.orquestrador import Orquestrador
from app.application.agentes.verificador import verificar
from app.application.portas import RespostaLLM
from app.application.recuperacao.regras import TrechoRecuperado
from app.application.respostas.f1 import ResponderF1
from app.domain.politicas import AVISO_DECISAO

TRECHOS = [
    TrechoRecuperado(11, 1, "3.1. O valor global do contrato é de R$ 2.340.000,00.", "c.docx", "sintetico/c.docx",
                     "CONTRATO Nº 044/2023", "cláusula terceira", 1, "contrato", "sintetico", "2023-09-01", False,
                     None),
    TrechoRecuperado(12, 2, "Decisão: prorrogar por 12 meses. Avaliação do resultado: positivo.", "d.txt",
                     "sintetico/d.txt", "DECISÃO DA GESTÃO DG-011/2025", None, 1, "decisao_gestao", "sintetico",
                     "2025-07-30", False, None),
]


class LLMRoteiro:
    """Responde conforme o papel indicado no prompt de sistema; registra quais agentes foram chamados."""

    nome, remoto = "falso", False

    def __init__(self):
        self.papeis, self._trava = [], threading.Lock()

    def chat(self, mensagens, *, schema=None, max_tokens=700, temperatura=0.0, json_livre=False):
        sistema = mensagens[0]["content"]
        papel = sistema.split("Papel: ")[1].split(".")[0].split(" ")[0] if "Papel: " in sistema else "?"
        with self._trava:
            self.papeis.append(papel)
        if "Modo F2" in sistema:
            saida = {"resposta": "A prorrogação é viável, considerando o valor de R$ 2.340.000,00 [T11] e o "
                                 "precedente positivo [T12].", "consensos": ["há base para prorrogar"],
                     "divergencias": [], "alternativas": [{"descricao": "prorrogar", "pros": ["continuidade"],
                                                           "contras": ["custo"]}],
                     "riscos": [{"descricao": "aumento de preço", "probabilidade": "media", "impacto": "medio",
                                 "mitigacao": "pesquisa de preços"}], "base_legal": [], "precedentes": ["DG-011/2025"],
                     "lacunas": [], "fontes": ["T11", "T12"], "classificacao": "inferencia", "confianca": 0.7,
                     "aviso": "x"}
        elif "Modo F1" in sistema:
            saida = {"resposta": "O valor global é R$ 2.340.000,00 [T11].", "fontes": ["T11"],
                     "classificacao": "fato", "confianca": 0.9, "lacunas": []}
        else:
            saida = {"parecer": "Parecer favorável à prorrogação.", "afirmacoes": [
                {"id": "A1", "texto": "O valor é R$ 2.340.000,00.", "tipo": "fato", "citacoes": ["T11"]},
                {"id": "A2", "texto": "Há precedente positivo.", "tipo": "fato", "citacoes": ["T999"]}],
                "fundamentacao_legal": [], "riscos": [], "alternativas": [], "recomendacao": "prorrogar",
                "lacunas": [], "conflitos": [], "confianca": "0.8"}
        texto = json.dumps(saida, ensure_ascii=False)
        return RespostaLLM(texto, "falso", 100, 50, 10, json=saida)


def criar(llm):
    return Orquestrador(lambda pergunta, k: TRECHOS, ResponderF1(llm, verificador=verificar), llm,
                        linha_do_tempo=lambda docs: "LINHA DO TEMPO: contrato 044/2023 prorrogado em 2025.")


def test_f1_nao_aciona_especialistas():
    llm = LLMRoteiro()
    estado = criar(llm).executar("Qual é o valor global do Contrato nº 044/2023?")
    assert estado["decisao"].rota == "F1_simples" and llm.papeis == ["RELATOR"]
    assert "2.340.000,00" in estado["resposta"].resposta


def test_f2_aciona_so_os_especialistas_escolhidos_e_relator_com_aviso():
    llm = LLMRoteiro()
    estado = criar(llm).executar("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?")
    decisao = estado["decisao"]
    assert decisao.rota == "F2" and "gestor_publico" in decisao.agentes
    pareceres = estado["pareceres"]
    assert sorted(p.agente for p in pareceres) == sorted(decisao.agentes)
    assert llm.papeis.count("RELATOR") == 1 and len(llm.papeis) == len(decisao.agentes) + 1
    p = pareceres[0]
    assert p.valido_reparado and not p.valido_bruto  # confianca veio como texto: reparo de forma
    assert [a["id"] for a in p.dados["afirmacoes"]] == ["A1"] and p.afirmacoes_removidas == 1  # T999 descartada
    final = estado["resposta"]
    assert final.valido and final.resposta.endswith(AVISO_DECISAO) and final.dados["aviso"] == AVISO_DECISAO
    assert {t.id for t in final.fontes} == {11, 12}
    nos = [n for n, _ in estado["tempos"]]
    assert nos[:3] == ["rotear", "recuperar", "contexto_f2"] and nos[-1] == "relator"


class LLMQueCorta(LLMRoteiro):
    """Simula saída cortada por max_tokens (JSON inválido) para especialistas e/ou relator."""

    def __init__(self, cortar_especialistas=1, cortar_relator=0):
        super().__init__()
        self.cortes = {"esp": cortar_especialistas, "rel": cortar_relator}
        self.orcamentos = []

    def chat(self, mensagens, **kw):
        alvo = "rel" if "Modo F2" in mensagens[0]["content"] else "esp"
        with self._trava:
            self.orcamentos.append((alvo, kw.get("max_tokens")))
            cortar = self.cortes[alvo] > 0
            self.cortes[alvo] -= cortar
        if cortar:
            raise RuntimeError("O modelo não retornou JSON válido.")
        return super().chat(mensagens, **kw)


def test_especialista_cortado_tenta_de_novo_com_orcamento_maior():
    llm = LLMQueCorta(cortar_especialistas=1)
    estado = criar(llm).executar("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?")
    assert all(p.valido_reparado for p in estado["pareceres"])
    assert sorted(p.tentativas for p in estado["pareceres"])[-1] == 2
    orc = [o for a, o in llm.orcamentos if a == "esp"]
    assert max(orc) > min(orc)  # a nova tentativa teve mais tokens


def test_falha_persistente_nao_derruba_o_grafo():
    llm = LLMQueCorta(cortar_especialistas=99, cortar_relator=99)
    estado = criar(llm).executar("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?")
    assert estado["pareceres"] and not any(p.valido_reparado for p in estado["pareceres"])
    final = estado["resposta"]
    assert not final.valido and "relator_sem_json_valido" in final.observacoes
    assert final.resposta.endswith(AVISO_DECISAO) and final.dados["confianca"] == 0.0


class LLMQueRegistra(LLMRoteiro):
    def __init__(self):
        super().__init__()
        self.prompts_usuario = []

    def chat(self, mensagens, **kw):
        with self._trava:
            self.prompts_usuario.append(mensagens[-1]["content"])
        return super().chat(mensagens, **kw)


def test_f2_recebe_precedentes_da_memoria_e_entrega_os_seis_elementos():
    from app.application.decisoes.recomendacao import elementos_rf20
    from app.domain.decisoes import Decisao, Precedente

    prec = Precedente(Decisao(titulo="DECISÃO DA GESTÃO DG-011/2025 — Prorrogação do Contrato nº 044/2023",
                              decisao="Prorrogar por 12 meses.", data="2025-07-30", id=2, codigo="DG-011/2025",
                              resultado="Execução regular.", avaliacao_resultado="positivo"), 0.97, "P2")
    llm = LLMQueRegistra()
    orq = Orquestrador(lambda pergunta, k: TRECHOS, ResponderF1(llm, verificador=verificar), llm,
                       linha_do_tempo=lambda docs: "", precedentes=lambda pergunta, docs: [prec])
    estado = orq.executar("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?")
    assert all("[P2]" in p for p in llm.prompts_usuario)  # especialistas e relator veem o precedente
    final = estado["resposta"]
    assert final.valido  # schema relator.v2
    assert [p["codigo"] for p in final.dados["precedentes"]] == ["DG-011/2025"]
    assert set(elementos_rf20(final.dados).values()) <= {"presente", "declarado"}
