"""Login, sessão, configuração inicial, troca de senha e gestão de usuários."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import __version__
from app.api.deps import LOCAL_REQUIRED, LOGIN_REQUIRED, require_admin
from app.core import auth
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter()
log = get_logger("api.auth")


class LoginIn(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=200)


class SetupIn(BaseModel):
    username: str = Field(..., max_length=50)
    name: str = Field(..., max_length=120)
    password: str = Field(..., max_length=200)


class PasswordIn(BaseModel):
    current_password: str = Field(..., max_length=200)
    new_password: str = Field(..., max_length=200)


class UserIn(BaseModel):
    username: str = Field(..., max_length=50)
    name: str = Field(..., max_length=120)
    profile: str
    password: str = Field(..., max_length=200)


class UserUpdateIn(BaseModel):
    name: str | None = Field(None, max_length=120)
    profile: str | None = None
    active: bool | None = None


class ResetIn(BaseModel):
    password: str = Field(..., max_length=200)


def _start_session(request, response, user):
    token = auth.create_session(user["id"], request.state.client_ip)
    response.set_cookie(auth.COOKIE_NAME, token, max_age=settings.session_hours * 3600, httponly=True,
                        samesite="strict", secure=settings.https, path="/")
    return user


def _bad_request(exc):
    return HTTPException(400, str(exc))


@router.get("/api/auth/status")
def status(request: Request):
    """Situação para o painel decidir qual tela mostrar (login, configuração inicial ou sistema)."""
    return {
        "version": __version__,
        "setup_required": auth.count_users() == 0,
        "is_local": request.state.is_local,
        "network_mode": settings.network_mode,
        "https": settings.https,
        "user": request.state.user,
    }


@router.post("/api/auth/setup")
def setup(body: SetupIn, request: Request, response: Response):
    """Cria o primeiro administrador. Só funciona sem usuários cadastrados e no próprio computador."""
    if auth.count_users() > 0:
        raise HTTPException(409, "O sistema já foi configurado. Faça login.")
    if not request.state.is_local:
        raise HTTPException(403, LOCAL_REQUIRED)
    try:
        user = auth.create_user(body.username, body.name, "admin", body.password, must_change_password=False)
    except auth.AuthError as exc:
        raise _bad_request(exc)
    log.info("Configuração inicial: administrador %s criado", user["username"])
    return _start_session(request, response, user)


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    try:
        user = auth.authenticate(body.username, body.password, request.state.client_ip)
    except auth.AuthError as exc:
        raise HTTPException(401, str(exc))
    return _start_session(request, response, user)


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.end_session(request.state.token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    if request.state.user:
        log.info("Logout: %s", request.state.user["username"])
    return {"ok": True}


@router.post("/api/auth/password")
def change_password(body: PasswordIn, request: Request):
    """Troca a própria senha (permitido também durante a troca obrigatória)."""
    user = request.state.user
    if not user:
        raise HTTPException(401, LOGIN_REQUIRED)
    try:
        return auth.change_own_password(user["id"], body.current_password, body.new_password)
    except auth.AuthError as exc:
        raise _bad_request(exc)


# ---------------------------------------------------------------- usuários (administradores)

@router.get("/api/users")
def list_users(_admin=Depends(require_admin)):
    return {"users": auth.list_users(), "profiles": auth.PROFILES}


@router.post("/api/users")
def create_user(body: UserIn, admin=Depends(require_admin)):
    try:
        user = auth.create_user(body.username, body.name, body.profile, body.password, must_change_password=True)
    except auth.AuthError as exc:
        raise _bad_request(exc)
    log.info("Usuário %s criado por %s", user["username"], admin["username"])
    return user


@router.put("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdateIn, admin=Depends(require_admin)):
    try:
        user = auth.update_user(user_id, body.name, body.profile, body.active)
    except auth.AuthError as exc:
        raise _bad_request(exc)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado.")
    log.info("Usuário %s alterado por %s", user["username"], admin["username"])
    return user


@router.post("/api/users/{user_id}/password")
def reset_password(user_id: int, body: ResetIn, admin=Depends(require_admin)):
    """Define uma senha temporária; o usuário deverá trocá-la no próximo acesso."""
    try:
        user = auth.set_password(user_id, body.password, must_change_password=True)
    except auth.AuthError as exc:
        raise _bad_request(exc)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado.")
    log.info("Senha de %s redefinida por %s", user["username"], admin["username"])
    return user


@router.post("/api/users/{user_id}/unlock")
def unlock_user(user_id: int, admin=Depends(require_admin)):
    user = auth.unlock(user_id)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado.")
    log.info("Usuário %s desbloqueado por %s", user["username"], admin["username"])
    return user
