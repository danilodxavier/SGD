"""Corrige fichas cujo "valor atual (após aditivo)" é, na verdade, o acréscimo/supressão do aditivo (sem LLM).

O LLM da extração copiava "o valor global é acrescido de R$ 73.150,00" como novo valor global (2026-11-23). A
extração já recusa esse caso (`extracao.e_variacao`); este script limpa as fichas gravadas antes: remove
`valor_atual`/`aditivo_valor` quando o trecho citado mostra uma variação — a pergunta de valor vai então ao caminho
completo (o LLM lê os trechos). Só imprime contagens (acervo real: nada de conteúdo na saída).

Uso:  python scripts/sadgd/corrigir_valor_atual.py            (simula)
      python scripts/sadgd/corrigir_valor_atual.py --aplicar  (grava; faça backup do banco antes)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def corrigir(repo, aplicar=False) -> dict:
    from app.application.fichas.extracao import e_variacao

    resumo = {"fichas": 0, "com_valor_atual": 0, "variacao": 0, "sem_trecho": 0}
    for ficha in repo.todas():
        resumo["fichas"] += 1
        campos = ficha["campos"]
        item = campos.get("valor_atual")
        if not item:
            continue
        resumo["com_valor_atual"] += 1
        doc = (campos.get("aditivo_valor") or {}).get("documento_id")
        textos = dict(repo.trechos_do_documento(doc)) if doc else {}
        texto = textos.get(item.get("trecho_id"))
        if texto is None:
            resumo["sem_trecho"] += 1
            continue
        if e_variacao(item["valor"], texto):
            resumo["variacao"] += 1
            if aplicar:
                campos.pop("valor_atual", None)
                campos.pop("aditivo_valor", None)
                repo.salvar(ficha)
    return resumo


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    from app.core.config import settings
    from app.infrastructure.sqlite.conexao import conectar
    from app.infrastructure.sqlite.repositorio_fichas import RepositorioFichasSqlite

    repo = RepositorioFichasSqlite(lambda: conectar(settings.database_path, vetores=False))
    r = corrigir(repo, a.aplicar)
    acao = "corrigidas" if a.aplicar else "a corrigir (simulação; use --aplicar)"
    print(f"fichas: {r['fichas']}; com valor atual: {r['com_valor_atual']}; {acao}: {r['variacao']}; "
          f"trecho não encontrado: {r['sem_trecho']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
