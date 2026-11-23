"""Gera um certificado HTTPS autoassinado para uso SÓ nesta estação (enquanto a STI não fornece o oficial).

Cria em ferramentas\\certificados\\ (fora do Git) `local.crt` e `local.key` para os nomes informados e, com
`--confiar`, instala o certificado em "Autoridades de Certificação Raiz Confiáveis" do computador (exige administrador),
para o Edge/Chrome abrirem https://<nome>/ sem aviso. Outros computadores continuam vendo o aviso — para a rede, usar o
certificado da STI (`instalar_certificado.py`). Imprime só metadados (nunca a chave).

Uso:
  python scripts/rede/gerar_certificado_local.py --confiar
  python scripts/rede/gerar_certificado_local.py --nomes sad.sema.mt.gov.br sistemasad.sema.mt.gov.br --dias 365
Reverter: Remove-Item Cert:\\LocalMachine\\Root\\<impressão digital impressa> e apagar os dois arquivos.
"""
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "ferramentas" / "certificados"
NOMES_PADRAO = ["sad.sema.mt.gov.br", "sistemasad.sema.mt.gov.br"]


def gerar(nomes, dias=365, agora=None):
    """Devolve (certificado, chave) autoassinados, válidos para `nomes` (SAN) e só para servidor TLS."""
    agora = agora or dt.datetime.now(dt.timezone.utc)
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sujeito = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nomes[0]),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SAD-GD (certificado local)")])
    cert = (x509.CertificateBuilder().subject_name(sujeito).issuer_name(sujeito).public_key(chave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(agora - dt.timedelta(minutes=5)).not_valid_after(agora + dt.timedelta(days=dias))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in nomes]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True, content_commitment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(chave, hashes.SHA256()))
    return cert, chave


def gravar(cert, chave, destino=DESTINO):
    destino.mkdir(parents=True, exist_ok=True)
    arq_cert, arq_chave = destino / "local.crt", destino / "local.key"
    arq_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    arq_chave.write_bytes(chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                              serialization.NoEncryption()))
    return arq_cert, arq_chave


def confiar(arq_cert):
    cmd = f"Import-Certificate -FilePath '{arq_cert}' -CertStoreLocation Cert:\\LocalMachine\\Root | Out-Null"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nomes", nargs="+", default=NOMES_PADRAO)
    p.add_argument("--dias", type=int, default=365)
    p.add_argument("--confiar", action="store_true", help="instala na raiz confiável do computador (administrador)")
    a = p.parse_args()
    cert, chave = gerar(a.nomes, a.dias)
    arq_cert, arq_chave = gravar(cert, chave)
    print(f"[OK] Certificado local para {', '.join(a.nomes)} — válido até {cert.not_valid_after_utc:%d/%m/%Y}")
    print(f"     impressão digital SHA-1: {cert.fingerprint(hashes.SHA1()).hex().upper()}")
    print(f"     .env: SSL_CERTFILE={arq_cert}")
    print(f"           SSL_KEYFILE={arq_chave}")
    if a.confiar:
        ok, erro = confiar(arq_cert)
        print("[OK] Instalado na raiz confiável deste computador." if ok else f"[ERRO] Não instalado: {erro}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
