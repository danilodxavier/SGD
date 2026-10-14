"""Exigências de acesso usadas pelas rotas (login, perfil de administrador, uso no próprio computador)."""
from fastapi import HTTPException, Request

LOGIN_REQUIRED = "Sua sessão expirou ou você não está conectado. Faça login para continuar."
PASSWORD_CHANGE = "Troque sua senha temporária para continuar."
ADMIN_REQUIRED = "Esta função é restrita a administradores."
LOCAL_REQUIRED = "Esta função só pode ser usada no computador onde o sistema está instalado."


def require_login(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, LOGIN_REQUIRED)
    if user["must_change_password"]:
        raise HTTPException(403, PASSWORD_CHANGE)
    return user


def require_admin(request: Request):
    user = require_login(request)
    if not user["is_admin"]:
        raise HTTPException(403, ADMIN_REQUIRED)
    return user


def require_local(request: Request):
    if not getattr(request.state, "is_local", False):
        raise HTTPException(403, LOCAL_REQUIRED)
