"""SAD-090/091/092 — Testes ponta a ponta no navegador real (Playwright + Microsoft Edge do sistema, headless).

RF-21: pergunta → resposta → fonte que abre o documento original e o trecho citado.
RF-22: upload → indexação no servidor → documento aparece no acervo e na busca.
RF-13: linha do tempo com fases e relações com evidência clicável.

O servidor sobe de verdade (uvicorn, porta livre) com banco e acervo temporários; só o orquestrador (LLM) é
substituído por um dublê, para o teste não depender da GPU. Pulado se o Playwright ou o Edge não existirem."""
import os
import socket
import threading
import time
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
pytest.importorskip("sqlite_vec")

from app.application.agentes.roteador import rotear  # noqa: E402
from app.application.respostas.f1 import RespostaF1  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure import servico_indexacao  # noqa: E402
from app.infrastructure.servico_indexacao import ServicoIndexacao  # noqa: E402
from app.infrastructure.sqlite.busca import RepositorioTrechosSqlite  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402
from app.interfaces.api import perguntar as api  # noqa: E402
from tests.helpers import PASSWORD, ensure_user  # noqa: E402

CONTRATO = ("CONTRATO Nº 012/2023\nCuiabá, 1º de março de 2023.\nCLÁUSULA PRIMEIRA – DO OBJETO\nPrestação de "
            "serviços de limpeza e conservação.\nCLÁUSULA SEGUNDA – DO VALOR\nO valor global do contrato é de "
            "R$ 1.200.000,00.\n")
SUSPENSAO = ("ORDEM DE SUSPENSÃO Nº 004/2023\nCuiabá, 10 de outubro de 2023.\nFica suspensa a execução do Contrato "
             "nº 012/2023 por falta de dotação.\n")
REINICIO = ("ORDEM DE REINÍCIO Nº 005/2023\nCuiabá, 4 de dezembro de 2023.\nFica retomada a execução do Contrato "
            "nº 012/2023.\n")


def _captura(page, nome):
    """Com SADGD_E2E_CAPTURAS=1, salva a tela em docs/img/fase09/ (evidência para o relatório)."""
    if os.environ.get("SADGD_E2E_CAPTURAS") == "1":
        destino = Path(__file__).resolve().parents[2] / "docs" / "img" / "fase09"
        destino.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destino / f"{nome}.png"), full_page=True)


def _resposta_f2(decisao, trecho):
    """Recomendação F2 montada pelas regras reais de RF-20 (completar), com pareceres e precedente negativo."""
    from app.application.agentes.especialistas import Parecer, RespostaF2
    from app.application.decisoes.recomendacao import completar
    from app.domain.decisoes import Decisao, Precedente
    from app.domain.politicas import AVISO_DECISAO

    alt = {"descricao": "Prorrogar com plano de ação e fiscalização quinzenal", "pros": ["continuidade do serviço"],
           "contras": ["histórico de advertências"]}
    risco = {"descricao": "Reincidência no descumprimento", "probabilidade": "alta", "impacto": "alto",
             "mitigacao": "cláusula de rescisão e fiscalização reforçada"}
    pareceres = [
        Parecer("gestor_publico", {"parecer": f"O valor de R$ 1.200.000,00 [{trecho.rotulo}] é compatível.",
                                   "recomendacao": "Prorrogar com condicionantes.", "confianca": 0.7,
                                   "afirmacoes": [{"id": "A1", "texto": "Valor global de R$ 1.200.000,00.",
                                                   "tipo": "fato", "citacoes": [trecho.rotulo]}],
                                   "alternativas": [alt], "riscos": [risco], "lacunas": []}, True, True),
        Parecer("fiscal_contrato", {"parecer": "A execução teve interrupção por falta de dotação.",
                                    "confianca": 0.6, "afirmacoes": [], "riscos": [risco], "lacunas": []}, True, True)]
    prec = Precedente(Decisao(titulo="DECISÃO DA GESTÃO DG-004/2024 — Prorrogação do contrato de limpeza",
                              decisao="Prorrogar por 12 meses com plano de ação.", data="2024-02-26", id=1,
                              codigo="DG-004/2024", resultado="Contrato rescindido depois por descumprimento.",
                              avaliacao_resultado="negativo"), 0.9, "P1")
    dados = {"resposta": f"O contrato tem valor de R$ 1.200.000,00 [{trecho.rotulo}]; o precedente [P1] alerta "
                         "para reincidência.", "recomendacao": "Prorrogar somente com plano de ação e fiscalização "
                         "quinzenal.", "consensos": ["há base para prorrogar com condicionantes"], "divergencias": [],
             "alternativas": [], "riscos": [], "lacunas": [], "classificacao": "inferencia", "confianca": 0.8,
             "aviso": AVISO_DECISAO, "fontes": [trecho.rotulo]}
    completar(dados, [trecho], pareceres, [prec])
    r = RespostaF2(dados["resposta"] + f"\n\n{AVISO_DECISAO}", dados, [trecho], pareceres, True)
    return {"decisao": decisao, "resposta": r, "pareceres": pareceres, "tempos": []}


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def servidor(db, tmp_path, monkeypatch):
    import uvicorn

    from app.main import create_app

    raiz = tmp_path / "corpus"
    (raiz / "sintetico" / "P01").mkdir(parents=True)
    for nome, texto in (("S001_contrato_012-2023.txt", CONTRATO), ("S002_ordem_suspensao_004-2023.txt", SUSPENSAO),
                        ("S003_ordem_reinicio_005-2023.txt", REINICIO)):
        (raiz / "sintetico" / "P01" / nome).write_text(texto, encoding="utf-8")
    servico = ServicoIndexacao(raiz, com_embeddings=False)
    monkeypatch.setattr(servico_indexacao, "servico", servico)
    servico.iniciar(None)
    assert servico.aguardar(60)["erro"] is None

    class Orquestrador:
        def __init__(self, tracer):
            pass

        def executar(self, pergunta):
            conn = conectar(settings.database_path, vetores=False)
            tid = conn.execute("SELECT id FROM trechos WHERE texto LIKE '%valor global%'").fetchone()[0]
            conn.close()
            trecho = RepositorioTrechosSqlite(lambda: conectar(settings.database_path)).obter([tid])[0]
            decisao = rotear(pergunta)
            if decisao.rota == "F2":
                return _resposta_f2(decisao, trecho)
            r = RespostaF1(f"O valor global do Contrato nº 012/2023 é R$ 1.200.000,00 [T{tid}].", "fato", 0.9,
                           [trecho], tokens_entrada=10, tokens_saida=5)
            return {"decisao": decisao, "resposta": r, "pareceres": [], "tempos": []}

    monkeypatch.setitem(api._componentes, "fabrica_orquestrador", Orquestrador)
    ensure_user("admin.e2e", "admin")
    porta = _porta_livre()
    srv = uvicorn.Server(uvicorn.Config(create_app(auto_index=False), host="127.0.0.1", port=porta,
                                        log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{porta}", raiz
    srv.should_exit = True
    t.join(10)


@pytest.fixture()
def pagina(servidor):
    with playwright_api.sync_playwright() as p:
        try:
            navegador = p.chromium.launch(channel="msedge", headless=True)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Microsoft Edge indisponível para o Playwright: {exc}")
        contexto = navegador.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900})
        page = contexto.new_page()
        page.set_default_timeout(20000)
        url, _ = servidor
        page.goto(url)
        page.fill("#login-username", "admin.e2e")
        page.fill("#login-password", PASSWORD)
        page.press("#login-password", "Enter")
        page.wait_for_selector("#menu .nav-item[data-view='perguntar']", state="visible")
        yield page, contexto, servidor
        navegador.close()


def test_pergunta_resposta_e_fonte_que_abre_o_documento(pagina):
    page, contexto, _ = pagina
    page.click("#menu .nav-item[data-view='perguntar']")
    page.fill("#sg-pergunta", "Qual o valor global do Contrato nº 012/2023?")
    page.click("#sg-enviar")
    page.wait_for_selector("#sg-resultado .answer")
    assert "R$ 1.200.000,00" in page.inner_text("#sg-resultado .answer-text")
    assert "Fato documental" in page.inner_text("#sg-resultado .answer-head")
    _captura(page, "01_perguntar_f1")
    # a citação [T…] abre o trecho citado
    page.click("#sg-resultado .answer-text .cit")
    page.wait_for_selector("#doc-dialog[open] .passage")
    assert "valor global" in page.inner_text("#doc-dialog .passage")
    _captura(page, "02_trecho_citado")
    page.click("#doc-dialog-close")
    # a fonte abre o documento original numa nova aba
    with contexto.expect_page() as nova:
        page.click("#sg-resultado .source a:has-text('Abrir documento')")
    doc = nova.value
    doc.wait_for_load_state()
    assert "R$ 1.200.000,00" in doc.content()


def test_upload_indexa_e_aparece_no_acervo_e_na_busca(pagina, tmp_path):
    page, _, (url, _) = pagina
    arquivo = tmp_path / "oficio_elevadores.txt"
    arquivo.write_text("OFÍCIO Nº 77/2025\nManutenção corretiva dos elevadores do prédio-sede.\n", encoding="utf-8")
    page.click("#menu .nav-item[data-view='acervo']")
    page.set_input_files("#ac-arquivo", str(arquivo))
    page.click("#ac-upload button[type='submit']")
    page.wait_for_selector("#ac-indexacao-texto:has-text('Concluído')", timeout=60000)
    page.wait_for_selector("#ac-tabela tbody tr:has-text('oficio_elevadores.txt')")
    assert "Real" in page.inner_text("#ac-tabela tbody tr:has-text('oficio_elevadores.txt')")
    _captura(page, "03_acervo_upload")
    busca = page.request.get(f"{url}/api/sadgd/busca?q=elevadores").json()["resultados"]
    assert busca and "elevadores" in busca[0]["texto"]


def test_linha_do_tempo_com_fases_e_evidencia(pagina):
    page, _, _ = pagina
    page.click("#menu .nav-item[data-view='linha']")
    page.wait_for_selector("#tl-processo option:has-text('Contrato 012/2023')", state="attached")
    valor = page.eval_on_selector("#tl-processo option:has-text('Contrato 012/2023')", "o => o.value")
    page.select_option("#tl-processo", valor)
    page.wait_for_selector(".sg-timeline .sg-evento")
    assert page.locator(".sg-evento").count() == 3
    fases = page.inner_text(".sg-fases")
    assert "Interrupção" in fases and "Execução retomada" in fases
    _captura(page, "04_linha_do_tempo")
    page.click(".sg-relacao:has-text('ruptura') button:has-text('Ver evidência')")
    page.wait_for_selector("#doc-dialog[open] .passage")
    assert "suspensa" in page.inner_text("#doc-dialog .passage")


def test_f2_mostra_recomendacao_elementos_precedente_e_pareceres(pagina):
    page, _, _ = pagina
    page.click("#menu .nav-item[data-view='perguntar']")
    page.fill("#sg-pergunta", "Devo prorrogar novamente o Contrato nº 012/2023 de limpeza?")
    page.click("#sg-enviar")
    page.wait_for_selector("#sg-resultado .sg-recomendacao")
    assert "plano de ação" in page.inner_text(".sg-recomendacao")
    elementos = page.inner_text(".sg-elementos")
    assert "Precedentes: presente" in elementos and "Aviso: presente" in elementos
    assert "Base legal: ausência declarada" in elementos  # contexto sem norma: ausência explícita, nunca inventada
    assert "resultado negativo" in page.inner_text(".warning-note")  # precedente negativo vira alerta
    assert "DG-004/2024" in page.inner_text(".sg-prec")
    assert page.locator(".sg-parecer").count() == 2
    page.click(".sg-parecer summary >> nth=0")
    assert "Valor global" in page.inner_text(".sg-parecer >> nth=0")
    _captura(page, "05_perguntar_f2")
