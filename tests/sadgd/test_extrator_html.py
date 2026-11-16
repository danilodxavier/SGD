"""Extrator HTML de atos normativos: texto tachado vira marcador de revogação."""
from app.application.ingestao.chunking import Pagina, dividir
from app.infrastructure.extratores.html_legal import extrair_texto

HTML = """<html><head><meta charset="windows-1252"><title>L99999</title><style>p{}</style></head><body>
<p align="center"><b>LEI N&ordm; 99.999, DE 1&ordm; DE ABRIL DE 2030</b></p>
<p>Art.&nbsp;1&ordm;&nbsp; Esta Lei estabelece normas gerais.</p>
<p><strike>Art. 2&ordm; Reda&ccedil;&atilde;o antiga do artigo.</strike></p>
<p>Art. 2&ordm; Nova reda&ccedil;&atilde;o do artigo. (Reda&ccedil;&atilde;o dada pela Lei n&ordm; 1)</p>
<p><strike>I - inciso revogado;</strike></p>
<p>Art. 3&ordm; Vigente.</p>
</body></html>""".encode("cp1252")


def test_extrai_texto_e_marca_tachado_apos_o_rotulo():
    texto = extrair_texto(HTML)
    linhas = texto.splitlines()
    assert "LEI Nº 99.999, DE 1º DE ABRIL DE 2030" in linhas
    assert "Art. 2º [REVOGADO] Redação antiga do artigo." in linhas
    assert "I - [REVOGADO] inciso revogado;" in linhas
    assert "p{}" not in texto  # conteúdo de <style> é ignorado


def test_versao_revogada_e_vigente_viram_trechos_distintos():
    trechos = dividir([Pagina(extrair_texto(HTML), None)])
    artigos = [(t.dispositivo, t.revogado) for t in trechos if t.tipo_dispositivo == "artigo"]
    assert artigos == [("art. 1º", False), ("art. 2º", True), ("art. 2º", False), ("art. 3º", False)]
