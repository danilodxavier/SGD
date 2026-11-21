"""Pergunta por voz: leitura de WAV sem ffmpeg e endpoint de transcrição (transcritor falso, sem modelo)."""
import io
import wave

import numpy as np
import pytest

from app.infrastructure.voz.transcritor import AudioInvalido, ler_wav
from app.interfaces.api import voz as api_voz
from tests.helpers import HEADERS, anonymous_client, logged_client


def wav(segundos=1.0, taxa=16000, canais=1, largura=2):
    n = int(segundos * taxa)
    sinal = (np.sin(np.linspace(0, 440 * 2 * np.pi * segundos, n)) * 8000).astype(np.int16)
    if canais == 2:
        sinal = np.repeat(sinal, 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(largura)
        w.setframerate(taxa)
        w.writeframes(sinal.tobytes() if largura == 2 else sinal.astype(np.int8).tobytes())
    return buf.getvalue()


def test_ler_wav_converte_para_16khz_mono():
    audio = ler_wav(wav(1.0, taxa=48000, canais=2))
    assert audio.dtype == np.float32 and abs(len(audio) - 16000) <= 1 and float(np.abs(audio).max()) <= 1.0


@pytest.mark.parametrize("caso", ["nao_wav", "8_bits", "longo"])
def test_audio_invalido_e_recusado(caso):
    dados = {"nao_wav": lambda: b"nao e wav", "8_bits": lambda: wav(largura=1),
             "longo": lambda: wav(segundos=91, taxa=8000)}[caso]()
    with pytest.raises(AudioInvalido):
        ler_wav(dados)


class TranscritorFalso:
    def __init__(self):
        self.recebidos = []

    def transcrever(self, dados):
        self.recebidos.append(len(dados))
        ler_wav(dados)
        return {"texto": "Qual a vigência do contrato 12/2023?", "duracao_s": 1.0, "ms": 5, "modelo": "falso"}


@pytest.fixture()
def falso(db, monkeypatch):
    t = TranscritorFalso()
    monkeypatch.setitem(api_voz._transcritor, "t", t)
    return t


def test_transcrever_exige_login(falso):
    with anonymous_client() as c:
        r = c.post("/api/sadgd/transcrever", content=wav(), headers={**HEADERS, "Content-Type": "audio/wav"})
    assert r.status_code == 401 and falso.recebidos == []


def test_transcrever_devolve_o_texto_para_conferencia(falso):
    with logged_client() as c:
        r = c.post("/api/sadgd/transcrever", content=wav(), headers={**HEADERS, "Content-Type": "audio/wav"})
        ruim = c.post("/api/sadgd/transcrever", content=b"xx", headers={**HEADERS, "Content-Type": "audio/wav"})
        vazio = c.post("/api/sadgd/transcrever", content=b"", headers={**HEADERS, "Content-Type": "audio/wav"})
    assert r.status_code == 200 and r.json()["texto"].startswith("Qual a vigência")
    assert ruim.status_code == 400 and vazio.status_code == 400
