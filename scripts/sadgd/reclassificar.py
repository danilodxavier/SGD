"""Recalcula os metadados (tipo, número, título, datas, processo, vigência) a partir dos trechos JÁ indexados,
sem reabrir os arquivos nem refazer OCR — usado quando as regras de metadados mudam (ex.: 2º nível, A1).

Imprime somente contagens (seguro para acervo real). Rode `construir_grafo.py` depois.
Uso: python scripts/sadgd/reclassificar.py [--simular]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.ingestao.metadados import ESPECIE, extrair_metadados  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.domain.normas import EspecieNormativa  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402

ESFERA_PADRAO = {"publico": "federal", "sintetico": "estadual", "real": "estadual"}


def _iso(d):
    return d.isoformat() if d else None


def texto_do_documento(conn, documento_id, limite=40):
    """Texto aproximado do início do documento: os primeiros trechos, na ordem (os metadados usam o início)."""
    partes = [r[0] for r in conn.execute("SELECT texto FROM trechos WHERE documento_id = ? ORDER BY ordem LIMIT ?",
                                         (documento_id, limite))]
    return "\n".join(partes)


def reclassificar(conn, simular=False):
    docs = conn.execute("SELECT id, caminho_relativo, extensao, tipo_documental, numero, corpus_origem "
                        "FROM documentos").fetchall()
    transicoes, mudou_numero, estritos_iguais, estritos = Counter(), 0, 0, 0
    normas_ins = normas_del = 0
    for doc_id, relativo, ext, tipo_ant, num_ant, origem in docs:
        md = extrair_metadados(texto_do_documento(conn, doc_id), relativo, ext)
        if tipo_ant != "outro":  # fidelidade da reconstrução: o 1º nível deve repetir o resultado da indexação
            estritos += 1
            estritos_iguais += md.tipo_documental == tipo_ant
        transicoes[(tipo_ant, md.tipo_documental)] += 1
        mudou_numero += (md.numero or None) != (num_ant or None)
        if simular:
            continue
        conn.execute("UPDATE documentos SET tipo_documental = ?, numero = ?, titulo = ?, data_documento = ?, "
                     "orgao = ?, processo = ?, vigencia_inicio = ?, vigencia_fim = ? WHERE id = ?",
                     (md.tipo_documental, md.numero, md.titulo, _iso(md.data), md.orgao, md.processo,
                      _iso(md.vigencia_inicio), _iso(md.vigencia_fim), doc_id))
        especie = ESPECIE.get(md.tipo_documental)
        tem_norma = conn.execute("SELECT 1 FROM normas WHERE documento_id = ?", (doc_id,)).fetchone()
        if especie and especie is not EspecieNormativa.PARECER:
            if not tem_norma:
                conn.execute("INSERT INTO normas (documento_id, especie, nivel, esfera, numero, ano, situacao, "
                             "evidencia_situacao) VALUES (?,?,?,?,?,?,?,?)",
                             (doc_id, md.tipo_documental, especie.nivel, ESFERA_PADRAO.get(origem), md.numero,
                              md.data.year if md.data else None, md.situacao or "vigente", md.evidencia_situacao))
                normas_ins += 1
        elif tem_norma:
            conn.execute("DELETE FROM normas WHERE documento_id = ?", (doc_id,))
            normas_del += 1
    if not simular:
        conn.commit()
    return {"documentos": len(docs), "transicoes": transicoes, "numeros_alterados": mudou_numero,
            "fidelidade_reconstrucao": round(estritos_iguais / estritos, 4) if estritos else None,
            "classificados_antes": estritos, "normas_inseridas": normas_ins, "normas_removidas": normas_del}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--simular", action="store_true", help="só conta; não grava")
    a = p.parse_args()
    conn = conectar(settings.database_path, vetores=False)
    try:
        r = reclassificar(conn, a.simular)
    finally:
        conn.close()
    antes = Counter()
    depois = Counter()
    for (de, para), n in r["transicoes"].items():
        antes[de] += n
        depois[para] += n
    print(f"{'[SIMULAÇÃO] ' if a.simular else ''}documentos: {r['documentos']}")
    print(f"fidelidade da reconstrução (1º nível repetido nos {r['classificados_antes']} já classificados): "
          f"{r['fidelidade_reconstrucao']}")
    print("tipos antes :", antes.most_common())
    print("tipos depois:", depois.most_common())
    print("'outro' antes -> depois:", antes["outro"], "->", depois["outro"])
    mudancas = [(k, n) for k, n in r["transicoes"].items() if k[0] != k[1] and k[0] != "outro"]
    print("reclassificados que já tinham tipo:", sorted(mudancas, key=lambda x: -x[1])[:10])
    print(f"números alterados: {r['numeros_alterados']} | normas +{r['normas_inseridas']} -{r['normas_removidas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
