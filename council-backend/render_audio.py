"""
Bir bolum transkriptini (run_episode.py ciktisi) sese cevirir.

Kullanim:
    python render_audio.py output/bolum_0-...json

auro-backend/main.py'deki /api/tts endpoint'iyle AYNI ElevenLabs cagri
seklini kullanir, ayri bir HTTP servisi acmadan dogrudan dosyaya yazar.
[ATLANDI ...] ile isaretli (API anahtari eksik oldugu icin uretilmemis)
veya ses kimligi henuz atanmamis (voices.py) turler otomatik atlanir -
bolumun geri kalani yine de seslendirilir.
"""
import argparse
import json
import os
import shutil
import subprocess

import httpx

from personas import PERSONAS
from voices import VOICE_IDS

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
if not ELEVENLABS_API_KEY:
    # providers.py gibi .env'i kendi dizininden yukler
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

TTS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize(text, voice_id):
    response = httpx.post(
        TTS_URL_TEMPLATE.format(voice_id=voice_id),
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.65,
                "similarity_boost": 0.75,
                "style": 0.4,
                "use_speaker_boost": True,
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def render(transcript_path):
    if not ELEVENLABS_API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY yok - council-backend/.env dosyasina ekleyin "
            "(auro-backend/.env'deki degerle ayni kullanilabilir)"
        )

    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    episode_name = os.path.splitext(os.path.basename(transcript_path))[0]
    audio_dir = os.path.join(os.path.dirname(__file__), "output", "audio", episode_name)
    os.makedirs(audio_dir, exist_ok=True)

    clip_paths = []
    for i, turn in enumerate(data["transcript"]):
        speaker = turn["speaker"]
        text = turn["text"]
        display_name = PERSONAS[speaker]["display_name"]
        voice_id = VOICE_IDS.get(speaker, "")

        if text.startswith("[ATLANDI"):
            print(f"[{i:02d}] {display_name}: icerik yok, atlandi (API anahtari eksikti)")
            continue
        if not voice_id:
            print(f"[{i:02d}] {display_name}: ses kimligi atanmamis, atlandi (bkz. voices.py)")
            continue

        clip_path = os.path.join(audio_dir, f"{i:02d}_{speaker}.mp3")
        print(f"[{i:02d}] {display_name}: seslendiriliyor...")
        audio_bytes = synthesize(text, voice_id)
        with open(clip_path, "wb") as f:
            f.write(audio_bytes)
        clip_paths.append(clip_path)

    print(f"\n{len(clip_paths)} klip uretildi -> {audio_dir}")

    if not clip_paths:
        return

    if shutil.which("ffmpeg") is None:
        print(
            "ffmpeg bulunamadi - klipler ayri ayri duruyor, tek dosyada "
            "birlestirme icin ffmpeg kurulmasi gerekiyor."
        )
        return

    concat_list_path = os.path.join(audio_dir, "_concat.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    full_episode_path = os.path.join(audio_dir, "_full_episode.mp3")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_path, "-c", "copy", full_episode_path,
        ],
        check=True,
        capture_output=True,
    )
    print(f"Tam bolum sesi -> {full_episode_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", help="run_episode.py ciktisi olan JSON dosyasi")
    args = parser.parse_args()
    render(args.transcript)
