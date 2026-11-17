"""SAD-090/091 — API do acervo SAD-GD (RF-21, RF-22): painel, documentos, arquivo original, trecho, busca, upload
e indexação no servidor.

Segurança: o arquivo só é servido se estiver dentro da raiz documental (sem path traversal) e sempre com
`Content-Security-Policy: sandbox` + `nosniff` — HTML de terceiros (portal da legislação) não executa scripts na
origem do sistema. Upload: Gestor/Administrador, extensões suportadas, até 25 MB, nome saneado, nunca sobrescreve;
grava em `<raiz>/enviados/AAAA-MM-DD/` (origem "real": nunca vai a provedor remoto — política LGPD)."""
import mimetypes
import re
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import require_admin, require_gestor, require_login
from app.core.config import settings
from app.infrastructure.sqlite.conexao import conectar

router = APIRouter(prefix="/api/sadgd", dependencies=[Depends(require_login)], tags=["SAD-GD"])

MAX_UPLOAD = 25 * 1024 * 1024
CABECALHOS_ARQUIVO = {"Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff",
                      "Cache-Control": "no-store"}


def _servico():
    from app.infrastructure import servico_indexacao

    return servico_indexacao.servico


def _conn():
    return conectar(settings.database_path, vetores=False)


def _auditar(user, acao, alvo, request):
    conn = _conn()
    try:
        conn.execute("INSERT INTO auditoria (usuario_id, acao, alvo, ip, criado_em) VALUES (?, ?, ?, ?, ?)",
                     (user["id"], acao, alvo, request.client.host if request.client else None,
                      datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


@router.get("/painel")
def painel():
    conn = conectar(settings.database_path)  # com sqlite-vec: conta os vetores
    try:
        um = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
        origens = {r[0]: r[1] for r in conn.execute(
            "SELECT corpus_origem, count(*) FROM documentos WHERE status != 'REMOVIDO' GROUP BY corpus_origem")}
        consultas = conn.execute("SELECT rota, count(*), avg(latencia_ms) FROM consultas WHERE rota IS NOT NULL "
                                 "GROUP BY rota").fetchall()
        return {
            "documentos": sum(origens.values()), "por_origem": origens,
            "trechos": um("SELECT count(*) FROM trechos"), "vetores": um("SELECT count(*) FROM trechos_vec")
            if _tem_tabela(conn, "trechos_vec") else None,
            "normas_revogadas": um("SELECT count(*) FROM normas WHERE situacao = 'revogada'"),
            "processos": um("SELECT count(*) FROM (SELECT processo_id FROM documento_processo GROUP BY processo_id "
                            "HAVING count(*) > 1)"),
            "relacoes": um("SELECT count(*) FROM relacoes WHERE tipo != 'fundamenta'"),
            "contradicoes": um("SELECT count(*) FROM relacoes WHERE tipo = 'contradicao'"),
            "decisoes": um("SELECT count(*) FROM decisoes"),
            "consultas": [{"rota": r[0], "total": r[1], "latencia_media_ms": round(r[2] or 0)} for r in consultas],
            "ultima_indexacao": dict(zip(("inicio", "fim", "novos", "alterados", "removidos", "erros", "trechos"),
                                         conn.execute("SELECT inicio, fim, novos, alterados, removidos, erros, trechos "
                                                      "FROM indexacoes ORDER BY id DESC LIMIT 1").fetchone() or [],
                                         strict=False)),
            "indexacao": _servico().estado,
        }
    finally:
        conn.close()


def _tem_tabela(conn, nome):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (nome,)).fetchone() is not None


@router.get("/documentos")
def listar_documentos(q: str = "", tipo: str = "", origem: str = "", limite: int = 300):
    sql = ("SELECT d.id, d.titulo, d.tipo_documental, d.numero, d.data_documento, d.corpus_origem, d.status, "
           "d.caminho_relativo, d.paginas, n.situacao AS situacao_norma, "
           "(SELECT count(*) FROM trechos t WHERE t.documento_id = d.id) AS trechos "
           "FROM documentos d LEFT JOIN normas n ON n.documento_id = d.id WHERE d.status != 'REMOVIDO'")
    params = []
    if q.strip():
        sql += " AND (d.titulo LIKE ? OR d.caminho_relativo LIKE ? OR d.numero LIKE ?)"
        params += [f"%{q.strip()}%"] * 3
    if tipo:
        sql += " AND d.tipo_documental = ?"
        params.append(tipo)
    if origem:
        sql += " AND d.corpus_origem = ?"
        params.append(origem)
    sql += " ORDER BY d.data_documento DESC, d.id DESC LIMIT ?"
    params.append(min(max(limite, 1), 2000))
    conn = _conn()
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def _caminho_seguro(caminho: str) -> Path | None:
    """Arquivo existente e DENTRO da raiz documental (evita servir qualquer outro arquivo da máquina)."""
    p = Path(caminho).resolve()
    raiz = _servico().raiz
    return p if p.is_file() and p.is_relative_to(raiz) else None


@router.get("/documentos/{documento_id}/arquivo")
def arquivo(documento_id: int):
    conn = _conn()
    try:
        r = conn.execute("SELECT caminho FROM documentos WHERE id = ? AND status != 'REMOVIDO'",
                         (documento_id,)).fetchone()
    finally:
        conn.close()
    caminho = _caminho_seguro(r[0]) if r else None
    if caminho is None:
        raise HTTPException(404, "O arquivo original não está disponível no acervo.")
    media = mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
    if media.startswith("text/"):
        media += "; charset=utf-8" if caminho.suffix.lower() in (".txt", ".md", ".csv") else ""
    return FileResponse(caminho, media_type=media, filename=caminho.name, content_disposition_type="inline",
                        headers=CABECALHOS_ARQUIVO)


@router.get("/trechos/{trecho_id}")
def obter_trecho(trecho_id: int):
    conn = _conn()
    try:
        r = conn.execute("SELECT t.id, t.documento_id, t.texto, t.pagina, t.dispositivo, t.revogado, d.titulo, "
                         "d.caminho_relativo, d.tipo_documental, d.data_documento, d.corpus_origem, "
                         "n.situacao AS situacao_norma FROM trechos t JOIN documentos d ON d.id = t.documento_id "
                         "LEFT JOIN normas n ON n.documento_id = d.id WHERE t.id = ?", (trecho_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        raise HTTPException(404, "Trecho não encontrado.")
    return dict(r)


@router.get("/busca")
def busca(q: str, modo: str = "bm25", k: int = 10):
    """Busca de trechos: bm25 (instantânea) ou hibrido_rerank (carrega os modelos na primeira chamada)."""
    from app.application.recuperacao.hibrida import MODOS, RecuperadorHibrido
    from app.infrastructure.sqlite.busca import BuscaLexicalSqlite, RepositorioTrechosSqlite

    if len(q.strip()) < 2:
        raise HTTPException(422, "Informe o texto da busca.")
    if modo not in MODOS:
        raise HTTPException(422, f"Modo inválido; use um de {', '.join(MODOS)}.")

    def fabrica():
        return conectar(settings.database_path)

    embedder = vetores = reranker = None
    if modo != "bm25":
        from app.infrastructure.modelos import compartilhados
        from app.infrastructure.sqlite.vetores import SqliteVecStore

        embedder, vetores, reranker = compartilhados.embedder(), SqliteVecStore(fabrica), compartilhados.reranker()
    rec = RecuperadorHibrido(BuscaLexicalSqlite(fabrica), RepositorioTrechosSqlite(fabrica), embedder, vetores,
                             reranker)
    r = rec.recuperar(q, k=min(max(k, 1), 30), modo=modo, incluir_historico=True)
    return {"termos": r.termos, "tempos_ms": r.tempos_ms, "resultados": [
        {"trecho_id": t.id, "documento_id": t.documento_id, "titulo": t.titulo, "arquivo": t.caminho_relativo,
         "dispositivo": t.dispositivo, "pagina": t.pagina, "texto": t.texto[:500], "pontuacao": round(t.pontuacao, 4),
         "revogado": t.revogado, "situacao_norma": t.situacao_norma} for t in r.trechos + r.historico]}


def _nome_seguro(nome: str) -> str:
    base = Path(nome or "documento").name
    base = re.sub(r"[^\w.\- ()]+", "_", base, flags=re.UNICODE).strip(" .") or "documento"
    return base[:120]


@router.post("/documentos", status_code=202)
async def enviar(request: Request, arquivo: UploadFile = File(...), user=Depends(require_gestor)):  # noqa: B008
    from app.infrastructure.extratores.adaptador import extensoes_suportadas

    nome = _nome_seguro(arquivo.filename)
    extensao = Path(nome).suffix.lower()
    if extensao not in extensoes_suportadas():
        raise HTTPException(415, f"Formato não suportado ({extensao or 'sem extensão'}).")
    dados = await arquivo.read(MAX_UPLOAD + 1)
    if len(dados) > MAX_UPLOAD:
        raise HTTPException(413, "Arquivo maior que 25 MB.")
    if not dados:
        raise HTTPException(422, "Arquivo vazio.")
    servico = _servico()
    if servico.estado["executando"]:
        raise HTTPException(409, "Já há uma indexação em andamento. Aguarde a conclusão e envie novamente.")
    pasta = servico.raiz / "enviados" / date.today().isoformat()
    pasta.mkdir(parents=True, exist_ok=True)
    destino, n = pasta / nome, 1
    while destino.exists():  # nunca sobrescreve um documento existente
        destino = pasta / f"{Path(nome).stem} ({n}){extensao}"
        n += 1
    destino.write_bytes(dados)
    relativo = destino.relative_to(servico.raiz).as_posix()
    _auditar(user, "enviar_documento", relativo, request)
    servico.iniciar([relativo])
    return {"arquivo": relativo, "tamanho": len(dados), "indexacao": servico.estado}


@router.post("/indexar", status_code=202)
def indexar(request: Request, user=Depends(require_admin)):  # noqa: B008
    servico = _servico()
    if not servico.iniciar(None):
        raise HTTPException(409, "Já há uma indexação em andamento.")
    _auditar(user, "indexar_acervo", str(servico.raiz), request)
    return servico.estado


@router.get("/indexacao")
def estado_indexacao():
    return _servico().estado
