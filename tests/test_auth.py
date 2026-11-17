"""Controle de acesso: login, perfis, senhas, bloqueio, acesso pela rede e ferramentas de linha de comando."""
import os
import subprocess
import sys
import zipfile

import pytest

from app.core import auth
from app.core.config import BASE_DIR, settings
from app.core.database import get_conn
from tests.helpers import HEADERS, PASSWORD, anonymous_client, ensure_user, logged_client

REMOTE = "192.168.10.20"


# ---------------------------------------------------------------- configuração inicial

def test_configuracao_inicial_somente_local_e_uma_vez(db):
    body = {"username": "maria.silva", "name": "Maria Silva", "password": "Contratos2026"}
    with anonymous_client(REMOTE) as remote:
        assert remote.get("/api/auth/status").json()["setup_required"] is True
        assert remote.post("/api/auth/setup", json=body, headers=HEADERS).status_code == 403
    with anonymous_client() as local:
        r = local.post("/api/auth/setup", json=body, headers=HEADERS)
        assert r.status_code == 200 and r.json()["profile"] == "admin"
        assert local.get("/api/sadgd/painel").status_code == 200  # já entra conectado
        assert local.post("/api/auth/setup", json=body, headers=HEADERS).status_code == 409


def test_senha_guardada_apenas_como_hash(db):
    ensure_user("ana.souza", "consulta")
    with get_conn() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE username = 'ana.souza'").fetchone()[0]
    assert PASSWORD not in stored and stored.startswith("pbkdf2_sha256$")


@pytest.mark.parametrize("password, message", [
    ("curta1", "pelo menos 8"), ("somenteletras", "letras e números"), ("12345678", "letras e números"),
    ("joao.lima1", "igual ao nome"),
])
def test_politica_de_senha(db, password, message):
    with pytest.raises(auth.AuthError, match=message):
        auth.create_user("joao.lima1", "João", "consulta", password)


def test_usuario_invalido(db):
    with pytest.raises(auth.AuthError, match="Usuário inválido"):
        auth.create_user("João Lima", "João", "consulta", "Senha1234")


# ---------------------------------------------------------------- login, sessão e senha

def test_sem_login_nada_e_acessivel(db):
    with anonymous_client() as client:
        for path in ("/api/sadgd/documentos", "/api/sadgd/painel", "/api/sadgd/processos", "/api/sadgd/decisoes",
                     "/api/sadgd/busca?q=xx", "/api/sadgd/trechos/1", "/api/sadgd/documentos/1/arquivo"):
            assert client.get(path).status_code == 401, path
        r = client.post("/api/sadgd/perguntar", json={"pergunta": "Qual o valor?"}, headers=HEADERS)
        assert r.status_code == 401 and "Faça login" in r.json()["detail"]
        assert client.get("/health").status_code == 200  # saúde continua pública (sem dados)
        assert client.get("/").status_code == 200  # tela de login


def test_login_logout_e_mensagem_generica(db):
    ensure_user("ana.souza", "consulta")
    with anonymous_client() as client:
        wrong = client.post("/api/auth/login", json={"username": "ana.souza", "password": "errada123"}, headers=HEADERS)
        missing = client.post("/api/auth/login", json={"username": "ninguem", "password": "errada123"}, headers=HEADERS)
        assert wrong.status_code == missing.status_code == 401
        assert wrong.json()["detail"] == missing.json()["detail"] == "Usuário ou senha inválidos."
        ok = client.post("/api/auth/login", json={"username": "ANA.SOUZA", "password": PASSWORD}, headers=HEADERS)
        assert ok.status_code == 200
        cookie = ok.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert client.get("/api/sadgd/documentos").status_code == 200
        client.post("/api/auth/logout", headers=HEADERS)
        assert client.get("/api/sadgd/documentos").status_code == 401


def test_bloqueio_apos_tentativas_e_desbloqueio(db):
    ensure_user("ana.souza", "consulta")
    with anonymous_client() as client:
        for _ in range(auth.MAX_FAILURES):
            client.post("/api/auth/login", json={"username": "ana.souza", "password": "errada123"}, headers=HEADERS)
        r = client.post("/api/auth/login", json={"username": "ana.souza", "password": PASSWORD}, headers=HEADERS)
        assert r.status_code == 401 and "bloqueada" in r.json()["detail"]
    with logged_client() as admin:
        user_id = auth.get_user_by_username("ana.souza")["id"]
        assert admin.post(f"/api/users/{user_id}/unlock", headers=HEADERS).status_code == 200
    with logged_client("ana.souza", "consulta") as client:
        assert client.get("/api/sadgd/documentos").status_code == 200


def test_senha_temporaria_exige_troca(db):
    with logged_client() as admin:
        r = admin.post("/api/users", json={"username": "carlos.dias", "name": "Carlos Dias", "profile": "consulta",
                                           "password": "Temporaria1"}, headers=HEADERS)
        assert r.status_code == 200 and r.json()["must_change_password"] is True
    with anonymous_client() as client:
        client.post("/api/auth/login", json={"username": "carlos.dias", "password": "Temporaria1"}, headers=HEADERS)
        blocked = client.get("/api/sadgd/documentos")
        assert blocked.status_code == 403 and "Troque sua senha" in blocked.json()["detail"]
        bad = client.post("/api/auth/password", json={"current_password": "errada", "new_password": "NovaSenha9"},
                          headers=HEADERS)
        assert bad.status_code == 400 and "senha atual" in bad.json()["detail"]
        same = client.post("/api/auth/password", json={"current_password": "Temporaria1",
                                                       "new_password": "Temporaria1"}, headers=HEADERS)
        assert same.status_code == 400
        ok = client.post("/api/auth/password", json={"current_password": "Temporaria1",
                                                     "new_password": "NovaSenha9"}, headers=HEADERS)
        assert ok.status_code == 200 and ok.json()["must_change_password"] is False
        assert client.get("/api/sadgd/documentos").status_code == 200


def test_desativar_usuario_encerra_sessao(db):
    ensure_user("ana.souza", "consulta")
    with logged_client("ana.souza", "consulta") as client, logged_client() as admin:
        user_id = auth.get_user_by_username("ana.souza")["id"]
        assert admin.put(f"/api/users/{user_id}", json={"active": False}, headers=HEADERS).status_code == 200
        assert client.get("/api/sadgd/documentos").status_code == 401
        r = client.post("/api/auth/login", json={"username": "ana.souza", "password": PASSWORD}, headers=HEADERS)
        assert "desativado" in r.json()["detail"]


def test_ultimo_administrador_nao_pode_ser_removido(db):
    with logged_client() as admin:
        me = auth.get_user_by_username("admin.teste")
        r = admin.put(f"/api/users/{me['id']}", json={"profile": "consulta"}, headers=HEADERS)
        assert r.status_code == 400 and "último administrador" in r.json()["detail"]
        r = admin.put(f"/api/users/{me['id']}", json={"active": False}, headers=HEADERS)
        assert r.status_code == 400


# ---------------------------------------------------------------- perfis

ADMIN_ONLY = [
    ("get", "/api/config"), ("post", "/api/config"), ("post", "/api/sadgd/indexar"), ("get", "/api/logs"),
    ("get", "/api/diagnostics"), ("get", "/api/ocr"), ("post", "/api/ocr"),
    ("get", "/api/users"), ("post", "/api/users"), ("get", "/api/docs"),
]


@pytest.mark.parametrize("method, path", ADMIN_ONLY)
def test_perfil_consulta_nao_acessa_funcoes_administrativas(db, method, path):
    with logged_client("ana.souza", "consulta") as client:
        kwargs = {"headers": HEADERS, "json": {}} if method == "post" else {}
        assert getattr(client, method)(path, **kwargs).status_code == 403


def test_perfil_consulta_usa_o_sistema(db):
    with logged_client("ana.souza", "consulta") as client:
        for path in ("/api/sadgd/painel", "/api/sadgd/documentos", "/api/sadgd/processos", "/api/sadgd/decisoes",
                     "/api/sadgd/busca?q=contrato", "/api/sadgd/indexacao"):
            assert client.get(path).status_code == 200, path


# ---------------------------------------------------------------- acesso pela rede

def test_computador_remoto_da_rede_interna(db):
    with logged_client(client_ip=REMOTE) as remote:
        assert remote.get("/api/auth/status").json()["is_local"] is False
        assert remote.get("/api/sadgd/painel").status_code == 200  # consultar funciona pela rede
        r = remote.post("/api/config/browse", headers=HEADERS)  # abrir janelas no servidor: só no próprio computador
        assert r.status_code == 403 and "computador onde o sistema está instalado" in r.json()["detail"]
        assert remote.post("/api/system/shutdown", headers=HEADERS).status_code == 403


@pytest.mark.parametrize("ip, allowed", [("10.1.2.3", True), ("172.20.0.5", True), ("192.168.0.9", True),
                                         ("8.8.8.8", False), ("200.1.2.3", False)])
def test_faixas_de_rede_autorizadas(db, ip, allowed):
    with anonymous_client(ip) as client:
        assert (client.get("/health").status_code == 200) is allowed


def test_faixas_personalizadas(db, monkeypatch):
    monkeypatch.setattr(settings, "allowed_clients", ["10.20.0.0/16", "192.168.1.50"])
    with anonymous_client("10.20.5.5") as ok, anonymous_client("10.30.5.5") as no, \
            anonymous_client("192.168.1.51") as no2, anonymous_client("127.0.0.1") as local:
        assert ok.get("/health").status_code == 200
        assert no.get("/health").status_code == 403 and no2.get("/health").status_code == 403
        assert local.get("/health").status_code == 200  # o próprio computador é sempre aceito


def test_nome_de_acesso_desconhecido_e_recusado(db, monkeypatch):
    with anonymous_client(base_url="http://site-externo.com") as client:
        assert client.get("/health").status_code == 403
    monkeypatch.setattr(settings, "allowed_hosts", ["agente-documental.sema.mt.gov.br"])
    with anonymous_client(base_url="http://agente-documental.sema.mt.gov.br:8000") as client:
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------- linha de comando, backup e indexação

def _cli(script, tmp_path, *args):
    env = {**os.environ, "DATA_DIR": str(tmp_path / "data"), "DATABASE_PATH": str(tmp_path / "data" / "cli.db"),
           "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(BASE_DIR / "scripts" / script), *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, timeout=120)


def test_ferramenta_de_usuarios(tmp_path):
    assert "Nenhum usuário cadastrado" in _cli("usuarios.py", tmp_path, "listar").stdout
    r = _cli("usuarios.py", tmp_path, "criar", "--usuario", "maria.silva", "--nome", "Maria Silva", "--perfil",
             "admin", "--senha", "Contratos2026")
    assert "[OK]" in r.stdout, r.stdout + r.stderr
    assert "maria.silva" in _cli("usuarios.py", tmp_path, "listar").stdout
    r = _cli("usuarios.py", tmp_path, "redefinir-senha", "--usuario", "maria.silva", "--senha", "Provisoria9")
    assert "deverá ser trocada" in r.stdout
    assert "[OK]" in _cli("usuarios.py", tmp_path, "desbloquear", "--usuario", "maria.silva").stdout
    r = _cli("usuarios.py", tmp_path, "criar", "--usuario", "x", "--nome", "X", "--senha", "abc")
    assert r.returncode == 1 and "[ERRO]" in r.stdout


def test_backup_com_destino_retencao_e_restauracao(tmp_path):
    _cli("usuarios.py", tmp_path, "criar", "--usuario", "maria.silva", "--nome", "Maria", "--perfil", "admin",
         "--senha", "Contratos2026")
    dest = tmp_path / "BACKUP"
    for name in ("backup_20200101_000000.zip", "backup_20200102_000000.zip"):
        dest.mkdir(exist_ok=True)
        (dest / name).write_bytes(b"antigo")
    r = _cli("backup.py", tmp_path, "--destino", str(dest), "--manter", "2")
    assert r.returncode == 0, r.stdout + r.stderr
    backups = sorted(p.name for p in dest.glob("backup_*.zip"))
    assert len(backups) == 2 and "backup_20200101_000000.zip" not in backups
    newest = dest / backups[-1]
    assert "database/cli.db" in zipfile.ZipFile(newest).namelist()

    # apaga o usuário e restaura: ele volta, e o banco anterior fica guardado
    _cli("usuarios.py", tmp_path, "criar", "--usuario", "extra.user", "--nome", "Extra", "--senha", "Contratos2026")
    r = _cli("restaurar.py", tmp_path, "--arquivo", str(newest))
    assert r.returncode == 0, r.stdout + r.stderr
    users = _cli("usuarios.py", tmp_path, "listar").stdout
    assert "maria.silva" in users and "extra.user" not in users
    assert list((tmp_path / "data").glob("cli.db.antes_restauracao_*"))
    bad = tmp_path / "invalido.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("qualquer.txt", "x")
    assert "não é um backup válido" in _cli("restaurar.py", tmp_path, "--arquivo", str(bad)).stdout


def test_pastas_da_aplicacao_nunca_sao_indexadas(db, tmp_path):
    """Mesmo com a raiz documental contendo a pasta de dados do sistema, banco/relatórios não entram no acervo."""
    from app.infrastructure.servico_indexacao import ServicoIndexacao

    root = tmp_path
    (root / "contratos").mkdir()
    (root / "contratos" / "nota.txt").write_text("Contrato nº 001/2026", encoding="utf-8")
    reports = settings.data_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "relatorio.txt").write_text("Relatório gerado pelo sistema", encoding="utf-8")
    servico = ServicoIndexacao(root, com_embeddings=False)
    servico.iniciar(None)
    estado = servico.aguardar(60)
    assert estado["erro"] is None
    with get_conn() as conn:
        nomes = {r[0] for r in conn.execute("SELECT caminho_relativo FROM documentos")}
    assert nomes == {"contratos/nota.txt"} and estado["resumo"]["encontrados"] == 1
