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
    POST /tts   {text, stream,    -> stream=false: tam audio/wav (16-bit PCM).
                 speaker}            stream=true: HAM PCM akisi (s16le/24kHz/mono,
                                     header YOK) - cumle cumle uretilir, ilk ses
                                     ~2-3s'de baslar. Istemci `ffmpeg -f s16le
                                     -ar 24000 -ac 1 -i pipe:0` ile tuketir.
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


# --- Metin temizleme ---
# Chatterbox'in tokenizer'i bazi Unicode noktalama isaretlerini tanimiyor;
# tanimadigi bir karakterde model dogal bir "bitis" noktasina hic ulasamayip
# GPU'yu %100'de tutarak dakikalarca ayni sesi tekrar edebiliyor (Sign
# Council'da 2026-09-02 Bolum 10 render'inda gozlendi - kok neden U+2011
# bitisik tire + akilli tirnaklardi; ayni ders `council-backend/render_audio.py`
# `_PUNCT_FIXES`'te de var). Prod app'ten VEYA Sign Council'dan gelen metin
# bu karakterleri tasiyabildigi icin uretimden ONCE ASCII'ye sabitliyoruz.
_PUNCT_FIXES = {
    "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "…": "...",  # yatay ucnokta (_SENT_END "..."i de tanir)
    "·": ".", "•": ".",  # orta nokta / madde imi -> cumle sonu gibi
}
# Sifir-genislikli / yon isaretleri: tokenizer'i sessizce kaydirabilir.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍‎‏﻿"), None)


def sanitize_text(text: str) -> str:
    for bad, good in _PUNCT_FIXES.items():
        text = text.replace(bad, good)
    text = text.translate(_ZERO_WIDTH)
    # kontrol karakterleri (satir sonlari haric) -> bosluk
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    return text


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
    clean = sanitize_text(req.text)
    sentences = [s for s in (split_sentences(clean) or [clean.strip()]) if s.strip()]
    if not sentences:
        # Metin temizlikten sonra bos kaldi (or. sadece sifir-genislik/noktalama)
        # - modele bos string gondermek yerine kisa bir sessizlik don.
        raise HTTPException(status_code=400, detail="seslendirilecek metin yok")

    if not req.stream:
        chunks = [_generate(s, ref_wav) for s in sentences]
        audio = np.concatenate(chunks) if chunks else np.zeros(1, "float32")
        return Response(content=_wav_bytes(audio), media_type="audio/wav")

    def gen():
        # HAM PCM (s16le, 24kHz, mono) - header YOK, cumle siniri isareti YOK.
        # Istemci tek bir uzun-omurlu ffmpeg'e (`-f s16le -ar 24000 -ac 1 -i
        # pipe:0`) chunk'lari geldigi gibi akitir; hizalama/parse derdi yok.
        # Uretim cumle cumle yapiliyor (ilk cumle ~2-3s'de akmaya baslar,
        # tur sonunu beklemez) ama cikti kesintisiz tek bir PCM akisidir.
        # Sahte WAV header (eski 0xFFFFFFFF) bilerek kaldirildi - ffmpeg
        # pipe'ta onu kirilgan sekilde yorumluyordu (faz-2, 2026-09-03).
        for s in sentences:
            t0 = time.time()
            audio = _generate(s, ref_wav)
            print(f"[voice] '{s[:40]}...' {len(audio)/SR:.1f}s ses / {time.time()-t0:.1f}s", flush=True)
            yield _pcm_bytes(audio)

    return StreamingResponse(
        gen(),
        media_type="audio/L16; rate=24000; channels=1",
        headers={
            "X-Audio-Format": "s16le",
            "X-Sample-Rate": str(SR),
            "X-Channels": "1",
        },
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AURA_VOICE_PORT", "8123"))
    _spk = ", ".join(sorted(_speaker_map().keys()))
    print(f"[voice] Aura Voice Mesh baslatiliyor :{port}  (sesler: {_spk} / varsayilan: {DEFAULT_SPEAKER})", flush=True)
    _load_model()  # baslangicta yukle - ilk istek beklemesin
    uvicorn.run(app, host="0.0.0.0", port=port)
