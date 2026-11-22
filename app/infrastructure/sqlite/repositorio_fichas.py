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

    def numero_no_acervo(self, chave: str, limite: int = 5) -> dict:
        """Onde o número aparece: quantos trechos, quantos o citam COMO CONTRATO ("contrato nº X") e até `limite`
        documentos distintos (id, tipo, data, trecho) que o citam — para responder "não há contrato com esse número;
        ele aparece em…"."""
        from app.application.fichas.agrupamento import normalizar

        numero, ano = chave.split("/")
        n = str(int(numero))
        padrao = re.compile(rf"(?<!\d)0*{n}\s*[/\-._]\s*{ano}(?!\d)")
        como_contrato = re.compile(rf"contrato\s*(?:administrativo\s*)?(?:n[º°o]?\.?\s*|numero\s*)?0*{n}\s*[/\-.]\s*"
                                   rf"{ano}(?!\d)")
        conn = self._conexao()
        try:
            linhas = conn.execute(
                "SELECT t.id, t.texto, d.id, d.tipo_documental, d.data_documento FROM trechos t JOIN documentos d "
                "ON d.id = t.documento_id WHERE instr(t.texto, ?) > 0 ORDER BY d.data_documento DESC, t.ordem",
                (ano,)).fetchall()
        finally:
            conn.close()
        total = contrato = 0
        documentos: dict[int, dict] = {}
        for tid, texto, did, tipo, data in linhas:
            if not padrao.search(texto or ""):
                continue
            total += 1
            contrato += bool(como_contrato.search(normalizar(texto)))
            if did not in documentos and len(documentos) < limite:
                documentos[did] = {"documento_id": did, "tipo": tipo, "data": data, "trecho_id": tid}
        return {"trechos": total, "como_contrato": contrato, "documentos": list(documentos.values())}

    def documento_do_tipo_no_ano(self, pasta: str | None, documento_ids: list[int] | None, termos: list[str],
                                 ano: str) -> bool:
        """Há documento cujo INÍCIO (1º trecho: título/abertura) cita o assunto e que é do ano pedido — ou sem data
        (dúvida)? Mais preciso que procurar o termo em qualquer trecho: uma cláusula que cita "ordem de serviço"
        num trecho com "2026" não é uma ordem de serviço de 2026."""
        if not termos:
            return True
        filtro = " OR ".join("t.texto LIKE ?" for _ in termos)
        alvo, params_alvo = "1 = 1", []
        if pasta:
            alvo, params_alvo = "(d.caminho_relativo LIKE ? OR d.caminho_relativo LIKE ?)", [f"{pasta}/%",
                                                                                          f"{pasta}\\%"]
        elif documento_ids:
            alvo = f"d.id IN ({','.join('?' * len(documento_ids))})"  # noqa: S608 - só marcadores
            params_alvo = list(documento_ids)
        conn = self._conexao()
        try:
            return conn.execute(
                f"SELECT 1 FROM documentos d JOIN trechos t ON t.id = (SELECT id FROM trechos WHERE documento_id = "  # noqa: S608
                f"d.id ORDER BY ordem LIMIT 1) WHERE {alvo} AND ({filtro}) AND (d.data_documento LIKE ? OR "
                f"d.data_documento IS NULL OR d.data_documento = '' OR t.texto LIKE ?) LIMIT 1",
                params_alvo + [f"%{t}%" for t in termos] + [f"{ano}%", f"%{ano}%"]).fetchone() is not None
        finally:
            conn.close()

    def candidatos_do_tipo_no_ano(self, pasta: str | None, documento_ids: list[int] | None, termos: list[str],
                                  ano: str, limite: int = 8) -> tuple[int, list[dict]]:
        """Os documentos que fazem documento_do_tipo_no_ano dar verdadeiro: (total, até `limite` itens com
        documento_id, data e o 1º trecho_id), mais recentes primeiro — para mostrar ao usuário em vez de recusar."""
        if not termos:
            return 0, []
        filtro = " OR ".join("t.texto LIKE ?" for _ in termos)
        alvo, params_alvo = "1 = 1", []
        if pasta:
            alvo, params_alvo = "(d.caminho_relativo LIKE ? OR d.caminho_relativo LIKE ?)", [f"{pasta}/%",
                                                                                          f"{pasta}\\%"]
        elif documento_ids:
            alvo = f"d.id IN ({','.join('?' * len(documento_ids))})"  # noqa: S608 - só marcadores
            params_alvo = list(documento_ids)
        conn = self._conexao()
        try:
            linhas = conn.execute(
                f"SELECT d.id, d.data_documento, t.id FROM documentos d JOIN trechos t ON t.id = (SELECT id FROM "  # noqa: S608
                f"trechos WHERE documento_id = d.id ORDER BY ordem LIMIT 1) WHERE {alvo} AND ({filtro}) AND "
                f"(d.data_documento LIKE ? OR d.data_documento IS NULL OR d.data_documento = '' OR t.texto LIKE ?) "
                f"ORDER BY COALESCE(d.data_documento, '') DESC, d.id DESC",
                params_alvo + [f"%{t}%" for t in termos] + [f"{ano}%", f"%{ano}%"]).fetchall()
        finally:
            conn.close()
        itens = [{"documento_id": r[0], "data": r[1] or None, "trecho_id": r[2],
                  "no_ano": str(r[1] or "").startswith(ano)} for r in linhas[:limite]]
        return len(linhas), itens

    def documentos_da_pasta(self, pasta: str) -> set[int]:
        """Todos os documentos da pasta do contrato (inclusive os de tipo "outro", fora do inventário)."""
        conn = self._conexao()
        try:
            return {r[0] for r in conn.execute(
                "SELECT id FROM documentos WHERE caminho_relativo LIKE ? OR caminho_relativo LIKE ?",
                (f"{pasta}/%", f"{pasta}\\%"))}
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

    def menciona_ano(self, pasta: str | None, documento_ids: list[int] | None, termos: list[str], ano: str) -> bool:
        """Algum trecho cita um dos termos E o ano? Sem pasta e sem documentos: o acervo inteiro."""
        if not termos:
            return True
        filtro = " OR ".join("t.texto LIKE ?" for _ in termos)
        params = [f"%{ano}%"] + [f"%{t}%" for t in termos]
        alvo, params_alvo = "1 = 1", []
        if pasta:
            alvo, params_alvo = "(d.caminho_relativo LIKE ? OR d.caminho_relativo LIKE ?)", [f"{pasta}/%",
                                                                                          f"{pasta}\\%"]
        elif documento_ids:
            alvo = f"d.id IN ({','.join('?' * len(documento_ids))})"  # noqa: S608 - só marcadores
            params_alvo = list(documento_ids)
        conn = self._conexao()
        try:
            return conn.execute(
                f"SELECT 1 FROM trechos t JOIN documentos d ON d.id = t.documento_id WHERE {alvo} "  # noqa: S608
                f"AND t.texto LIKE ? AND ({filtro}) LIMIT 1", params_alvo + params).fetchone() is not None
        finally:
            conn.close()

    def _linha(self, r) -> dict:
        campos = json.loads(r[3] or "{}")
        return {"id": r[0], "chave": r[1], "pasta": r[2],
                "campos": {k: v for k, v in campos.items() if not k.startswith("_")},
                "apelidos": campos.get("_apelidos", []), "complemento": campos.get("_complemento", 0),
                "aditivos_lidos": campos.get("_aditivos_lidos"), "aditivos_versao": campos.get("_aditivos_versao", 1),
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
                  "_complemento": ficha.get("complemento", 0), "_aditivos_lidos": ficha.get("aditivos_lidos"),
                  "_aditivos_versao": ficha.get("aditivos_versao", 1)}
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
