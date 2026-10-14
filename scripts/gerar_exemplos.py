"""Cria documentos FICTÍCIOS para experimentar o painel.

    python scripts\\gerar_exemplos.py               cria em .\\exemplos\\documentos
    python scripts\\gerar_exemplos.py D:\\Teste     cria no diretório informado
"""
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from tests.sample_docs import build  # noqa: E402

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "exemplos" / "documentos"
    build(target)
    legados = BASE_DIR / "tests" / "fixtures" / "legados"
    if legados.is_dir():  # DOC, XLS, PPT, PPTX, RTF, ODT e ODS salvos pelo Office (conteúdo fictício)
        shutil.copytree(legados, target / "Legados", dirs_exist_ok=True)
    print(f"[OK] Documentos fictícios criados em {target}")
    print("     Defina esse caminho em Configurações > Diretório documental para testar.")
