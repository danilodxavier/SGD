"""Gera as fichas de contrato (Fase 12) com o LLM local — rodar fora do horário de uso; retomável.

Agrupa os documentos por contrato (pasta de 1º nível ou número citado), monta o inventário por tipo e extrai, do
instrumento e das portarias de designação, número, contratada, objeto, vigência, valor, fiscal e gestor (cada valor
conferido contra o trecho citado). Imprime só contagens — nenhum conteúdo de documento.

Uso: python scripts/sadgd/gerar_fichas.py [--max-minutos 8] [--refazer]
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--max-minutos", type=float, default=None)
    p.add_argument("--refazer", action="store_true", help="extrai de novo mesmo as fichas já prontas")
    a = p.parse_args()

    from app.application.fichas.gerar import GerarFichas
    from app.core.config import settings
    from app.infrastructure.llm.openai_compativel import OpenAICompativelAdapter
    from app.infrastructure.sqlite.conexao import conectar, migrar
    from app.infrastructure.sqlite.repositorio_fichas import RepositorioFichasSqlite

    if settings.ai_allow_remote:
        print("[ERRO] Fichas usam só o LLM local: mantenha AI_ALLOW_REMOTE=false no .env.")
        return 1
    conn = conectar(settings.database_path, vetores=False)
    migrar(conn)
    conn.close()
    repo = RepositorioFichasSqlite(lambda: conectar(settings.database_path, vetores=False))
    llm = OpenAICompativelAdapter("ollama", settings.ollama_url + "/v1", settings.llm_modelo_padrao, timeout=300)

    def progresso(chave, ficha):  # sem conteúdo: só o número de campos e de documentos
        print(f"  ficha: {len(ficha['campos'])} campos conferidos, {len(ficha['documentos'])} documentos, "
              f"{len(ficha.get('apelidos', []))} apelido(s), extração={ficha['extracao']}", flush=True)

    r = GerarFichas(repo, llm).executar(a.max_minutos * 60 if a.max_minutos else None, a.refazer, progresso)
    print(f"[{'PARCIAL' if r['pendentes'] else 'OK'}] contratos={r['contratos']} extraídas={r['extraidas']} "
          f"já prontas={r['puladas']} sem instrumento={r['sem_documento']} falhas={r['falhas']} "
          f"pendentes={r['pendentes']} campos aceitos={r['campos_aceitos']}")
    return 3 if r["pendentes"] else 0


if __name__ == "__main__":
    sys.exit(main())
