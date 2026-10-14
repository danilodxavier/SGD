"""Diagnóstico do ambiente. Sai com código 1 se houver algum [ERRO]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    try:
        from app.services.diagnostics import run_checks
    except Exception as exc:
        print(f"[ERRO] Não foi possível carregar a aplicação: {exc}")
        print("       Execute instalar.bat para instalar as dependências.")
        return 1

    print("=== Diagnóstico — Agente de Inteligência Documental ===")
    checks = run_checks()
    for c in checks:
        print(f"[{c['level']}] {c['name']}: {c['message']}")
    errors = sum(c["level"] == "ERRO" for c in checks)
    warnings = sum(c["level"] == "WARNING" for c in checks)
    print(f"\nResultado: {errors} erro(s), {warnings} aviso(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
