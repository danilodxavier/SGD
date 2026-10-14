"""Gestão de usuários pela linha de comando (no computador onde o sistema está instalado).

Serve principalmente para recuperar o acesso quando nenhum administrador consegue entrar.

    python scripts\\usuarios.py listar
    python scripts\\usuarios.py criar --usuario maria.silva --nome "Maria Silva" --perfil admin
    python scripts\\usuarios.py redefinir-senha --usuario maria.silva
    python scripts\\usuarios.py desbloquear --usuario maria.silva
    python scripts\\usuarios.py ativar --usuario maria.silva

A senha é digitada sem aparecer na tela. A opção --senha existe para automação, mas a senha fica no
histórico do terminal: evite usá-la.
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import auth  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402


def _ask_password(given):
    if given:
        return given
    first = getpass.getpass("Nova senha (não aparece na tela): ")
    second = getpass.getpass("Repita a nova senha: ")
    if first != second:
        raise auth.AuthError("As senhas digitadas não conferem.")
    return first


def _find(username):
    user = auth.get_user_by_username(username)
    if user is None:
        raise auth.AuthError(f"Usuário “{username}” não encontrado. Use o comando listar.")
    return user


def main():
    parser = argparse.ArgumentParser(description="Gestão de usuários do Agente de Inteligência Documental.")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("listar", help="lista os usuários")
    criar = sub.add_parser("criar", help="cria um usuário")
    criar.add_argument("--usuario", required=True)
    criar.add_argument("--nome", required=True)
    criar.add_argument("--perfil", choices=sorted(auth.PROFILES), default="consulta")
    criar.add_argument("--senha")
    for name, help_text in (("redefinir-senha", "define uma senha temporária (troca obrigatória no próximo acesso)"),
                            ("desbloquear", "libera uma conta bloqueada por tentativas erradas"),
                            ("ativar", "reativa um usuário desativado")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--usuario", required=True)
        if name == "redefinir-senha":
            cmd.add_argument("--senha")
    args = parser.parse_args()

    setup_logging()
    init_db()
    try:
        if args.comando == "listar":
            users = auth.list_users()
            if not users:
                print("Nenhum usuário cadastrado. Abra o painel neste computador para criar o primeiro administrador,")
                print("ou use: usuarios.bat criar --usuario SEU_USUARIO --nome \"Seu Nome\" --perfil admin")
            for u in users:
                situation = "ativo" if u["active"] else "DESATIVADO"
                if u["locked_until"]:
                    situation += f", bloqueado até {u['locked_until'][11:16]}"
                print(f"{u['username']:<25} {u['profile_label']:<14} {situation:<30} {u['name']}")
        elif args.comando == "criar":
            user = auth.create_user(args.usuario, args.nome, args.perfil, _ask_password(args.senha),
                                    must_change_password=False)
            print(f"[OK] Usuário {user['username']} criado ({user['profile_label']}).")
        elif args.comando == "redefinir-senha":
            user = _find(args.usuario)
            auth.set_password(user["id"], _ask_password(args.senha), must_change_password=True)
            print(f"[OK] Senha de {user['username']} redefinida. Ela deverá ser trocada no próximo acesso.")
        elif args.comando == "desbloquear":
            user = _find(args.usuario)
            auth.unlock(user["id"])
            print(f"[OK] Usuário {user['username']} desbloqueado.")
        elif args.comando == "ativar":
            user = _find(args.usuario)
            auth.update_user(user["id"], active=True)
            auth.unlock(user["id"])
            print(f"[OK] Usuário {user['username']} reativado.")
    except auth.AuthError as exc:
        print(f"[ERRO] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
