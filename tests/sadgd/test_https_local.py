"""HTTPS local: certificado autoassinado e servidor em duas portas (http em APP_PORT + https em HTTPS_PORT)."""
import importlib.util
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from app.core.config import settings

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("gerar_cert", RAIZ / "scripts" / "rede" / "gerar_certificado_local.py")
gerar_cert = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gerar_cert)


def test_certificado_cobre_os_nomes_e_so_serve_para_servidor(tmp_path):
    cert, chave = gerar_cert.gerar(["sad.exemplo.gov.br", "outro.exemplo.gov.br"], dias=30)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.DNSName) == ["sad.exemplo.gov.br", "outro.exemplo.gov.br"]
    assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False
    assert ExtendedKeyUsageOID.SERVER_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    arq_cert, arq_chave = gerar_cert.gravar(cert, chave, tmp_path)
    assert arq_cert.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert b"PRIVATE KEY" in arq_chave.read_bytes()


def _servidores(monkeypatch, cert, chave, https_port):
    from app.__main__ import criar_servidores

    monkeypatch.setattr(settings, "ssl_certfile", cert)
    monkeypatch.setattr(settings, "ssl_keyfile", chave)
    monkeypatch.setattr(settings, "https_port", https_port)
    return criar_servidores(object())


def test_https_port_cria_segundo_servidor_sem_lifespan(monkeypatch):
    s = _servidores(monkeypatch, "c.pem", "k.pem", 443)
    assert len(s) == 2
    assert s[0].config.port == settings.app_port and s[0].config.ssl_certfile is None  # :8000 continua http
    assert s[1].config.port == 443 and s[1].config.ssl_certfile == "c.pem" and s[1].config.lifespan == "off"


def test_sem_https_port_mantem_um_servidor(monkeypatch):
    assert len(_servidores(monkeypatch, "", "", 0)) == 1
    s = _servidores(monkeypatch, "c.pem", "k.pem", 0)  # comportamento anterior: APP_PORT com certificado
    assert len(s) == 1 and s[0].config.ssl_certfile == "c.pem"


def test_cookie_de_sessao_segue_o_protocolo_do_acesso():
    from types import SimpleNamespace

    from fastapi import Response

    from app.api import routes_auth

    def cookie(scheme):
        resp = Response()
        req = SimpleNamespace(url=SimpleNamespace(scheme=scheme), state=SimpleNamespace(client_ip="127.0.0.1"))
        orig = routes_auth.auth.create_session
        routes_auth.auth.create_session = lambda *a: "tok"
        try:
            routes_auth._start_session(req, resp, {"id": 1})
        finally:
            routes_auth.auth.create_session = orig
        return resp.headers["set-cookie"].lower()

    assert "secure" not in cookie("http")  # login por http://...:8000 continua funcionando com HTTPS ligado
    assert "secure" in cookie("https")
