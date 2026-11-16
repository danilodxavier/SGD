"""Consistência da especificação dos agentes (Fase 2): prompts versionados, schemas e catálogo."""
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PROMPTS = RAIZ / "app" / "application" / "agentes" / "prompts"
SCHEMAS = RAIZ / "app" / "application" / "agentes" / "schemas"
CATALOGO = RAIZ / "docs" / "agentes" / "README.md"

ESPECIALISTAS = {
    "procurador_estado", "advogado", "controlador_geral", "fiscal_contrato", "gestor_publico",
    "analista_administrativo", "analista_orcamentario_financeiro", "especialista_licitacoes",
}
ORQUESTRACAO = {"roteador", "analista_linha_do_tempo", "verificador_fontes", "relator"}
CAMPOS_OBRIGATORIOS = {"nome", "versao", "tipo", "schema", "modelo_perfil", "max_tokens", "temperatura", "acionamento"}


def front_matter(caminho):
    texto = caminho.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.+)$", texto, re.S)
    assert m, f"{caminho.name}: front-matter ausente"
    meta = dict(linha.split(":", 1) for linha in m.group(1).splitlines())
    return {k.strip(): v.strip() for k, v in meta.items()}, m.group(2)


def prompts():
    return sorted(p for p in PROMPTS.glob("*.v*.md") if not p.name.startswith("_"))


def test_todos_os_agentes_tem_prompt():
    nomes = {front_matter(p)[0]["nome"] for p in prompts()}
    assert nomes == ESPECIALISTAS | ORQUESTRACAO


@pytest.mark.parametrize("caminho", prompts(), ids=lambda p: p.name)
def test_prompt_tem_metadados_e_schema_existente(caminho):
    meta, corpo = front_matter(caminho)
    assert CAMPOS_OBRIGATORIOS <= meta.keys()
    assert caminho.name == f"{meta['nome']}.v{meta['versao']}.md"
    assert (SCHEMAS / meta["schema"]).is_file()
    assert 0 <= float(meta["temperatura"]) <= 1 and int(meta["max_tokens"]) > 0
    assert len(corpo.strip()) > 200
    if meta["nome"] in ESPECIALISTAS:
        assert meta["schema"] == "parecer_especialista.v1.json"


@pytest.mark.parametrize("caminho", sorted(SCHEMAS.glob("*.json")), ids=lambda p: p.name)
def test_schemas_sao_json_schema_validos(caminho):
    schema = json.loads(caminho.read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    assert set(schema["required"]) <= set(schema["properties"])
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(schema)


def test_parecer_exige_elementos_do_prompt_mestre():
    schema = json.loads((SCHEMAS / "parecer_especialista.v1.json").read_text(encoding="utf-8"))
    for campo in ("parecer", "fundamentacao_legal", "afirmacoes", "confianca", "riscos"):
        assert campo in schema["required"]
    citacao = schema["properties"]["afirmacoes"]["items"]["properties"]["citacoes"]
    assert citacao["minItems"] == 1 and citacao["items"]["pattern"] == "^T[0-9]+$"


def test_roteador_nunca_aciona_todos_os_agentes():
    schema = json.loads((SCHEMAS / "roteador.v1.json").read_text(encoding="utf-8"))
    assert schema["properties"]["agentes"]["maxItems"] < len(ESPECIALISTAS)


def test_regras_comuns_e_catalogo_referenciam_todos():
    assert (PROMPTS / "_regras_comuns.v1.md").is_file()
    catalogo = CATALOGO.read_text(encoding="utf-8")
    for p in prompts():
        assert p.name in catalogo, f"{p.name} não está no catálogo docs/agentes/README.md"
