"""Verificação de aceitação: confere os critérios de conclusão da especificação (seção 48).

Usa documentos FICTÍCIOS em uma pasta temporária, com banco e logs próprios; os dados do usuário
(diretório documental, banco, relatórios) não são lidos nem alterados.

    python scripts\\aceitacao.py
"""
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix="agente_aceitacao_"))
ENV = {
    "DATA_DIR": str(WORK / "data"),
    "DATABASE_PATH": str(WORK / "data" / "aceitacao.db"),
    "DOCUMENTS_ROOT": str(WORK / "documentos"),
    "OCR_ENABLED": "false",
    "AI_PROVIDER": "local",
    "AUTO_INDEX": "false",
    "PYTHONIOENCODING": "utf-8",
}
os.environ.update(ENV)  # antes de importar a aplicação
sys.path.insert(0, str(BASE_DIR))

results = []


def check(criterion, func):
    try:
        detail = func()
        results.append((True, criterion, detail or ""))
    except Exception as exc:  # cada critério é independente
        results.append((False, criterion, f"{type(exc).__name__}: {exc}"))


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _hashes(root):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _quiet_console():
    """Mantém os logs no arquivo, mas fora da tela, para o resultado ficar legível."""
    import logging
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    logger = logging.getLogger("agente")
    for handler in list(logger.handlers):
        if type(handler) is logging.StreamHandler:
            logger.removeHandler(handler)


def main():
    import warnings

    warnings.filterwarnings("ignore", message=".*httpx.*")  # aviso interno do cliente de teste
    from fastapi.testclient import TestClient

    from app.core.database import init_db, set_setting
    from app.core.logging import setup_logging
    from app.main import create_app
    from app.services import diagnostics
    from tests import sample_docs

    root = sample_docs.build(WORK / "documentos")
    original = _hashes(root)
    setup_logging()
    _quiet_console()
    init_db()
    set_setting("documents_root", str(root))
    headers = {"X-Requested-With": "AgenteDocumental"}
    from app.core import auth

    auth.create_user("aceitacao", "Verificação de aceitação", "admin", "Aceitacao2026", must_change_password=False)
    client = TestClient(create_app(auto_index=False), base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    client.__enter__()
    login = client.post("/api/auth/login", json={"username": "aceitacao", "password": "Aceitacao2026"},
                        headers=headers)
    if login.status_code != 200:
        raise SystemExit(f"[ERRO] Não foi possível entrar no sistema de teste: {login.text}")
    ask = lambda q: client.post("/api/ask", json={"question": q}, headers=headers).json()  # noqa: E731

    def installed():
        import fastapi, openpyxl, pypdf, docx, fpdf, pypdfium2  # noqa: E401,F401
        expect(sys.platform == "win32", "não é Windows")
        return f"Windows, Python {sys.version.split()[0]}, dependências importadas"

    port = _free_port()
    server = {}

    def start():
        env = {**os.environ, "APP_PORT": str(port)}
        server["proc"] = subprocess.Popen([sys.executable, "-m", "app", "--sem-navegador"], cwd=BASE_DIR, env=env,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                return f"servidor iniciado (python -m app, como no start.bat) na porta {port}"
            except OSError:
                time.sleep(0.25)
        raise AssertionError("o servidor não respondeu")

    def panel():
        html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode("utf-8")
        expect("Agente Documental" in html, "painel não carregou")
        return "painel HTML servido em 127.0.0.1"

    def root_detected():
        expect(client.get("/health").json()["documents_root"] == "ok", "diretório não detectado")
        return str(root)

    index = {}

    def indexing():
        from app.indexing.indexer import run_index
        index.update(run_index())
        expect(index["found"] == 11 and index["new"] == 11, index)
        return f"{index['found']} arquivos, {index['errors']} com erro (arquivo corrompido proposital)"

    def reads(ext):
        def inner():
            docs = client.get("/api/documents").json()["items"]
            ok = [d for d in docs if d["extension"] == ext and d["status"] == "COM_TEXTO"]
            expect(ok, f"nenhum {ext} lido")
            return ", ".join(d["filename"] for d in ok)
        return inner

    def search():
        r = client.get("/api/search", params={"q": "12.345.678/0001-90"}).json()["results"]
        expect(r, "busca sem resultados")
        return f"{len(r)} trecho(s) para o CNPJ pesquisado"

    def answers():
        r = ask("Qual é o objeto do contrato 034/2022?")
        expect(r["kind"] == "FATO_DOCUMENTAL", r["kind"])
        return r["answer"][:90] + "…"

    def sources():
        r = ask("Quando encerra o contrato 034/2022?")
        expect(r["sources"] and any(s["page"] for s in r["sources"]), "sem fontes com página")
        return "; ".join(f"{s['filename']} pág. {s['page'] or '-'}" for s in r["sources"])

    def absence():
        r = ask("Qual a forma de pagamento do contrato 034/2022?")
        expect(r["answer"] == "Não localizei essa informação nos documentos disponibilizados.", r["answer"])
        return r["answer"]

    def conflict():
        r = ask("Qual o valor do contrato 034/2022?")
        expect(r["kind"] == "CONFLITO", r["kind"])
        return " × ".join(c["value"] for c in r["conflicts"])

    def contracts():
        c = client.get("/api/contracts").json()
        expect(c and c[0]["contract_number"] == "034/2022", c)
        return f"{c[0]['contract_number']} — {c[0]['contractor']}"

    def items():
        r = ask("Quais são os itens do contrato 034/2022?")
        expect(r["kind"] == "FATO_DOCUMENTAL" and "Servente de limpeza" in r["answer"], r["answer"])
        return r["answer"].splitlines()[0]

    checklist_id = {}

    def run_checklist():
        c = client.post("/api/checklists", headers=headers, json={
            "name": "Aceitação", "contract_ref": "034/2022",
            "text": "1. Contrato assinado\n2. Termo aditivo de prorrogação\n3. Certidão de regularidade do FGTS\n"
                    "4. Portaria de designação do fiscal"}).json()
        checklist_id["id"] = c["checklist"]["id"]
        r = client.post(f"/api/checklists/{checklist_id['id']}/run", headers=headers).json()
        expect(r["summary"].get("ATENDIDO", 0) >= 3, r["summary"])
        return ", ".join(f"{k}: {v}" for k, v in r["summary"].items())

    def organization():
        org = client.get(f"/api/checklists/{checklist_id['id']}/organization").json()
        expect(org["folders"], "sem pastas virtuais")
        return " | ".join(f["name"] for f in org["folders"])

    def report():
        r = client.get("/api/reports/contratos", params={"format": "pdf"})
        expect(r.status_code == 200 and r.content.startswith(b"%PDF"), r.status_code)
        files = client.get("/api/reports/files").json()
        return f"PDF de {len(r.content) // 1024} KB salvo em data\\reports ({files[0]['name']})"

    def diagnostic():
        checks = diagnostics.run_checks(check_port=False)
        errors = [c for c in checks if c["level"] == "ERRO"]
        expect(not errors, errors)
        return f"{len(checks)} verificações, nenhum erro"

    def logs():
        log = Path(ENV["DATA_DIR"]) / "logs" / "app.log"
        content = log.read_text(encoding="utf-8")
        expect("Indexação concluída" in content and "Consulta de aceitacao" in content and "Login: aceitacao" in content,
               "eventos não registrados")
        return f"{len(content.splitlines())} linhas em data\\logs\\app.log"

    def access_control():
        with TestClient(create_app(auto_index=False), base_url="http://127.0.0.1:8000",
                        client=("192.168.10.20", 50000)) as anonymous:
            r = anonymous.get("/api/documents")
            expect(r.status_code == 401, f"acesso sem login retornou {r.status_code}")
            r = anonymous.post("/api/documents/1/open", headers=headers)
            expect(r.status_code in (401, 403), r.status_code)
        with TestClient(create_app(auto_index=False), base_url="http://127.0.0.1:8000",
                        client=("8.8.8.8", 50000)) as outside:
            expect(outside.get("/health").status_code == 403, "computador fora da rede interna foi aceito")
        return "sem login: recusado; computador fora da rede interna: recusado"

    def preserved():
        expect(_hashes(root) == original, "algum documento original foi alterado")
        return f"{len(original)} arquivos com hash idêntico ao inicial"

    def stop():
        r = subprocess.run([sys.executable, "-m", "app", "parar"], cwd=BASE_DIR, env={**os.environ},
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        server["proc"].wait(timeout=30)
        return r.stdout.strip()

    criteria = [
        ("instalar no Windows 11", installed),
        ("iniciar pelo start.bat", start),
        ("abrir http://127.0.0.1:8000", panel),
        ("detectar o diretório documental", root_detected),
        ("indexar documentos", indexing),
        ("ler PDFs", reads(".pdf")),
        ("ler DOCX", reads(".docx")),
        ("ler XLSX", reads(".xlsx")),
        ("pesquisar documentos", search),
        ("responder perguntas", answers),
        ("apresentar fontes", sources),
        ("detectar informação ausente", absence),
        ("detectar conflitos", conflict),
        ("identificar contratos", contracts),
        ("identificar itens", items),
        ("processar checklist", run_checklist),
        ("organizar documentos virtualmente", organization),
        ("gerar relatório", report),
        ("executar diagnóstico", diagnostic),
        ("registrar logs", logs),
        ("preservar documentos originais", preserved),
        ("exigir login e recusar computadores não autorizados", access_control),
        ("encerrar pelo stop.bat", stop),
    ]
    try:
        for name, func in criteria:
            check(name, func)
    finally:
        client.__exit__(None, None, None)
        if server.get("proc") and server["proc"].poll() is None:
            server["proc"].kill()

    print("=== Verificação de aceitação — critérios da especificação (seção 48) ===")
    print("Documentos fictícios em pasta temporária; seus dados não foram usados.\n")
    for ok, name, detail in results:
        print(f"[{'OK' if ok else 'ERRO'}] {name}" + (f" — {detail}" if detail else ""))
    failed = sum(not ok for ok, _, _ in results)
    print(f"\nResultado: {len(results) - failed} de {len(results)} critérios atendidos.")
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        code = main()
    finally:
        import logging

        logging.shutdown()
        shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(code)
