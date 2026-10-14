"""Proteções aplicadas a todas as requisições do painel.

1. Origem: só atende computadores das faixas em ALLOWED_CLIENTS (o próprio computador sempre é aceito).
2. Nome de acesso (cabeçalho Host): só os nomes deste computador e os de ALLOWED_HOSTS (evita DNS rebinding).
3. Operações que alteram dados exigem o cabeçalho X-Requested-With do painel (impede ataques vindos de outros sites).
4. Sessão: identifica o usuário pelo cookie de sessão (a exigência de login fica nas rotas — ver app/api/deps.py).
"""
import ipaddress
import socket
from functools import lru_cache
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core import auth
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("security")

CLIENT_HEADER = "AgenteDocumental"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ADMIN_ONLY_PATHS = ("/api/docs", "/api/openapi.json")  # documentação técnica da API


@lru_cache(maxsize=1)
def local_names():
    """Nomes e endereços pelos quais este computador pode ser acessado."""
    names = {"127.0.0.1", "localhost", "::1"}
    try:
        hostname = socket.gethostname()
        names |= {hostname.lower(), socket.getfqdn().lower()}
        names |= {ip.lower() for ip in socket.gethostbyname_ex(hostname)[2]}
        names |= {info[4][0].lower() for info in socket.getaddrinfo(hostname, None)}
    except OSError:
        pass
    return names


def allowed_hosts():
    hosts = local_names() | set(settings.allowed_hosts)
    if settings.app_host not in ("0.0.0.0", "::"):
        hosts.add(settings.app_host.lower())
    return hosts


@lru_cache(maxsize=64)
def _networks(spec):
    nets = []
    for item in spec:
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            log.warning("Faixa inválida em ALLOWED_CLIENTS ignorada: %s", item)
    return nets


def is_loopback(ip):
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def client_allowed(ip):
    if is_loopback(ip):
        return True
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in net for net in _networks(tuple(settings.allowed_clients)))


def _host_of(request):
    host = request.headers.get("host", "")
    if host.startswith("["):  # IPv6 entre colchetes
        return host[1:host.find("]")].lower()
    return host.rsplit(":", 1)[0].lower() if host.count(":") == 1 else host.lower()


class NetworkGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ip = request.client.host if request.client else ""
        if not client_allowed(ip):
            log.warning("Acesso recusado: computador fora das faixas autorizadas (%s)", ip)
            return JSONResponse({"detail": "Este computador não está autorizado a acessar o sistema."},
                                status_code=403)
        if _host_of(request) not in allowed_hosts():
            return JSONResponse({"detail": "Endereço de acesso não reconhecido. Use o endereço informado pelo "
                                           "administrador do sistema."}, status_code=403)
        if request.method not in SAFE_METHODS and request.headers.get("x-requested-with") != CLIENT_HEADER:
            return JSONResponse({"detail": "Requisição não autorizada."}, status_code=403)

        request.state.is_local = is_loopback(ip)
        request.state.client_ip = ip
        request.state.token = request.cookies.get(auth.COOKIE_NAME)
        request.state.user = auth.user_for_token(request.state.token)
        if request.url.path.startswith(ADMIN_ONLY_PATHS) and not (request.state.user or {}).get("is_admin"):
            return JSONResponse({"detail": "Restrito a administradores."}, status_code=403)
        return await call_next(request)


def is_within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False
