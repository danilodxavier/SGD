"""Regra de dependência da Clean Architecture (ADR-013), verificada por análise estática dos imports."""
import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
STDLIB = set(sys.stdlib_module_names)

# camada -> prefixos de módulos do projeto que ela pode importar
PERMITIDOS = {
    "domain": ("app.domain",),
    "application": ("app.domain", "app.application"),
}
# bibliotecas externas permitidas por camada (o domínio é Python puro)
EXTERNOS_PERMITIDOS = {
    "domain": set(),
    "application": {"langgraph", "langchain_core", "pydantic", "jsonschema"},
}


def modulos_importados(arquivo: Path):
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                yield alias.name
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            yield no.module


def arquivos(camada):
    return sorted((APP / camada).rglob("*.py"))


@pytest.mark.parametrize("camada", ["domain", "application"])
def test_camadas_internas_nao_dependem_de_camadas_externas(camada):
    violacoes = []
    for arquivo in arquivos(camada):
        for modulo in modulos_importados(arquivo):
            raiz = modulo.split(".")[0]
            if raiz == "app":
                if not modulo.startswith(PERMITIDOS[camada]):
                    violacoes.append(f"{arquivo.relative_to(APP)} importa {modulo}")
            elif raiz not in STDLIB and raiz not in EXTERNOS_PERMITIDOS[camada]:
                violacoes.append(f"{arquivo.relative_to(APP)} importa biblioteca externa {modulo}")
    assert not violacoes, "\n".join(violacoes)


def test_dominio_nao_faz_io():
    proibidos = {"sqlite3", "os", "pathlib", "requests", "urllib", "socket", "subprocess", "shutil"}
    for arquivo in arquivos("domain"):
        usados = {m.split(".")[0] for m in modulos_importados(arquivo)}
        assert not usados & proibidos, f"{arquivo.name} usa {usados & proibidos}"
