"""Auxiliares dos testes de API: cliente já autenticado, local ou simulando outro computador da rede."""
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.core import auth
from app.main import create_app

HEADERS = {"X-Requested-With": "AgenteDocumental"}
PASSWORD = "Senha1234"


def ensure_user(username, profile, password=PASSWORD):
    if auth.get_user_by_username(username) is None:
        auth.create_user(username, f"Teste {username}", profile, password, must_change_password=False)


@contextmanager
def anonymous_client(client_ip="127.0.0.1", base_url="http://127.0.0.1:8000"):
    with TestClient(create_app(auto_index=False), base_url=base_url, client=(client_ip, 50000)) as client:
        yield client


@contextmanager
def logged_client(username="admin.teste", profile="admin", client_ip="127.0.0.1"):
    ensure_user(username, profile)
    with anonymous_client(client_ip) as client:
        r = client.post("/api/auth/login", json={"username": username, "password": PASSWORD}, headers=HEADERS)
        assert r.status_code == 200, r.text
        yield client
