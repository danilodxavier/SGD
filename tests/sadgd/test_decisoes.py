"""Memória de decisões (SAD-080, RF-19) e recomendação F2 completa (SAD-081, RF-20)."""
import hashlib
import math

import pytest

from app.application.agentes.especialistas import Parecer
from app.application.decisoes.recomendacao import LACUNAS, base_legal, completar, elementos_rf20
from app.application.recuperacao.regras import TrechoRecuperado
from app.domain.decisoes import AvaliacaoResultado, Decisao, Precedente


def trecho(id_, tipo, titulo, texto="texto", situacao=None, revogado=False, dispositivo=None):
    return TrechoRecuperado(id_, id_, texto, "a.txt", f"x/{id_}.txt", titulo, dispositivo, None, tipo, "sintetico",
                            "2024-01-01", revogado, situacao)


def parecer(agente, fundamentos=(), alternativas=(), riscos=(), valido=True):
    return Parecer(agente, {"parecer": "ok", "fundamentacao_legal": list(fundamentos),
                            "alternativas": list(alternativas), "riscos": list(riscos)}, valido, valido)


def precedente(id_, avaliacao="positivo"):
    d = Decisao(titulo=f"DECISÃO DG-{id_:03d}/2024", decisao="Prorrogar.", data="2024-01-01", id=id_,
                codigo=f"DG-{id_:03d}/2024", avaliacao_resultado=avaliacao)
    return Precedente(d, 0.9, f"P{id_}")


# ----------------------------------------------------------------- domínio
def test_decisao_exige_titulo_e_texto_e_licao_segue_o_resultado():
    with pytest.raises(ValueError):
        Decisao(titulo=" ", decisao="x", data="2024-01-01")
    assert "ATENÇÃO" in precedente(1, "negativo").licao and "fraco" in precedente(2, "pendente").licao
    p = precedente(3)
    assert p.resumo()["id"] == "P3" and "[P3]" in p.como_contexto()


# ----------------------------------------------------------------- RF-20
LEI = trecho(1, "lei", "LEI Nº 14.133/2021", dispositivo="Art. 107")
DECRETO = trecho(2, "decreto", "DECRETO Nº 11.462/2023")
REVOGADA = trecho(3, "lei", "LEI Nº 8.666/1993", situacao="revogada")
ORIENTACAO = trecho(4, "orientacao", "ORIENTAÇÃO NORMATIVA Nº 02/2024")
CONTRATO = trecho(5, "contrato", "CONTRATO Nº 012/2023")


def test_base_legal_vem_dos_pareceres_pela_hierarquia_e_revogada_vai_ao_historico():
    p = parecer("procurador_estado", [{"norma": "Orientação 02/2024", "trecho": "T4"},
                                      {"norma": "Lei 8.666", "trecho": "T3"},
                                      {"norma": "Lei 14.133", "dispositivo": "art. 107", "trecho": "T1"},
                                      {"norma": "Inventada", "trecho": "T99"}])  # fora do contexto: descartada
    vigentes, historico = base_legal([LEI, DECRETO, REVOGADA, ORIENTACAO, CONTRATO], [p])
    assert [v["norma"] for v in vigentes] == ["Lei 14.133", "Orientação 02/2024"]  # lei (2) antes de orientação (5)
    assert [h["norma"] for h in historico] == ["Lei 8.666"]


def test_sem_fundamentacao_nos_pareceres_usa_as_normas_recuperadas():
    vigentes, _ = base_legal([CONTRATO, DECRETO, LEI], [parecer("gestor_publico")])
    assert [v["trecho"] for v in vigentes] == ["T1", "T2"]


def test_completar_preenche_pelos_pareceres_declara_lacunas_e_limita_confianca():
    alt = {"descricao": "Prorrogar", "pros": ["continuidade"], "contras": ["custo"]}
    p = parecer("fiscal_contrato", alternativas=[alt])
    d = {"confianca": 0.9, "alternativas": [], "riscos": [], "lacunas": []}
    origem = completar(d, [CONTRATO], [p], [precedente(7, "negativo")])
    assert d["alternativas"][0]["descricao"] == "Prorrogar" and origem["alternativas"] == "sistema"
    assert origem["riscos"] == "lacuna" and LACUNAS["riscos"] in d["lacunas"]
    assert origem["base_legal"] == "lacuna" and d["confianca"] == 0.5  # sem base legal: teto 0,5
    assert d["precedentes"][0]["id"] == "P7" and d["alertas"]  # precedente negativo gera alerta
    d["aviso"] = "O sistema sugere; a decisão cabe à gestão."
    estado = elementos_rf20(d)
    assert estado == {"alternativas": "presente", "riscos": "declarado", "base_legal": "declarado",
                      "precedentes": "presente", "confianca": "presente", "aviso": "presente"}


def test_precedentes_nunca_vem_do_llm():
    d = {"confianca": 0.8, "alternativas": [], "riscos": [], "precedentes": ["DG-999/2020 inventado"]}
    completar(d, [LEI], [parecer("gestor_publico")], [])
    assert d["precedentes"] == [] and LACUNAS["precedentes"] in d["lacunas"]


# ----------------------------------------------------------------- memória (SQLite real, embedder falso)
class EmbedderFalso:
    nome_modelo = "falso"

    def embed(self, textos):
        vetores = []
        for t in textos:
            v = [0.0] * 1024
            for palavra in t.lower().split():
                v[int(hashlib.md5(palavra.strip(".,;:?").encode()).hexdigest(), 16) % 1024] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            vetores.append([x / n for x in v])
        return vetores


class RerankerFalso:
    def pontuar(self, consulta, textos):
        termos = set(consulta.lower().split())
        return [len(termos & set(t.lower().split())) / 10 for t in textos]


@pytest.fixture()
def memoria(db):
    pytest.importorskip("sqlite_vec")
    from app.application.decisoes.memoria import MemoriaDecisoes
    from app.core.config import settings
    from app.infrastructure.sqlite.conexao import conectar
    from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite

    m = MemoriaDecisoes(RepositorioDecisoesSqlite(lambda: conectar(settings.database_path)), EmbedderFalso(),
                        RerankerFalso(), limiar_rerank=0.15)
    for cod, titulo, decisao, aval in [
        ("DG-001/2024", "Prorrogação do contrato de limpeza", "Prorrogar o contrato de limpeza por 12 meses.",
         "negativo"),
        ("DG-002/2024", "Multa por atraso na entrega de mobiliário", "Aplicar advertência ao fornecedor.", "positivo"),
        ("DG-003/2024", "Teletrabalho parcial", "Implantar teletrabalho para equipes administrativas.", "positivo")]:
        m.registrar(Decisao(titulo=titulo, decisao=decisao, data="2024-01-01", codigo=cod, avaliacao_resultado=aval,
                            corpus_origem="sintetico"))
    return m


@pytest.mark.parametrize("modo", ["bm25", "denso", "hibrido", "hibrido_rerank"])
def test_precedente_semelhante_e_recuperado_em_todos_os_modos(memoria, modo):
    achados = memoria.precedentes("Devemos prorrogar o contrato de limpeza?", k=3, modo=modo)
    assert achados[0].decisao.codigo == "DG-001/2024"
    assert achados[0].decisao.avaliacao_resultado is AvaliacaoResultado.NEGATIVO


def test_limiar_evita_falso_precedente_e_reimportacao_e_idempotente(memoria):
    assert memoria.precedentes("Compra de passagens aéreas internacionais", modo="hibrido_rerank") == []
    memoria.registrar(Decisao(titulo="Teletrabalho parcial revisado", decisao="Manter o teletrabalho.",
                              data="2025-01-01", codigo="DG-003/2024"))
    assert len(memoria.repo.listar()) == 3
    assert memoria.precedentes("teletrabalho", modo="bm25")[0].decisao.titulo == "Teletrabalho parcial revisado"


def test_atualizar_resultado(memoria):
    alvo = memoria.precedentes("teletrabalho", modo="bm25")[0].decisao
    assert memoria.atualizar_resultado(alvo.id, "Produtividade mantida.", "positivo")
    assert not memoria.atualizar_resultado(9999, "x", "neutro")
    with pytest.raises(ValueError):
        memoria.atualizar_resultado(alvo.id, "x", "otimo")
