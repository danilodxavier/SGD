"""Abertura do documento (início + cláusula do objeto) junto dos trechos recuperados."""
from app.application.recuperacao.aberturas import com_aberturas, recorte_abertura
from app.application.recuperacao.regras import TrechoRecuperado


def tr(id_, doc, texto, ordem_dispositivo=None):
    return TrechoRecuperado(id_, doc, texto, "a.pdf", f"p{doc}/a.pdf", None, ordem_dispositivo, None, "contrato",
                            "sintetico", None, False, None)


class RepoFalso:
    def __init__(self, por_doc):
        self.por_doc, self.pedidos = por_doc, []

    def iniciais(self, documento_ids, ate_ordem=4):
        self.pedidos.append(list(documento_ids))
        return {d: self.por_doc[d] for d in documento_ids if d in self.por_doc}


CABECALHO = "CONTRATO Nº 012/2023. Contratante: Secretaria. Contratada: Empresa X. " + "Considerando. " * 90
OBJETO = "CLÁUSULA PRIMEIRA – DO OBJETO. Suporte às licenças de banco de dados."


def test_abertura_entra_antes_do_primeiro_trecho_do_documento():
    meio = tr(50, 1, "CLÁUSULA OITAVA – O suporte será prestado em regime integral.")
    repo = RepoFalso({1: [tr(10, 1, CABECALHO), tr(11, 1, OBJETO)]})
    saida = com_aberturas([meio], repo)
    assert [t.id for t in saida] == [10, 11, 50]
    assert saida[0].texto.startswith("CONTRATO Nº 012/2023") and saida[0].texto.endswith("[…]")
    assert len(saida[0].texto) < len(CABECALHO) and saida[0].dispositivo == "abertura do documento"
    assert saida[1].texto.startswith("CLÁUSULA PRIMEIRA – DO OBJETO")


def test_sem_objeto_extra_quando_a_abertura_ja_traz_o_objeto():
    repo = RepoFalso({1: [tr(10, 1, "CONTRATO Nº 1/2024. Objeto: limpeza."), tr(11, 1, OBJETO)]})
    assert [t.id for t in com_aberturas([tr(50, 1, "Cláusula oitava.")], repo)] == [10, 50]


def test_trecho_ja_presente_nao_e_repetido_e_limita_os_documentos():
    repo = RepoFalso({1: [tr(10, 1, "CONTRATO Nº 1/2024. Objeto: limpeza.")],
                      2: [tr(20, 2, "CONTRATO Nº 2/2024. Objeto: vigilância.")]})
    trechos = [tr(10, 1, "CONTRATO Nº 1/2024. Objeto: limpeza."), tr(21, 2, "x"), tr(31, 3, "y")]
    saida = com_aberturas(trechos, repo, max_docs=2)
    assert [t.id for t in saida] == [10, 20, 21, 31] and repo.pedidos == [[1, 2]]


def test_recorte_e_literal_e_pega_o_objeto_depois_do_inicio():
    texto = "TERMO. " + "Preâmbulo longo. " * 50 + "\nCLÁUSULA PRIMEIRA – DO OBJETO\nAquisição de licenças. " + \
        "Demais condições. " * 50
    recorte = recorte_abertura(texto)
    assert recorte.startswith("TERMO.") and "DO OBJETO" in recorte and len(recorte) < 1100
    assert all(p.strip() in texto for p in recorte.split("[…]") if p.strip())
    assert recorte_abertura("Curto. Objeto: x.") == "Curto. Objeto: x."


def test_documento_com_numero_na_ficha_nao_recebe_abertura():
    com_numero = tr(50, 1, "Cláusula oitava.")
    com_numero.numero = "012/2023"
    repo = RepoFalso({1: [tr(10, 1, "CONTRATO Nº 012/2023. Objeto: limpeza.")],
                      2: [tr(20, 2, "CONTRATO Nº 2/2024. Objeto: vigilância.")]})
    assert [t.id for t in com_aberturas([com_numero, tr(60, 2, "y")], repo)] == [50, 20, 60]
    assert repo.pedidos == [[2]]
