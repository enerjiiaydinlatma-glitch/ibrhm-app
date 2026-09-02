"""Aura Voice Mesh - TTS cekirdek servisi.

Chatterbox Multilingual (Turkce) ile Aura'nin KENDI sesini uretir. Ayri bir
process olarak GPU'lu bir makinede kosar (simdilik gelistirici PC'si + Cloudflare
Tunnel, sonra kiralik GPU). auro-backend bu servise HTTP ile baglanir; servis
ulasilmazsa auro-backend ElevenLabs'e duser.

Calistirma:
    set AURA_VOICE_KEY=uzun-gizli-bir-anahtar
    python server.py                       # veya: uvicorn server:app --host 0.0.0.0 --port 8123

Uclar:
    GET  /health                 -> {status, model_loaded, device, sr, speakers}
    POST /tts   {text, stream,    -> audio/wav (16-bit PCM). stream=true ise
                 speaker}            cumle cumle StreamingResponse.
Kimlik: X-Voice-Key basligi AURA_VOICE_KEY ile eslesecek (bos ise kontrol yok).

Cok-karakter: `voices/<isim>.wav` referans seslerinden secim. `speaker` alani
bos/bilinmiyorsa "aura"ya duser. Boylece TEK Chatterbox modeli (tek GPU kopyasi)
hem Aura APP'ine hem Sign Council podcast'ine hizmet eder - iki ayri model
yuklemeden kaynakli CUDA OOM ortadan kalkar.
"""
from __future__ import annotations

import io
import os
import re
import struct
import time
import threading
import wave

import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

VOICE_KEY = os.getenv("AURA_VOICE_KEY", "").strip()
_HERE = os.path.dirname(__file__)
REF_WAV = os.path.join(_HERE, "aura_voice.wav")  # varsayilan (Aura) - geriye donuk uyum
VOICES_DIR = os.getenv("AURA_VOICE_VOICES_DIR", os.path.join(_HERE, "voices"))
DEFAULT_SPEAKER = os.getenv("AURA_VOICE_DEFAULT_SPEAKER", "aura").strip().lower()
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SR = 24000  # Chatterbox cikis ornekleme hizi


def _speaker_map() -> dict[str, str]:
    """voices/<isim>.wav -> {isim: tam_yol}. 'aura' her zaman var (aura_voice.wav)."""
    out: dict[str, str] = {"aura": REF_WAV}
    try:
        for fn in os.listdir(VOICES_DIR):
            if fn.lower().endswith(".wav"):
                out[os.path.splitext(fn)[0].lower()] = os.path.join(VOICES_DIR, fn)
    except OSError:
        pass
    return out


def _resolve_ref(speaker: str | None) -> str:
    name = (speaker or DEFAULT_SPEAKER).strip().lower()
    m = _speaker_map()
    return m.get(name) or m.get(DEFAULT_SPEAKER) or REF_WAV

# Chatterbox uretim parametreleri - Turkce'de token tekrari/erken kesme
# gozlemlendigi icin muhafazakar. Kullanici geri bildirimiyle ayarlanacak.
EXAGGERATION = float(os.getenv("AURA_TTS_EXAGGERATION", "0.4"))
CFG_WEIGHT = float(os.getenv("AURA_TTS_CFG_WEIGHT", "0.5"))

app = FastAPI(title="Aura Voice Mesh - TTS")

_model = None
_model_lock = threading.Lock()
# Chatterbox tek GPU'da ayni anda tek uretim - istekleri seri hale getir.
_gen_lock = threading.Lock()


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        t0 = time.time()
        m = ChatterboxMultilingualTTS.from_pretrained(device=DEVICE)
        print(f"[voice] model yuklendi: {time.time() - t0:.1f}s ({DEVICE})", flush=True)
        _model = m
        return _model


def _check_key(x_voice_key: str | None):
    if VOICE_KEY and (x_voice_key or "") != VOICE_KEY:
        raise HTTPException(status_code=401, detail="gecersiz anahtar")


# --- Turkce cumle bolucu (kisaltmalara toleransli, basit ve dayanikli) ---
_ABBREV = {"dr", "av", "sn", "no", "vb", "vs", "bkz", "age", "bkz", "prof", "doc"}
_SENT_END = re.compile(r"([.!?…]+)(\s+|$)")


def split_sentences(text: str, max_len: int = 240) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    out: list[str] = []
    start = 0
    for m in _SENT_END.finditer(text):
        end = m.end()
        chunk = text[start:end].strip()
        # noktalama oncesi son kelime - kisaltma kontrolu icin. Bos listeye
        # karsi guvenli ('or [""]' - dar pencere/basi bosluk cokme yapmasin).
        words_before = text[:m.start()].split()
        prev_word = (words_before or [""])[-1].lower().strip(".")
        if prev_word in _ABBREV:
            continue
        if chunk:
            out.append(chunk)
        start = end
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    # cok uzun cumleleri virgul/noktali virgulden ikinci bir kez bol
    final: list[str] = []
    for s in out:
        if len(s) <= max_len:
            final.append(s)
            continue
        parts, buf = [], ""
        for piece in re.split(r"(,|;| ve | ama | fakat )", s):
            if len(buf) + len(piece) > max_len and buf:
                parts.append(buf.strip())
                buf = piece
            else:
                buf += piece
        if buf.strip():
            parts.append(buf.strip())
        final.extend(parts)
    return [s for s in final if s]


def _wav_bytes(samples: np.ndarray) -> bytes:
    """float32 [-1,1] -> 16-bit PCM WAV (tam dosya, header dahil)."""
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _pcm_bytes(samples: np.ndarray) -> bytes:
    """float32 -> ham 16-bit PCM (header YOK - streaming govdesi icin)."""
    pcm = np.clip(samples, -1.0, 1.0)
    return (pcm * 32767.0).astype("<i2").tobytes()


def _wav_header(data_len: int) -> bytes:
    """Streaming icin onden gonderilecek WAV header. data_len bilinmiyorsa
    buyuk bir deger yazip (0xFFFFFFFF) oynaticilarin yine de calmasina birak."""
    n = data_len if data_len > 0 else 0xFFFFFFFF - 44
    return (
        b"RIFF" + struct.pack("<I", n + 36) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, SR, SR * 2, 2, 16)
        + b"data" + struct.pack("<I", n)
    )


def _generate(text: str, ref_wav: str = REF_WAV) -> np.ndarray:
    model = _load_model()
    with _gen_lock:
        wav = model.generate(
            text,
            language_id="tr",
            audio_prompt_path=ref_wav,
            exaggeration=EXAGGERATION,
            cfg_weight=CFG_WEIGHT,
        )
    return wav.squeeze(0).detach().cpu().numpy().astype("float32")


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    stream: bool = False
    speaker: str | None = None  # voices/<isim>.wav; bos -> "aura"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "device": DEVICE,
        "sr": SR,
        "speakers": sorted(_speaker_map().keys()),
        "default_speaker": DEFAULT_SPEAKER,
    }


@app.post("/tts")
def tts(req: TTSRequest, x_voice_key: str | None = Header(default=None)):
    _check_key(x_voice_key)
    ref_wav = _resolve_ref(req.speaker)
    sentences = split_sentences(req.text) or [req.text.strip()]

    if not req.stream:
        chunks = [_generate(s, ref_wav) for s in sentences]
        audio = np.concatenate(chunks) if chunks else np.zeros(1, "float32")
        return Response(content=_wav_bytes(audio), media_type="audio/wav")

    def gen():
        # Once header (uzunluk bilinmiyor - 0xFFFFFFFF), sonra her cumle
        # uretildikce ham PCM govdesi. Oynaticilarin cogu bunu sorunsuz calar.
        yield _wav_header(0)
        for s in sentences:
            t0 = time.time()
            audio = _generate(s, ref_wav)
            print(f"[voice] '{s[:40]}...' {len(audio)/SR:.1f}s ses / {time.time()-t0:.1f}s", flush=True)
            yield _pcm_bytes(audio)

    return StreamingResponse(gen(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AURA_VOICE_PORT", "8123"))
    _spk = ", ".join(sorted(_speaker_map().keys()))
    print(f"[voice] Aura Voice Mesh baslatiliyor :{port}  (sesler: {_spk} / varsayilan: {DEFAULT_SPEAKER})", flush=True)
    _load_model()  # baslangicta yukle - ilk istek beklemesin
    uvicorn.run(app, host="0.0.0.0", port=port)
