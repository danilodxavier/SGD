"""Verifica a configuração do Gemini (F2 em nuvem) SEM exibir a chave.

Mostra apenas: opções do .env, se a chave está preenchida (e seu tamanho), os modelos disponíveis e uma resposta
curta de teste com conteúdo fictício. Uso: python scripts/sadgd/testar_gemini.py
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.core.config import settings  # noqa: E402
from app.infrastructure.llm.provedores import gemini_configurado, llm_f2_remoto  # noqa: E402


def main():
    chave = os.getenv("GEMINI_API_KEY", "").strip()
    print(f"SADGD_LLM_F2={settings.llm_f2} | AI_ALLOW_REMOTE={settings.ai_allow_remote} | "
          f"modelo={settings.gemini_modelo} | chave preenchida={bool(chave)} ({len(chave)} caracteres)")
    if not gemini_configurado():
        print("[ERRO] Gemini não configurado.")
        return 1
    try:  # modelos disponíveis para a chave (a chave vai no cabeçalho, nunca é impressa)
        req = urllib.request.Request(settings.gemini_url.rstrip("/") + "/models",  # noqa: S310 - https da config
                                     headers={"Authorization": f"Bearer {chave}"})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - URL https da configuração
            ids = sorted(m["id"].removeprefix("models/") for m in json.load(r).get("data", []))
        flash = [i for i in ids if "flash" in i and "image" not in i and "tts" not in i]
        print(f"[OK] {len(ids)} modelos acessíveis; 'flash': {', '.join(flash[:12])}")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] listar modelos: {type(exc).__name__}: {str(exc)[:200]}")
        return 1
    llm = llm_f2_remoto(timeout=60)
    t0 = time.perf_counter()
    try:
        r = llm.chat([{"role": "user", "content": 'Responda somente o JSON {"ok": true, "lingua": "<idioma>"} '
                                                  'para a frase: "O contrato fictício foi prorrogado."'}],
                     max_tokens=60, json_livre=True)
        print(f"[OK] {llm.nome} respondeu em {time.perf_counter() - t0:.1f}s: {r.json} "
              f"(tokens {r.tokens_entrada}/{r.tokens_saida})")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] chamada de teste: {type(exc).__name__}: {str(exc)[:300]}")
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
