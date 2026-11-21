"""Instalador do certificado HTTPS da STI: nome (inclusive curinga), validade e par de chaves."""
import datetime as dt
import importlib.util
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

SPEC = importlib.util.spec_from_file_location(
    "instalar_certificado", Path(__file__).resolve().parents[1] / "scripts" / "rede" / "instalar_certificado.py")
ic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ic)
AGORA = dt.datetime(2026, 11, 21, tzinfo=dt.UTC)


def certificado(nomes, inicio=AGORA - dt.timedelta(days=1), fim=AGORA + dt.timedelta(days=365), chave=None):
    chave = chave or ec.generate_private_key(ec.SECP256R1())
    sujeito = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nomes[0])])
    cert = (x509.CertificateBuilder().subject_name(sujeito).issuer_name(sujeito).public_key(chave.public_key())
            .serial_number(1).not_valid_before(inicio).not_valid_after(fim)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in nomes]), critical=False)
            .sign(chave, hashes.SHA256()))
    return cert, chave


def test_certificado_do_endereco_e_aceito_e_gravado_sem_vazar_a_chave(tmp_path):
    cert, chave = certificado(["sistemasad.sema.mt.gov.br"])
    assert ic.validar(cert, chave, "sistemasad.sema.mt.gov.br", AGORA) == []
    arq_cert, arq_chave = ic.gravar(cert, chave, [], tmp_path)
    assert b"BEGIN CERTIFICATE" in arq_cert.read_bytes() and b"PRIVATE KEY" in arq_chave.read_bytes()
    assert "PRIVATE" not in ic.resumo(cert)


def test_curinga_cobre_um_nivel_so():
    cert, chave = certificado(["*.sema.mt.gov.br"])
    assert ic.validar(cert, chave, "sistemasad.sema.mt.gov.br", AGORA) == []
    assert ic.validar(cert, chave, "a.b.sema.mt.gov.br", AGORA)


def test_outro_nome_vencido_ou_chave_trocada_sao_recusados():
    cert, chave = certificado(["outro.sema.mt.gov.br"])
    assert "não cobre" in ic.validar(cert, chave, "sistemasad.sema.mt.gov.br", AGORA)[0]
    vencido, chave_v = certificado(["sistemasad.sema.mt.gov.br"], fim=AGORA - dt.timedelta(days=1),
                                   inicio=AGORA - dt.timedelta(days=30))
    assert "vencido" in ic.validar(vencido, chave_v, "sistemasad.sema.mt.gov.br", AGORA)[0]
    bom, _ = certificado(["sistemasad.sema.mt.gov.br"])
    outra = ec.generate_private_key(ec.SECP256R1())
    assert "não corresponde" in ic.validar(bom, outra, "sistemasad.sema.mt.gov.br", AGORA)[0]
