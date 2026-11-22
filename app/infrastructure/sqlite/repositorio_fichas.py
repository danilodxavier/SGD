"""Persistência das fichas de contrato (migração 007) e leitura do acervo para gerá-las."""
import json
import re
from datetime import datetime

from app.application.fichas.agrupamento import DocumentoAcervo


class RepositorioFichasSqlite:
    def __init__(self, fabrica_conexao):
        self._conexao = fabrica_conexao

    def documentos_acervo(self) -> list[DocumentoAcervo]:
        conn = self._conexao()
        try:
            return [DocumentoAcervo(i, rel, tipo, tit, data, (txt or "")[:600], tid)
                    for i, rel, tipo, tit, data, txt, tid
                    in conn.execute(
                        "SELECT d.id, d.caminho_relativo, d.tipo_documental, d.titulo, d.data_documento, t.texto, t.id "
                        "FROM documentos d LEFT JOIN trechos t ON t.id = (SELECT id FROM trechos WHERE documento_id = "
                        "d.id ORDER BY ordem LIMIT 1)")]
        finally:
            conn.close()

    def trechos_do_documento(self, documento_id: int) -> list[tuple[int, str]]:
        conn = self._conexao()
        try:
            return [(r[0], r[1]) for r in conn.execute(
                "SELECT id, texto FROM trechos WHERE documento_id = ? ORDER BY ordem", (documento_id,))]
        finally:
            conn.close()

    def ocorrencias_numero(self, chave: str) -> int:
        """Quantos trechos citam o número (012/2023, 12/2023, 012-2023, 34.2022…) — com fronteira numérica."""
        numero, ano = chave.split("/")
        n = str(int(numero))
        padrao = re.compile(rf"(?<!\d)0*{n}\s*[/\-._]\s*{ano}(?!\d)")
        conn = self._conexao()
        try:
            candidatos = conn.execute("SELECT texto FROM trechos WHERE instr(texto, ?) > 0", (ano,))
            return sum(1 for (texto,) in candidatos if padrao.search(texto or ""))
        finally:
            conn.close()

    def menciona(self, pasta: str | None, documento_ids: list[int], termos: list[str]) -> bool:
        """Algum trecho da pasta do contrato (ou dos documentos listados) contém algum dos termos? LIKE do SQLite
        ignora caixa em ASCII; os termos são radicais sem acento ("paralis", "ordem de servi")."""
        if not termos or not (pasta or documento_ids):
            return False
        filtro_termos = " OR ".join("t.texto LIKE ?" for _ in termos)
        params = [f"%{t}%" for t in termos]
        if pasta:
            alvo, params_alvo = "(d.caminho_relativo LIKE ? OR d.caminho_relativo LIKE ?)", [f"{pasta}/%",
                                                                                          f"{pasta}\\%"]
        else:
            alvo = f"d.id IN ({','.join('?' * len(documento_ids))})"  # noqa: S608 - só marcadores
            params_alvo = list(documento_ids)
        conn = self._conexao()
        try:
            return conn.execute(
                f"SELECT 1 FROM trechos t JOIN documentos d ON d.id = t.documento_id WHERE {alvo} "  # noqa: S608
                f"AND ({filtro_termos}) LIMIT 1", params_alvo + params).fetchone() is not None
        finally:
            conn.close()

    def _linha(self, r) -> dict:
        campos = json.loads(r[3] or "{}")
        return {"id": r[0], "chave": r[1], "pasta": r[2],
                "campos": {k: v for k, v in campos.items() if not k.startswith("_")},
                "apelidos": campos.get("_apelidos", []), "complemento": campos.get("_complemento", 0),
                "documentos": json.loads(r[4] or "[]"), "texto_busca": r[5], "extracao": r[6], "gerada_em": r[7]}

    def ficha(self, chave: str) -> dict | None:
        conn = self._conexao()
        try:
            r = conn.execute("SELECT id, chave, pasta, campos, documentos, texto_busca, extracao, gerada_em "
                             "FROM fichas_contrato WHERE chave = ?", (chave,)).fetchone()
            return self._linha(r) if r else None
        finally:
            conn.close()

    def todas(self) -> list[dict]:
        conn = self._conexao()
        try:
            return [self._linha(r) for r in conn.execute(
                "SELECT id, chave, pasta, campos, documentos, texto_busca, extracao, gerada_em FROM fichas_contrato")]
        finally:
            conn.close()

    def salvar(self, ficha: dict) -> None:
        campos = {**ficha.get("campos", {}), "_apelidos": ficha.get("apelidos", []),
                  "_complemento": ficha.get("complemento", 0)}
        conn = self._conexao()
        try:
            conn.execute(
                "INSERT INTO fichas_contrato (chave, pasta, campos, documentos, texto_busca, extracao, gerada_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(chave) DO UPDATE SET pasta = excluded.pasta, "
                "campos = excluded.campos, documentos = excluded.documentos, texto_busca = excluded.texto_busca, "
                "extracao = excluded.extracao, gerada_em = excluded.gerada_em",
                (ficha["chave"], ficha.get("pasta"), json.dumps(campos, ensure_ascii=False),
                 json.dumps(ficha.get("documentos", []), ensure_ascii=False), ficha.get("texto_busca", ""),
                 ficha.get("extracao", "pendente"), datetime.now().isoformat(timespec="seconds")))
            conn.commit()
        finally:
            conn.close()
