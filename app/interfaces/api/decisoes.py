"""SAD-082 — API da memória de decisões (RF-19): registrar decisões da gestão, atualizar o resultado, listar e
consultar precedentes. Registrar/atualizar exige perfil Administrador (o perfil Gestor chega na Fase 9, RF-23);
toda escrita vai para a trilha de auditoria."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.api.deps import require_admin, require_login
from app.core.config import settings
from app.domain.decisoes import AvaliacaoResultado, Decisao
from app.infrastructure.sqlite.conexao import conectar
from app.infrastructure.sqlite.repositorio_decisoes import RepositorioDecisoesSqlite

router = APIRouter(prefix="/api/sadgd", dependencies=[Depends(require_login)], tags=["SAD-GD"])


class NovaDecisao(BaseModel):
    titulo: str = Field(min_length=5, max_length=300)
    decisao: str = Field(min_length=5, max_length=4000)
    data: date
    contexto: str = Field("", max_length=4000)
    fundamentos: str = Field("", max_length=4000)
    resultado: str = Field("", max_length=4000)
    avaliacao_resultado: AvaliacaoResultado = AvaliacaoResultado.PENDENTE
    codigo: str | None = Field(None, max_length=60)
    processo_id: int | None = None
    consulta_id: int | None = None
    documento_ids: list[int] = Field(default_factory=list, max_length=50)
    trecho_ids: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("titulo", "decisao")
    @classmethod
    def sem_branco(cls, v):
        if not v.strip():
            raise ValueError("campo obrigatório")
        return v.strip()


class Resultado(BaseModel):
    resultado: str = Field(min_length=3, max_length=4000)
    avaliacao_resultado: AvaliacaoResultado


def _repo():
    return RepositorioDecisoesSqlite(lambda: conectar(settings.database_path))


def _auditar(user, acao, alvo, request):
    conn = conectar(settings.database_path, vetores=False)
    try:
        conn.execute("INSERT INTO auditoria (usuario_id, acao, alvo, ip, criado_em) VALUES (?, ?, ?, ?, ?)",
                     (user["id"], acao, alvo, request.client.host if request.client else None,
                      datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def _saida(d: Decisao):
    return {"id": d.id, "codigo": d.codigo, "titulo": d.titulo, "data": d.data, "contexto": d.contexto,
            "decisao": d.decisao, "fundamentos": d.fundamentos, "resultado": d.resultado,
            "avaliacao_resultado": d.avaliacao_resultado.value, "processo_id": d.processo_id,
            "corpus_origem": d.corpus_origem, "documento_ids": d.documento_ids}


@router.get("/decisoes")
def listar(processo_id: int | None = None, limite: int = 200):
    return [_saida(d) for d in _repo().listar(processo_id, min(max(limite, 1), 1000))]


@router.post("/decisoes", status_code=201)
def registrar(corpo: NovaDecisao, request: Request, user=Depends(require_admin)):
    from app.interfaces.api.perguntar import memoria_decisoes

    d = Decisao(titulo=corpo.titulo, decisao=corpo.decisao, data=corpo.data.isoformat(), contexto=corpo.contexto,
                fundamentos=corpo.fundamentos, resultado=corpo.resultado,
                avaliacao_resultado=corpo.avaliacao_resultado, codigo=corpo.codigo, processo_id=corpo.processo_id,
                consulta_id=corpo.consulta_id, decisor_perfil=user.get("profile_label"), corpus_origem="real")
    decisao_id = memoria_decisoes().registrar(d, corpo.documento_ids, corpo.trecho_ids)
    _auditar(user, "registrar_decisao", f"decisao:{decisao_id}", request)
    return _saida(_repo().obter([decisao_id])[0])


@router.patch("/decisoes/{decisao_id}/resultado")
def atualizar_resultado(decisao_id: int, corpo: Resultado, request: Request, user=Depends(require_admin)):
    if not _repo().atualizar_resultado(decisao_id, corpo.resultado, corpo.avaliacao_resultado.value):
        raise HTTPException(404, "Decisão não encontrada.")
    _auditar(user, "avaliar_resultado_decisao", f"decisao:{decisao_id}", request)
    return _saida(_repo().obter([decisao_id])[0])


@router.get("/precedentes")
def precedentes(pergunta: str, k: int = 3):
    from app.interfaces.api.perguntar import memoria_decisoes

    if len(pergunta.strip()) < 3:
        raise HTTPException(422, "Informe a pergunta.")
    return [p.resumo() for p in memoria_decisoes().precedentes(pergunta, k=min(max(k, 1), 10))]
