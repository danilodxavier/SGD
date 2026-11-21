"""Instala o certificado HTTPS fornecido pela STI para o endereço interno do SAD-GD.

Aceita .pfx/.p12 (com senha) ou o par .crt/.cer/.pem + .key. Valida antes de instalar: o nome do endereço consta do
certificado (SAN/CN), a data de validade e que a chave privada corresponde ao certificado. Grava em
ferramentas\\certificados\\ (fora do Git) os arquivos PEM que o servidor usa (SSL_CERTFILE/SSL_KEYFILE) e imprime só
metadados do certificado — nunca a chave.

Uso:
  python scripts/rede/instalar_certificado.py --pfx C:\\caminho\\sistemasad.pfx       (pede a senha)
  python scripts/rede/instalar_certificado.py --crt arquivo.crt --key arquivo.key [--cadeia cadeia.crt]
  python scripts/rede/instalar_certificado.py --verificar                              (confere o instalado)
"""
import argparse
import datetime as dt
import getpass
import os
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtensionOID, NameOID

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "ferramentas" / "certificados"
NOME_PADRAO = "sistemasad.sema.mt.gov.br"


def nomes_do_certificado(cert: x509.Certificate) -> list[str]:
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        nomes = san.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        nomes = []
    cn = [a.value for a in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)]
    return list(dict.fromkeys([*nomes, *cn]))


def cobre(nome: str, padrao: str) -> bool:
    """Nome coberto pelo certificado, inclusive curinga de um nível (*.sema.mt.gov.br)."""
    nome, padrao = nome.lower(), padrao.lower()
    if padrao.startswith("*."):
        return nome.count(".") == padrao.count(".") and nome.endswith(padrao[1:])
    return nome == padrao


def validar(cert, chave, nome, agora=None) -> list[str]:
    problemas = []
    agora = agora or dt.datetime.now(dt.UTC)
    nomes = nomes_do_certificado(cert)
    if not any(cobre(nome, n) for n in nomes):
        problemas.append(f"o certificado não cobre {nome} (nomes: {', '.join(nomes) or 'nenhum'})")
    if agora < cert.not_valid_before_utc:
        problemas.append(f"certificado ainda não é válido (a partir de {cert.not_valid_before_utc:%d/%m/%Y})")
    if agora > cert.not_valid_after_utc:
        problemas.append(f"certificado vencido em {cert.not_valid_after_utc:%d/%m/%Y}")
    publica = serialization.PublicFormat.SubjectPublicKeyInfo
    if chave.public_key().public_bytes(serialization.Encoding.PEM, publica) != \
            cert.public_key().public_bytes(serialization.Encoding.PEM, publica):
        problemas.append("a chave privada não corresponde ao certificado")
    return problemas


def resumo(cert) -> str:
    emissor = ", ".join(a.value for a in cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)) or "?"
    return (f"nomes: {', '.join(nomes_do_certificado(cert))} | emissor: {emissor} | válido de "
            f"{cert.not_valid_before_utc:%d/%m/%Y} a {cert.not_valid_after_utc:%d/%m/%Y}")


def gravar(cert, chave, cadeia, destino: Path) -> tuple[Path, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    arq_cert, arq_chave = destino / "sistemasad.crt", destino / "sistemasad.key"
    pem = cert.public_bytes(serialization.Encoding.PEM) + b"".join(
        c.public_bytes(serialization.Encoding.PEM) for c in cadeia)  # cadeia completa: navegadores exigem
    arq_cert.write_bytes(pem)
    arq_chave.write_bytes(chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    try:  # restringe a chave ao usuário atual (Windows)
        os.system(f'icacls "{arq_chave}" /inheritance:r /grant:r "%USERNAME%:R" >nul 2>&1')  # noqa: S605
    except OSError:
        pass
    return arq_cert, arq_chave


def carregar(a):
    if a.pfx:
        senha = os.environ.get("SADGD_PFX_SENHA") or getpass.getpass("Senha do arquivo .pfx: ")
        chave, cert, cadeia = pkcs12.load_key_and_certificates(Path(a.pfx).read_bytes(), senha.encode() or None)
        return cert, chave, list(cadeia or [])
    certs = x509.load_pem_x509_certificates(Path(a.crt).read_bytes())
    cadeia = certs[1:] + (x509.load_pem_x509_certificates(Path(a.cadeia).read_bytes()) if a.cadeia else [])
    chave = serialization.load_pem_private_key(Path(a.key).read_bytes(), password=None)
    return certs[0], chave, cadeia


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pfx")
    p.add_argument("--crt")
    p.add_argument("--key")
    p.add_argument("--cadeia", help="certificados intermediários/raiz da autoridade (PEM)")
    p.add_argument("--nome", default=NOME_PADRAO)
    p.add_argument("--verificar", action="store_true")
    a = p.parse_args()
    if a.verificar:
        arq_cert, arq_chave = DESTINO / "sistemasad.crt", DESTINO / "sistemasad.key"
        if not (arq_cert.is_file() and arq_chave.is_file()):
            print("[ERRO] Nenhum certificado instalado em ferramentas\\certificados\\.")
            return 1
        cert = x509.load_pem_x509_certificates(arq_cert.read_bytes())[0]
        chave = serialization.load_pem_private_key(arq_chave.read_bytes(), password=None)
    else:
        if not (a.pfx or (a.crt and a.key)):
            p.error("informe --pfx ou --crt e --key")
        cert, chave, cadeia = carregar(a)
    problemas = validar(cert, chave, a.nome)
    print("[INFO]", resumo(cert))
    if problemas:
        print("[ERRO] " + "; ".join(problemas))
        return 1
    if a.verificar:
        print("[OK] Certificado instalado é válido para", a.nome)
        return 0
    arq_cert, arq_chave = gravar(cert, chave, cadeia, DESTINO)
    print(f"[OK] Instalado: {arq_cert.relative_to(RAIZ)} e {arq_chave.relative_to(RAIZ)} "
          f"(cadeia: {len(cadeia)} certificado(s)). Próximo passo: scripts\\rede\\publicar_rede.ps1 -Acao publicar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
