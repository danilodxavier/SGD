"""Avaliação com documentos reais (scripts/sadgd/avaliar_real.py): validação, revisão e métricas, sem modelos."""
import importlib.util
import json
from pathlib import Path

import pytest

ARQ = Path(__file__).resolve().parents[2] / "scripts" / "sadgd" / "avaliar_real.py"


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("avaliar_real", ARQ)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for nome, arquivo in (("PASTA", ""), ("PERGUNTAS", "perguntas.csv"), ("RESULTADOS", "resultados.jsonl"),
                          ("REVISAO", "revisao.csv"), ("RESUMO", "resumo.json")):
        monkeypatch.setattr(m, nome, tmp_path / arquivo if arquivo else tmp_path)
    monkeypatch.setattr(m, "RAIZ", tmp_path)
    return m


class Args:
    k, max_minutos = 5, None


def _preparar(mod):
    mod._gravar_csv(mod.PERGUNTAS, mod.CAMPOS, [
        {"id": "Q1", "pergunta": "Qual o valor do contrato 12/2024?", "tipo": "fato", "termos_esperados": "R$ 1.000,00",
         "documento_esperado": "contrato_12"},
        {"id": "Q2", "pergunta": "Qual o empenho do contrato 12/2024?", "tipo": "ausencia", "termos_esperados": "",
         "documento_esperado": ""},
        {"id": "Q3", "pergunta": "Quando terminou o contrato 13/2024?", "tipo": "linha_do_tempo",
         "termos_esperados": "31/12/2025", "documento_esperado": "aditivo_13"}])
    regs = [
        {"id": "Q1", "tipo": "fato", "ms": 10000, "erro": None, "rota": "F1_simples", "classificacao": "fato",
         "resposta": "O valor é R$ 1.000,00 [T1].", "fontes": [{"arquivo": "pasta/Contrato_12.pdf", "pagina": 2}],
         "recuperados": [{"arquivo": "pasta/Contrato_12.pdf", "pagina": 2}]},
        {"id": "Q2", "tipo": "ausencia", "ms": 8000, "erro": None, "rota": "F1_simples", "classificacao": "ausencia",
         "resposta": "Não localizei essa informação nos documentos disponibilizados.", "fontes": [], "recuperados": []},
        {"id": "Q3", "tipo": "linha_do_tempo", "ms": 20000, "erro": None, "rota": "F1_complexa",
         "classificacao": "ausencia", "resposta": "Não localizei essa informação nos documentos disponibilizados.",
         "fontes": [], "recuperados": [{"arquivo": "outro.pdf", "pagina": 1}]}]
    mod.RESULTADOS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in regs) + "\n", encoding="utf-8")


def test_modelo_nao_sobrescreve_e_exemplos_ficticios_sao_recusados(mod):
    assert mod.modelo(Args) == 0
    original = mod.PERGUNTAS.read_text(encoding="utf-8-sig")
    assert mod.modelo(Args) == 0 and mod.PERGUNTAS.read_text(encoding="utf-8-sig") == original
    erros = mod._validar(mod._ler_csv(mod.PERGUNTAS))
    assert any("fictício" in e for e in erros)


def test_resumo_calcula_metricas_e_preserva_julgamento_humano(mod):
    _preparar(mod)
    assert mod.revisao(Args) == 0
    linhas = mod._ler_csv(mod.REVISAO)
    for ln in linhas:
        ln["julgamento"] = {"Q1": "C", "Q2": "C", "Q3": "I"}[ln["id"]]
        ln["fontes_corretas"] = "S" if ln["id"] == "Q1" else "N"
    mod._gravar_csv(mod.REVISAO, list(linhas[0].keys()), linhas)
    assert mod.revisao(Args) == 0  # regerar não apaga o julgamento
    assert [ln["julgamento"] for ln in mod._ler_csv(mod.REVISAO)] == ["C", "C", "I"]
    assert mod.resumo(Args) == 0
    r = json.loads(mod.RESUMO.read_text(encoding="utf-8"))
    assert r["recall@5_documento_esperado"] == 0.5  # Q1 sim, Q3 não
    assert r["termos_esperados_na_resposta"] == 0.5
    assert r["recusa_correta (tipo ausencia)"] == 1.0 and r["recusa_indevida (demais tipos)"] == 0.5
    assert r["exatidao_humana (C + 0,5·P)"] == round(2 / 3, 3) and r["julgamento_humano"]["alucinacao"] == 0.0


def test_executar_recusa_envio_remoto_com_documentos_reais(mod, monkeypatch):
    from app.core.config import settings

    _preparar(mod)
    monkeypatch.setattr(settings, "ai_allow_remote", True)
    assert mod.executar(Args) == 1


def test_precisao_dos_tipos_pela_amostra_conferida(mod, monkeypatch):
    monkeypatch.setattr(mod, "AMOSTRA_TIPOS", mod.PASTA / "amostra_tipos.csv")
    campos = ["documento_id", "arquivo", "tipo_atribuido", "numero_atribuido", "titulo_detectado", "tipo_correto",
              "numero_correto"]
    mod._gravar_csv(mod.AMOSTRA_TIPOS, campos, [
        {"documento_id": 1, "tipo_atribuido": "nota_fiscal", "tipo_correto": "nota_fiscal"},
        {"documento_id": 2, "tipo_atribuido": "nota_fiscal", "tipo_correto": "certidao"},
        {"documento_id": 3, "tipo_atribuido": "contrato", "numero_atribuido": "045/2022", "tipo_correto": "contrato",
         "numero_correto": "045/2022"},
        {"documento_id": 4, "tipo_atribuido": "outro", "tipo_correto": ""}])  # não conferido: ignorado
    assert mod.medir_tipos(Args) == 0
    r = json.loads((mod.PASTA / "resumo_tipos.json").read_text(encoding="utf-8"))
    assert r["conferidos"] == 3 and r["precisao_geral"] == round(2 / 3, 3)
    assert r["precisao_por_tipo"]["nota_fiscal"] == {"n": 2, "precisao": 0.5} and r["numero_correto"] == 1.0
