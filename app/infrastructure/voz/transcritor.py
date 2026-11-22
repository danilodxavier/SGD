"""Transcrição de voz LOCAL (faster-whisper na CPU) — perguntas faladas não saem da máquina.

O reconhecimento embutido do navegador (Web Speech API do Chrome) envia o áudio a servidores externos; as perguntas
citam contratos reais, o que contraria a regra de dados reais só locais. O navegador grava, converte para WAV 16 kHz
mono e envia ao servidor; aqui o áudio é lido com a biblioteca padrão (`wave`) — sem ffmpeg — e transcrito em
português. O áudio não é gravado em disco. Medição (voz sintética pt-BR, modelo small int8, CPU): 1,2–1,4 s para
6–7 s de fala, transcrição exata, números normalizados ("12 de 2023").
"""
import io
import os
import re
import threading
import time
import wave

import numpy as np

TAXA = 16000
MAX_SEGUNDOS = 90
CONTEXTO = ("Pergunta à gestão pública sobre contratos administrativos, termos aditivos, apostilamentos, empenho, "
            "nota fiscal, vigência, prorrogação, fiscal do contrato, ordem de serviço, licitação, pregão.")


class AudioInvalido(ValueError):
    pass


# Números de atos falados ("contrato doze barra dois mil e vinte e três" → Whisper: "contrato 12 barra 2023";
# "decreto 7892 de 2013") viram a forma escrita que a busca e as fichas reconhecem ("nº 12/2023").
_ATO = (r"contrato|termo aditivo|aditivo|apostilamento|decreto|lei|portaria|resolu[cç][aã]o|instru[cç][aã]o normativa|"
        r"parecer|of[ií]cio|ordem de servi[cç]o|ordem de suspens[aã]o|ordem de rein[ií]cio|processo|preg[aã]o|edital|"
        r"conv[eê]nio|notifica[cç][aã]o|relat[oó]rio")
_RE_BARRA = re.compile(r"(?<![\d/])(\d{1,5}(?:\.\d{3})?)\s*(?:barra|/)\s*((?:19|20)\d{2})(?!\d)", re.I)
_RE_ATO_DE_ANO = re.compile(
    rf"\b({_ATO})\s+(?:n[uú]mero\s+|n[º°o]\.?\s*)?(\d{{1,5}}(?:\.\d{{3}})?)\s+de\s+((?:19|20)\d{{2}})(?!\d)", re.I)
_RE_ATO_NUMERO = re.compile(rf"\b({_ATO})\s+(?:n[uú]mero\s+|n[º°o]\.?\s*)?(?=\d)", re.I)
_RE_INTERROGATIVA = re.compile(r"^(quando|qual|quais|quem|como|onde|o que|por que|porque|quanto|quantos|quantas|existe|"
                               r"existem|h[aá]|houve|tem|devo|deve|devemos|[eé]|est[aá]|foi|foram|pode|posso)\b", re.I)


def normalizar_fala(texto: str) -> str:
    """Forma escrita para perguntas faladas: "contrato 12 barra 2023." → "contrato nº 12/2023?"."""
    t = " ".join(texto.split())
    t = _RE_ATO_DE_ANO.sub(lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}", t)
    t = _RE_BARRA.sub(r"\1/\2", t)
    t = _RE_ATO_NUMERO.sub(lambda m: f"{m.group(1)} nº ", t)
    if _RE_INTERROGATIVA.match(t) and t.endswith("."):
        t = t[:-1] + "?"
    return t


def ler_wav(dados: bytes) -> np.ndarray:
    """WAV PCM 16 bits → float32 mono 16 kHz (reamostra por interpolação se preciso)."""
    try:
        with wave.open(io.BytesIO(dados), "rb") as w:
            taxa, canais, largura, quadros = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            if largura != 2:
                raise AudioInvalido("Áudio deve ser WAV PCM de 16 bits.")
            if quadros / max(taxa, 1) > MAX_SEGUNDOS:
                raise AudioInvalido(f"Áudio maior que {MAX_SEGUNDOS} s.")
            amostras = np.frombuffer(w.readframes(quadros), dtype=np.int16).astype(np.float32) / 32768.0
    except (wave.Error, EOFError) as exc:
        raise AudioInvalido("Arquivo de áudio inválido (esperado WAV).") from exc
    if canais > 1:
        amostras = amostras.reshape(-1, canais).mean(axis=1)
    if taxa != TAXA and len(amostras):
        n = int(len(amostras) * TAXA / taxa)
        amostras = np.interp(np.linspace(0, len(amostras), n, endpoint=False), np.arange(len(amostras)),
                             amostras).astype(np.float32)
    return amostras


class TranscritorLocal:
    """Carrega o modelo na primeira transcrição e o mantém (≈ 0,5 GB de RAM no small int8)."""

    def __init__(self, modelo: str | None = None, threads: int | None = None):
        self.modelo = modelo or os.environ.get("SADGD_WHISPER_MODELO", "small")
        self.threads = threads or int(os.environ.get("SADGD_WHISPER_THREADS", "4"))
        self._whisper, self._trava = None, threading.Lock()

    def _carregar(self):
        if self._whisper is None:
            from faster_whisper import WhisperModel

            raiz = os.path.join(os.environ.get("HF_HOME", "modelos/hf"), "whisper")
            self._whisper = WhisperModel(self.modelo, device="cpu", compute_type="int8", cpu_threads=self.threads,
                                         download_root=raiz)
        return self._whisper

    def transcrever(self, dados: bytes) -> dict:
        audio = ler_wav(dados)
        if len(audio) < TAXA // 2:
            raise AudioInvalido("Áudio muito curto.")
        inicio = time.perf_counter()
        with self._trava:  # um áudio por vez (CPU compartilhada com a busca)
            segmentos, info = self._carregar().transcribe(audio, language="pt", beam_size=1, vad_filter=False,
                                                          initial_prompt=CONTEXTO, condition_on_previous_text=False)
            texto = normalizar_fala(" ".join(s.text.strip() for s in segmentos).strip())
        return {"texto": texto, "duracao_s": round(info.duration, 1),
                "ms": int((time.perf_counter() - inicio) * 1000), "modelo": self.modelo}
